"""OpenAlex resolver — DOI lookup + title fuzzy search for nearest-match."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from citeguard.models import Citation, NearestMatch, VerifyResult

_BASE = "https://api.openalex.org"
_TIMEOUT_SEC = 10.0
_REGISTRY = "openalex"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    r = await client.get(url, timeout=_TIMEOUT_SEC)
    # 404 is a legitimate "not found"; only retry on transport / 5xx.
    if 500 <= r.status_code < 600:
        r.raise_for_status()
    return r


async def verify(client: httpx.AsyncClient, citation: Citation) -> VerifyResult:
    """Look up a DOI on OpenAlex.

    Hit → status=hit with the OpenAlex work URL as evidence.
    Miss → status=miss with up to three nearest title matches.
    """
    doi = citation.identifier
    url = f"{_BASE}/works/doi:{doi}"
    try:
        r = await _get(client, url)
    except Exception as exc:  # noqa: BLE001 — network problems are degraded, not miss
        return VerifyResult(
            citation=citation, status="degraded", registry=_REGISTRY, note=str(exc)
        )

    if r.status_code == 200:
        data = r.json()
        return VerifyResult(
            citation=citation,
            status="hit",
            registry=_REGISTRY,
            evidence_url=data.get("id"),
        )

    if r.status_code == 404:
        candidates = await _nearest(client, doi)
        return VerifyResult(
            citation=citation,
            status="miss",
            registry=_REGISTRY,
            nearest_matches=candidates,
        )

    return VerifyResult(
        citation=citation,
        status="degraded",
        registry=_REGISTRY,
        note=f"unexpected status {r.status_code}",
    )


async def _nearest(client: httpx.AsyncClient, doi: str) -> list[NearestMatch]:
    """Best-effort title fuzzy search using the DOI suffix as the seed phrase.

    The suffix often contains words from the paper's title (e.g. doi
    `10.1145/3460120.3484797` is uninformative, but `10.1234/relevant-words`
    is).  We strip non-letters, query OpenAlex `search`, and rank by
    Levenshtein distance to the original suffix.  Cheap and good enough as
    a "did you mean…" hint.
    """
    suffix = doi.split("/", 1)[-1]
    seed = " ".join(part for part in suffix.replace("-", " ").replace("_", " ").split() if part.isalpha())
    if not seed:
        return []
    try:
        r = await _get(client, f"{_BASE}/works?search={seed}&per-page=3")
        if r.status_code != 200:
            return []
        results = r.json().get("results", [])
    except Exception:
        return []

    out: list[NearestMatch] = []
    for item in results[:3]:
        title = item.get("title") or "<no title>"
        candidate_doi = (item.get("doi") or "").replace("https://doi.org/", "")
        out.append(
            NearestMatch(
                title=title,
                identifier=candidate_doi or item.get("id", ""),
                distance=_levenshtein(seed, title.lower())[:1][0]
                if False
                else _levenshtein(seed, title.lower()),
            )
        )
    out.sort(key=lambda m: m.distance)
    return out


def _levenshtein(a: str, b: str) -> int:
    """Small iterative Levenshtein — fine for short strings, no extra dep."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]
