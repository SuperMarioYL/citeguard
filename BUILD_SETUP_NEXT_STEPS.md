# Build setup — next steps

This file lists the manual steps to take CiteGuard from "scaffold on disk" to
"published on PyPI + GitHub" so contributors can `pipx install citeguard`.

## 1. Local smoke (5 minutes)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q              # also bootstraps tests/fixtures/sample_paper.pdf
ruff check src tests
citeguard tests/fixtures/withdrawn_paper.md   # expect a red-heavy table
```

The first `pytest` run materialises `tests/fixtures/sample_paper.pdf` via
`tests/conftest.py` (regenerable from `tests/fixtures/_build_pdf.py` — no
opaque binary is checked in).

## 2. Record the demo GIF + asciinema cast

Install [vhs](https://github.com/charmbracelet/vhs) once:

```bash
brew install vhs            # or: go install github.com/charmbracelet/vhs@latest
```

Then:

```bash
vhs assets/demo.tape
```

This drops `assets/demo.gif` and `assets/demo.cast` next to the tape.  Upload
the cast to [asciinema.org](https://asciinema.org/) and replace the
`asciinema.org/a/PLACEHOLDER` link in both READMEs with the real cast ID.

## 3. Push to GitHub

```bash
git init
git add .
git commit -m "feat: initial v0.1 release"
git branch -M main
git remote add origin git@github.com:SuperMarioYL/citeguard.git
git push -u origin main
```

CI on GitHub will run the lint + test matrix; the badges in the README expect
the repository to be at `SuperMarioYL/citeguard`.

After the push:

```bash
gh repo edit --add-topic citation-verification --add-topic peer-review \
             --add-topic cve --add-topic bibliography
```

## 4. Publish to PyPI

```bash
pip install build twine
python -m build
twine upload dist/*
```

`pipx install citeguard` becomes the install path documented in the README.

## 5. Launch checklist (mvp_plan §7)

- [ ] Schedule Show HN for Tue 08:00 ET.
- [ ] Cross-post r/MachineLearning with the 5-withdrawn-papers retro report.
- [ ] Push the bilingual README (English + Chinese — already in place).
- [ ] Send the three KOL pings from `go_to_market.md` §3 (one each, not group).

## 6. Cutting the v0.2.0 release

v0.2.0 ships the GitHub Action wrapper. After the v0.1 push lands, follow
these one-time setup steps before tagging v0.2.0:

### 6.1 PyPI trusted publishing (one-time)

`.github/workflows/release.yml` publishes via PyPI's *trusted publishing*
flow, so the repository never holds an API token. To enable it once:

1. Go to <https://pypi.org/manage/account/publishing/> while logged in as the
   owner of the `citeguard` PyPI project.
2. Add a *Pending Publisher* with:
   - PyPI project name: `citeguard`
   - Owner: `SuperMarioYL`
   - Repository name: `citeguard`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
3. In the GitHub repo, create an Environment named `pypi` under
   *Settings → Environments*. No secrets required.

### 6.2 Tag + publish

```bash
git tag -a v0.2.0 -m "v0.2.0 — GitHub Action wrapper"
git push origin v0.2.0
```

The `Release` workflow will: verify the tag matches `pyproject.toml`, build
the sdist + wheel, and publish to PyPI via trusted publishing.

### 6.3 Marketplace listing (free)

1. Create a GitHub release for the `v0.2.0` tag.
2. Check **Publish this Action to the GitHub Marketplace** in the release UI.
3. Pick a primary category (`Continuous integration`) and a secondary
   (`Code quality`).
4. Confirm the `action.yml` `branding` (icon `check-circle`, color `green`)
   is acceptable.

### 6.4 Real-world PR (launch hinge)

`go_to_market_v0.2.0.md` §2 lists three candidate OSS repositories to
target. Pick **one**, add `.github/workflows/citeguard.yml` (use the snippet
from `examples/citeguard-action.yml`), open a PR, and attach a screenshot of
the sticky comment on a synthetic PR in this repo. Merge → CI badge +
sticky comment self-traffic on every subsequent PR in the target repo.

### 6.5 Smoke-test the Action against this repo

Before tagging, sanity-check the composite action locally via
[act](https://github.com/nektos/act) on a draft PR:

```bash
act pull_request -W .github/workflows/example-pr.yml  # if you wire one up
```

The simpler check is to open a draft PR in the `citeguard` repo itself that
modifies one of the fixtures and observe that the Action sticky-comments on
its own PR.

## 7. Known follow-ups for v0.3

- GitLab CI component (the CLI flags are platform-neutral, so this is a
  thin wrapper around `citeguard --changed-only`).
- Optional LLM-based extraction as a `--strict` recall booster (off by
  default; deterministic regex remains the trust anchor).
- Windows binary packaging.

## 7.5 v0.3.0 — first-time contributor setup

`v0.3` adds a pre-release smoke gate (`m6_preflight_lint`).  Two minutes of
one-off setup for every new clone:

```bash
pip install -e ".[dev]"                    # picks up pre-commit>=3.7
pre-commit install --hook-type pre-push    # ruff runs once at git-push time
make help                                  # see all dev targets
make lint                                  # what CI + pre-push will run
```

Why pre-push and not pre-commit: editor saves and quick WIP commits stay
fast, but the gate fires exactly once at `git push` so a stale lint cannot
slip into a PR and force a same-day hotfix commit on `main` (the failure
mode that motivated this milestone — see CHANGELOG `[0.3.0]`).

The CI job `pin-actions-versions` enforces the same rule for GitHub Action
pins: any `actions/checkout@v[1-4]` or `actions/setup-python@v[1-5]` in a
real workflow fails the build.  The in-tree fixture
`.github/workflows/_fixture_stale_action.yml.example` documents what stale
pins look like and is exempted via a `:!*.example` git-grep pathspec.

## 8. Build-time caveats

- The PDF fixture (`tests/fixtures/sample_paper.pdf`) is generated at test
  collection time; the source script (`_build_pdf.py`) is the authoritative
  artifact.
- The `assets/demo.cast` and `assets/demo.gif` placeholders are populated on
  first `vhs` run — see step 2.
- The OpenAlex "nearest match" heuristic uses the DOI suffix as the seed
  query.  For DOIs whose suffix is a numeric hash (e.g. `10.1145/3460120.x`)
  the suggestion is empty by design — that's better than a false-positive
  candidate.
