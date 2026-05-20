# Changelog

All notable changes to CiteGuard will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); semver per
[SemVer 2.0](https://semver.org/).

## [0.2.0] — 2026-05-20

Headline feature: **CiteGuard runs in CI**. A composite GitHub Action wraps
the CLI; every PR gets its citations verified, with a sticky red/green PR
comment, job summary, and inline annotations.

### Added — m4_cli_ci_mode
- New CLI flags backing CI mode: `--changed-only PATH`, `--fail-on
  {none,miss,degraded}`, `--max-misses N`, `--paths "<glob>,<glob>"`, and
  `--summary-out PATH`.
- Stable v0.2 §2b exit-code contract:
  - `0` — all citations within threshold (pass).
  - `1` — `miss` / `degraded` count crossed threshold (CI fail when
    `fail-on != none`).
  - `2` — usage / IO error (always fails).
- GitHub workflow-command annotation output (`::error file=…::` for misses,
  `::warning::` for degraded), with the proper `%` / `\r` / `\n` escapes.
- Job-summary Markdown writer that appends to `$GITHUB_STEP_SUMMARY` and
  carries a `<!-- citeguard:sticky -->` marker for the PR-comment upsert.
- New module `citeguard.ci` housing the platform-neutral CI helpers
  (`load_changed_files`, `filter_paths`, `should_fail`, `render_annotations`,
  `render_job_summary`).
- 14 new tests in `tests/test_ci.py` covering glob filtering, the three
  fail-on thresholds (`none` / `miss` / `degraded`), annotation formatting +
  escaping, summary Markdown, GITHUB_OUTPUT writeback, and CLI end-to-end
  dispatch via `click.testing.CliRunner`.

### Added — m5_github_action
- `action.yml` — composite Action that installs `citeguard` from PyPI via
  `pipx`, computes the PR diff with `gh pr diff --name-only`, runs the CLI in
  CI mode, upserts a sticky PR comment (edit-in-place via `gh api`), writes
  the job summary, and exits non-zero when the fail-on threshold is crossed.
- `examples/citeguard-action.yml` — copy-paste consumer workflow.
- `docs/github-action.md` — full Action reference: inputs, outputs,
  permissions, threshold-picking guide, security notes, self-hosted runner
  network allowlist, versioning policy.
- `.github/workflows/release.yml` — tag-driven PyPI publish via trusted
  publishing (no API token), with a tag-vs-pyproject version verification
  step.
- Action `branding`: `icon=check-circle, color=green` for the Marketplace
  listing.

### Changed
- Package version bumped to `0.2.0`; JSON sidecar `generator` field bumped to
  `citeguard/0.2` (the test only asserts the `citeguard/` prefix, so the
  schema remains backward-compatible).
- README + README.en gained a new `GitHub Action (new in v0.2)` section, an
  expanded configuration table covering the four CI flags, and an updated
  roadmap that ticks off m4 and m5.

### Not changed (still out of scope per `mvp_plan.md` §6)
- GitLab CI integration / CI component (deferred to v0.3; the CLI flags are
  already platform-neutral).
- SARIF output / GitHub code-scanning Security-tab integration.
- GitHub Marketplace paid or verified-publisher listing (free listing only).
- Auto-fixing fabricated citations (CiteGuard still only reports existence).
- LLM-based extraction.

## [0.1.0] — 2026-05-20

First public release covering all three v0.1 milestones from the MVP plan.

### Added — m1_extract_refs
- Deterministic regex-based extraction of DOI, arXiv (new and legacy), CVE,
  GitHub commit SHA, and `owner/repo#issue` identifiers.
- File-type dispatch covering PDF (text layer via `pypdf`), LaTeX, Markdown,
  and plain text.
- Stable `Citation` model with `(kind, identifier)` de-duplication.

### Added — m2_resolve_batch
- Async resolver fan-out across five registries: OpenAlex, Crossref, arXiv,
  NVD, GitHub REST.
- Tenacity-driven exponential backoff with stop-after-three on transport
  errors and 5xx responses.
- SQLite cache (`~/.cache/citeguard/registry.db`) with a 7-day TTL and a
  refusal to memoise `degraded` outcomes.
- Bounded concurrency (semaphore of 8) so a 30-reference paper does not
  self-DoS NVD's per-IP quota.

### Added — m3_render_report
- Rich red/green terminal table with status glyph, kind, identifier,
  registry, and evidence column.
- JSON sidecar (`<input>.citeguard.json`) and Markdown report exports.
- "Nearest match" candidates for missed DOIs (OpenAlex title fuzzy search) and
  CVEs (year-neighbour heuristic).
- Three golden fixtures (a withdrawn paper, a clean paper, an OSS bug report)
  driving the end-to-end test path.

### Added — packaging
- `pipx install citeguard` entry point, MIT licensed.
- Bilingual README (zh-CN primary, English sibling).
- GitHub Actions CI matrix: Python 3.11 + 3.12 on Ubuntu + macOS.
- `vhs` tape under `assets/demo.tape` that regenerates the 30-second README
  recording on demand.
