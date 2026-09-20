**English** | [简体中文](README.md)

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/hero-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img src="assets/hero-light.svg" width="920" alt="CiteGuard citation shield and converging particles: check references, keep the evidence.">
</picture>

**CiteGuard extracts identifiers from papers and issue reports, queries the relevant registries, and keeps each result with its evidence link and source location.**

`v0.9.0` · `Python ≥ 3.11` · `CLI + GitHub Action` · [Apache-2.0](LICENSE)

[Use cases](#use-cases) · [Architecture](#architecture) · [Install](#install) · [Offline quickstart](#offline-quickstart) · [Verification](#network-verification-and-output) · [CI](#ci-integration) · [Configuration](#configuration) · [Scope](#current-scope-and-next-directions)

## Use cases

When you encounter a DOI, arXiv ID or CVE, the useful questions include what the registry returns and where the identifier appears in the source. CiteGuard turns that check into a batchable command-line workflow with a saved record, for authors, reviewers and maintainers handling issue reports.

A verification result indicates whether the queried registry found the identifier. It does not establish whether a paper supports a claim, and a single `miss` does not prove that an author fabricated a reference. Formatting, context and registry availability can all warrant further inspection.

## Architecture

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/architecture-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/architecture-dark.svg">
  <img src="assets/architecture-light.svg" width="920" alt="Offline extraction creates Citation objects; network resolvers query registries; caching and reports retain results and source context.">
</picture>

The [extractor](src/citeguard/extract.py) reads text-layer PDFs, TeX, Markdown and plain text. Deterministic patterns recognize DOIs, arXiv IDs, CVEs, anchored commit SHAs and GitHub issue/PR references. A `Citation` retains the raw match, normalized identifier, file, character span and line number.

The [CLI orchestrator](src/citeguard/cli.py) routes identifiers to their resolvers with at most eight concurrent checks. DOI lookup starts with OpenAlex and falls back to Crossref only on `miss`. If Crossref is unreachable, the result stays `degraded` rather than caching an unconfirmed absence.

The [SQLite cache](src/citeguard/resolvers/__init__.py) uses a seven-day TTL and does not store degraded results. SQLite read/write errors leave the lookup path available. The [report layer](src/citeguard/report.py) renders network `VerifyResult` objects as a terminal table, JSON and optional Markdown.

## Install

Requires Python 3.11 or newer. Check `python3 --version`, then install from source:

```bash
git clone https://github.com/SuperMarioYL/citeguard.git
cd citeguard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Installing dependencies needs network access. Extraction calls neither models nor registries; full verification needs external registry access.

## Offline quickstart

Create the complete input first. These illustrative identifiers are used to demonstrate extraction; their existence is not queried in this example:

```bash
mkdir -p examples
cat > examples/identifiers.md <<'CITEGUARD_INPUT'
Research note
DOI: 10.1145/3460120.
arXiv:1706.03762v2
CVE-2024-3094
commit 0123456789abcdef0123456789abcdef01234567
https://github.com/example/project/issues/42
Repeat: arXiv:1706.03762
CITEGUARD_INPUT
```

As of v0.9.0 the documented short form works directly:

```bash
citeguard extract examples/identifiers.md
```

(Releases before v0.9.0 parsed a top-level `PATH` before the subcommand, so the path had to appear both before and after `extract`.)

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/process-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/process-dark.svg">
  <img src="assets/process-light.svg" width="920" alt="Seven input lines yield five unique identifiers with complete values and source line numbers, without registry queries.">
</picture>

The output contains five deduplicated `Citation` objects. arXiv version suffixes are removed and the repeated arXiv ID collapses to one object. Each object retains its matched line number. The actual standard output is:

```json
[
  {"raw_text":"DOI: 10.1145/3460120.","kind":"doi","identifier":"10.1145/3460120","context_span":{"file":"examples/identifiers.md","start":14,"end":35,"line":2}},
  {"raw_text":"arXiv:1706.03762v2","kind":"arxiv","identifier":"1706.03762","context_span":{"file":"examples/identifiers.md","start":36,"end":54,"line":3}},
  {"raw_text":"CVE-2024-3094","kind":"cve","identifier":"CVE-2024-3094","context_span":{"file":"examples/identifiers.md","start":55,"end":68,"line":4}},
  {"raw_text":"commit 0123456789abcdef0123456789abcdef01234567","kind":"commit","identifier":"0123456789abcdef0123456789abcdef01234567","context_span":{"file":"examples/identifiers.md","start":69,"end":116,"line":5}},
  {"raw_text":"https://github.com/example/project/issues/42","kind":"gh_issue","identifier":"example/project#42","context_span":{"file":"examples/identifiers.md","start":117,"end":161,"line":6}}
]
```

Two additional complete inputs cover normalization and matching boundaries:

| Input | Actual invocation | Output from this run |
|---|---|---|
| [Normalization example](examples/normalized.tex) | `citeguard examples/normalized.tex extract examples/normalized.tex` | Two identifiers after DOI case and arXiv version normalization |
| [Boundary example](examples/boundaries.txt) | `citeguard examples/boundaries.txt extract examples/boundaries.txt` | A DOI and a GitHub issue; the bare 40-character hash is not extracted as a commit |

[Complete inputs, commands and output](docs/demo-results.json) · [Input creation and replay script](docs/demo.sh) · [Text transcript](docs/demo-output.txt)

## Network verification and output

With the input prepared, use the top-level command for full verification. Put options before the input path:

```bash
citeguard --json report.json --md report.md examples/identifiers.md
```

| Status | Meaning | What to inspect next |
|---|---|---|
| `hit` | The queried registry returned a record | `evidence_url` and the source context |
| `miss` | The lookup path did not find a record | Identifier format, registry choice and any nearest candidates |
| `degraded` | A timeout, rate limit, missing context or other problem prevented a verdict | The specific reason in `note` |

The OpenAlex DOI miss path can include up to three nearest candidates as leads for review. An anchored bare commit can be extracted but still lacks the repository context required for verification; cite a complete GitHub commit URL in the source.

By default, the full workflow writes `<input>.citeguard.json`. The document contains `generator` and `results`; each result includes `citation`, `status`, `registry`, optional `evidence_url`, `nearest_matches` and `note`. Offline `extract` only prints a Citation array to standard output and does not produce verification statuses.

The existing [terminal recording](assets/demo.gif) and [VHS tape](docs/demo.tape) are retained for the network workflow. Registry results depend on external state at query time. The offline results in this section are defined by the recorded commands above.

## Capabilities and integration

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/integrations-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/integrations-dark.svg">
  <img src="assets/integrations-light.svg" width="920" alt="Registry routes for five identifier types, document inputs, JSON and Markdown reports, and the GitHub Action.">
</picture>

| Content | Current route | Boundary |
|---|---|---|
| DOI | OpenAlex, then Crossref on miss | Checks registry records, not the quality of an argument |
| arXiv | arXiv API | Extraction normalizes IDs by removing version suffixes |
| CVE | NVD | Identifies and queries CVEs; it does not assess whether your system is affected |
| GitHub commits and issues/PRs | GitHub REST | Commit verification needs repository context |
| PDF, TeX, Markdown, plain text | Text loading and pattern extraction | PDFs need a text layer; free-form references without identifiers may not be extracted |
| Automation | JSON, Markdown, GitHub Action | Downstream users choose thresholds and review policy |

## CI integration

The repository supplies a [GitHub composite Action](action.yml) with changed-file input, job summaries, sticky PR comments and source-line annotations. See the [Action reference](docs/github-action.md) and [workflow example](examples/citeguard-action.yml). You can prepare the same input locally:

```bash
printf '%s\n' examples/identifiers.md > changed.txt
citeguard --changed-only changed.txt --fail-on miss --max-misses 0 --summary-out summary.md
```

`--fail-on none` reports only, `miss` counts missing results, and `degraded` counts both missing and inconclusive results. Failure occurs only above `--max-misses`. CI exit codes are `0` for a result within threshold, `1` for an exceeded threshold and `2` for usage or I/O errors.

v0.8.0 includes a line number in annotations when `context_span.line` is present. For PDFs, this is a line in extracted text, not a visual page coordinate. PR comments need suitable repository write permissions. The Action's implementation does not mean this offline example ran in hosted CI.

## Configuration

| Option | Default / scope | Purpose |
|---|---|---|
| `--json PATH` | Full workflow: `<input>.citeguard.json` | Select JSON output |
| `--md PATH` | No Markdown file | Add a report |
| `--no-cache` | Cache enabled | Query registries again; this is not an offline mode |
| `--strict` | Off | Exit 1 on a miss in the top-level full workflow |
| `--changed-only PATH` | CI mode off | Read one changed path per line |
| `--fail-on` | `none` | CI threshold class: none / miss / degraded |
| `--max-misses N` | `0` | CI tolerated count |
| `--paths` | `**/*.pdf,**/*.tex,**/*.md` | Filter CI files |
| `--summary-out PATH` | No summary file | Append a Markdown job summary |
| `--annotations / --no-annotations` | On in CI mode | Control workflow-command annotations |
| `GITHUB_TOKEN` | Optional | Authenticate GitHub resolver requests |

There is no configuration file. The default cache is `~/.cache/citeguard/registry.db`. Deduplication uses `(kind, identifier)`, and output follows matcher-pass order rather than necessarily following document order.

## Current scope and next directions

v0.8.0 implements five identifier types, registry resolvers, caching, reports, CI thresholds, a GitHub Action and line-aware annotations. The current implementation has no OCR, LLM extraction, automatic citation repair, full argument assessment or hosted team interface. GitLab CI components, an optional LLM fallback and Windows distribution remain future directions.

Development commands and dependencies are defined in [pyproject.toml](pyproject.toml). Existing tests exercise resolver, cache and CI contracts. Their mocked responses test branches; they are not evidence that a live registry confirmed a citation.

## License

[Apache-2.0](LICENSE) · [Source and issues](https://github.com/SuperMarioYL/citeguard)
