"""Stable contract between extraction and verification layers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CitationKind = Literal["doi", "arxiv", "cve", "commit", "gh_issue", "bib_entry"]
"""The five identifier classes CiteGuard recognises plus a free-form bib entry."""

VerifyStatus = Literal["hit", "miss", "degraded"]
"""hit = registry confirms; miss = registry says it does not exist; degraded = timeout / rate-limit / unknown."""


class ContextSpan(BaseModel):
    """Where in the source file the citation was found."""

    file: str
    start: int
    end: int
    # 1-based line number, populated at extraction time so GitHub workflow-command
    # annotations can anchor inline annotations to the exact line (not just the
    # file).  Optional so callers that construct spans without source text (tests,
    # fixtures) keep working and annotations gracefully omit `line=` when absent.
    line: int | None = None


class Citation(BaseModel):
    """A single identifier found in the source document.

    `raw_text` is preserved so the report can echo the exact sentence the author
    wrote; `identifier` is the registry-normalised form used for lookup.
    """

    raw_text: str
    kind: CitationKind
    identifier: str
    context_span: ContextSpan | None = None

    def __hash__(self) -> int:
        return hash((self.kind, self.identifier))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Citation):
            return NotImplemented
        return self.kind == other.kind and self.identifier == other.identifier


class NearestMatch(BaseModel):
    """A registry candidate offered when an identifier misses."""

    title: str
    identifier: str
    distance: int = Field(ge=0)


class VerifyResult(BaseModel):
    """Output of running a single :class:`Citation` through one resolver."""

    citation: Citation
    status: VerifyStatus
    registry: str
    evidence_url: str | None = None
    nearest_matches: list[NearestMatch] = Field(default_factory=list)
    note: str | None = None
