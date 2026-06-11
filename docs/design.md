# 详细设计文档 — 自动化网络数据采集与本地知识库构建

> 对应需求文档：[requirements.md](./requirements.md)

## 1. 总体架构

系统由三层组成：

```
┌─────────────────────────────────────────────────────────┐
│  入口层  CLI (auto_knowledge_base/cli.py)                            │
│    build  → 确定性流水线（LangGraph）                     │
│    agent  → 交互式研究 Agent（deepagents）                │
├─────────────────────────────────────────────────────────┤
│  编排层                                                  │
│    pipeline.py   LangGraph StateGraph 六节点流水线        │
│    agent.py      deepagents create_deep_agent + 工具集    │
├─────────────────────────────────────────────────────────┤
│  能力层                                                  │
│    search.py     SearchClient 协议 + Tavily 实现          │
│    storage.py    多用户知识库存储 / 去重 / 侧边车元数据    │
│    indexer.py    README.md 与离线 index.html 生成器       │
│    models.py     Pydantic 数据模型                        │
│    utils.py      HTML→MD 转换、Hash、Slug 等纯函数        │
└─────────────────────────────────────────────────────────┘
```

设计原则：

* **依赖注入**：LLM（`BaseChatModel`）与搜索后端（`SearchClient`）均通过构造参数注入，单元测试用 Fake 实现替换，不依赖网络与 API Key。
* **存储即真相**：去重、增量构建均以磁盘上的 `_Metadata/` 侧边车文件为唯一事实来源，进程无内部状态，天然支持多次增量运行。
* **多用户物理隔离**：所有路径都由 `KnowledgeBaseStorage(data_root, user_id, kb_name)` 推导，不同用户/知识库互不可见。

## 2. 存储层设计（storage.py）

### 2.1 目录布局

```
<data_root>/
└── <user_id>/                       # 用户隔离目录
    └── <kb_name>/                   # 一个知识库一个文件夹
        ├── README.md                # AI 生成的全局总览（indexer 重建）
        ├── index.html               # 离线浏览入口（indexer 重建）
        ├── Articles/
        │   └── <Category>/<slug>.md # 按子主题分类的 Markdown 正文
        ├── Attachments/             # 多媒体资产（扁平）
        ├── Data/
        │   ├── Raw/                 # 原始抓取的结构化数据
        │   └── Processed/           # 清洗后的结构化数据
        └── _Metadata/
            └── <Category>/<slug>.json   # 与文章路径镜像的侧边车元数据
```

* `user_id` 与 `kb_name` 经过 `slugify` 清洗后才参与路径拼接，防止路径穿越。
* `_Metadata/` 与 `Articles/` 采用**镜像路径**（同分类目录、同文件名、仅扩展名不同），保证一一对应可被程序快速反查。

### 2.2 元数据模型（models.py）

```python
class ArticleMetadata(BaseModel):
    url: str                    # 来源 URL
    title: str                  # 文章标题
    content_hash: str           # 正文 MD5，用于内容级去重
    crawl_time: str             # ISO-8601 采集时间戳
    tags: list[str]             # LLM 生成的标签
    category: str               # LLM 归类的子主题（决定 Articles/ 下的子目录）
    summary: str                # LLM 生成的文章摘要（需求 5.2）
    source_keywords: list[str]  # 命中该文章的搜索关键词
    article_relpath: str        # 文章相对知识库根目录的路径
```

### 2.3 去重机制

两级去重，发生在不同阶段以尽量节省下载与 LLM 调用：

1. **URL 级**（搜索结果阶段）：`known_urls()` 扫描全部侧边车 JSON，已存在的 URL 直接丢弃，不下载。
2. **内容 Hash 级**（入库前）：正文转换为 Markdown 后计算 MD5，与 `known_hashes()` 比对，命中则跳过（同文不同址场景）。

## 3. 流水线设计（pipeline.py, LangGraph）

`StateGraph` 线性六节点，State 为 `TypedDict`：

```
optimize_topic → generate_keywords → search → dedupe → summarize_and_save → update_index
```

| 节点 | 输入 → 输出 | 说明 |
| --- | --- | --- |
| `optimize_topic` | `topic` → `optimized_topic` | LLM 优化、扩展用户原始主题（需求 2.1） |
| `generate_keywords` | `optimized_topic` → `keywords[]` | LLM 生成搜索关键词，每行一个，便于解析（需求 2.2） |
| `search` | `keywords[]` → `search_results[]` | 每个关键词调用 SearchClient，按 URL 合并结果（需求 2.3） |
| `dedupe` | `search_results[]` → 过滤后的 `search_results[]` | URL 级去重（需求 2.4） |
| `summarize_and_save` | `search_results[]` → `saved[]`, `skipped` | 取正文（搜索原文或 HTTP 抓取）→ Hash 去重 → LLM 单次调用产出摘要/分类/标签 → 写入文章 + 侧边车 |
| `update_index` | — | 重建 README.md 与 index.html（需求 2.6） |

