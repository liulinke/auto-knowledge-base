# auto-knowledge-base — 自动采集网络资料，攒一个会生长的本地知识库

[English version](README.md)

## 这是什么

给它一个研究主题，剩下的它来：LLM 先把主题理顺、拆出几个搜索关键词，然后抓取排名靠前的网页，滤掉库里已有的内容，把每篇文章整理成干净的 Markdown 存好。摘要也由 LLM 代写，连同来源、标签一起放进每篇文章的 JSON 元数据里。最后生成一个 `index.html`，断网也能翻整个库。

基于 deepagents、LangChain 和 LangGraph。

重点在"攒"字上：知识库不是一次建完就结束的。每个用户、每个库各占一个文件夹，今天建好，过几天换个角度接着查，只有新文章会进来。去重有两道关，来源 URL 一道，内容 Hash 一道，记录都在 `_Metadata/` 里，所以查询范围重叠也不怕存重。

## 需要准备什么

- Python 3.11 以上
- [`uv`](https://docs.astral.sh/uv/)
- 两个 API Key（只跑测试的话不用）：
  - `OPENAI_API_KEY`：LLM 用，默认模型 `gpt-4o-mini`
  - `TAVILY_API_KEY`：搜索用

## 安装

```bash
# 建虚拟环境 + 装全部依赖（含 pytest 等开发工具），一步到位
uv sync

# 把样例配置复制一份，填入自己的 Key
# .env 不会进 git，程序启动时自动读取
cp .env.sample .env
```

之后所有命令都走 `uv run ...`，不用手动激活虚拟环境。

## 怎么用

### 流水线模式：建库，然后慢慢养

`build` 每次跑一遍固定流程：优化主题 → 生成关键词 → 搜索 → 去重 → 摘要入库 → 重建索引。库可以反复养：

```bash
# 第一天，建库
uv run auto-knowledge-base build \
  --user alice \
  --kb quantum-computing \
  --topic "quantum error correction" \
  --max-results 5
# => Saved 8 new article(s), skipped 0 duplicate(s).

# 第二天，换个角度再查。和昨天重复的 3 篇被自动跳过
uv run auto-knowledge-base build \
  --user alice \
  --kb quantum-computing \
  --topic "surface codes and fault tolerance"
# => Saved 5 new article(s), skipped 3 duplicate(s).

# 几周后，回头刷新最早的主题，看看有没有新文章
uv run auto-knowledge-base build \
  --user alice \
  --kb quantum-computing \
  --topic "quantum error correction 2026 advances"
# => Saved 2 new article(s), skipped 6 duplicate(s).
```

每跑完一次，库里的 `README.md` 和 `index.html` 都会重建，历次采集的文章按分类汇总在一起。入过库的东西不会再下载第二遍。

### Agent 模式：边聊边攒

不想自己琢磨关键词，就直接和 Agent 聊。它先看库里有什么，再决定搜什么，摘要写好才入库：

```bash
uv run auto-knowledge-base agent --user alice --kb quantum-computing
you> find recent surveys about surface codes
agent> Saved 4 new articles under "Surface Codes" ...
you> now add material about logical qubit demonstrations
agent> The kb already covers 2 of the top results; saved 3 new articles ...
```

### 库的结构

```
kb_data/<user>/<kb>/
├── README.md            # 全库总览：主题、关键词、文章清单
├── index.html           # 双击打开，离线浏览：目录树 / 搜索 / 预览
├── Articles/<分类>/<文章>.md
├── Attachments/         # 图片等多媒体，和正文分开放
├── Data/Raw/  Data/Processed/
└── _Metadata/<分类>/<文章>.json   # URL、Hash、标签、LLM 摘要
```

`index.html` 不依赖任何 CDN，断网照样能搜、能看。

### 配置

都可以写进 `.env`（参考 `.env.sample`）。环境变量里已有同名值时，以环境变量为准。

| 配置项 | 命令行参数 | 环境变量 | 默认值 |
| --- | --- | --- | --- |
| 存储根目录 | `--data-root` | `AUTO_KB_DATA_ROOT` | `./kb_data` |
| 模型 | `--model` | `AUTO_KB_MODEL` | `gpt-4o-mini` |
| OpenAI Key | 无 | `OPENAI_API_KEY` | 必填 |
| Tavily Key | 无 | `TAVILY_API_KEY` | 必填 |

## 测试

测试用假的 LLM 和搜索客户端，不联网、不花钱：

```bash
uv run pytest                      # 全部测试
uv run pytest -v --tb=short       # 详细输出
uv run pytest tests/test_pipeline.py   # 只跑一个文件
uv run pytest --cov=auto_knowledge_base --cov-report=term   # 看覆盖率
```

目前 42 个测试，覆盖率约 91%。重点盯这几件事：用户目录互相隔离、`../` 这类恶意路径会被清洗；两级去重在反复运行时真的生效；摘要确实写进了元数据；流水线端到端能跑通，第二次运行能把旧文章全部跳过；`index.html` 无外部依赖、`</script>` 已转义；Agent 的四个工具都落到存储层。
