# CiteGuard GitHub Action

Run CiteGuard automatically on every PR. The Action installs the CLI from PyPI,
detects the PR's changed files, runs `citeguard --changed-only`, and surfaces
the verdict on the PR via a sticky comment, a job summary, and inline
annotations.

This page is the reference for `inputs`, `outputs`, permissions, and the
exit-code contract. The headline copy lives in the README.

---

## Quick install

Copy [`examples/citeguard-action.yml`](../examples/citeguard-action.yml) into
your repository at `.github/workflows/citeguard.yml`. That is the entire
integration — no Docker image, no secrets, no extra runner.

## Required permissions

The Action upserts a sticky PR comment and emits inline annotations, so the
job needs:

```yaml
permissions:
  contents: read
  pull-requests: write
```

`contents: read` is the default; `pull-requests: write` you must add. If you
disable comments (`comment: "false"`) you can drop the `pull-requests`
permission entirely.

## Inputs

| Input | Type | Default | Meaning |
| :--- | :--- | :--- | :--- |
| `version` | string | `0.5.0` | Pinned `citeguard` version installed via `pipx`. Set to `latest` to track HEAD. |
| `fail-on` | enum | `miss` | Which outcome trips a failing check. One of `none` / `miss` / `degraded`. |
| `max-misses` | integer | `0` | Tolerate up to N misses before `fail-on` triggers. |
| `paths` | glob list | `**/*.pdf,**/*.tex,**/*.md` | Comma-separated glob filter applied to the PR's changed files. |
| `comment` | boolean | `true` | Post a sticky PR comment with the red/green report. |
| `github-token` | string | `${{ github.token }}` | Token used for `gh pr diff` and the sticky-comment upsert. |

## Outputs

| Output | Meaning |
| :--- | :--- |
| `hit` | Number of citations that resolved successfully. |
| `miss` | Number of citations the registries could not find. |
| `degraded` | Number of citations the registries did not return a verdict on. |
| `failed` | `"true"` iff the `fail-on` threshold was crossed. |

You can chain on the outputs:

```yaml
- name: Post Slack notification on regression
  if: ${{ steps.citeguard.outputs.failed == 'true' }}
  run: ...
```

## Exit-code contract (CLI side)

The composite Action is a thin shell over the `citeguard --changed-only` CLI.
The CLI's exit codes are a stable v0.2.0 contract:

| Exit | Meaning | CI effect |
| :--- | :--- | :--- |
| `0` | All citations within threshold (pass) | Check passes |
| `1` | `miss` / `degraded` count crossed threshold | Check fails when `fail-on != none` |
| `2` | Usage / IO error (bad flag, unreadable file) | Check fails (always) |

`fail-on: none` is advisory mode: the sticky comment and annotations still
render, but the check never goes red on content issues. We recommend OSS
projects start there.

## What the Action emits

1. **Sticky PR comment** — one auto-updating comment per PR. The Action looks
   for a comment containing the marker `<!-- citeguard:sticky -->` and edits it
   in place, so noisy PRs do not produce comment spam.
2. **Job summary** — the same red/green table is written to
   `$GITHUB_STEP_SUMMARY`, so it shows up under the Actions run page even if
   you turn the PR comment off.
3. **Inline annotations** — every miss becomes an `::error file=...::` line so
   GitHub renders it as a red annotation on the PR's `Files changed` tab.
   Degraded results render as `::warning`.

## Choosing a threshold

| Audience | Recommended setting | Rationale |
| :--- | :--- | :--- |
| Journals, conference review | `fail-on: miss`, `max-misses: 0` | Block any fabricated citation reaching reviewers. |
| OSS docs / advisory rollout | `fail-on: none` | Sticky comment only; never blocks a PR. Useful for the first week. |
| Critical security advisories | `fail-on: degraded`, `max-misses: 0` | Any unresolved CVE / commit fails the check, including registry timeouts. Add retries upstream. |

## Self-hosted runners

The Action only requires Python 3.11+, `pipx`, and outbound HTTPS to
`api.openalex.org`, `api.crossref.org`, `export.arxiv.org`,
`services.nvd.nist.gov`, and `api.github.com`. If your self-hosted runner
restricts egress, allowlist those hosts before installing.

## Security

* The Action does not send the PR diff or repository contents anywhere — only
  the identifiers extracted from changed files are looked up in public
  registries.
* All registry calls are HTTPS GETs; no API keys are required for default
  usage. (NVD will optionally honour an API key passed in the environment for
  higher quotas; see the README.)
* The `github-token` input is only used for two things: `gh pr diff
  --name-only` to enumerate changed files, and `gh api` to upsert the sticky
  comment. No code is pushed, no webhooks are registered.

## Versioning

* `@v0.5.0` — pinned major+minor+patch. Recommended for production.
* `@v0` — latest 0.x. Use only if you can tolerate flag additions across
  minor versions.
* `@main` — bleeding edge. Do not use in production.

When v0.3 ships, the v0.2 line will continue to receive registry bug fixes
for at least 30 days after release.

## Roadmap

The CLI flags (`--changed-only`, `--fail-on`, `--paths`) are deliberately
platform-neutral. v0.3 will ship a thin GitLab CI component reusing the same
backend. SARIF output / GitHub code-scanning Security tab integration is out
of scope (see `mvp_plan.md` §6).
