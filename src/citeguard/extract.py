"""Deterministic extraction of citations from PDF / TeX / Markdown / plain text.

No LLM is involved (and none will be: see `mvp_plan.md` §6 out-of-scope).  We use
regexes targeting five identifier classes plus a fallback bibliography-entry
scrape for `.bib` and `\\bibitem` blocks.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from citeguard.models import Citation, ContextSpan


# Order matters for nothing in particular, but DOI must be matched before
# bare 10.xxx tokens get swallowed by some other pattern.  We anchor each one
# on tight boundaries so we don't pull substrings out of URLs unrelated to the
# claim being verified.
_DOI_RE = re.compile(
    r"""\b(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?      # optional prefix
        (10\.\d{4,9}/[-._;()/:A-Z0-9]+)                  # the DOI proper
        (?=[\s.,;)\]]|$)                                 # right boundary
    """,
    re.IGNORECASE | re.VERBOSE,
)

# arXiv has two historical formats: new YYMM.NNNNN (since 2007-04) and the
# legacy archive/0701001 form.  We accept both and normalise to the bare ID.
_ARXIV_NEW_RE = re.compile(
    r"""\barXiv:?\s*                                     # required prefix in modern usage
        (\d{4}\.\d{4,5})                                 # YYMM.NNNNN
        (v\d+)?                                          # optional version
        \b
    """,
    re.IGNORECASE | re.VERBOSE,
)
_ARXIV_NEW_URL_RE = re.compile(
    r"https?://arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(v\d+)?",
    re.IGNORECASE,
)
_ARXIV_OLD_RE = re.compile(
    r"\barXiv:?\s*([a-z\-]+(?:\.[A-Z]{2})?/\d{7})\b", re.IGNORECASE
)

_CVE_RE = re.compile(r"\b(CVE-\d{4}-\d{4,7})\b")

# A "commit" identifier is a 40-char hex SHA-1 with at least one preceding
# anchor (the word "commit", "sha", or a GitHub URL).  We refuse bare
# 40-hex tokens to avoid colliding with unrelated hashes.
_COMMIT_RE = re.compile(
    r"""(?:commit\s+|sha[:=]\s*|github\.com/[^/\s]+/[^/\s]+/commit/)
        ([0-9a-f]{40})
        \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# owner/repo#issue — accepts both the "shortcut" form and full URLs.
_GH_ISSUE_RE = re.compile(
    r"""(?:https?://github\.com/)?
        ([A-Za-z0-9][A-Za-z0-9._-]{0,38})                 # owner
        /
        ([A-Za-z0-9][A-Za-z0-9._-]{0,99})                 # repo
        (?:/(?:issues|pull)/|\#)
        (\d{1,7})                                          # issue or PR number
        \b
    """,
    re.VERBOSE,
)


def _read_pdf(path: Path) -> str:
    """Return concatenated text-layer contents of a PDF.

    Scans without OCR; PDFs without a text layer are out of scope (see plan §6).
    """
    from pypdf import PdfReader  # local import keeps non-PDF flows fast

    reader = PdfReader(str(path))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            # A single malformed page should not abort the document.
            continue
    return "\n".join(chunks)


def load_text(path: Path) -> str:
    """Dispatch on file suffix.  PDFs go through pypdf; everything else is read
    as UTF-8 (with replacement) since LaTeX / Markdown / bug-reports are text.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    return path.read_text(encoding="utf-8", errors="replace")


def _span_for(file: str, match: re.Match[str]) -> ContextSpan:
    return ContextSpan(file=file, start=match.start(), end=match.end())


def _dedupe(citations: Iterable[Citation]) -> list[Citation]:
    """Drop duplicates while preserving first-seen order.

    Two citations are equal iff `(kind, identifier)` match — see the
    `__eq__` override on :class:`Citation`.
    """
    seen: set[tuple[str, str]] = set()
    out: list[Citation] = []
    for c in citations:
        key = (c.kind, c.identifier)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def extract_citations(text: str, source: str = "<stdin>") -> list[Citation]:
    """Run all five matchers against `text` and return de-duped citations."""
    results: list[Citation] = []

    for m in _DOI_RE.finditer(text):
        identifier = m.group(1).rstrip(".,);]")
        results.append(
            Citation(
                raw_text=m.group(0),
                kind="doi",
                identifier=identifier.lower(),
                context_span=_span_for(source, m),
            )
        )

    # New-style arXiv: prefer the prefixed form, fall back to URL form.
    for m in _ARXIV_NEW_RE.finditer(text):
        results.append(
            Citation(
                raw_text=m.group(0),
                kind="arxiv",
                identifier=m.group(1),
                context_span=_span_for(source, m),
            )
        )
    for m in _ARXIV_NEW_URL_RE.finditer(text):
        results.append(
            Citation(
                raw_text=m.group(0),
                kind="arxiv",
                identifier=m.group(1),
                context_span=_span_for(source, m),
            )
        )
    for m in _ARXIV_OLD_RE.finditer(text):
        results.append(
            Citation(
                raw_text=m.group(0),
                kind="arxiv",
                identifier=m.group(1),
                context_span=_span_for(source, m),
            )
        )

    for m in _CVE_RE.finditer(text):
        results.append(
            Citation(
                raw_text=m.group(0),
                kind="cve",
                identifier=m.group(1).upper(),
                context_span=_span_for(source, m),
            )
        )

    for m in _COMMIT_RE.finditer(text):
        results.append(
            Citation(
                raw_text=m.group(0),
                kind="commit",
                identifier=m.group(1).lower(),
                context_span=_span_for(source, m),
            )
        )

    for m in _GH_ISSUE_RE.finditer(text):
        owner, repo, num = m.group(1), m.group(2), m.group(3)
        results.append(
            Citation(
                raw_text=m.group(0),
                kind="gh_issue",
                identifier=f"{owner}/{repo}#{num}",
                context_span=_span_for(source, m),
            )
        )

    return _dedupe(results)


def extract_from_path(path: Path) -> list[Citation]:
    """Convenience: read a path, extract citations, tag the source."""
    text = load_text(path)
    return extract_citations(text, source=str(path))
