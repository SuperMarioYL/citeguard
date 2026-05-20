# 3 lines using CiteGuard

```bash
pipx install citeguard
citeguard paper.pdf
cat paper.pdf.citeguard.json | jq '.results[] | select(.status=="miss")'
```

That's the whole loop: extract identifiers, fan out across OpenAlex / Crossref
/ arXiv / NVD / GitHub, render a red-green table, and drop a JSON sidecar for
your downstream scripts.

## CI usage (GitHub Action shape, planned for v0.2)

```yaml
- run: pipx install citeguard
- run: citeguard --strict bug_report.md
```

`--strict` exits 1 if any citation comes back `miss` — perfect for failing
a PR before a maintainer reads it.
