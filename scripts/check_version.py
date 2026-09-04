#!/usr/bin/env python3
"""Pre-flight version-consistency gate (m6_preflight_lint extension).

Guards the v0.3.0 publish-day defect class (the hand-fix where ``pyproject``
lagged the CHANGELOG): assert that

  * ``pyproject.toml`` ``[project].version`` equals the version of the TOP
    entry in ``CHANGELOG.md`` (Keep-a-Changelog ``## [X.Y.Z]`` heading),
  * ``src/citeguard/__init__.py`` ``__version__`` equals that same version
    (v0.6.0 extension — closes the drift class where ``citeguard --version``
    shipped a stale ``__version__`` because the gate only watched two of the
    three version sources),
  * ``action.yml`` ``version`` input ``default`` equals that same version
    (v0.7.0 extension — closes the drift class where the composite Action
    installed a stale ``citeguard==<old>`` because the gate never watched the
    Action's pinned default as a fourth version source), and
  * no git tag for a HIGHER version than the declared one exists
    (v0.8.0 extension — closes the "tagged but not bumped" drift class: v0.7.0
    shipped while every version string stayed at 0.6.0 because the gate only
    asked "does tag v{py} exist" — v0.6.0 did, so it printed OK — and never
    noticed the higher v0.7.0 tag), and
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
_ACTION = _ROOT / "action.yml"

# Matches the newest Keep-a-Changelog version heading, e.g. `## [0.4.0] — 2026-06-20`.
_CHANGELOG_HEADING = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]")

# Matches `__version__ = "X.Y.Z"` at the top of src/citeguard/__init__.py.
_INIT_VERSION = re.compile(r'^__version__\s*=\s*["\'](\d+\.\d+\.\d+)["\']')

# Matches `default: "X.Y.Z"` (the `version` input default inside action.yml).
_ACTION_VERSION_DEFAULT = re.compile(r'^\s*default:\s*["\'](\d+\.\d+\.\d+)["\']')


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


def _action_version_default() -> str | None:
    """Read the ``version`` input ``default`` from ``action.yml``.

    Tracks the first ``default:`` line inside the ``version:`` input block.
    Returns ``None`` when ``action.yml`` is absent so synthetic test trees
    that do not model the Action do not trip the gate (best-effort, like the
    git-tag check); in a real repo the file always exists, so the check is
    strict there.
    """
    if not _ACTION.exists():
        return None
    in_version = False
    for line in _ACTION.read_text(encoding="utf-8").splitlines():
        if line.strip() == "version:":
            in_version = True
            continue
        if in_version:
            m = _ACTION_VERSION_DEFAULT.match(line)
            if m:
                return m.group(1)
    raise SystemExit("check-version: no `version` input default found in action.yml")


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


def _git_tags() -> list[str]:
    """Return all ``vX.Y.Z`` git tags as bare version strings (no leading ``v``).

    Best-effort: returns ``[]`` outside a git repo so synthetic test trees that do
    not model tags do not trip the gate.
    """
    try:
        out = subprocess.run(
            ["git", "tag", "--list"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    tags: list[str] = []
    for raw in out.stdout.splitlines():
        tag = raw.strip()
        if tag.startswith("v"):
            tag = tag[1:]
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", tag)
        if m:
            tags.append(tag)
    return tags


def _highest_tag_above(version: str) -> str | None:
    """Return the highest git tag strictly greater than ``version``, or ``None``.

    Closes the "tagged-but-not-bumped" drift class (v0.8.0 extension): a release
    was cut (a higher tag exists) while the version strings in pyproject /
    __init__ / CHANGELOG / action.yml stayed at an older value.  The pre-v0.8.0
    gate only asked "does tag ``v{py}`` exist" — it did (so the gate printed OK)
    and never noticed the higher release tag, so v0.7.0 shipped with every
    version string frozen at 0.6.0.
    """
    py_parts = tuple(int(p) for p in version.split("."))
    highest: tuple[int, ...] | None = None
    highest_label: str | None = None
    for tag in _git_tags():
        parts = tuple(int(p) for p in tag.split("."))
        if parts > py_parts and (highest is None or parts > highest):
            highest = parts
            highest_label = tag
    return highest_label


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

    action = _action_version_default()
    if action is not None and action != py:
        print(
            f"check-version: DRIFT — action.yml `version` default {action!r}"
            f" != pyproject version {py!r}",
            file=sys.stderr,
        )
        return 1

    # v0.8.0: a release tag strictly above the declared version means a release
    # was cut while the version strings were not bumped — the "tagged but not
    # bumped" drift class that let v0.7.0 ship with every string at 0.6.0.
    higher = _highest_tag_above(py)
    if higher is not None:
        print(
            f"check-version: DRIFT — git tag v{higher} is strictly greater than the"
            f" declared version {py!r} (a release was cut but the version strings"
            " were not bumped)",
            file=sys.stderr,
        )
        return 1

    # If this version is already tagged, the tag must agree (it will, since the
    # tag *is* vX.Y.Z — this guards a manual mis-tag).  A missing tag is fine:
    # the release isn't published yet.
    if _git_tag_for(py):
        print(
            f"check-version: OK — pyproject == CHANGELOG == __init__ == action.yml"
            f" == git tag v{py} (no higher tag)"
        )
    else:
        print(
            f"check-version: OK — pyproject == CHANGELOG == __init__ == action.yml == {py} (no tag yet)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
