#!/usr/bin/env bash
set -euo pipefail
mkdir -p examples
cat > examples/boundaries.txt <<'CITEGUARD_INPUT'
DOI fragment: https://doi.org/10.1145/3460120#2
Bare digest: 0123456789abcdef0123456789abcdef01234567
Linked issue: https://github.com/example/project/issues/42
CITEGUARD_INPUT
cat > examples/identifiers.md <<'CITEGUARD_INPUT'
Research note
DOI: 10.1145/3460120.
arXiv:1706.03762v2
CVE-2024-3094
commit 0123456789abcdef0123456789abcdef01234567
https://github.com/example/project/issues/42
Repeat: arXiv:1706.03762
CITEGUARD_INPUT
cat > examples/normalized.tex <<'CITEGUARD_INPUT'
\section{References}
\noindent DOI: 10.1000/EXAMPLE.
\noindent DOI: 10.1000/example.
See https://arxiv.org/abs/1706.03762v3.
See arXiv:1706.03762v2.
CITEGUARD_INPUT
# v0.8.0 requires the leading top-level PATH before the extract subcommand.
citeguard examples/identifiers.md extract examples/identifiers.md
citeguard examples/normalized.tex extract examples/normalized.tex
citeguard examples/boundaries.txt extract examples/boundaries.txt