### 3.1 单篇文章的 LLM 分析协议

为了便于测试与解析稳定性，不使用结构化输出 API，而约定纯文本行协议：

```
SUMMARY: <两三句话的摘要>
CATEGORY: <单个子主题名>
TAGS: <逗号分隔的标签>
```

解析失败时回退默认值（`category="General"`、`summary=正文截断`），保证流水线不因 LLM 输出格式波动而中断。

## 4. 交互式 Agent 设计（agent.py, deepagents）

`create_deep_agent`（deepagents ≥ 0.6）构建研究型 Agent，支持用户对同一知识库**持续追加查询**：

* **model**：注入的 `BaseChatModel`（生产环境为 `ChatOpenAI`，默认 `gpt-4o-mini`）。
* **tools**：
  * `internet_search(query)` — 调用 SearchClient 返回结果列表；
  * `save_article(url, title, markdown, summary, category, tags)` — 带 URL/Hash 去重的入库工具，复用 storage 层；
  * `list_saved_articles()` — 列出库内已有文章，供 Agent 规划增量方向；
  * `rebuild_index()` — 重建 README 与 index.html。
* **system_prompt**：约束 Agent 工作流（先查库内已有内容 → 搜索 → 摘要 → 入库 → 重建索引），并强制摘要由 LLM 生成后随文章一起保存。

deepagents 自带规划（todo）与子任务能力，适合"多轮搜索逐步覆盖一个主题"的长任务。

## 5. 离线入口设计（indexer.py）

### 5.1 README.md

由元数据汇总生成：主题、采集时间戳、关键词范围、分类统计表、全部文章清单（标题 + 摘要 + 相对链接）。

### 5.2 index.html

* **零外部依赖**：所有 CSS/JS 内联在单文件中，无 CDN 引用（需求 5.3）。
* **数据内嵌**：构建时把全部元数据与文章 Markdown 正文序列化为 JSON 内嵌进 `<script>` 标签——因为 `file://` 协议下浏览器禁止 `fetch()` 本地文件，内嵌是唯一可靠的全离线方案。JSON 中的 `</` 转义为 `<\/` 防止提前闭合标签。
* **动态目录树**：按 `category` 分组渲染可折叠树。
* **离线搜索**：对标题/摘要/标签/分类做子串匹配的轻量检索。
* **Markdown 预览**：内置约 60 行的迷你 Markdown 渲染器（标题/粗斜体/链接/图片/代码块/列表）。如需完整 CommonMark 支持，可把 `marked.min.js` 落盘到 `Attachments/_assets/` 并改为本地 `<script src>` 引用，仍满足离线要求。

## 6. 配置与入口（config.py / cli.py）

API Key 与配置统一从项目根目录的 `.env` 文件读取（模板见 `.env.sample`，`.env` 已被 git 忽略）；CLI 启动时通过 `load_env()`（python-dotenv）加载，**真实环境变量优先于 `.env` 文件值**，便于部署侧覆盖。

| 配置项 | 来源 | 默认值 |
| --- | --- | --- |
| `data_root` | `--data-root` / `AUTO_KB_DATA_ROOT` | `./kb_data` |
| `model` | `--model` / `AUTO_KB_MODEL` | `gpt-4o-mini`（OpenAI） |
| `OPENAI_API_KEY` | `.env` / 环境变量 | 必填（仅生产运行） |
| `TAVILY_API_KEY` | `.env` / 环境变量 | 必填（仅生产运行） |

CLI 命令：

```bash
auto-knowledge-base build --user alice --kb quantum-computing --topic "量子计算纠错" --max-results 5
auto-knowledge-base agent --user alice --kb quantum-computing        # 交互式 deepagents 模式
```

## 7. 测试策略

* 全部单元测试**不依赖网络与真实 API Key**：
  * LLM 用 `FakeListChatModel`（langchain-core 内置）按序回放预设响应；
  * 搜索用进程内 `FakeSearchClient`，返回带 `raw_content` 的固定结果。
* 覆盖点：
  * `utils`：slug、hash、HTML→Markdown 纯函数；
  * `storage`：目录初始化、镜像侧边车、URL/Hash 双级去重、多用户隔离；
  * `indexer`：README 与 index.html 内容断言（无 CDN、含内嵌索引）；
  * `pipeline`：端到端假数据跑通 + **二次运行验证增量去重**；
  * `agent`：deepagents 图构建成功。
* 运行方式：`uv run pytest`。
