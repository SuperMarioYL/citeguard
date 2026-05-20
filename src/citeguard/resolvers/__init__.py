"""Per-registry verifiers + the SQLite cache that fronts them.

Each resolver exposes a single coroutine::

    async def verify(client: httpx.AsyncClient, identifier: str) -> VerifyResult

The orchestrator in :mod:`citeguard.cli` dispatches each :class:`Citation` to
the right resolver based on its `kind`.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from citeguard.models import VerifyResult


_DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days — plan §4
_SCHEMA = """
CREATE TABLE IF NOT EXISTS verify_cache (
    kind        TEXT NOT NULL,
    identifier  TEXT NOT NULL,
    payload     TEXT NOT NULL,
    cached_at   INTEGER NOT NULL,
    PRIMARY KEY (kind, identifier)
);
"""


def default_cache_path() -> Path:
    home = Path.home() / ".cache" / "citeguard"
    home.mkdir(parents=True, exist_ok=True)
    return home / "registry.db"


@contextmanager
def _conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


class RegistryCache:
    """Tiny SQLite-backed memoiser.

    The cache stores serialised :class:`VerifyResult` payloads keyed by
    `(kind, identifier)`.  TTL is enforced at read time — expired rows are
    treated as misses and the resolver is invoked again.
    """

    def __init__(self, path: Path | None = None, ttl_seconds: int = _DEFAULT_TTL_SECONDS):
        self.path = path or default_cache_path()
        self.ttl_seconds = ttl_seconds

    def get(self, kind: str, identifier: str) -> VerifyResult | None:
        cutoff = int(time.time()) - self.ttl_seconds
        with _conn(self.path) as conn:
            row = conn.execute(
                "SELECT payload, cached_at FROM verify_cache WHERE kind=? AND identifier=?",
                (kind, identifier),
            ).fetchone()
        if not row:
            return None
        payload, cached_at = row
        if cached_at < cutoff:
            return None
        return VerifyResult.model_validate_json(payload)

    def put(self, result: VerifyResult) -> None:
        # We never cache `degraded` outcomes — they're network-side hiccups, not
        # facts about the registry, and caching them would freeze a bad result
        # for a week.
        if result.status == "degraded":
            return
        with _conn(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO verify_cache(kind, identifier, payload, cached_at)"
                " VALUES (?, ?, ?, ?)",
                (
                    result.citation.kind,
                    result.citation.identifier,
                    result.model_dump_json(),
                    int(time.time()),
                ),
            )

    def clear(self) -> None:
        with _conn(self.path) as conn:
            conn.execute("DELETE FROM verify_cache")


__all__ = ["RegistryCache", "default_cache_path"]
