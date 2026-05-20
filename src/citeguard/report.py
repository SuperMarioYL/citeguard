"""Terminal red/green table + JSON / Markdown exporters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from rich.console import Console
from rich.table import Table
from rich.text import Text

from citeguard.models import VerifyResult


_STATUS_GLYPH = {"hit": "✓", "miss": "✗", "degraded": "?"}
_STATUS_STYLE = {"hit": "bold green", "miss": "bold red", "degraded": "bold yellow"}


def _shorten(s: str, n: int = 60) -> str:
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def render_terminal(results: Iterable[VerifyResult], console: Console | None = None) -> None:
    """Print a `rich` table summarising every :class:`VerifyResult`."""
    console = console or Console()
    results = list(results)

    table = Table(show_lines=False, expand=True, header_style="bold")
    table.add_column("", width=2, justify="center")
    table.add_column("Kind", width=10)
    table.add_column("Identifier", overflow="fold", min_width=20)
    table.add_column("Registry", width=10)
    table.add_column("Evidence / nearest match", overflow="fold")

    for r in results:
        glyph = Text(_STATUS_GLYPH[r.status], style=_STATUS_STYLE[r.status])
        evidence = r.evidence_url or ""
        if r.status == "miss" and r.nearest_matches:
            evidence = "\n".join(
                f"≈ {_shorten(m.title, 40)}  ({m.identifier})  d={m.distance}"
                for m in r.nearest_matches
            )
        if r.status == "degraded" and r.note:
            evidence = f"[yellow]{r.note}[/yellow]"
        table.add_row(glyph, r.citation.kind, r.citation.identifier, r.registry, evidence)

    console.print(table)

    hit = sum(1 for r in results if r.status == "hit")
    miss = sum(1 for r in results if r.status == "miss")
    degraded = sum(1 for r in results if r.status == "degraded")
    summary = Text(
        f"{hit} hit · ",
        style="bold green",
    )
    summary.append(f"{miss} miss", style="bold red")
    summary.append(" · ", style="dim")
    summary.append(f"{degraded} degraded", style="bold yellow")
    console.print(summary)


def to_json(results: Iterable[VerifyResult]) -> str:
    """Stable JSON sidecar.  Schema is `{generator, results:[VerifyResult]}`."""
    payload = {
        "generator": "citeguard/0.2",
        "results": [r.model_dump(mode="json") for r in results],
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def to_markdown(results: Iterable[VerifyResult]) -> str:
    """Markdown report suitable for pasting into a PR or issue."""
    lines: list[str] = ["# CiteGuard report", "", "| Status | Kind | Identifier | Registry | Evidence / nearest match |", "| :---: | :--- | :--- | :--- | :--- |"]
    results = list(results)
    for r in results:
        glyph = {"hit": "✓", "miss": "✗", "degraded": "?"}[r.status]
        if r.status == "miss" and r.nearest_matches:
            evidence = "<br>".join(
                f"≈ {_shorten(m.title, 50)} (`{m.identifier}`, d={m.distance})"
                for m in r.nearest_matches
            )
        elif r.status == "degraded" and r.note:
            evidence = r.note
        else:
            evidence = r.evidence_url or ""
        lines.append(
            f"| {glyph} | {r.citation.kind} | `{r.citation.identifier}` | {r.registry} | {evidence} |"
        )

    hit = sum(1 for r in results if r.status == "hit")
    miss = sum(1 for r in results if r.status == "miss")
    degraded = sum(1 for r in results if r.status == "degraded")
    lines.extend(["", f"**{hit} hit · {miss} miss · {degraded} degraded**", ""])
    return "\n".join(lines)


def write_json(results: Iterable[VerifyResult], path: Path) -> None:
    path.write_text(to_json(results), encoding="utf-8")


def write_markdown(results: Iterable[VerifyResult], path: Path) -> None:
    path.write_text(to_markdown(results), encoding="utf-8")
