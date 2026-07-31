"""Tests for the v0.2.0 CI-mode helpers + CLI integration.

Covers:
* changed-file fixture loading + glob filtering (path filter behaviour)
* the §2b exit-code contract across the three fail-on thresholds
* GitHub workflow-command annotation formatting (incl. escape rules)
* job-summary Markdown shape
* end-to-end CLI dispatch (clean PR → exit 0; bad PR with ``fail-on: miss`` → exit 1)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from citeguard import ci as ci_mod
from citeguard.cli import main as cli_main
from citeguard.models import Citation, ContextSpan, NearestMatch, VerifyResult

FIXTURES = Path(__file__).parent / "fixtures"


# ---------- changed-file fixture + glob filter -----------------------------


def test_load_changed_files_skips_blank_and_comments():
    paths = ci_mod.load_changed_files(FIXTURES / "pr_diff_sample.txt")
    assert "docs/architecture.md" in paths
    assert "paper.tex" in paths
    assert "assets/logo.png" in paths
    # comments + blank lines stripped
    assert not any(p.startswith("#") for p in paths)
    assert "" not in paths


def test_filter_paths_default_glob_keeps_text_drops_binary():
    paths = ci_mod.load_changed_files(FIXTURES / "pr_diff_sample.txt")
    kept = ci_mod.filter_paths(paths, "**/*.pdf,**/*.tex,**/*.md")
    assert "paper.tex" in kept
    assert "docs/architecture.md" in kept
    assert "README.md" in kept
    assert "assets/logo.png" not in kept
    assert "src/citeguard/cli.py" not in kept


def test_filter_paths_empty_glob_keeps_all():
    paths = ["a.py", "docs/b.md"]
    assert ci_mod.filter_paths(paths, "") == paths
    assert ci_mod.filter_paths(paths, "   ") == paths


def test_filter_paths_handles_top_level_files():
    # ``**/*.md`` must match ``README.md`` (top-level, no directory prefix)
    assert "README.md" in ci_mod.filter_paths(["README.md"], "**/*.md")


# ---------- exit-code contract (§2b) ---------------------------------------


def _make_results(hits: int, misses: int, degraded: int) -> list[VerifyResult]:
    out: list[VerifyResult] = []
    for i in range(hits):
        out.append(
            VerifyResult(
                citation=Citation(raw_text="x", kind="doi", identifier=f"10.1/h{i}"),
                status="hit",
                registry="openalex",
                evidence_url="u",
            )
        )
    for i in range(misses):
        out.append(
            VerifyResult(
                citation=Citation(raw_text="x", kind="arxiv", identifier=f"9999.{i:05d}"),
                status="miss",
                registry="arxiv",
            )
        )
    for i in range(degraded):
        out.append(
            VerifyResult(
                citation=Citation(raw_text="x", kind="cve", identifier=f"CVE-2099-{i}"),
                status="degraded",
                registry="nvd",
                note="timeout",
            )
        )
    return out


def test_fail_on_none_always_passes():
    assert ci_mod.should_fail(_make_results(0, 5, 5), fail_on="none", max_misses=0) is False


def test_fail_on_miss_triggers_above_threshold():
    results = _make_results(0, 2, 0)
    assert ci_mod.should_fail(results, fail_on="miss", max_misses=0) is True
    assert ci_mod.should_fail(results, fail_on="miss", max_misses=1) is True
    assert ci_mod.should_fail(results, fail_on="miss", max_misses=2) is False


def test_fail_on_miss_ignores_degraded():
    # 0 misses + 5 degraded should pass under ``fail-on: miss``
    results = _make_results(3, 0, 5)
    assert ci_mod.should_fail(results, fail_on="miss", max_misses=0) is False


def test_fail_on_degraded_counts_both():
    results = _make_results(0, 1, 1)
    # 2 combined > max_misses=0 → fail
    assert ci_mod.should_fail(results, fail_on="degraded", max_misses=0) is True
    assert ci_mod.should_fail(results, fail_on="degraded", max_misses=2) is False


def test_fail_on_unknown_raises():
    with pytest.raises(ValueError):
        ci_mod.should_fail([], fail_on="bogus", max_misses=0)


# ---------- workflow-command annotations -----------------------------------


def test_render_annotations_silent_on_hits():
    assert ci_mod.render_annotations(_make_results(3, 0, 0)) == []


def test_render_annotations_error_for_miss_warning_for_degraded():
    results = _make_results(0, 1, 1)
    lines = ci_mod.render_annotations(results)
    assert len(lines) == 2
    assert any(line.startswith("::error") and "fabricated citation" in line for line in lines)
    assert any(line.startswith("::warning") and "registry degraded" in line for line in lines)


def test_render_annotations_includes_file_when_span_present():
    citation = Citation(
        raw_text="arXiv:9999.00001",
        kind="arxiv",
        identifier="9999.00001",
        context_span=ContextSpan(file="paper.tex", start=10, end=27),
    )
    result = VerifyResult(citation=citation, status="miss", registry="arxiv")
    line = ci_mod.render_annotations([result])[0]
    assert "file=paper.tex" in line


def test_render_annotations_escapes_newlines_and_percent():
    citation = Citation(raw_text="x", kind="cve", identifier="CVE-2099-1")
    result = VerifyResult(
        citation=citation,
        status="degraded",
        registry="nvd",
        note="rate-limit 50%\nretry later",
    )
    line = ci_mod.render_annotations([result])[0]
    assert "50%25" in line
    assert "%0A" in line


def test_render_annotations_appends_nearest_match_when_present():
    citation = Citation(raw_text="x", kind="doi", identifier="10.9/x")
    result = VerifyResult(
        citation=citation,
        status="miss",
        registry="openalex",
        nearest_matches=[NearestMatch(title="close", identifier="10.9/y", distance=2)],
    )
    line = ci_mod.render_annotations([result])[0]
    assert "nearest match" in line
    assert "10.9/y" in line


# ---------- job-summary Markdown -------------------------------------------


def test_render_job_summary_includes_verdict_and_sticky_marker():
    results = _make_results(1, 1, 0)
    md = ci_mod.render_job_summary(results, fail_on="miss", max_misses=0, failed=True)
    assert "[**FAIL**]" in md
    assert "fail-on: miss" in md
    assert "1 hit · 1 miss · 0 degraded" in md
    assert "<!-- citeguard:sticky -->" in md
    # markdown table header
    assert "| Status | Kind | Identifier | Registry |" in md


def test_render_job_summary_handles_empty_results():
    md = ci_mod.render_job_summary([], fail_on="none", max_misses=0, failed=False)
    assert "no citations found" in md
    assert "[**PASS**]" in md


# ---------- CLI end-to-end (click runner) ----------------------------------


def _write_diff_file(tmp_path: Path, contents: list[str]) -> Path:
    p = tmp_path / "changed.txt"
    p.write_text("\n".join(contents) + "\n", encoding="utf-8")
    return p


def test_cli_ci_clean_pr_exits_zero(tmp_path, monkeypatch):
    """A PR whose changed files contain no citations passes regardless of fail-on."""
    no_cites = tmp_path / "notes.md"
    no_cites.write_text("# release notes\n\nNo citations here.\n", encoding="utf-8")
    diff = _write_diff_file(tmp_path, [str(no_cites)])

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--changed-only",
            str(diff),
            "--fail-on",
            "miss",
            "--paths",
            "**/*.md",
            "--no-cache",
        ],
    )
    assert result.exit_code == ci_mod.EXIT_PASS, result.output


def test_cli_ci_missing_changed_file_emits_warning_not_failure(tmp_path):
    diff = _write_diff_file(tmp_path, ["does_not_exist.md"])
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--changed-only",
            str(diff),
            "--fail-on",
            "miss",
            "--paths",
            "**/*.md",
            "--no-cache",
            "--no-annotations",
        ],
    )
    # No citations gathered → pass under any fail-on setting.
    assert result.exit_code == ci_mod.EXIT_PASS, result.output


def test_cli_ci_writes_summary_when_requested(tmp_path):
    md_path = tmp_path / "clean.md"
    md_path.write_text("Empty.", encoding="utf-8")
    diff = _write_diff_file(tmp_path, [str(md_path)])
    summary = tmp_path / "summary.md"

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--changed-only",
            str(diff),
            "--fail-on",
            "none",
            "--paths",
            "**/*.md",
            "--summary-out",
            str(summary),
            "--no-cache",
        ],
    )
    assert result.exit_code == ci_mod.EXIT_PASS
    assert summary.exists()
    assert "CiteGuard report" in summary.read_text(encoding="utf-8")


def test_cli_ci_writes_github_output(tmp_path, monkeypatch):
    md_path = tmp_path / "clean.md"
    md_path.write_text("nothing.", encoding="utf-8")
    diff = _write_diff_file(tmp_path, [str(md_path)])
    gh_out = tmp_path / "github_output.txt"
    gh_out.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh_out))

    runner = CliRunner()
    runner.invoke(
        cli_main,
        [
            "--changed-only",
            str(diff),
            "--fail-on",
            "none",
            "--paths",
            "**/*.md",
            "--no-cache",
        ],
    )
    body = gh_out.read_text(encoding="utf-8")
    assert "hit=" in body
    assert "miss=" in body
    assert "failed=false" in body


def test_cli_usage_error_for_missing_input_path():
    runner = CliRunner()
    result = runner.invoke(cli_main, ["/path/that/definitely/does/not/exist.pdf"])
    assert result.exit_code == ci_mod.EXIT_USAGE


# ---------- v0.5.0: fix-action-version-pin-stale ---------------------------
#
# The composite Action's `version` input defaulted to "0.2.0", so the Install
# step ran `pipx install "citeguard==0.2.0"` — predating every v0.4.0
# correctness fix (Crossref fallback, DOI percent-encoding, gh_issue anchor).
# The same stale `@v0.2.0` pin was duplicated in the example workflow + READMEs.
# These guards pin the default + the consumer-facing files to the shipped tag.

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_action_version_default_tracks_shipped_version():
    action = (_REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    assert 'default: "0.5.0"' in action, "action.yml `version` input default is stale"


def test_no_stale_citeguard_action_pin_in_consumer_facing_files():
    stale = re.compile(r"citeguard@v0\.[0-4]\.\d+")
    for rel in ("action.yml", "examples/citeguard-action.yml", "README.md", "README.en.md"):
        body = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        assert not stale.search(body), f"stale citeguard action pin in {rel}: {stale.findall(body)}"
