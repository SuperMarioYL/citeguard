"""GitHub REST resolver — commit + issue/PR existence checks.

We do not require a token: unauthenticated GitHub REST gives 60 req/h per IP,
which is enough for a typical paper.  When `GITHUB_TOKEN` is set in the
environment we use it to lift the limit to 5000/h.
"""

from __future__ import annotations

import os

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from citeguard.models import Citation, VerifyResult

_BASE = "https://api.github.com"
_TIMEOUT_SEC = 10.0
_REGISTRY = "github"


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "citeguard/0.1",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    r = await client.get(url, headers=_headers(), timeout=_TIMEOUT_SEC)
    if r.status_code == 403 or 500 <= r.status_code < 600:
        # 403 here is usually secondary rate-limit; retry with backoff.
        r.raise_for_status()
    return r


async def verify(client: httpx.AsyncClient, citation: Citation) -> VerifyResult:
    """Dispatch on `kind`: commit SHA hits `/repos/.../commits/{sha}`, issue
    references hit `/repos/.../issues/{n}` (which also returns PRs).

    Commit verification is best-effort: without an `owner/repo` context the
    bare SHA is ambiguous, so commits extracted without a URL context are
    flagged degraded with a clear note.
    """
    cid = citation.identifier
    if citation.kind == "commit":
        return await _verify_commit(client, citation, cid)
    if citation.kind == "gh_issue":
        return await _verify_issue(client, citation, cid)
    return VerifyResult(
        citation=citation,
        status="degraded",
        registry=_REGISTRY,
        note=f"github resolver received unexpected kind {citation.kind!r}",
    )


async def _verify_commit(
    client: httpx.AsyncClient, citation: Citation, sha: str
) -> VerifyResult:
    # A bare 40-hex string cannot be resolved without a repo, and the
    # extractor only keeps SHAs that appear near a github.com/<owner>/<repo>
    # URL or the words "commit"/"sha".  The url-form case carries enough
    # context for us to peel out owner/repo from the raw_text.
    raw = citation.raw_text
    if "github.com/" in raw:
        # raw_text like: "github.com/owner/repo/commit/<sha>"
        try:
            after = raw.split("github.com/", 1)[1]
            owner, repo, _ = after.split("/", 2)
            url = f"{_BASE}/repos/{owner}/{repo}/commits/{sha}"
            r = await _get(client, url)
        except Exception as exc:  # noqa: BLE001
            return VerifyResult(
                citation=citation, status="degraded", registry=_REGISTRY, note=str(exc)
            )
        if r.status_code == 200:
            return VerifyResult(
                citation=citation,
                status="hit",
                registry=_REGISTRY,
                evidence_url=f"https://github.com/{owner}/{repo}/commit/{sha}",
            )
        if r.status_code in (404, 422):
            return VerifyResult(citation=citation, status="miss", registry=_REGISTRY)
        return VerifyResult(
            citation=citation,
            status="degraded",
            registry=_REGISTRY,
            note=f"unexpected status {r.status_code}",
        )
    return VerifyResult(
        citation=citation,
        status="degraded",
        registry=_REGISTRY,
        note="commit SHA without owner/repo context; cite as github.com/<owner>/<repo>/commit/<sha>",
    )


async def _verify_issue(
    client: httpx.AsyncClient, citation: Citation, ident: str
) -> VerifyResult:
    # ident format: "owner/repo#123"
    repo, _, num = ident.rpartition("#")
    owner, _, repo_name = repo.partition("/")
    if not (owner and repo_name and num.isdigit()):
        return VerifyResult(
            citation=citation,
            status="degraded",
            registry=_REGISTRY,
            note=f"malformed identifier {ident!r}",
        )
    url = f"{_BASE}/repos/{owner}/{repo_name}/issues/{num}"
    try:
        r = await _get(client, url)
    except Exception as exc:  # noqa: BLE001
        return VerifyResult(
            citation=citation, status="degraded", registry=_REGISTRY, note=str(exc)
        )
    if r.status_code == 200:
        return VerifyResult(
            citation=citation,
            status="hit",
            registry=_REGISTRY,
            evidence_url=f"https://github.com/{owner}/{repo_name}/issues/{num}",
        )
    if r.status_code == 404:
        return VerifyResult(citation=citation, status="miss", registry=_REGISTRY)
    return VerifyResult(
        citation=citation,
        status="degraded",
        registry=_REGISTRY,
        note=f"unexpected status {r.status_code}",
    )
