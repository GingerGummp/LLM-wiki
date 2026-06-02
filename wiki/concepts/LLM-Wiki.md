---
title: "LLM-Wiki"
type: concept
tags: [知识管理, AI协作, 方法论]
sources: [raw/01-articles/karpathy-llm-wiki.md]
last_updated: 2026-06-02
---

# LLM-Wiki

## 核心定义

一种针对 LLM 协作优化的个人知识库形态。参考 [Karpathy LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 提出的规范，把碎片化信息编译成结构化、高度互链的 Markdown 库，让 AI 能高效检索 / 引用 / 更新。

## 四层目录契约

```
raw/      不可变源（剪藏 / 论文 / 转写）
inbox/    长期 prompt 输入层
project/  可变工作层
wiki/     编译输出层
```

## 四种知识类型

| 类型 | 目录 | 内容 |
|---|---|---|
| Source | `wiki/sources/` | raw 资料的摘要，kebab-case |
| Entity | `wiki/entities/` | 人物 / 公司 / 工具 / 产品，TitleCase |
| Concept | `wiki/concepts/` | 概念 / 框架 / 方法论，TitleCase |
| Synthesis | `wiki/syntheses/` | 综述类长文，kebab-case |

## 三大不变量

1. **`raw/` 绝对只读** — 唯一真相来源
2. **强制双链** — 每页 `## 关联连接` 区块，禁止孤岛
3. **冲突共存** — 新旧矛盾不静默覆盖，开 `## 知识冲突` 区块

## 关联连接

- [Skill 三件套](Skill三件套.md) — 维护 LLM-Wiki 的三个核心 Skill
- [Claude Code](../entities/ClaudeCode.md) — 主要协作工具
- [摘要-karpathy-llm-wiki](../sources/摘要-karpathy-llm-wiki.md) — 思想来源
- [LLM-Wiki 工作流综述](../syntheses/llm-wiki-工作流综述.md) — 整体方案
