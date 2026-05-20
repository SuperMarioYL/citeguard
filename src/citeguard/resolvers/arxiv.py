"""arXiv resolver — Atom-feed lookup by ID.

The arXiv API returns an Atom feed; a hit has at least one `<entry>`, a miss
returns a feed with zero entries (rather than a 404).  We parse with stdlib
ElementTree to avoid pulling in another dep.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from citeguard.models import Citation, VerifyResult

_BASE = "https://export.arxiv.org/api/query"
_NS = {"a": "http://www.w3.org/2005/Atom"}
_TIMEOUT_SEC = 10.0
_REGISTRY = "arxiv"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    r = await client.get(url, timeout=_TIMEOUT_SEC)
    if 500 <= r.status_code < 600:
        r.raise_for_status()
    return r


async def verify(client: httpx.AsyncClient, citation: Citation) -> VerifyResult:
    arxiv_id = citation.identifier
    url = f"{_BASE}?id_list={arxiv_id}&max_results=1"
    try:
        r = await _get(client, url)
    except Exception as exc:  # noqa: BLE001
        return VerifyResult(
            citation=citation, status="degraded", registry=_REGISTRY, note=str(exc)
        )

    if r.status_code != 200:
        return VerifyResult(
            citation=citation,
            status="degraded",
            registry=_REGISTRY,
            note=f"unexpected status {r.status_code}",
        )

    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as exc:
        return VerifyResult(
            citation=citation,
            status="degraded",
            registry=_REGISTRY,
            note=f"feed parse failure: {exc}",
        )

    entries = root.findall("a:entry", _NS)
    # arXiv returns one "error" entry for malformed IDs — treat that as miss.
    if not entries:
        return VerifyResult(citation=citation, status="miss", registry=_REGISTRY)

    first = entries[0]
    summary = (first.findtext("a:summary", default="", namespaces=_NS) or "").strip()
    if summary.lower().startswith("error: malformed"):
        return VerifyResult(citation=citation, status="miss", registry=_REGISTRY)

    return VerifyResult(
        citation=citation,
        status="hit",
        registry=_REGISTRY,
        evidence_url=f"https://arxiv.org/abs/{arxiv_id}",
    )
