"""NVD resolver — CVE existence check via NVD 2.0 JSON API.

NVD's unauthenticated rate limit is 5 requests / 30 s, which is plenty for
a single paper.  On miss we offer year-neighbour CVE suggestions: humans
mistype "CVE-2023-12345" as "CVE-2023-21345" routinely, and the year is the
single most reliable anchor in a fake CVE.
"""

from __future__ import annotations

import re

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from citeguard.models import Citation, NearestMatch, VerifyResult

_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_TIMEOUT_SEC = 15.0
_REGISTRY = "nvd"
_CVE_RE = re.compile(r"^CVE-(\d{4})-(\d{4,7})$")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1.0, max=6),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get(client: httpx.AsyncClient, url: str, params: dict) -> httpx.Response:
    r = await client.get(url, params=params, timeout=_TIMEOUT_SEC)
    # NVD uses 403 / 503 for rate-limit; treat as transient.
    if r.status_code in (403, 503) or 500 <= r.status_code < 600:
        r.raise_for_status()
    return r


async def verify(client: httpx.AsyncClient, citation: Citation) -> VerifyResult:
    cve = citation.identifier
    try:
        r = await _get(client, _BASE, {"cveId": cve})
    except Exception as exc:  # noqa: BLE001
        return VerifyResult(
            citation=citation, status="degraded", registry=_REGISTRY, note=str(exc)
        )

    if r.status_code == 404:
        return VerifyResult(
            citation=citation,
            status="miss",
            registry=_REGISTRY,
            nearest_matches=_year_neighbours(cve),
        )
    if r.status_code != 200:
        return VerifyResult(
            citation=citation,
            status="degraded",
            registry=_REGISTRY,
            note=f"unexpected status {r.status_code}",
        )

    data = r.json()
    if data.get("totalResults", 0) >= 1 and data.get("vulnerabilities"):
        return VerifyResult(
            citation=citation,
            status="hit",
            registry=_REGISTRY,
            evidence_url=f"https://nvd.nist.gov/vuln/detail/{cve}",
        )

    return VerifyResult(
        citation=citation,
        status="miss",
        registry=_REGISTRY,
        nearest_matches=_year_neighbours(cve),
    )


def _year_neighbours(cve: str) -> list[NearestMatch]:
    """Suggest 3 candidates that differ only in the trailing digit(s).

    These are hint candidates only — we do not call NVD again to verify
    them, because the goal is to suggest "did you mean…" not to chase a
    second round-trip.  Humans verify the suggestions in their browser.
    """
    m = _CVE_RE.match(cve)
    if not m:
        return []
    year, num = m.group(1), int(m.group(2))
    candidates: list[NearestMatch] = []
    for delta in (-1, 1, -10):
        n = num + delta
        if n <= 0:
            continue
        identifier = f"CVE-{year}-{n:04d}"
        candidates.append(
            NearestMatch(title=f"adjacent CVE for {year}", identifier=identifier, distance=abs(delta))
        )
    return candidates
