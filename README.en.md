<p align="right"><strong>English</strong> | <a href="./README.md">简体中文</a></p>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=2,6,12&height=160&section=header&text=CiteGuard&fontSize=58&fontColor=ffffff&fontAlignY=42&desc=Paste%20a%20paper.%20Get%20a%20red%2Fgreen%20bibliography%20verdict%20in%2010s.&descSize=14&descAlignY=70" alt="CiteGuard banner" />
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg" /></a>
  <a href="https://pypi.org/project/citeguard/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/citeguard.svg?label=pypi" /></a>
  <a href="https://github.com/SuperMarioYL/citeguard/actions"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/SuperMarioYL/citeguard/ci.yml?label=CI" /></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" />
  <img alt="Status" src="https://img.shields.io/badge/status-alpha-orange.svg" />
</p>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&size=18&pause=1000&color=2EA043&center=true&vCenter=true&width=620&lines=DOI+%E2%80%A2+arXiv+%E2%80%A2+CVE+%E2%80%A2+Commit+SHA+%E2%80%A2+GitHub+Issue;Batch-resolved+against+real+registries;One+command.+No+LLM.+No+server." alt="Animated tagline" />
</p>

> **CiteGuard is a CLI that batch-verifies every citation, DOI, arXiv ID, CVE, and commit SHA in a paper or bug report against real registries (OpenAlex / Crossref / arXiv / NVD / GitHub) — in 10 seconds.**

---

## Table of Contents

