# Changelog

All notable changes to CiteGuard will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); semver per
[SemVer 2.0](https://semver.org/).

## [0.5.0] — 2026-08-01

Correctness + release-hygiene release.  Five fix milestones from the autonomous
grill (signal-harvest → bug-hunt on shipped v0.4.0 source → 4 parallel critics
PASS): the GitHub-Action version pin stops shipping pre-fix logic, two
extraction-regex false-positive holes close, PyPI trusted-publishing is wired,
and the post-ship Apache-2.0 license adoption is reconciled locally.  No new
audience / distribution channel / out-of-scope scope expansion.

### Fixed
- **Action version pin bumped off 0.2.0** (`fix-action-version-pin-stale`).
  The composite Action's `version` input defaulted to `0.2.0`, and the same
  stale `@v0.2.0` pin was duplicated in `examples/citeguard-action.yml`,
  `README.md`, and `README.en.md`.  v0.2.0 predates every v0.4.0 correctness
  fix, so the documented Action channel silently shipped the exact
  false-fabrication regressions v0.4.0 repaired.  The default is now `0.5.0`
  and all consumer-facing pins point at `@v0.5.0`.
- **DOIs followed by `?` or `#` are no longer truncated/dropped**
  (`fix-doi-truncated-before-query-fragment`).  `_DOI_RE`'s right-boundary
  lookahead admitted `.` but not `?`/`#`; a DOI suffix containing a `.` followed
  by `?`/`#` backtracked to the last `.` boundary and returned the truncated
  prefix (e.g. `10.1145/3460120.3484797?ref=x` → `10.1145/3460120`), and a
  no-`.` suffix was dropped entirely.  `?#` was added to the boundary class so
  the full DOI matches and stops at the query/fragment delimiter — this also
  makes the v0.4.0 resolver-side percent-encoding reachable for `?`/`#`.
- **The `gh_issue` shortcut no longer matches DOI fragments / domain paths**
  (`fix-gh-issue-overmatches-dot-owner`).  The owner character class admitted
  `.`, so a bare `10.1145/3460120#2` after whitespace (or `example.com/docs#2`)
  was mis-extracted as a `gh_issue` and dispatched to the GitHub REST API
  (404 → false `miss`/fabricated).  `.` was dropped from the OWNER class
  (`[A-Za-z0-9][A-Za-z0-9_-]{0,38}`); GitHub org/user names never contain
  dots, so no real `owner/repo#N` reference is lost.  The repo class keeps `.`.

### Changed — release hygiene
- **PyPI trusted-publishing repaired** (`repair-pypi-trusted-publishing`).
  v0.3.0/v0.4.0 never reached PyPI (latest = 0.2.0);
  `.github/workflows/release.yml` already wires
  `pypa/gh-action-pypi-publish@release/v1` with `permissions: id-token: write`
  and the `pypi` environment (no API token).  The remaining step is the one-time
  PyPI-side OIDC trusted-publisher enrollment on
  pypi.org/manage/account/publishing (external, non-code) — once confirmed, the
  next tag auto-publishes and `pipx install citeguard==0.5.0` resolves.
- **Apache-2.0 license reconciled locally** (`reconcile-apache2-license`).
  The 2026-07-20 Apache-2.0 adoption had landed GitHub-only (plan/source drift);
  the local build clone still carried MIT.  `LICENSE` is now the canonical
  Apache-2.0 text, `pyproject.toml` `[project].license` is `Apache-2.0` (and the
  trove classifier updated), and the README license badges / sections in both
  locales point at Apache-2.0.

## [0.4.0] — 2026-06-20

Correctness release.  Three false-positive defects let CiteGuard flag real,
verifiable citations as fabricated — exactly the failure mode that erodes
trust in a `--fail-on miss` CI gate.  Plus a pre-flight-gate extension that
generalises the v0.3 lint smoke test.

### Fixed
- **Crossref fallback is now wired in** (`fix-crossref-fallback-unwired`).
  `crossref_resolver` was imported on the surface but never invoked, so an
  OpenAlex 404 became an immediate `miss`.  DOIs that are live on Crossref but
  not yet backfilled into OpenAlex were reported as fabricated.  `_verify_one`
  now falls back to Crossref on an OpenAlex DOI miss and upgrades to `hit` when
  Crossref confirms; a `miss` is emitted only when both registries 404.  The
  post-fallback result is what gets cached.
- **DOIs are percent-encoded before the request path is built**
  (`fix-doi-not-url-encoded`).  The extraction regex admits URL-reserved chars
  (`?`, `#`, `;`); interpolating a raw DOI truncated the path at the query /
  fragment boundary, producing a malformed URL → spurious 404 → false
  fabrication.  Both `openalex` and `crossref` resolvers now wrap the DOI in
  `urllib.parse.quote(doi, safe="")`.
- **The `gh_issue` shortcut regex is left-anchored**
  (`fix-gh-issue-regex-overmatch`).  The bare `owner/repo#N` branch had no
  required anchor, so any `<word>/<word>#<digits>` substring matched — a DOI
  fragment like `10.1145/3460120#2` or a path like `results/table#3` was
  mis-extracted as a `gh_issue`, sent to the GitHub API, and flagged `miss`.
  The shortcut form now fires only at start-of-string or after whitespace; the
  full `github.com/...` URL form remains unconditional.

### Changed — m6_preflight_lint extension
- `make lint` now runs a **version-consistency check** (`make check-version`,
  `scripts/check_version.py`): it asserts `pyproject [project].version` equals
  the top `## [X.Y.Z]` CHANGELOG entry (and the matching git tag, when one
  exists) and fails the gate on drift.  This guards the v0.3.0 publish-day
  defect class where `pyproject` lagged the CHANGELOG and needed a hand-fix.
- The stale-Action-major **grep guard now scans every file under
  `.github/workflows/`** (including `demo.yml` and `release.yml`), not just
  `ci.yml`.  The `ci.yml` self-exemption was removed — the pattern matches a
  literal `@vN` pin, not the regex string documented in the guard step — so the
  Action-pin policy can no longer silently lapse on a new workflow surface.

### Added
- New offline tests + golden fixtures covering each fix:
  `tests/fixtures/crossref_fallback.jsonl`,
  `tests/fixtures/doi_url_encoding.jsonl`,
  `tests/fixtures/gh_issue_overmatch.jsonl`, with matching cases in
  `tests/test_resolvers.py` (httpx `MockTransport`) asserting the
  OpenAlex-404 → Crossref-200 upgrade, the percent-encoded request URL, and
  the gh_issue overmatch rejections.

### Not changed (still out of scope per `mvp_plan.md` §6)
- GitLab CI integration / CI component.
- SARIF output / GitHub code-scanning Security-tab integration.
- LLM-based extraction recall booster.

## [0.3.0] — 2026-05-23

Pre-release smoke gate.  No new user-visible feature; the surface area is
purely developer ergonomics — same milestone (`m6_preflight_lint`) drove
every change.  Triggered by the v0.2.0 release-day pattern (three commits
in five minutes on day zero — initial release + ruff hotfix across 15
files + Action-version bump), all of which a local gate would have caught.

### Added — m6_preflight_lint
- `Makefile` with `help`, `install-dev`, `lint`, `lint-fix`, and `test`
  targets.  `make lint` runs `ruff check .` + `ruff format --check .` and
  is the canonical pre-release gate.
- `.pre-commit-config.yaml` wiring `astral-sh/ruff-pre-commit@v0.7.4` to
  the `pre-push` stage so the same lint that gates a release also fires
  before a `git push` ever reaches CI.  `pre-commit` itself is now a dev
  dependency (`pre-commit>=3.7`).
- New CI job `pin-actions-versions` (`.github/workflows/ci.yml`) that
  `git grep`s the repo for `actions/checkout@v[1-4]` or
  `actions/setup-python@v[1-5]` and fails the build if any are found —
  pinning every workflow to the post-2026-06 Node.js-24 majors
  (`checkout@v5` / `setup-python@v6`).  `.example`-suffixed fixtures are
  excluded from the scan so the in-tree documentation fixture
  (`.github/workflows/_fixture_stale_action.yml.example`) does not trip
  the guard.

### Changed
- `action.yml` and `examples/citeguard-action.yml` bumped from
  `setup-python@v5` / `checkout@v4` to `setup-python@v6` / `checkout@v5`
  to satisfy the new grep guard.
- README.md and README.en.md gained a small note in the existing
  `开发` / `Development` section pointing first-time contributors at
  `make lint` and `pre-commit install --hook-type pre-push`.
- `BUILD_SETUP_NEXT_STEPS.md` updated with the v0.3 first-time-contributor
  setup (`pip install -e .[dev]` + `pre-commit install --hook-type
  pre-push`).
- `pyproject.toml` dev extras gain `pre-commit>=3.7`.  No runtime
  dependency change.

### Not changed (still out of scope per `mvp_plan.md` §6)
- GitLab CI integration / CI component (still deferred — no external usage
  signal yet).
- SARIF output / GitHub code-scanning Security-tab integration.
- Windows pipx binary.
- `--strict` LLM-based extraction recall booster.

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
- `pipx install citeguard` entry point, Apache 2.0 licensed.
- Bilingual README (zh-CN primary, English sibling).
- GitHub Actions CI matrix: Python 3.11 + 3.12 on Ubuntu + macOS.
- `vhs` tape under `assets/demo.tape` that regenerates the 30-second README
  recording on demand.
