---
name: ingest
description: 将 raw/ 或 inbox/ 下的原始资料编译进 wiki/。raw/ 和 inbox/ 为只读输入层，不得修改或删除源文件。支持 /ingest（扫描全 raw）、/ingest <path>（指定文件）、/ingest inbox/<path>（长期 prompt 文件）。当用户说"摄入"、"导入"、"收入这份资料"时也应触发。
user-invocable: true
---

# ingest 技能

## 角色

你是 LLM-Wiki 编译器。`raw/` 与 `inbox/` 是不可变输入，`wiki/` 是你的输出。

## 编译流水线

对每个待处理源文件：

### 1. 读取源文件
- `.md` 文件：完整读取
- `.pdf` 文件：尝试提取文本；失败则只记元信息
- `inbox/*` 文件：只读，保留用户原始表达

### 2. 提炼
- 核心主旨（1-2 句）
- 实体（人物 / 公司 / 工具 / 产品）
- 概念（框架 / 方法论 / 理论）
- 非中文一律翻译成中文

### 3. 创建 source 摘要
路径：`wiki/sources/摘要-{slug}.md`，文件名 kebab-case

```markdown
---
title: "摘要-{slug}"
type: source
tags: [来源]
sources: [raw/path/to/file]
last_updated: YYYY-MM-DD
---

## 核心摘要
3-5 句话总结

## 关联连接
- [EntityName](../entities/EntityName.md)
- [ConceptName](../concepts/ConceptName.md)
```

### 4. 创建 / 合并实体 / 概念页
- 不存在 → 按 Frontmatter 模板新建
- 已存在 → 增量合并，不覆盖
- 发现冲突 → 不静默，开 `## 知识冲突` 区块

### 5. 更新注册表
- `wiki/index.md`：按分类追加新页面
- `wiki/log.md`：追加 `## [日期] ingest | 简述`

### 6. 保留源文件
确认上述全部完成后停止，**绝不修改 raw/ 与 inbox/ 内容**。

## 触发模式

- `/ingest` → 扫描全 `raw/`（除 `raw/09-archive/`）
- `/ingest <path>` → 仅处理该文件
- `/ingest inbox/<path>` → 处理长期 prompt，原意优先

## 红线
- 禁止读取 `raw/09-archive/`
- 禁止修改、移动、删除 `raw/` 与 `inbox/` 文件
- 所有 wiki 页必须有 `## 关联连接`，禁止孤岛
