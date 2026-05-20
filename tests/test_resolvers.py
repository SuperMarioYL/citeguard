"""Resolver-layer tests.

We avoid hitting real registries from CI — instead each resolver is exercised
via httpx's transport-mocking so we can assert their hit / miss / degraded
contract deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from citeguard.extract import extract_citations, extract_from_path
from citeguard.models import Citation, NearestMatch, VerifyResult
from citeguard.report import to_json, to_markdown
from citeguard.resolvers import RegistryCache
from citeguard.resolvers import arxiv as arxiv_resolver
from citeguard.resolvers import crossref as crossref_resolver
from citeguard.resolvers import github as github_resolver
from citeguard.resolvers import nvd as nvd_resolver
from citeguard.resolvers import openalex as openalex_resolver

FIXTURES = Path(__file__).parent / "fixtures"


# ---------- m1: extraction -------------------------------------------------


def test_extract_finds_all_kinds_in_markdown():
    citations = extract_from_path(FIXTURES / "withdrawn_paper.md")
    kinds = {c.kind for c in citations}
    assert {"arxiv", "doi", "cve", "commit"}.issubset(kinds)
    by_kind = {c.kind: c.identifier for c in citations}
    assert by_kind["arxiv"] == "9999.00001"
    assert by_kind["cve"] == "CVE-9999-99999"
    assert by_kind["doi"].startswith("10.9999/")


def test_extract_handles_tex_fixture():
    citations = extract_from_path(FIXTURES / "clean_paper.tex")
    arxiv_ids = sorted(c.identifier for c in citations if c.kind == "arxiv")
    assert arxiv_ids == ["1409.3215", "1706.03762"]
    assert any(c.kind == "gh_issue" and c.identifier == "curl/curl#12604" for c in citations)


def test_extract_reads_pdf_text_layer():
    citations = extract_from_path(FIXTURES / "sample_paper.pdf")
    kinds = {c.kind for c in citations}
    assert {"arxiv", "doi", "cve"}.issubset(kinds)


def test_extract_dedupes_repeated_identifiers():
    text = "See arXiv:2401.12345. Again arXiv:2401.12345. Once more arXiv:2401.12345."
    citations = extract_citations(text)
    assert len(citations) == 1


def test_extract_refuses_bare_40_hex():
    # A bare SHA without `commit ` / `sha:` / URL context must NOT be picked up.
    text = "Hash digest 0123456789abcdef0123456789abcdef01234567 is not a citation."
    citations = extract_citations(text)
    assert all(c.kind != "commit" for c in citations)


# ---------- m2: resolvers (mocked transports) ------------------------------


def _mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


@pytest.mark.asyncio
async def test_openalex_hit_returns_evidence_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/works/doi:10.1145/" in str(request.url)
        return httpx.Response(200, json={"id": "https://openalex.org/W1234567"})

    citation = Citation(raw_text="doi:10.1145/foo", kind="doi", identifier="10.1145/foo")
    async with _mock_client(handler) as client:
        result = await openalex_resolver.verify(client, citation)
    assert result.status == "hit"
    assert result.evidence_url == "https://openalex.org/W1234567"


@pytest.mark.asyncio
async def test_openalex_miss_returns_nearest_matches():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/works/doi:" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Roughly Similar Paper",
                        "doi": "https://doi.org/10.1/similar",
                        "id": "x",
                    },
                    {
                        "title": "Another Candidate",
                        "doi": "https://doi.org/10.1/another",
                        "id": "y",
                    },
                ]
            },
        )

    citation = Citation(
        raw_text="doi:10.9999/not-real-fake-12345",
        kind="doi",
        identifier="10.9999/not-real-fake-12345",
    )
    async with _mock_client(handler) as client:
        result = await openalex_resolver.verify(client, citation)
    assert result.status == "miss"
    assert len(result.nearest_matches) >= 1


@pytest.mark.asyncio
async def test_crossref_hit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"DOI": "10.1145/foo"}})

    citation = Citation(raw_text="doi:10.1145/foo", kind="doi", identifier="10.1145/foo")
    async with _mock_client(handler) as client:
        result = await crossref_resolver.verify(client, citation)
    assert result.status == "hit"
    assert result.evidence_url == "https://doi.org/10.1145/foo"


@pytest.mark.asyncio
async def test_arxiv_miss_when_feed_empty():
    feed = '<?xml version="1.0"?>\n<feed xmlns="http://www.w3.org/2005/Atom"></feed>'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=feed)

    citation = Citation(raw_text="arXiv:9999.00001", kind="arxiv", identifier="9999.00001")
    async with _mock_client(handler) as client:
        result = await arxiv_resolver.verify(client, citation)
    assert result.status == "miss"


@pytest.mark.asyncio
async def test_arxiv_hit_when_entry_present():
    feed = (
        '<?xml version="1.0"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<entry><summary>Real abstract</summary></entry>"
        "</feed>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=feed)

    citation = Citation(raw_text="arXiv:1706.03762", kind="arxiv", identifier="1706.03762")
    async with _mock_client(handler) as client:
        result = await arxiv_resolver.verify(client, citation)
    assert result.status == "hit"
    assert result.evidence_url and "1706.03762" in result.evidence_url


@pytest.mark.asyncio
async def test_nvd_miss_offers_year_neighbours():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"totalResults": 0, "vulnerabilities": []})

    citation = Citation(raw_text="CVE-2099-12345", kind="cve", identifier="CVE-2099-12345")
    async with _mock_client(handler) as client:
        result = await nvd_resolver.verify(client, citation)
    assert result.status == "miss"
    assert any(m.identifier.startswith("CVE-2099-") for m in result.nearest_matches)


@pytest.mark.asyncio
async def test_github_commit_with_repo_context_hits():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/repos/foo/bar/commits/" in str(request.url):
            return httpx.Response(200, json={"sha": "abcdef" + "0" * 34})
        return httpx.Response(404)

    citation = Citation(
        raw_text="github.com/foo/bar/commit/abcdef" + "0" * 34,
        kind="commit",
        identifier="abcdef" + "0" * 34,
    )
    async with _mock_client(handler) as client:
        result = await github_resolver.verify(client, citation)
    assert result.status == "hit"


@pytest.mark.asyncio
async def test_github_issue_miss():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    citation = Citation(
        raw_text="curl/curl#999999",
        kind="gh_issue",
        identifier="curl/curl#999999",
    )
    async with _mock_client(handler) as client:
        result = await github_resolver.verify(client, citation)
    assert result.status == "miss"


# ---------- m2: cache layer ------------------------------------------------


def test_cache_round_trip(tmp_path):
    cache = RegistryCache(path=tmp_path / "cache.db", ttl_seconds=3600)
    citation = Citation(raw_text="arXiv:2401.12345", kind="arxiv", identifier="2401.12345")
    result = VerifyResult(citation=citation, status="hit", registry="arxiv", evidence_url="x")
    cache.put(result)
    fetched = cache.get("arxiv", "2401.12345")
    assert fetched is not None
    assert fetched.status == "hit"


def test_cache_does_not_persist_degraded(tmp_path):
    cache = RegistryCache(path=tmp_path / "cache.db")
    citation = Citation(raw_text="x", kind="arxiv", identifier="9999.99999")
    cache.put(VerifyResult(citation=citation, status="degraded", registry="arxiv", note="timeout"))
    assert cache.get("arxiv", "9999.99999") is None


# ---------- m3: report rendering ------------------------------------------


def test_to_json_round_trips_results():
    citation = Citation(raw_text="x", kind="doi", identifier="10.1/x")
    payload = to_json(
        [
            VerifyResult(citation=citation, status="hit", registry="openalex", evidence_url="u"),
            VerifyResult(
                citation=Citation(raw_text="y", kind="cve", identifier="CVE-2024-1"),
                status="miss",
                registry="nvd",
                nearest_matches=[
                    NearestMatch(title="adjacent", identifier="CVE-2024-2", distance=1)
                ],
            ),
        ]
    )
    parsed = json.loads(payload)
    assert parsed["generator"].startswith("citeguard/")
    assert len(parsed["results"]) == 2
    assert parsed["results"][1]["nearest_matches"][0]["identifier"] == "CVE-2024-2"


def test_to_markdown_includes_status_glyphs():
    citation = Citation(raw_text="x", kind="doi", identifier="10.1/x")
    md = to_markdown(
        [
            VerifyResult(citation=citation, status="hit", registry="openalex", evidence_url="u"),
        ]
    )
    assert "✓" in md
    assert "openalex" in md
    assert "1 hit · 0 miss · 0 degraded" in md
