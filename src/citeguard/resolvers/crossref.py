"""Crossref resolver — authoritative DOI existence check.

Crossref is the issuing authority for most DOIs.  We use it as a confirming
second source when OpenAlex 404s: a DOI that exists on Crossref but not on
OpenAlex is a legitimate hit (OpenAlex backfill lag); a DOI absent from both
is a miss with high confidence.
"""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from citeguard.models import Citation, VerifyResult

_BASE = "https://api.crossref.org"
_TIMEOUT_SEC = 10.0
_REGISTRY = "crossref"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    r = await client.get(
        url,
        timeout=_TIMEOUT_SEC,
        headers={"User-Agent": "citeguard/0.1 (https://github.com/SuperMarioYL/citeguard)"},
    )
    if 500 <= r.status_code < 600:
        r.raise_for_status()
    return r


async def verify(client: httpx.AsyncClient, citation: Citation) -> VerifyResult:
    doi = citation.identifier
    try:
        r = await _get(client, f"{_BASE}/works/{doi}")
    except Exception as exc:  # noqa: BLE001
        return VerifyResult(citation=citation, status="degraded", registry=_REGISTRY, note=str(exc))

    if r.status_code == 200:
        return VerifyResult(
            citation=citation,
            status="hit",
            registry=_REGISTRY,
            evidence_url=f"https://doi.org/{doi}",
        )
    if r.status_code == 404:
        return VerifyResult(citation=citation, status="miss", registry=_REGISTRY)

    return VerifyResult(
        citation=citation,
        status="degraded",
        registry=_REGISTRY,
        note=f"unexpected status {r.status_code}",
    )
