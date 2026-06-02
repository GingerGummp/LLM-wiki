---
title: "摘要-karpathy-llm-wiki"
type: source
tags: [来源, LLM-Wiki, 方法论]
sources: [raw/01-articles/karpathy-llm-wiki.md]
last_updated: 2026-06-02
---

# 摘要 - Karpathy LLM-Wiki 规范

## 核心摘要

Karpathy 在 GitHub Gist 提出：LLM 时代的个人知识库应该写成 markdown wiki，按 **sources / entities / concepts / syntheses** 四类组织，强制双向链接，让 AI 既能高效检索也能持续更新。核心不变量：raw 只读、wiki 互链、矛盾共存。

## 关键要点

1. 知识库不是文档归档，而是 AI 协作底座
2. 四类页面（source / entity / concept / synthesis）形态各异但都遵循同一 frontmatter 规范
3. 索引页（index.md）+ 日志页（log.md）是必备基石
4. 知识冲突保留双方表述，等待人工裁决

## 关联连接

- [LLM-Wiki](../concepts/LLM-Wiki.md) — 直接由此规范派生
- [Skill 三件套](../concepts/Skill三件套.md) — 实施 LLM-Wiki 的最小工具集
