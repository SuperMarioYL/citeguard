"""CI-mode helpers — drive CiteGuard from inside GitHub Actions.

The CLI grew four new flags in v0.2.0 (`--changed-only`, `--fail-on`,
`--max-misses`, `--paths`). The helpers below are the platform-neutral pieces
that back those flags:

* :func:`load_changed_files` reads the changed-file list passed in by the
  composite action (one path per line, repo-relative).
* :func:`filter_paths` applies a comma-separated glob expression to that list.
* :func:`should_fail` implements the v0.2.0 §2b exit-code contract.
* :func:`render_annotations` emits GitHub workflow-command annotations on a
  per-miss / per-degraded basis.
* :func:`render_job_summary` returns Markdown for ``$GITHUB_STEP_SUMMARY``.

The sticky PR comment itself is upserted from the composite action's shell
step (``gh api``) — keeping that out of Python avoids dragging in a GitHub SDK
and lets the Action be deployed as a thin wrapper.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable

from citeguard.models import VerifyResult


FailOn = str  # one of: "none" | "miss" | "degraded"

EXIT_PASS = 0
EXIT_THRESHOLD = 1
EXIT_USAGE = 2


def load_changed_files(source: Path) -> list[str]:
    """Read a newline-separated changed-file list (composite-action output).

    Blank lines and ``#`` comments are skipped so the file is hand-editable
    in tests. Paths are returned verbatim (repo-relative) — globbing happens
    in :func:`filter_paths`.
    """
    out: list[str] = []
    for raw in source.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def filter_paths(paths: Iterable[str], globs: str) -> list[str]:
    """Keep only paths matching at least one of the comma-separated globs.

    Empty / whitespace globs mean "no filter — keep everything".
    """
    expanded = [g.strip() for g in globs.split(",") if g.strip()]
    if not expanded:
        return list(paths)
    out: list[str] = []
    for p in paths:
        # fnmatch on the full path handles both ``**/*.tex`` and ``docs/*.md``.
        if any(_matches(p, g) for g in expanded):
            out.append(p)
    return out


def _matches(path: str, pattern: str) -> bool:
    """fnmatch with ``**`` glob support (``**/`` swallows directory prefixes)."""
    if pattern.startswith("**/"):
        tail = pattern[3:]
        # Match either the bare tail (top-level files) or anywhere down the tree.
        return fnmatch.fnmatchcase(path, tail) or fnmatch.fnmatchcase(path, f"*/{tail}")
    return fnmatch.fnmatchcase(path, pattern)


def count_outcomes(results: Iterable[VerifyResult]) -> tuple[int, int, int]:
    hit = miss = degraded = 0
    for r in results:
        if r.status == "hit":
            hit += 1
        elif r.status == "miss":
            miss += 1
        else:
            degraded += 1
    return hit, miss, degraded


def should_fail(
    results: Iterable[VerifyResult],
    fail_on: FailOn,
    max_misses: int,
) -> bool:
    """Implement the v0.2.0 §2b exit-code contract for ``fail-on`` thresholds.

    * ``none`` — always pass (advisory mode).
    * ``miss`` — fail when miss count > ``max_misses``.
    * ``degraded`` — fail when (miss + degraded) > ``max_misses``.

    ``max_misses`` of 0 means "any miss is fatal" — the most strict setting
    journals will want.
    """
    if fail_on == "none":
        return False
    _hit, miss, degraded = count_outcomes(results)
    if fail_on == "miss":
        return miss > max_misses
    if fail_on == "degraded":
        return (miss + degraded) > max_misses
    # Defensive: caller passed an unknown threshold — treat as usage error
    # upstream (CLI validates via click.Choice).
    raise ValueError(f"unknown fail-on threshold: {fail_on!r}")


def _escape_annotation(text: str) -> str:
    """Escape per the GitHub workflow-command spec.

    See https://docs.github.com/actions/reference/workflow-commands-for-github-actions
    """
    return (
        text.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def render_annotations(results: Iterable[VerifyResult]) -> list[str]:
    """Emit one GitHub workflow-command line per miss / degraded result.

    The composite action prints these to stdout so GitHub renders them as
    inline PR annotations. ``hit`` results are silent.
    """
    out: list[str] = []
    for r in results:
        if r.status == "hit":
            continue
        level = "error" if r.status == "miss" else "warning"
        span = r.citation.context_span
        loc_parts: list[str] = []
        if span is not None:
            loc_parts.append(f"file={span.file}")
        msg = _annotation_message(r)
        loc = ",".join(loc_parts)
        prefix = f"::{level} {loc}::" if loc else f"::{level}::"
        out.append(prefix + _escape_annotation(msg))
    return out


def _annotation_message(r: VerifyResult) -> str:
    label = "fabricated citation" if r.status == "miss" else "registry degraded"
    base = f"CiteGuard: {label} — {r.citation.kind} {r.citation.identifier} (registry: {r.registry})"
    if r.status == "miss" and r.nearest_matches:
        nm = r.nearest_matches[0]
        base += f" · nearest match: {nm.identifier} (d={nm.distance})"
    if r.status == "degraded" and r.note:
        base += f" · {r.note}"
    return base


def render_job_summary(
    results: Iterable[VerifyResult],
    fail_on: FailOn,
    max_misses: int,
    failed: bool,
) -> str:
    """Build the Markdown that goes into ``$GITHUB_STEP_SUMMARY``."""
    results = list(results)
    hit, miss, degraded = count_outcomes(results)
    verdict = (
        "[**FAIL**]" if failed else "[**PASS**]"
    )
    lines: list[str] = [
        "## CiteGuard report",
        "",
        f"{verdict} `fail-on: {fail_on}` · `max-misses: {max_misses}` · "
        f"**{hit} hit · {miss} miss · {degraded} degraded**",
        "",
        "| Status | Kind | Identifier | Registry | Evidence / nearest match |",
        "| :---: | :--- | :--- | :--- | :--- |",
    ]
    for r in results:
        glyph = {"hit": "✓", "miss": "✗", "degraded": "?"}[r.status]
        if r.status == "miss" and r.nearest_matches:
            evidence = "<br>".join(
                f"≈ {m.identifier} (d={m.distance})" for m in r.nearest_matches[:3]
            )
        elif r.status == "degraded" and r.note:
            evidence = r.note
        else:
            evidence = r.evidence_url or ""
        lines.append(
            f"| {glyph} | {r.citation.kind} | `{r.citation.identifier}` | {r.registry} | {evidence} |"
        )
    if not results:
        lines.append("| — | — | _no citations found_ | — | — |")
    lines.append("")
    lines.append("<!-- citeguard:sticky -->")
    return "\n".join(lines)


__all__ = [
    "EXIT_PASS",
    "EXIT_THRESHOLD",
    "EXIT_USAGE",
    "count_outcomes",
    "filter_paths",
    "load_changed_files",
    "render_annotations",
    "render_job_summary",
    "should_fail",
]
