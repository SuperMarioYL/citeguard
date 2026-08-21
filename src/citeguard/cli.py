"""CiteGuard CLI entry point.

Sub-commands::

    citeguard extract  PATH                       # m1: print structured citations
    citeguard verify   PATH [--no-report]         # m2: hit the registries, optionally hide the table
    citeguard          PATH [--json OUT]          # m3: default = extract + verify + render
    citeguard          --changed-only FILE ...    # m4: CI mode (consumed by action.yml)

The bare ``citeguard PATH`` form is the user-facing happy path documented in
``mvp_plan.md`` §3.  The ``--changed-only`` form is the v0.2.0 §2b CI mode
backing the GitHub Action.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Iterable
from pathlib import Path

import click
import httpx
from rich.console import Console

from citeguard import __version__
from citeguard import ci as ci_mod
from citeguard.extract import extract_from_path
from citeguard.models import Citation, VerifyResult
from citeguard.report import render_terminal, write_json, write_markdown
from citeguard.resolvers import RegistryCache
from citeguard.resolvers import arxiv as arxiv_resolver
from citeguard.resolvers import crossref as crossref_resolver
from citeguard.resolvers import github as github_resolver
from citeguard.resolvers import nvd as nvd_resolver
from citeguard.resolvers import openalex as openalex_resolver

_CONSOLE = Console()
_DEFAULT_CI_GLOB = "**/*.pdf,**/*.tex,**/*.md"


def _pick_resolver(citation: Citation):
    """Map :class:`Citation` kind → resolver coroutine."""
    if citation.kind == "doi":
        return openalex_resolver.verify
    if citation.kind == "arxiv":
        return arxiv_resolver.verify
    if citation.kind == "cve":
        return nvd_resolver.verify
    if citation.kind in ("commit", "gh_issue"):
        return github_resolver.verify
    return None


async def _verify_one(
    client: httpx.AsyncClient, cache: RegistryCache | None, citation: Citation
) -> VerifyResult:
    if cache is not None:
        cached = cache.get(citation.kind, citation.identifier)
        if cached is not None:
            return cached
    resolver = _pick_resolver(citation)
    if resolver is None:
        return VerifyResult(
            citation=citation,
            status="degraded",
            registry="unknown",
            note=f"no resolver registered for kind {citation.kind!r}",
        )
    result = await resolver(client, citation)

    # Crossref fallback for DOIs: OpenAlex backfill lags Crossref, so a DOI that
    # 404s on OpenAlex but is live on Crossref is a real hit, not a fabricated
    # citation.  Only when BOTH registries 404 do we keep the miss.  When the
    # Crossref fallback itself is transiently unreachable it returns `degraded`,
    # which means we have no authoritative second opinion — in that case we must
    # NOT keep the OpenAlex miss, because `cache.put` would freeze it as a
    # fabricated citation for the 7-day TTL on a Crossref blip.  Emit a degraded
    # result instead: the cache refuses to persist degraded, so both registries
    # are retried next run, and the outcome stays advisory under `--fail-on miss`.
    if citation.kind == "doi" and result.status == "miss":
        crossref_result = await crossref_resolver.verify(client, citation)
        if crossref_result.status == "hit":
            result = crossref_result
        elif crossref_result.status == "degraded":
            result = VerifyResult(
                citation=citation,
                status="degraded",
                registry="openalex",
                note="OpenAlex miss; Crossref fallback unreachable",
            )
        # crossref miss → both registries agree the DOI is absent; the OpenAlex
        # miss is the authoritative fabricated-citation verdict.

    if cache is not None:
        cache.put(result)
    return result


async def _verify_batch(
    citations: Iterable[Citation],
    cache: RegistryCache | None,
    concurrency: int = 8,
) -> list[VerifyResult]:
    """Fan out across all citations with a small semaphore."""
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(http2=False, follow_redirects=True) as client:

        async def _bounded(c: Citation) -> VerifyResult:
            async with sem:
                return await _verify_one(client, cache, c)

        return await asyncio.gather(*(_bounded(c) for c in citations))


@click.group(invoke_without_command=True)
@click.argument(
    "path", required=False, type=click.Path(exists=False, dir_okay=False, path_type=Path)
)
@click.option(
    "--json",
    "json_out",
    type=click.Path(dir_okay=False, path_type=Path),
    help="write the JSON sidecar to this path",
)
@click.option(
    "--md",
    "md_out",
    type=click.Path(dir_okay=False, path_type=Path),
    help="write a Markdown report to this path",
)
@click.option("--no-cache", is_flag=True, help="skip the SQLite cache (force live registry calls)")
@click.option(
    "--strict",
    is_flag=True,
    help="exit code 1 if any miss is found (CI-friendly; superseded by --fail-on in v0.2)",
)
@click.option(
    "--changed-only",
    "changed_only",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="CI mode: read the newline-separated list of changed files from PATH and verify each",
)
@click.option(
    "--fail-on",
    "fail_on",
    type=click.Choice(["none", "miss", "degraded"]),
    default="none",
    show_default=True,
    help="CI mode: which outcome counts as a CI failure (exit 1)",
)
@click.option(
    "--max-misses",
    "max_misses",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="CI mode: tolerate up to N misses before --fail-on triggers",
)
@click.option(
    "--paths",
    "paths_glob",
    default=_DEFAULT_CI_GLOB,
    show_default=True,
    help="CI mode: comma-separated glob filter applied to --changed-only entries",
)
@click.option(
    "--summary-out",
    "summary_out",
    type=click.Path(dir_okay=False, path_type=Path),
    help="CI mode: write the Markdown job summary here (typically $GITHUB_STEP_SUMMARY)",
)
@click.option(
    "--annotations/--no-annotations",
    "emit_annotations",
    default=None,
    help="CI mode: emit GitHub workflow-command annotations to stdout (default: on in CI mode)",
)
@click.version_option(__version__, prog_name="citeguard")
@click.pass_context
def main(
    ctx: click.Context,
    path: Path | None,
    json_out: Path | None,
    md_out: Path | None,
    no_cache: bool,
    strict: bool,
    changed_only: Path | None,
    fail_on: str,
    max_misses: int,
    paths_glob: str,
    summary_out: Path | None,
    emit_annotations: bool | None,
) -> None:
    """Verify every citation in PATH against real registries.

    Run ``citeguard --help`` for sub-commands, ``citeguard paper.pdf`` for the
    default end-to-end pipeline, or ``citeguard --changed-only <list>`` for
    the CI mode consumed by the GitHub Action.
    """
    if ctx.invoked_subcommand is not None:
        return

    if changed_only is not None:
        rc = _run_ci(
            changed_only=changed_only,
            fail_on=fail_on,
            max_misses=max_misses,
            paths_glob=paths_glob,
            summary_out=summary_out,
            no_cache=no_cache,
            emit_annotations=True if emit_annotations is None else emit_annotations,
        )
        ctx.exit(rc)
        return

    if path is None:
        click.echo(ctx.get_help())
        ctx.exit(0)

    if not path.exists():
        _CONSOLE.print(f"[red]error:[/red] {path} does not exist")
        ctx.exit(ci_mod.EXIT_USAGE)

    _run_full(path, json_out, md_out, no_cache, strict)


@main.command("extract")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def cmd_extract(path: Path) -> None:
    """Print every citation found in PATH as JSON (no network)."""
    citations = extract_from_path(path)
    click.echo("[\n  " + ",\n  ".join(c.model_dump_json() for c in citations) + "\n]")


@main.command("verify")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--no-cache", is_flag=True, help="skip the SQLite cache")
@click.option("--no-report", is_flag=True, help="suppress the terminal table; only print summary")
@click.option("--json", "json_out", type=click.Path(dir_okay=False, path_type=Path))
def cmd_verify(path: Path, no_cache: bool, no_report: bool, json_out: Path | None) -> None:
    """Verify PATH and optionally write a JSON sidecar."""
    citations = extract_from_path(path)
    cache = None if no_cache else RegistryCache()
    results = asyncio.run(_verify_batch(citations, cache))
    if not no_report:
        render_terminal(results, console=_CONSOLE)
    else:
        hit = sum(1 for r in results if r.status == "hit")
        miss = sum(1 for r in results if r.status == "miss")
        degraded = sum(1 for r in results if r.status == "degraded")
        click.echo(f"{hit} hit · {miss} miss · {degraded} degraded")
    if json_out:
        write_json(results, json_out)


def _run_full(
    path: Path,
    json_out: Path | None,
    md_out: Path | None,
    no_cache: bool,
    strict: bool,
) -> None:
    citations = extract_from_path(path)
    if not citations:
        _CONSOLE.print(f"[yellow]No citations found in {path}.[/yellow]")
        return
    cache = None if no_cache else RegistryCache()
    results = asyncio.run(_verify_batch(citations, cache))
    render_terminal(results, console=_CONSOLE)

    default_json = path.with_suffix(path.suffix + ".citeguard.json")
    target_json = json_out or default_json
    write_json(results, target_json)
    _CONSOLE.print(f"[dim]JSON sidecar:[/dim] {target_json}")

    if md_out:
        write_markdown(results, md_out)
        _CONSOLE.print(f"[dim]Markdown report:[/dim] {md_out}")

    if strict and any(r.status == "miss" for r in results):
        sys.exit(ci_mod.EXIT_THRESHOLD)


def _run_ci(
    *,
    changed_only: Path,
    fail_on: str,
    max_misses: int,
    paths_glob: str,
    summary_out: Path | None,
    no_cache: bool,
    emit_annotations: bool,
) -> int:
    """v0.2.0 §2b CI mode — returns an exit code, never raises for content."""
    try:
        raw_paths = ci_mod.load_changed_files(changed_only)
    except OSError as exc:
        _CONSOLE.print(f"[red]error:[/red] cannot read --changed-only file: {exc}")
        return ci_mod.EXIT_USAGE

    targets = ci_mod.filter_paths(raw_paths, paths_glob)

    # Empty target list → nothing to verify.  That's a pass, with a clear summary.
    all_results: list[VerifyResult] = []
    citations: list[Citation] = []
    skipped_missing: list[str] = []
    for rel in targets:
        p = Path(rel)
        if not p.exists():
            skipped_missing.append(rel)
            continue
        citations.extend(extract_from_path(p))

    if citations:
        cache = None if no_cache else RegistryCache()
        all_results = asyncio.run(_verify_batch(citations, cache))

    render_terminal(all_results, console=_CONSOLE) if all_results else _CONSOLE.print(
        "[dim]no citations in changed files[/dim]"
    )

    failed = ci_mod.should_fail(all_results, fail_on=fail_on, max_misses=max_misses)

    if emit_annotations:
        for line in ci_mod.render_annotations(all_results):
            click.echo(line)
        for rel in skipped_missing:
            click.echo(
                f"::warning::CiteGuard: changed file {rel} not present in workspace; skipped"
            )

    if summary_out is not None:
        summary_md = ci_mod.render_job_summary(
            all_results, fail_on=fail_on, max_misses=max_misses, failed=failed
        )
        # Append (rather than truncate) so we play nicely with other steps
        # already writing to $GITHUB_STEP_SUMMARY.
        with open(summary_out, "a", encoding="utf-8") as fh:
            fh.write(summary_md + "\n")

    # Surface the summary path via GITHUB_OUTPUT so the composite action can
    # read it back into the sticky-comment step.
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        hit, miss, degraded = ci_mod.count_outcomes(all_results)
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(
                f"hit={hit}\nmiss={miss}\ndegraded={degraded}\nfailed={'true' if failed else 'false'}\n"
            )

    return ci_mod.EXIT_THRESHOLD if failed else ci_mod.EXIT_PASS


if __name__ == "__main__":  # pragma: no cover
    main()