- [Who it's for](#who-its-for)
- [Why now](#why-now)
- [Install](#install)
- [30-second quickstart](#30-second-quickstart)
- [Demo](#demo)
- [How it works](#how-it-works)
- [Configuration](#configuration)
- [Output format](#output-format)
- [Out of scope (v0.1)](#out-of-scope-v01)
- [Roadmap](#roadmap)
- [GitHub Action (new in v0.2)](#github-action-new-in-v02)
- [Development](#development)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Who it's for

| You are | Your pain | What CiteGuard does for you |
| :--- | :--- | :--- |
| **Journal / conference reviewer** | A 30-reference submission costs 15–20 min of manual DOI lookups; volume × 3 breaks the system | Paste the PDF/.tex → red rows pinpoint fabricated citations |
| **arXiv moderator** | The official policy already lists "unverified LLM errors" as a ban trigger, but the tooling slot is empty | Pre-process the desk-reject queue in five minutes |
| **OSS security maintainer** | Linus calls the Linux security list "near-unmanageable" — bug reports cite CVEs / commits that *look* real but don't exist | Pipe `bug_report.md` in, red-flag every fabricated identifier |
| **Thesis / dissertation advisor** | Student work co-drafted by an LLM hides hallucinated references; per-paper hand-checking is unrealistic | Pre-submission self-check; any red row must be fixed |

## Why now

Three unlocks aligned in the last 12 months — none of them existed in 2024:

1. **Demand crossed the threshold.** arXiv's 2026-05 policy makes "fabricated citations" a one-year ban trigger ([640 upvotes / 69 comments](https://www.reddit.com/r/MachineLearning/)); Linus called the LKML security list "near-unmanageable." Two independent constituencies converging on the same root.
2. **Registry APIs became real-time.** OpenAlex (fully open since 2024), NVD JSON 2.0, the arXiv API, Crossref REST, GitHub REST — for the first time their latency × quota envelope is good enough for an interactive CLI. OpenAlex *did not exist* two years ago.
3. **Extraction got cheap.** Pulling structured references from PDF / .tex used to need a GROBID-grade engineering team; today ≤ 200 lines of deterministic regex covers 90 % recall. CiteGuard v0.1 deliberately uses **no LLM** — precision over recall.

> Remove any one of the three and CiteGuard could not have existed two years ago — that's why it shows up now.

## Install

```bash
pipx install citeguard
```

or `pip install citeguard`.  Python ≥ 3.11.  No GPU, no daemon, no LLM call.
Tested on Linux and macOS.

## 30-second quickstart

```bash
citeguard paper.pdf
```

Within 10 seconds you get a terminal red/green table:

- ✓ **green check** — the identifier exists in an authoritative registry (with evidence URL)
- ✗ **red cross** — the identifier was not found, plus up to 3 nearest-match candidates with edit distance
- ? **yellow question** — timeout / rate-limit / transient failure

A `paper.pdf.citeguard.json` sidecar drops alongside the input, ready for downstream tooling.

<details>
<summary>Sample terminal output</summary>

```
  ┌──┬──────────┬───────────────────────────────┬──────────┬────────────────────────────────────┐
  │  │ Kind     │ Identifier                    │ Registry │ Evidence / nearest match           │
  ├──┼──────────┼───────────────────────────────┼──────────┼────────────────────────────────────┤
  │✓ │ arxiv    │ 1706.03762                    │ arxiv    │ https://arxiv.org/abs/1706.03762   │
  │✗ │ arxiv    │ 9999.00001                    │ arxiv    │                                    │
  │✗ │ doi      │ 10.9999/not-a-real-doi-12345  │ openalex │ ≈ Probably-similar paper (d=23)    │
  │? │ cve      │ CVE-2024-77777                │ nvd      │ rate-limit; retry with backoff     │
  └──┴──────────┴───────────────────────────────┴──────────┴────────────────────────────────────┘
  1 hit · 2 miss · 1 degraded
```

</details>

## Demo

> 30 seconds: a withdrawn arXiv paper → 3 red rows pin the fabricated refs → JSON sidecar appears.

[![asciicast](https://asciinema.org/a/PLACEHOLDER.svg)](https://asciinema.org/a/PLACEHOLDER)

> 📼 `assets/demo.tape` is a [VHS](https://github.com/charmbracelet/vhs) script you can re-record in one command — see [`assets/README.md`](./assets/README.md).

## How it works

```
+----------+    +---------+    +------------------+    +----------+
|  Input   | -> | Extract | -> |  Resolver fanout | -> |  Report  |
| pdf/tex  |    | regex + |    |  5 resolvers     |    | rich /   |
| md/text  |    | pypdf   |    |  httpx + retry   |    | json/md  |
+----------+    +---------+    +--------+---------+    +----------+
                                        |
                                  +-----v------+
                                  | sqlite     |
                                  | cache 7d   |
                                  +------------+
```

1. **Extraction** uses `pypdf` for the PDF text layer + five identifier-class regexes.  No LLM, ever — precision over recall is the v0.1 contract.
2. **Resolver fan-out** runs the five resolvers through `asyncio.gather` with bounded concurrency, retried with `tenacity` exponential backoff on transport / 5xx, and a single shared `httpx.AsyncClient`.
3. **SQLite cache** at `~/.cache/citeguard/registry.db`, TTL = 7 days.  `degraded` outcomes are deliberately **not** cached so a single transient failure never freezes a result for a week.
4. **Report layer** renders the rich red/green table; the JSON sidecar drops by default; optional `--md` writes Markdown.

## Configuration

CiteGuard is intentionally configuration-free in v0.1 — everything lives on
the command line.

| Option | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `--json PATH` | path | `<input>.citeguard.json` | Where to write the JSON sidecar |
| `--md PATH` | path | *unset* | Also write a Markdown report |
| `--no-cache` | flag | `false` | Skip the SQLite cache (hit real registries every time) |
| `--strict` | flag | `false` | Exit 1 on any miss — superseded by `--fail-on` in v0.2, kept for back-compat |
| `--changed-only PATH` | path | *unset* | **v0.2 CI mode**: read newline-separated changed-file list from PATH and verify each |
| `--fail-on {none,miss,degraded}` | enum | `none` | **v0.2 CI mode**: which outcome counts as a failure |
| `--max-misses N` | int | `0` | **v0.2 CI mode**: tolerate up to N misses before `--fail-on` triggers |
| `--paths "<glob>,<glob>"` | string | `**/*.pdf,**/*.tex,**/*.md` | **v0.2 CI mode**: comma-separated glob filter applied to changed files |
| `--summary-out PATH` | path | *unset* | **v0.2 CI mode**: append the Markdown job summary to PATH (typically `$GITHUB_STEP_SUMMARY`) |
| `GITHUB_TOKEN` | env | *unset* | Raises the GitHub resolver from 60/hour to 5000/hour |

## Output format

The JSON sidecar has a stable schema downstream tools can consume:

```json
{
  "generator": "citeguard/0.2",
  "results": [
    {
      "citation": {"raw_text": "arXiv:1706.03762", "kind": "arxiv", "identifier": "1706.03762"},
      "status": "hit",
      "registry": "arxiv",
      "evidence_url": "https://arxiv.org/abs/1706.03762",
      "nearest_matches": []
    }
  ]
}
```

## Out of scope (v0.1)

Deliberately not done — each with a specific reason:

- Web UI / hosted SaaS — v0.1 is CLI only
- Multi-user / auth / team dashboards
- **LLM-based extraction** — only deterministic regex in v0.1; precision over recall
- Auto-reviewing / citation sentiment / writing suggestions (CiteGuard answers existence only)
- PDF OCR (text-layer PDFs / .tex / .md / plain text only)
- Self-trained models or anything requiring a GPU

> Since v0.2 the **GitHub Action wrapper** is no longer out of scope — see [GitHub Action (new in v0.2)](#github-action-new-in-v02). GitLab CI, SARIF output, and auto-fixing fabricated citations remain out of scope for v0.2.

## GitHub Action (new in v0.2)

Put CiteGuard in CI — every PR gets its citations verified, and the verdict
appears as a sticky red/green comment.

Drop this into `.github/workflows/citeguard.yml` (or copy
[`examples/citeguard-action.yml`](./examples/citeguard-action.yml)):

```yaml
name: CiteGuard

on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths: ["**/*.pdf", "**/*.tex", "**/*.md"]

permissions:
  contents: read
  pull-requests: write   # required for the sticky comment + inline annotations

jobs:
  citeguard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0
      - uses: SuperMarioYL/citeguard@v0.2.0
        with:
          fail-on: miss        # journals: keep `miss`; OSS: start with `none`
          max-misses: 0
          paths: "**/*.pdf,**/*.tex,**/*.md"
          comment: "true"
```

On every PR that touches `.pdf` / `.tex` / `.md`, the Action will:

1. **Upsert a sticky PR comment.** One auto-updating comment per PR, marked
   with `<!-- citeguard:sticky -->` so subsequent runs edit in place rather
   than spamming the thread.
2. **Write a job summary.** The same red/green table is appended to
   `$GITHUB_STEP_SUMMARY`, visible from the Actions run page even if you turn
   the comment off.
3. **Emit inline annotations.** Each miss becomes an `::error file=…::` line
   so GitHub renders a red annotation on the PR's *Files changed* tab.
   Degraded results render as `::warning`.

### Exit-code contract (CLI side, v0.2 §2b)

The CLI exit codes that the Action depends on are a stable v0.2 contract:

| Exit | Meaning | CI effect |
| :---: | :--- | :--- |
| `0` | All citations within `--fail-on` + `--max-misses` thresholds | check passes |
| `1` | `miss` / `degraded` count exceeded threshold | check fails when `fail-on != none` |
| `2` | Usage / IO error (bad flag, unreadable file) | check always fails |

Full inputs / outputs / permissions reference: [`docs/github-action.md`](./docs/github-action.md).

### Picking a threshold

| Audience | Recommended | Why |
| :--- | :--- | :--- |
| Journals, conference review | `fail-on: miss`, `max-misses: 0` | Block any PR carrying a fabricated reference. |
| OSS docs, advisory rollout | `fail-on: none` | Sticky comment only; never blocks a PR. Use this for the first 1–2 weeks. |
| Critical security advisories | `fail-on: degraded`, `max-misses: 0` | Anything the registries can't confirm fails the check, including transient timeouts. |

## Roadmap

- [x] **m1 — Extraction**: DOI / arXiv / CVE / commit SHA / `owner/repo#issue` across PDF + LaTeX + Markdown + plain text
- [x] **m2 — Resolver orchestration**: five concurrent registries with backoff + SQLite cache
- [x] **m3 — Reporting**: red/green table + JSON / Markdown export + nearest-match candidates
- [x] **m4 — CLI CI mode** (v0.2): `--changed-only` / `--fail-on` / `--max-misses` / `--paths` + exit-code contract + workflow-command annotations
- [x] **m5 — GitHub Action** (v0.2): composite `action.yml` + PyPI trusted publishing + sticky PR comment
- [ ] **m6 — GitLab CI component** (v0.3)
- [ ] **m7 — Optional LLM extraction fallback** (off by default)
- [ ] **m8 — Windows pipx binary**

## Development

```bash
git clone https://github.com/SuperMarioYL/citeguard.git
cd citeguard
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                 # first run materialises tests/fixtures/sample_paper.pdf
make lint                 # ruff check + ruff format --check (release gate as of v0.3)
pre-commit install --hook-type pre-push   # wire the same lint into `git push`
```

`make help` lists every target (`install-dev` / `lint` / `lint-fix` / `test`).
The `.pre-commit-config.yaml` attaches ruff to the `pre-push` stage — local
commits stay fast, but `git push` runs the same checks CI does so CI is never
the first place a lint failure shows up. CI also runs a grep guard that pins
every GitHub Action to the Node.js-24 majors (`checkout@v5` /
`setup-python@v6`); any PR that regresses to a stale pin fails the build.

Issues welcome — especially:

- false positives (a red row that should be green)
- false negatives (a fabricated reference we missed)
- proposals for adding a new registry

## License

[MIT](./LICENSE).  Free for commercial, academic, and personal use — and
that's not going to change.

## Acknowledgements

CiteGuard started from a concrete pain point: in 2026 arXiv began issuing
one-year submission bans for papers containing unchecked LLM errors such as
hallucinated references, and OSS security maintainers were drowning in
LLM-assisted bug reports citing CVEs and commits that don't exist.  This
repository is a deterministic, no-LLM answer to that pain — it only ever
answers "does this citation actually exist?".
