---
title: "LLM-Wiki 工作流综述"
type: synthesis
tags: [综述, 工作流, LLM-Wiki]
sources: [raw/01-articles/karpathy-llm-wiki.md, raw/01-articles/claude-code-intro.md]
last_updated: 2026-06-02
---

# LLM-Wiki 工作流综述

## 这页回答的问题

> 一个人怎么从「Doc 收藏夹 200+」演化到「AI 在我的知识库里做我的判断陪练」？最小可行路径是什么？

## 三层架构

```
源文档层 (raw/ + inbox/)
    ↓ ingest
视图层 (wiki/ 双链 markdown)
    ↓ query / lint
协作层 (Claude Code + 7 Agents)
```

## 最小启动路径

1. **建四层目录** — `raw/ inbox/ project/ wiki/`
2. **写一份 CLAUDE.md** — 把契约固化
3. **装三个 Skill** — `/ingest /query /lint`
4. **摄入第一份资料** — 用 `/ingest raw/xxx.md` 体验闭环
5. **一周后 `/query`** — 问一个业务问题，体验和通用 AI 的差别
6. **每周五 `/lint`** — 让知识库不熵增

## 为什么这个顺序

- 没有契约（CLAUDE.md），AI 会自由发挥，产出不稳定
- 没有三件套，知识库会偏科：只摄入不查询变垃圾桶，只查询不维护半年死链一片
- 没有第一次 `/query`，体感不出来，难坚持

## 关联连接

- [LLM-Wiki](../concepts/LLM-Wiki.md) — 核心概念
- [Skill 三件套](../concepts/Skill三件套.md) — 工具集
- [Claude Code](../entities/ClaudeCode.md) — 宿主
- [Codex](../entities/Codex.md) — 协作伙伴
- [摘要-karpathy-llm-wiki](../sources/摘要-karpathy-llm-wiki.md) — 思想来源
