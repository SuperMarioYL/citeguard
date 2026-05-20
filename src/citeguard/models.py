"""Stable contract between extraction and verification layers."""

from __future__ import annotations

from typing import Literal, Optional

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


class Citation(BaseModel):
    """A single identifier found in the source document.

    `raw_text` is preserved so the report can echo the exact sentence the author
    wrote; `identifier` is the registry-normalised form used for lookup.
    """

    raw_text: str
    kind: CitationKind
    identifier: str
    context_span: Optional[ContextSpan] = None

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
    evidence_url: Optional[str] = None
    nearest_matches: list[NearestMatch] = Field(default_factory=list)
    note: Optional[str] = None
