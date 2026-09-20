"""Write CiteGuard presentation content from the saved CLI record."""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
record = json.loads((ROOT / "docs/demo-results.json").read_text())
steps = record["steps"]
seed = json.loads((ROOT / "web/site.json").read_text())
example = next(
    item["text"] for item in record["inputs"] if item["path"] == "examples/identifiers.md"
)
install = "git clone https://github.com/SuperMarioYL/citeguard.git\ncd citeguard\npython3 -m venv .venv\nsource .venv/bin/activate\npython -m pip install -e ."
create_input = (
    "mkdir -p examples\ncat > examples/identifiers.md <<'CITEGUARD_INPUT'\n"
    + example
    + "CITEGUARD_INPUT"
)
network = "citeguard --json report.json --md report.md examples/identifiers.md"
ci = "printf '%s\\n' examples/identifiers.md > changed.txt\nciteguard --changed-only changed.txt --fail-on miss --max-misses 0 --summary-out summary.md"


def pair(zh, en):
    return {"zh": zh, "en": en}


def picture(name, alt):
    return f'''<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/{name}-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/{name}-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.svg">
  <img src="assets/{name}-light.svg" width="920" alt="{alt}">
</picture>'''


zh = """[English](README.en.md) | **简体中文**

HERO

**CiteGuard 从论文和问题报告中提取标识符，向对应 registry 查询，并把结果、证据链接和原文位置放到一起。**

`v0.8.0` · `Python ≥ 3.11` · `CLI + GitHub Action` · [Apache-2.0](LICENSE)

[用途](#用途) · [架构](#架构) · [安装](#安装) · [离线上手](#离线上手) · [联网核验](#联网核验与输出) · [CI](#接入-ci) · [配置](#配置) · [范围](#当前范围与后续方向)

## 用途

读到一个 DOI、arXiv ID 或 CVE 时，需要核对的不只是它看起来是否合理，还包括查询到了什么，以及它出现在原文哪里。CiteGuard 将这一步变成可以批量执行、保留记录的命令行流程，适合论文作者、评审人和处理问题报告的维护者。

核验结果回答标识符是否在相应 registry 中找到。它不判断论文是否支持某个论点，也不能仅凭一次 `miss` 认定作者编造了引用。格式、上下文和 registry 状态都值得继续检查。

## 架构

ARCHITECTURE

[抽取层](src/citeguard/extract.py) 读取文本层 PDF、TeX、Markdown 或纯文本，用确定性规则识别 DOI、arXiv、CVE、带前缀的 commit SHA 和 GitHub issue/PR 引用。`Citation` 保存原始匹配文本、规范化标识符、文件、字符区间和行号。

[CLI 编排](src/citeguard/cli.py) 将标识符交给对应 resolver，最多并发处理 8 条。DOI 先查 OpenAlex；只有它返回 `miss` 时才回退到 Crossref。Crossref 不可达时保留 `degraded`，不会把未经确认的缺失结果缓存下来。

[SQLite 缓存](src/citeguard/resolvers/__init__.py) 默认保留 7 天，`degraded` 不入缓存。缓存读写发生 SQLite 错误时，流程继续使用查询结果或重新查 registry。网络核验后的 `VerifyResult` 交给[报告层](src/citeguard/report.py)，生成终端表、JSON 和可选 Markdown。

## 安装

需要 Python 3.11 或更新版本；先用 `python3 --version` 检查环境。下面从源码安装：

```bash
INSTALL
```

安装依赖需要网络。抽取不调用模型或 registry；完整核验需要访问外部 registry。

## 离线上手

先创建一份完整输入。这里的标识符用于演示抽取，未在此示例中查询其存在性：

```bash
CREATE_INPUT
```

运行 v0.8.0 的实际可用调用形式：

```bash
EXTRACT
```

v0.8.0 的命令组会先解析顶层 `PATH`，所以这里把路径写在 `extract` 前后各一次。直接执行 `citeguard extract examples/identifiers.md` 会被误解析为未知子命令。上述调用进入现有抽取实现，无需改源码。

PROCESS

输出为 5 个去重后的 `Citation` 对象。arXiv 版本后缀被移除，重复的 arXiv ID 合并；每个对象保留匹配行号。实际标准输出为：

```json
EXTRACT_OUTPUT
```

另有两个可复制的边界示例：

| 输入 | 实际调用 | 本次输出 |
|---|---|---|
| [规范化示例](examples/normalized.tex) | `citeguard examples/normalized.tex extract examples/normalized.tex` | 2 个标识符；DOI 大小写与 arXiv 版本归一后去重 |
| [匹配边界示例](examples/boundaries.txt) | `citeguard examples/boundaries.txt extract examples/boundaries.txt` | DOI 与 GitHub issue；裸 40 位哈希未被当作 commit |

[完整输入、命令和输出](docs/demo-results.json) · [创建输入并重放的脚本](docs/demo.sh) · [文本记录](docs/demo-output.txt)

## 联网核验与输出

输入准备好后，完整核验使用顶层命令。选项放在输入路径前：

```bash
NETWORK
```

| 状态 | 含义 | 接下来查看什么 |
|---|---|---|
| `hit` | 查询的 registry 返回了对应记录 | `evidence_url` 与原文上下文 |
| `miss` | 查询路径未找到对应记录 | 标识符格式、registry 选择，以及可用的近似候选 |
| `degraded` | 超时、限流、缺少上下文等导致无法判定 | `note` 中的具体原因 |

OpenAlex 的 DOI 缺失路径可附最多 3 个近似候选；它们只是进一步核对的线索。裸 commit 即使带有 `commit` 前缀能被抽取，缺少 owner/repo 仍无法核验；请在原文提供完整 GitHub commit URL。

默认完整流程写入 `<input>.citeguard.json`。JSON 包含 `generator` 和 `results`；每条结果包含 `citation`、`status`、`registry`、可选 `evidence_url`、`nearest_matches` 和 `note`。离线 `extract` 只向标准输出打印 Citation 数组，不产生核验状态。

已有联网流程的[终端录像](assets/demo.gif)和 [VHS 录制脚本](docs/demo.tape)随文保留。registry 结果取决于查询时的外部状态；本节离线示例的输出由上面的实际命令记录定义。

## 能力与接入

INTEGRATIONS

| 内容 | 当前路径 | 责任边界 |
|---|---|---|
| DOI | OpenAlex，`miss` 时回退 Crossref | 查询登记记录，不判断文献论证质量 |
| arXiv | arXiv API | 抽取时规范化到不带版本后缀的 ID |
| CVE | NVD | 识别并查询 CVE，不分析漏洞是否影响你的系统 |
| GitHub commit、issue/PR | GitHub REST | commit 核验需要仓库上下文 |
| PDF、TeX、Markdown、纯文本 | 文本加载与正则抽取 | PDF 需要文本层；普通无标识符的书目不保证被抽取 |
| 自动化输出 | JSON、Markdown、GitHub Action | 下游决定阈值与人工复核流程 |

## 接入 CI

仓库提供 [GitHub composite Action](action.yml)，支持 changed-file 列表、job summary、sticky PR 评论和源行 annotation。完整配置见 [Action 说明](docs/github-action.md)和[工作流示例](examples/citeguard-action.yml)。本地也可以准备同样的 changed-file 输入：

```bash
CI_COMMAND
```

`--fail-on none` 只生成结果；`miss` 统计缺失；`degraded` 统计缺失与无法判定的合计。超过 `--max-misses` 才失败。CI 模式退出码为 `0`（阈值内）、`1`（超过阈值）、`2`（用法或 I/O 错误）。

v0.8.0 在有 `context_span.line` 时发出精确行号的 annotation。PDF 的行号来自提取出的文本，不是页面上的视觉坐标。PR 评论需要相应仓库写权限；GitHub Action 的接入不等于本次离线示例已经在托管 CI 中运行。

## 配置

| 选项 | 默认值 / 范围 | 用途 |
|---|---|---|
| `--json PATH` | 完整流程默认 `<input>.citeguard.json` | 指定 JSON 输出 |
| `--md PATH` | 不写 Markdown | 额外输出报告 |
| `--no-cache` | 使用缓存 | 绕过缓存，重新访问 registry；并非离线模式 |
| `--strict` | 关闭 | 顶层完整流程遇到 miss 时退出 1 |
| `--changed-only PATH` | 不启用 CI 模式 | 读取每行一个路径的文件列表 |
| `--fail-on` | `none` | CI 阈值类别：none / miss / degraded |
| `--max-misses N` | `0` | CI 容许数量 |
| `--paths` | `**/*.pdf,**/*.tex,**/*.md` | CI 文件过滤 |
| `--summary-out PATH` | 不输出 | 追加 Markdown job summary |
| `--annotations / --no-annotations` | CI 模式默认开启 | 控制 workflow-command annotation |
| `GITHUB_TOKEN` | 可选 | GitHub resolver 的认证 |

当前没有配置文件。默认缓存位于 `~/.cache/citeguard/registry.db`。按 `(kind, identifier)` 去重，输出顺序遵循各 matcher 的处理顺序，不保证与全文出现顺序一致。

## 当前范围与后续方向

v0.8.0 已有五类标识符抽取、registry resolver、缓存、报告、CI 阈值、GitHub Action，以及带行号的 annotation。当前实现没有 OCR、LLM 抽取、自动修正引用、全文论证判断或托管团队界面。GitLab CI component、可选 LLM fallback 和 Windows 分发仍属于后续方向，不作为已实现能力展示。

开发命令与依赖定义见 [pyproject.toml](pyproject.toml)。项目已有 resolver、缓存与 CI 契约测试，其中 mock 用于检验分支行为，不代表真实 registry 已确认某条引用。

## 许可证

[Apache-2.0](LICENSE) · [源码与问题反馈](https://github.com/SuperMarioYL/citeguard)
"""
en = """**English** | [简体中文](README.md)

HERO

**CiteGuard extracts identifiers from papers and issue reports, queries the relevant registries, and keeps each result with its evidence link and source location.**

`v0.8.0` · `Python ≥ 3.11` · `CLI + GitHub Action` · [Apache-2.0](LICENSE)

[Use cases](#use-cases) · [Architecture](#architecture) · [Install](#install) · [Offline quickstart](#offline-quickstart) · [Verification](#network-verification-and-output) · [CI](#ci-integration) · [Configuration](#configuration) · [Scope](#current-scope-and-next-directions)

## Use cases

When you encounter a DOI, arXiv ID or CVE, the useful questions include what the registry returns and where the identifier appears in the source. CiteGuard turns that check into a batchable command-line workflow with a saved record, for authors, reviewers and maintainers handling issue reports.

A verification result indicates whether the queried registry found the identifier. It does not establish whether a paper supports a claim, and a single `miss` does not prove that an author fabricated a reference. Formatting, context and registry availability can all warrant further inspection.

## Architecture

ARCHITECTURE

The [extractor](src/citeguard/extract.py) reads text-layer PDFs, TeX, Markdown and plain text. Deterministic patterns recognize DOIs, arXiv IDs, CVEs, anchored commit SHAs and GitHub issue/PR references. A `Citation` retains the raw match, normalized identifier, file, character span and line number.

The [CLI orchestrator](src/citeguard/cli.py) routes identifiers to their resolvers with at most eight concurrent checks. DOI lookup starts with OpenAlex and falls back to Crossref only on `miss`. If Crossref is unreachable, the result stays `degraded` rather than caching an unconfirmed absence.

The [SQLite cache](src/citeguard/resolvers/__init__.py) uses a seven-day TTL and does not store degraded results. SQLite read/write errors leave the lookup path available. The [report layer](src/citeguard/report.py) renders network `VerifyResult` objects as a terminal table, JSON and optional Markdown.

## Install

Requires Python 3.11 or newer. Check `python3 --version`, then install from source:

```bash
INSTALL
```

Installing dependencies needs network access. Extraction calls neither models nor registries; full verification needs external registry access.

## Offline quickstart

Create the complete input first. These illustrative identifiers are used to demonstrate extraction; their existence is not queried in this example:

```bash
CREATE_INPUT
```

Use this working v0.8.0 invocation:

```bash
EXTRACT
```

The v0.8.0 command group parses a top-level `PATH` before the subcommand, so the path appears both before and after `extract`. The shorter `citeguard extract examples/identifiers.md` is misparsed as an unknown subcommand. The invocation above reaches the existing extractor without changing source code.

PROCESS

The output contains five deduplicated `Citation` objects. arXiv version suffixes are removed and the repeated arXiv ID collapses to one object. Each object retains its matched line number. The actual standard output is:

```json
EXTRACT_OUTPUT
```

Two additional complete inputs cover normalization and matching boundaries:

| Input | Actual invocation | Output from this run |
|---|---|---|
| [Normalization example](examples/normalized.tex) | `citeguard examples/normalized.tex extract examples/normalized.tex` | Two identifiers after DOI case and arXiv version normalization |
| [Boundary example](examples/boundaries.txt) | `citeguard examples/boundaries.txt extract examples/boundaries.txt` | A DOI and a GitHub issue; the bare 40-character hash is not extracted as a commit |

[Complete inputs, commands and output](docs/demo-results.json) · [Input creation and replay script](docs/demo.sh) · [Text transcript](docs/demo-output.txt)

## Network verification and output

With the input prepared, use the top-level command for full verification. Put options before the input path:

```bash
NETWORK
```

| Status | Meaning | What to inspect next |
|---|---|---|
| `hit` | The queried registry returned a record | `evidence_url` and the source context |
| `miss` | The lookup path did not find a record | Identifier format, registry choice and any nearest candidates |
| `degraded` | A timeout, rate limit, missing context or other problem prevented a verdict | The specific reason in `note` |

The OpenAlex DOI miss path can include up to three nearest candidates as leads for review. An anchored bare commit can be extracted but still lacks the repository context required for verification; cite a complete GitHub commit URL in the source.

By default, the full workflow writes `<input>.citeguard.json`. The document contains `generator` and `results`; each result includes `citation`, `status`, `registry`, optional `evidence_url`, `nearest_matches` and `note`. Offline `extract` only prints a Citation array to standard output and does not produce verification statuses.

The existing [terminal recording](assets/demo.gif) and [VHS tape](docs/demo.tape) are retained for the network workflow. Registry results depend on external state at query time. The offline results in this section are defined by the recorded commands above.

## Capabilities and integration

INTEGRATIONS

| Content | Current route | Boundary |
|---|---|---|
| DOI | OpenAlex, then Crossref on miss | Checks registry records, not the quality of an argument |
| arXiv | arXiv API | Extraction normalizes IDs by removing version suffixes |
| CVE | NVD | Identifies and queries CVEs; it does not assess whether your system is affected |
| GitHub commits and issues/PRs | GitHub REST | Commit verification needs repository context |
| PDF, TeX, Markdown, plain text | Text loading and pattern extraction | PDFs need a text layer; free-form references without identifiers may not be extracted |
| Automation | JSON, Markdown, GitHub Action | Downstream users choose thresholds and review policy |

## CI integration

The repository supplies a [GitHub composite Action](action.yml) with changed-file input, job summaries, sticky PR comments and source-line annotations. See the [Action reference](docs/github-action.md) and [workflow example](examples/citeguard-action.yml). You can prepare the same input locally:

```bash
CI_COMMAND
```

`--fail-on none` reports only, `miss` counts missing results, and `degraded` counts both missing and inconclusive results. Failure occurs only above `--max-misses`. CI exit codes are `0` for a result within threshold, `1` for an exceeded threshold and `2` for usage or I/O errors.

v0.8.0 includes a line number in annotations when `context_span.line` is present. For PDFs, this is a line in extracted text, not a visual page coordinate. PR comments need suitable repository write permissions. The Action's implementation does not mean this offline example ran in hosted CI.

## Configuration

| Option | Default / scope | Purpose |
|---|---|---|
| `--json PATH` | Full workflow: `<input>.citeguard.json` | Select JSON output |
| `--md PATH` | No Markdown file | Add a report |
| `--no-cache` | Cache enabled | Query registries again; this is not an offline mode |
| `--strict` | Off | Exit 1 on a miss in the top-level full workflow |
| `--changed-only PATH` | CI mode off | Read one changed path per line |
| `--fail-on` | `none` | CI threshold class: none / miss / degraded |
| `--max-misses N` | `0` | CI tolerated count |
| `--paths` | `**/*.pdf,**/*.tex,**/*.md` | Filter CI files |
| `--summary-out PATH` | No summary file | Append a Markdown job summary |
| `--annotations / --no-annotations` | On in CI mode | Control workflow-command annotations |
| `GITHUB_TOKEN` | Optional | Authenticate GitHub resolver requests |

There is no configuration file. The default cache is `~/.cache/citeguard/registry.db`. Deduplication uses `(kind, identifier)`, and output follows matcher-pass order rather than necessarily following document order.

## Current scope and next directions

v0.8.0 implements five identifier types, registry resolvers, caching, reports, CI thresholds, a GitHub Action and line-aware annotations. The current implementation has no OCR, LLM extraction, automatic citation repair, full argument assessment or hosted team interface. GitLab CI components, an optional LLM fallback and Windows distribution remain future directions.

Development commands and dependencies are defined in [pyproject.toml](pyproject.toml). Existing tests exercise resolver, cache and CI contracts. Their mocked responses test branches; they are not evidence that a live registry confirmed a citation.

## License

[Apache-2.0](LICENSE) · [Source and issues](https://github.com/SuperMarioYL/citeguard)
"""
for name, body, alts in [
    (
        "README.md",
        zh,
        {
            "hero": "CiteGuard 引用括号盾牌与汇聚粒子：核验引用，保留证据。",
            "architecture": "离线抽取生成 Citation，联网 resolver 查询 registry，缓存和报告保留结果及原文上下文。",
            "process": "7 行输入抽取出 5 个唯一标识符，显示完整标识符与原文行号，未执行 registry 查询。",
            "integrations": "五类标识符的 registry 路由，以及文档输入、JSON、Markdown 和 GitHub Action 输出。",
        },
    ),
    (
        "README.en.md",
        en,
        {
            "hero": "CiteGuard citation shield and converging particles: check references, keep the evidence.",
            "architecture": "Offline extraction creates Citation objects; network resolvers query registries; caching and reports retain results and source context.",
            "process": "Seven input lines yield five unique identifiers with complete values and source line numbers, without registry queries.",
            "integrations": "Registry routes for five identifier types, document inputs, JSON and Markdown reports, and the GitHub Action.",
        },
    ),
]:
    for group in ["hero", "architecture", "process", "integrations"]:
        body = body.replace(group.upper(), picture(group, alts[group]))
    for marker, value in [
        ("INSTALL", install),
        ("CREATE_INPUT", create_input),
        ("EXTRACT_OUTPUT", steps[0]["output"].rstrip("\n")),
        ("EXTRACT", steps[0]["command"]),
        ("NETWORK", network),
        ("CI_COMMAND", ci),
    ]:
        body = body.replace(marker, value)
    (ROOT / name).write_text(body)

