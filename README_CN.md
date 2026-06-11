# auto-knowledge-base — 自动化网络资料采集与持续生长的本地知识库

[English version](README.md)

## 项目简介

`auto-knowledge-base` 将一个研究主题自动转化为结构化、可离线浏览的本地知识库。整个流程由 LLM 驱动：先对主题进行优化改写，生成精准的搜索关键词，随后采集排名靠前的网页结果，与库中已有内容去重，将每篇文章转换为规范的 Markdown 并附带 **LLM 生成的摘要**写入元数据，最后重建可离线浏览的 `index.html`。项目基于 **deepagents**、**LangChain** 与 **LangGraph** 构建。

**知识库没有"完成"的概念——它会持续生长。** 存储层为每个用户、每个知识库各分配一个独立文件夹，所有运行均为增量式：无论是次日、数周后，还是想到相关问题的任何时刻，只要针对同一组 `--user`/`--kb` 再次运行查询，就只会写入真正的新文章。去重机制分两级（来源 URL 与内容哈希，均持久化于 `_Metadata/` 元数据文件中），因此重复或交叉的查询不会产生任何冗余。

## 环境要求

- Python 3.11 及以上
- [`uv`](https://docs.astral.sh/uv/)（推荐的包管理工具）
- 实际采集时需要以下 API Key（仅运行测试时无需配置）：
  - `OPENAI_API_KEY` — 用于主题优化、关键词生成与摘要撰写，默认模型为 `gpt-4o-mini`
  - `TAVILY_API_KEY` — 用于网络搜索

## 安装

```bash
# 一条命令完成虚拟环境创建与全部依赖安装（含 pytest 等开发依赖）
uv sync

# 复制配置模板并填入 API Key
# .env 已被 git 忽略，程序启动时会自动加载
cp .env.sample .env
```

后续所有命令均通过 `uv run ...` 执行，无需手动激活虚拟环境。

## 使用方法

### 采集流水线（LangGraph）：建库并持续扩充

每次 `build` 都会执行一条确定性流程（主题优化 → 关键词生成 → 搜索 → 去重 → 摘要入库 → 重建索引），并始终作用于**同一个知识库目录**，因此可以一次次查询、逐步积累：

```bash
# 第一天：以初始主题建库
uv run auto-knowledge-base build \
  --user alice \
  --kb quantum-computing \
  --topic "quantum error correction" \
  --max-results 5
# => Saved 8 new article(s), skipped 0 duplicate(s).

# 第二天：同一知识库，换一个切入角度，仅新增内容会被写入
uv run auto-knowledge-base build \
  --user alice \
  --kb quantum-computing \
  --topic "surface codes and fault tolerance"
# => Saved 5 new article(s), skipped 3 duplicate(s).   <- 重叠部分自动跳过

# 数周后：重新检索最初的主题，补充最新进展
uv run auto-knowledge-base build \
  --user alice \
  --kb quantum-computing \
  --topic "quantum error correction 2026 advances"
# => Saved 2 new article(s), skipped 6 duplicate(s).
```

每次运行结束后，知识库内的 `README.md` 与 `index.html` 都会重建，呈现**历次累积**的全部内容——所有文章按分类汇总展示。已入库的内容不会被重复下载或重复存储：凡是 `_Metadata/` 中已记录的 URL 或内容哈希，一律自动跳过。

### 交互式深度智能体（deepagents）：对话式扩充

智能体是扩充既有知识库的另一种方式：它会先检视库中**已有的内容**，再规划补足空缺的搜索方案，仅保存附有摘要的新文章：

```bash
uv run auto-knowledge-base agent --user alice --kb quantum-computing
you> find recent surveys about surface codes
agent> Saved 4 new articles under "Surface Codes" ...
you> now add material about logical qubit demonstrations
agent> The kb already covers 2 of the top results; saved 3 new articles ...
```

### 导出流水线结构图

将 LangGraph 流水线的拓扑结构渲染为指定文件（无需任何 API Key）：

```bash
uv run auto-knowledge-base graph --output pipeline.png   # PNG 图片，经 mermaid.ink 渲染（需联网）
uv run auto-knowledge-base graph --output pipeline.mmd   # Mermaid 源码，完全离线
```

### 查看 LLM 的输入与输出

`build` 与 `agent` 均支持 `--debug` 参数，提供两种调试方式：

```bash
uv run auto-knowledge-base build ... --debug console    # 将每次 prompt 与响应直接打印到终端
uv run auto-knowledge-base build ... --debug langfuse   # 追踪数据发送至自托管的 Langfuse（LangSmith 的开源替代品）
```

Langfuse 可通过 Docker 在本地一键启动，每次运行在 Web 界面中呈现为一条完整
trace：各 LangGraph 节点、每次 LLM 调用的完整 prompt 与响应、Token 用量与耗时
一目了然。部署与使用指南见 [docs/llm-debugging.md](docs/llm-debugging.md)。

### 输出目录结构

```
kb_data/<user>/<kb>/
├── README.md            # AI 汇总的总览：主题、关键词范围、文章清单
├── index.html           # 双击即开的离线浏览器：目录树 / 搜索 / Markdown 预览
├── Articles/<分类>/<文章>.md
├── Attachments/         # 多媒体附件，与正文分开存放
├── Data/Raw/  Data/Processed/
└── _Metadata/<分类>/<文章>.json   # URL、内容哈希、标签、LLM 摘要等
```

直接在浏览器中打开 `kb_data/<user>/<kb>/index.html` 即可浏览——完全离线、不依赖任何 CDN，提供可折叠的分类目录树、搜索框与 Markdown 预览。

完整的目录规范——文件格式、`_Metadata/` 元数据 JSON 字段定义、面向 AI Agent 的查询方法以及可依赖的结构约定——详见 [docs/knowledge-base-structure.md](docs/knowledge-base-structure.md)。

### 配置

所有配置项均可写入 `.env`（参见 `.env.sample`）。已存在的环境变量优先于 `.env` 中的取值。

| 配置项 | 命令行参数 | 环境变量 | 默认值 |
| --- | --- | --- | --- |
| 存储根目录 | `--data-root` | `AUTO_KB_DATA_ROOT` | `./kb_data` |
| 模型 | `--model` | `AUTO_KB_MODEL` | `gpt-4o-mini` |
| OpenAI Key | — | `OPENAI_API_KEY` | 实际采集时必填 |
| Tavily Key | — | `TAVILY_API_KEY` | 实际采集时必填 |

## 测试

单元测试使用模拟的 LLM 与搜索客户端，无需联网，也无需配置 API Key。

```bash
uv run pytest                      # 运行全部测试
uv run pytest -v --tb=short       # 详细输出
uv run pytest tests/test_pipeline.py   # 运行单个文件
uv run pytest --cov=auto_knowledge_base --cov-report=term   # 统计覆盖率
```

当前共 48 个测试，覆盖率约 92%。重点覆盖的场景包括：

- 多用户目录隔离与路径穿越防护
- 增量运行下 URL 级与内容哈希级的双重去重
- 与文章一一对应的 `_Metadata/` 元数据文件及其 LLM 摘要
- LangGraph 流水线端到端运行（含二次运行时跳过全部重复项）
- 离线 `index.html` 生成（数据内嵌、无 CDN 依赖、`</script>` 转义）
- deepagents 工具链路（搜索 / 保存 / 列表 / 重建索引）
