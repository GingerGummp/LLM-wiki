# LLM-Wiki Personal Knowledge Base — 全局契约

> Claude Code 每次启动会自动加载此文件。修改时请保持简洁、可执行、无歧义。

## 语言与角色

- 始终用**简体中文**思考、回答、编写知识库
- 你正在维护一个 **LLM-Wiki**（参考 [Karpathy LLM-Wiki 规范](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)），把碎片化信息编译成**高度互链**的结构化知识库

## 四层目录契约（不可逾越的底线）

```
raw/       不可变源（剪藏 / 论文 / 转写）— 只读，禁止修改或删除
inbox/     长期 prompt 输入层 — 用户原始想法的收件箱
project/   可变工作层 — 日常任务 / 实验 / 草稿
wiki/      编译输出层 — 你的专属工作区
```

- `raw/` 是**唯一真相来源**，绝对只读
- `wiki/` 是你的输出，包含 `concepts/ entities/ sources/ syntheses/` 四个子目录
- `inbox/` 是用户的输入入口之一，禁止静默修改原文件

## Wiki Schema 三件套

### 1. 每个 wiki 页面必须有 Frontmatter

```yaml
---
title: "页面标题"
type: concept | entity | source | synthesis
tags: [标签数组]
sources: [关联的 raw/ 或 project/ 相对路径]
last_updated: YYYY-MM-DD
---
```

### 2. 强制双向链接，禁止孤岛

每页必须有 `## 关联连接` 区块，使用**标准 Markdown 相对链接**：

- 同分类内：`[Y](Y.md)`
- 跨分类：`[Y](../category/Y.md)`
- 不使用 Obsidian `[[]]` 语法（VSCode 原生预览不支持）

### 3. 矛盾不静默覆盖

新旧知识冲突时，开 `## 知识冲突` 区块**两种说法共存**，写明冲突点与暂定判断。

## 全局注册表（每次写入后必更）

- **`wiki/index.md`** — 总目录，新页面按分类追加：`[标题](category/标题.md) — 一句话描述`
- **`wiki/log.md`** — Append-only 操作日志：`## [YYYY-MM-DD] <动作> | <简述>`

## 三大 Skill 入口

- `/ingest <路径>` — 把 raw / inbox / project 文件编译进 wiki
- `/query <问题>` — 在 wiki 中检索并回答，必须用相对链接引用
- `/lint` — 全局扫死链 / 游离页 / 索引未同步 / 知识冲突

## 一键启动

- `/bootstrap <云文档父链接>` — 把现有云端知识库（kBase / Notion / Lark 等）一键迁移到本地，省掉冷启动成本。详见 `.claude/skills/bootstrap/SKILL.md`。

## 命名规范

- Entities / Concepts：TitleCase（如 `ClaudeCode.md`）
- Sources / Syntheses：kebab-case（如 `摘要-source-slug.md`）