info = [
    (
        "混合标识符",
        "Mixed identifiers",
        "7 行输入得到 5 个唯一标识符；重复 arXiv 被合并，每个结果保留原文行号。",
        "Seven input lines yield five unique identifiers. Repeated arXiv references collapse, and source line numbers are retained.",
        "process",
    ),
    (
        "规范化与去重",
        "Normalize and deduplicate",
        "两个大小写不同的 DOI 合为一个；不同版本的 arXiv 也合为一个，共输出 2 条。",
        "DOIs differing only in case collapse, as do arXiv references with different versions: two objects remain.",
        "demo-normalized",
    ),
    (
        "匹配边界",
        "Respect matching boundaries",
        "DOI 的 #2 片段没有变成 GitHub issue；没有前缀的 40 位哈希未被抽取，结果是 DOI 和一个 issue。",
        "The DOI fragment #2 does not become a GitHub issue. The unanchored 40-character hash is excluded, leaving a DOI and one issue.",
        "demo-boundaries",
    ),
]
site = {
    "schema": 3,
    "name": "CiteGuard",
    "github": "https://github.com/SuperMarioYL/citeguard",
    "palette": seed.get("palette", "auto"),
    "lang": {"primary": "zh", "toggle": True},
    "meta": {
        "visual_profile": "neon-particle",
        "content_version": "0.8.0",
        "demo_source": "docs/demo-results.json",
    },
    "hero": {
        "eyebrow": pair(
            "引用核验 · 证据与原文位置", "REFERENCE CHECKS · EVIDENCE AND SOURCE CONTEXT"
        ),
        "headline": pair("核验引用，\n保留证据与出处", "Check references.\nKeep the evidence."),
        "sub": pair(
            "从论文和问题报告抽取 DOI、arXiv、CVE 和 GitHub 标识符，向对应 registry 查询，保留核验结果和原文位置。",
            "Extract DOI, arXiv, CVE and GitHub identifiers from papers and issue reports, query the appropriate registries, and retain results with source context.",
        ),
        "href": "#quickstart",
        "cta": pair("运行离线示例", "Run the offline example"),
        "ctaGithub": pair("查看源码", "View source"),
    },
    "scene": {
        "kind": "neon-graph",
        "caption": pair("从标识符回到原文", "FROM IDENTIFIER TO SOURCE"),
        "fallback": "/assets/scene-dark.svg",
        "fallbackLight": "/assets/scene-light.svg",
    },
    "advantages": [
        {
            "title": pair("先找出需要核对的内容", "Find what needs checking"),
            "body": pair(
                "确定性抽取五类标识符，保留匹配文本与行号，可先在本地检查输入。",
                "Deterministic extraction finds five identifier types and retains matched text and line numbers for local inspection.",
            ),
        },
        {
            "title": pair("结果附带可追溯证据", "Keep evidence with the result"),
            "body": pair(
                "联网结果区分 hit、miss 与 degraded，保存 evidence_url 或原因，方便回到原文复核。",
                "Network results distinguish hit, miss and degraded, with evidence URLs or notes to support source review.",
            ),
        },
        {
            "title": pair("把核验接进已有流程", "Fit checks into your workflow"),
            "body": pair(
                "终端、JSON 和 Markdown 报告服务本地使用；GitHub Action 支持 changed files、summary 和 annotation。",
                "Terminal, JSON and Markdown reports serve local workflows; the GitHub Action supports changed files, summaries and annotations.",
            ),
        },
    ],
    "story": {
        "intro": {
            "title": pair(
                "一个看似可信的编号，\n还需要一次有出处的核对。",
                "A plausible identifier\nstill needs a traceable check.",
            ),
            "body": pair(
                "论文和问题报告中的引用可能包含笔误、缺少上下文，或遇到不可用的 registry。CiteGuard 把抽取、查询和定位放进同一个流程，让你知道找到了什么，也知道哪些结果仍需人工检查。",
                "References in papers and issue reports can have typos, missing context or unavailable registries. CiteGuard combines extraction, lookup and source location so you can inspect what was found and what still needs review.",
            ),
        },
        "sections": [
            {
                "title": pair(
                    "抽取标识符，保留原文位置", "Extract identifiers with source locations"
                ),
                "body": pair(
                    "先运行无需网络的 extract。示例中的重复 arXiv 合并为一个 ID，Citation 保留规范化值、原始匹配和原文行号。抽取本身不代表引用已被核验。",
                    "Start with network-free extraction. Repeated arXiv references collapse to one ID while Citation retains the normalized value, raw match and line number. Extraction is not verification.",
                ),
                "image": {
                    "light": "/assets/process-light.svg",
                    "dark": "/assets/process-dark.svg",
                    "alt": pair(
                        "离线示例的 5 个唯一标识符及行号。",
                        "Five unique identifiers and line numbers from the offline example.",
                    ),
                    "mobile": {
                        "light": "/assets/process-mobile-light.svg",
                        "dark": "/assets/process-mobile-dark.svg",
                    },
                },
            },
            {
                "title": pair("联网查询与本地状态各司其职", "Separate lookup from local state"),
                "body": pair(
                    "DOI 查询在 OpenAlex miss 后才回退 Crossref；缓存保留 7 天且不缓存 degraded。网络错误保留无法判定的状态，报告展示证据链接或原因。",
                    "DOI checks fall back to Crossref only after an OpenAlex miss. Cache entries last seven days and exclude degraded results. Network problems remain inconclusive, with evidence links or reasons in reports.",
                ),
                "image": {
                    "light": "/assets/architecture-light.svg",
                    "dark": "/assets/architecture-dark.svg",
                    "alt": pair(
                        "抽取、registry resolver、缓存与报告的数据路径。",
                        "Data paths through extraction, registry resolvers, cache and reports.",
                    ),
                    "mobile": {
                        "light": "/assets/architecture-mobile-light.svg",
                        "dark": "/assets/architecture-mobile-dark.svg",
                    },
                },
            },
            {
                "title": pair("按标识符类型选择核验路径", "Choose the route by identifier type"),
                "body": pair(
                    "五类标识符对应 OpenAlex、Crossref、arXiv、NVD 和 GitHub；文档与 CI 侧共用 Citation 和 VerifyResult。",
                    "The five identifier types route to OpenAlex, Crossref, arXiv, NVD and GitHub. Document and CI workflows share Citation and VerifyResult objects.",
                ),
                "image": {
                    "light": "/assets/integrations-light.svg",
                    "dark": "/assets/integrations-dark.svg",
                    "alt": pair(
                        "标识符类型、registry 路由与输出接入。",
                        "Identifier types, registry routes and output integrations.",
                    ),
                    "mobile": {
                        "light": "/assets/integrations-mobile-light.svg",
                        "dark": "/assets/integrations-mobile-dark.svg",
                    },
                },
            },
        ],
        "details": [
            {
                "title": pair("v0.8.0 的 extract 调用形式", "The v0.8.0 extract invocation"),
                "body": pair(
                    "当前命令组会先吃掉一个顶层 PATH，再解析 extract 子命令。离线示例把同一路径写在两处；普通 citeguard extract PATH 会被误解析。",
                    "The command group consumes a top-level PATH before parsing extract. The offline example supplies that path twice; the shorter citeguard extract PATH form is misparsed.",
                ),
                "code": steps[0]["command"],
            },
            {
                "title": pair("联网核验的输出", "Output from network verification"),
                "body": pair(
                    "默认写入 <input>.citeguard.json，可选择额外 Markdown。hit 表示 registry 返回记录，miss 表示未找到，degraded 表示无法判定。",
                    "The default output is <input>.citeguard.json, with optional Markdown. hit means a registry record was found, miss means it was not found, and degraded means no verdict was available.",
                ),
                "code": network,
            },
            {
                "title": pair("CI 阈值和原文行号", "CI thresholds and source lines"),
                "body": pair(
                    "changed-only 模式支持 none、miss 和 degraded 三类阈值，以及容许数量。v0.8.0 在有行号时输出对应 annotation；退出码区分通过、超限与用法错误。",
                    "Changed-only mode supports none, miss and degraded thresholds plus a tolerated count. v0.8.0 emits line-aware annotations when available, with separate exit codes for pass, threshold failure and usage errors.",
                ),
                "code": ci,
            },
        ],
    },
    "demo": {
        "title": pair("三个离线输入，查看原始 CLI 输出", "Three offline inputs, actual CLI output"),
        "note": pair(
            "以下为 CiteGuard v0.8.0 的实际抽取结果：5、2、2 个标识符。输入是可复制的示例文本；没有查询 registry，也没有用 mock 生成核验状态。",
            "These are actual CiteGuard v0.8.0 extraction outputs: five, two and two identifiers. Inputs are reproducible example text. No registries were queried and no mock verification statuses were produced.",
        ),
        "source": "/assets/demo-results.json",
        "steps": [
            {
                "label": pair(a, b),
                "body": pair(c, d),
                "image": f"/assets/{name}-light.svg",
                "imageDark": f"/assets/{name}-dark.svg",
                "command": step["command"],
                "output": step["output"],
            }
            for (a, b, c, d, name), step in zip(info, steps, strict=False)
        ],
    },
    "quickstart": {
        "title": pair("从完整输入开始", "Start with complete input"),
        "body": pair(
            "需要 Python 3.11+。安装需要网络，随后只执行本地抽取。该调用形式包含 v0.8.0 所需的顶层 PATH。",
            "Requires Python 3.11+. Installation needs network access; the following extraction is local. The invocation includes the top-level PATH required by v0.8.0.",
        ),
        "steps": [
            {"title": pair("从源码安装", "Install from source"), "code": install},
            {"title": pair("创建演示输入", "Create the demo input"), "code": create_input},
            {
                "title": pair("提取标识符与行号", "Extract identifiers and line numbers"),
                "code": steps[0]["command"],
            },
        ],
    },
    "limitations": [
        pair(
            "抽取到标识符不等于 registry 确认存在；核验也不判断论文是否支持某个论点。",
            "Extracting an identifier does not confirm its existence. Verification does not assess whether a paper supports a claim.",
        ),
        pair(
            "PDF 需要文本层；当前没有 OCR 或 LLM 抽取，普通无标识符书目不保证被识别。",
            "PDFs need a text layer. There is no OCR or LLM extraction, and free-form references without identifiers may not be recognized.",
        ),
        pair(
            "GitHub commit 核验需要 owner/repo；网络超时或缺少上下文会导致 degraded。",
            "GitHub commit verification needs owner/repo context; timeouts or missing context can yield degraded.",
        ),
    ],
    "footer": {
        "tag": pair("v0.8.0 · Python 3.11+ · Apache-2.0", "v0.8.0 · Python 3.11+ · Apache-2.0")
    },
}
# `host` (custom-domain) and `palette` are deployment-side keys: carry them over
# from the current site.json instead of hardcoding them here.
if seed.get("host"):
    site["host"] = seed["host"]
(ROOT / "web/site.json").write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n")
shutil.copy2(ROOT / "docs/demo-results.json", ROOT / "web/assets/demo-results.json")
print("Wrote full bilingual CiteGuard content and three exact public demo steps.")
