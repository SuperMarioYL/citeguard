#!/usr/bin/env python3
"""Pre-flight version-consistency gate (m6_preflight_lint extension).

Guards the v0.3.0 publish-day defect class (the hand-fix where ``pyproject``
lagged the CHANGELOG): assert that

  * ``pyproject.toml`` ``[project].version`` equals the version of the TOP
    entry in ``CHANGELOG.md`` (Keep-a-Changelog ``## [X.Y.Z]`` heading),
  * ``src/citeguard/__init__.py`` ``__version__`` equals that same version
    (v0.6.0 extension — closes the drift class where ``citeguard --version``
    shipped a stale ``__version__`` because the gate only watched two of the
    three version sources), and
  * when a git tag for that version already exists, it matches too.

Exit 0 on agreement, 1 on drift.  Stdlib-only so it runs anywhere ``make
lint`` does, no extra dependency (``__version__`` is read by parsing the
literal in ``__init__.py``, not by importing the package — that would drag
in the runtime deps and break the stdlib-only contract).
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
_INIT = _ROOT / "src" / "citeguard" / "__init__.py"

# Matches the newest Keep-a-Changelog version heading, e.g. `## [0.4.0] — 2026-06-20`.
_CHANGELOG_HEADING = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]")

# Matches `__version__ = "X.Y.Z"` at the top of src/citeguard/__init__.py.
_INIT_VERSION = re.compile(r'^__version__\s*=\s*["\'](\d+\.\d+\.\d+)["\']')


def _pyproject_version() -> str:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["version"]


def _changelog_top_version() -> str:
    for line in _CHANGELOG.read_text(encoding="utf-8").splitlines():
        m = _CHANGELOG_HEADING.match(line)
        if m:
            return m.group(1)
    raise SystemExit("check-version: no `## [X.Y.Z]` heading found in CHANGELOG.md")


def _init_version() -> str:
    """Read the ``__version__`` literal from ``src/citeguard/__init__.py``.

    Parsed rather than imported so the gate stays stdlib-only and does not
    pull the package's runtime deps into ``make lint``.
    """
    for line in _INIT.read_text(encoding="utf-8").splitlines():
        m = _INIT_VERSION.match(line)
        if m:
            return m.group(1)
    raise SystemExit('check-version: no `__version__ = "X.Y.Z"` found in src/citeguard/__init__.py')


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
    init = _init_version()

    if py != cl:
        print(
            f"check-version: DRIFT — pyproject version {py!r} != CHANGELOG top entry {cl!r}",
            file=sys.stderr,
        )
        return 1

    if init != py:
        print(
            f"check-version: DRIFT — src/citeguard/__init__.py __version__ {init!r}"
            f" != pyproject version {py!r}",
            file=sys.stderr,
        )
        return 1

    # If this version is already tagged, the tag must agree (it will, since the
    # tag *is* vX.Y.Z — this guards a manual mis-tag).  A missing tag is fine:
    # the release isn't published yet.
    if _git_tag_for(py):
        print(f"check-version: OK — pyproject == CHANGELOG == __init__ == git tag v{py}")
    else:
        print(f"check-version: OK — pyproject == CHANGELOG == __init__ == {py} (no tag yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
