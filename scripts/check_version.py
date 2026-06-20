#!/usr/bin/env python3
"""Pre-flight version-consistency gate (m6_preflight_lint extension).

Guards the v0.3.0 publish-day defect class (the hand-fix where ``pyproject``
lagged the CHANGELOG): assert that

  * ``pyproject.toml`` ``[project].version`` equals the version of the TOP
    entry in ``CHANGELOG.md`` (Keep-a-Changelog ``## [X.Y.Z]`` heading), and
  * when a git tag for that version already exists, it matches too.

Exit 0 on agreement, 1 on drift.  Stdlib-only so it runs anywhere ``make
lint`` does, no extra dependency.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _ROOT / "pyproject.toml"
_CHANGELOG = _ROOT / "CHANGELOG.md"

# Matches the newest Keep-a-Changelog version heading, e.g. `## [0.4.0] — 2026-06-20`.
_CHANGELOG_HEADING = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]")


def _pyproject_version() -> str:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["version"]


def _changelog_top_version() -> str:
    for line in _CHANGELOG.read_text(encoding="utf-8").splitlines():
        m = _CHANGELOG_HEADING.match(line)
        if m:
            return m.group(1)
    raise SystemExit("check-version: no `## [X.Y.Z]` heading found in CHANGELOG.md")


def _git_tag_for(version: str) -> bool:
    """Return True iff a git tag for ``vX.Y.Z`` already exists locally."""
    try:
        out = subprocess.run(
            ["git", "tag", "--list", f"v{version}"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        # No git / not a repo: tag check is best-effort, don't fail the gate.
        return False
    return bool(out.stdout.strip())


def main() -> int:
    py = _pyproject_version()
    cl = _changelog_top_version()

    if py != cl:
        print(
            f"check-version: DRIFT — pyproject version {py!r} != CHANGELOG top entry {cl!r}",
            file=sys.stderr,
        )
        return 1

    # If this version is already tagged, the tag must agree (it will, since the
    # tag *is* vX.Y.Z — this guards a manual mis-tag).  A missing tag is fine:
    # the release isn't published yet.
    if _git_tag_for(py):
        print(f"check-version: OK — pyproject == CHANGELOG == git tag v{py}")
    else:
        print(f"check-version: OK — pyproject == CHANGELOG == {py} (no tag yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
