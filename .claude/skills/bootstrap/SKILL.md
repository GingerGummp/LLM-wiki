---
name: bootstrap
description: 一键从云文档知识库（kBase / Notion / Lark / Confluence 等）批量初始化 LLM-Wiki。输入云文档父链接，skill 自动遍历整棵文档树，下载所有页面到 raw/，并按 LLM-Wiki schema 编译进 wiki/。适用于「我已经有云端个人知识库，想一键迁移到本地」场景。当用户输入 /bootstrap、/init-from-docs、/migrate 或要求"从云文档批量导入"、"初始化知识库"、"迁移我的 Notion / Docs"时调用。
user-invocable: true
---

# bootstrap 技能

## 角色

LLM-Wiki 首次启动迁移助手。把用户已有的云端知识库一键搬到本地，省掉「从零喂资料」的冷启动成本。

## 触发

- `/bootstrap <kBase 父链接>` — 标准用法
- `/bootstrap <kBase 父链接> --filter <关键词>` — 只导入标题包含关键词的文档
- `/bootstrap` 无参数 — 提示用户提供链接
- 自然语言：「把我这个 docs 知识库导进来」「从这个链接初始化我的 wiki」

## 后端适配

**默认后端：docs MCP**（公司内部 Docs，对应 `docs-mcp` 插件的 `docs_list_tree` / `docs_read` 工具）。

> **本仓库已捆绑 `docs-mcp` 插件**，位于 `plugins/docs-mcp/`，按 `plugins/README.md` 一次性安装即可开箱即用。Kuaishou 内网员工无需额外配置。

**通用接口要求**：任何能提供「列树」+「读单页」两个操作的源都可以适配，例如：

| 后端 | 列树工具 | 读页工具 |
|---|---|---|
| 内部 Docs | `docs_list_tree(url)` | `docs_read(url)` |
| Notion | Notion MCP / API | Notion MCP / API |
| Lark | Lark API | Lark API |
| Confluence | REST API | REST API |
| 本地 markdown 目录 | `find . -name "*.md"` | `Read(path)` |

适配时只需在执行流程的「步骤 3 列树」与「步骤 4 抓取」中替换对应工具调用即可。

## 工作流（七步）

### 1. 校验输入

- 必须有父链接，否则停下来问用户
- 识别 URL 类型（docs.corp.kuaishou.com → docs-mcp；notion.so → Notion 后端；……）
- 若无对应 MCP 工具，明确告诉用户「需要安装 X 插件」并停止

### 2. 列树并预览

- 调用对应后端的列树工具（默认 `docs_list_tree(url)`）
- 输出树形结构 + 总文档数 + 按目录层级的统计
- **必须等用户确认范围**：全部 / 按目录筛选 / 按关键词筛选 / 跳过某些
- 大于 50 篇时强制二次确认（避免误操作）

### 3. 准备落地目录

- 在 `raw/` 下创建 `04-docs-imported/<kbase-slug>/`
- `<kbase-slug>` 由父链接末尾 ID 派生或用户指定
- 已存在的同名 raw 文件**不覆盖**，记入「skipped」列表

### 4. 批量抓取到 raw/

对每个目标文档：

- 调用读页工具（默认 `docs_read(url, include_images=false)`）
- 保存到 `raw/04-docs-imported/<kbase-slug>/<doc-slug>.md`
- 在文件头部插入 YAML front-matter，**保留原始可追溯信息**：

```yaml
---
source_url: <原始云文档 URL>
fetched_at: <YYYY-MM-DD HH:mm>
original_title: <文档原标题>
imported_by: bootstrap
---
```

- 单页失败不中断整体流程，记入「failed」列表
- 每抓 10 篇输出一次进度

### 5. 批量编译进 wiki/

对每个新抓取的 raw 文件，调用 ingest 流程（参考 [`ingest`](../ingest/SKILL.md)）：

- 提炼 source / entity / concept
- 创建 / 合并对应 wiki 页面
- 强制建立双向链接
- 冲突保留共存（`## 知识冲突` 区块）

**节流**：每 5 篇批量提交一次，避免长时间无输出。

### 6. 更新注册表

- `wiki/index.md`：按分类追加所有新页面
- `wiki/log.md`：单条聚合日志

```markdown
## [YYYY-MM-DD] bootstrap | 从 <kBase 名称> 导入 N 篇
- **来源**: <父链接>
- **成功**: N 篇 → M 个 wiki 页面（sources / entities / concepts 各 X）
- **跳过**: K 篇（同名已存在）
- **失败**: F 篇（详见 raw/04-docs-imported/<slug>/_failed.json）
- **冲突**: C 处（详见 wiki/<page>.md 的知识冲突区块）
```

### 7. 输出报告 + 引导下一步

```markdown
# Bootstrap 完成报告

源: <kBase 名称>（<URL>）
抓取: 成功 N / 跳过 K / 失败 F
编译: 生成 X sources + Y entities + Z concepts + W syntheses

下一步建议：
1. 跑 `/lint` 检查知识库健康度（死链 / 游离页 / 索引同步）
2. 跑 `python3 scripts/stats.py` 看规模统计
3. 用 `/query <你的第一个问题>` 体验闭环
4. 失败列表见 raw/04-docs-imported/<slug>/_failed.json，可手动重试
```

## 失败列表格式

`raw/04-docs-imported/<slug>/_failed.json`：

```json
[
  {"url": "https://...", "title": "...", "reason": "timeout / permission_denied / parse_error", "ts": "..."}
]
```

## 增量再跑

`bootstrap` 是**幂等**的：

- 同一个父链接再跑一次，已下载的 raw 文件被跳过
- 新增的云文档会被增量抓取
- 已有 wiki 页面增量合并，不重复创建

适合「云端知识库持续更新，每月跑一次 bootstrap 同步本地」的节奏。

## 红线

- **不修改源文档** —— docs_read 是只读模式，bootstrap 永远不写回云端
- **大批量前必须确认** —— 超过 50 篇强制二次确认
- **不下载图片** —— 默认 `include_images=false`，避免拖慢和爆磁盘（用户可显式 `--with-images` 开启）
- **不删除已存在的 raw / wiki 文件** —— 只增量合并
- **失败不静默** —— 每个失败 URL 都进 `_failed.json`，便于排查

## 推荐节奏

1. **首次启动**：跑一次 bootstrap 把云端知识库整体迁过来
2. **日常**：用 `/ingest` 增量摄入新资料
3. **每月**：跑一次 bootstrap 同步云端新增内容
4. **每周**：跑 `/lint` 维护健康度
