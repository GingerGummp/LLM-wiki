---
title: "Skill 三件套"
type: concept
tags: [Skill, 工作流, Claude Code]
sources: []
last_updated: 2026-06-02
---

# Skill 三件套

## 核心定义

维护 LLM-Wiki 必备的三个 Claude Code Skill，构成「输入 → 检索 → 健康度」最小闭环。

## 三个 Skill 对照

| Skill | 角色 | 触发 | 写权限 |
|---|---|---|---|
| `/ingest` | 编译器 | 摄入 raw/inbox 到 wiki | 仅写 wiki |
| `/query` | 检索器 | 在 wiki 中查询并引用 | 只读 |
| `/lint` | 健康度扫描 | 死链 / 游离 / 索引 / 冲突 | 报告，需用户确认才修复 |

## 为什么是这三个

| 知识库阶段 | 必需能力 | 对应 Skill |
|---|---|---|
| 输入阶段 | 把碎片化内容结构化 | `/ingest` |
| 使用阶段 | 让 AI 真正用上知识库 | `/query` |
| 维护阶段 | 防止熵增、检测断链 | `/lint` |

少一个都不行：只摄入不查询，知识库变冷启动垃圾桶；只查询不维护，半年后死链一片。

## 一键启动配套 Skill

除了日常运转的「三件套」，还有一个**一次性初始化** Skill：

| Skill | 角色 | 触发 | 写权限 |
|---|---|---|---|
| `/bootstrap` | 一键迁移 | 从云文档父链接批量导入并编译 | 仅写 raw/ + wiki/ |

`/bootstrap` 解决「冷启动」痛点：你不需要一篇篇 `/ingest`，输入云端知识库的父链接（如 Kuaishou Docs kBase / Notion / Lark），skill 自动遍历整棵文档树、抓取所有页面、批量编译进 wiki。

合在一起就是完整生命周期：

| 阶段 | Skill |
|---|---|
| 首次启动（零成本拥有完整 wiki） | `/bootstrap` |
| 日常增量 | `/ingest` |
| 使用 | `/query` |
| 维护 | `/lint` |

## 设计原则

1. **只读优先**：`/query` 和 `/lint` 默认不写，避免静默破坏
2. **报告再修复**：`/lint` 出报告，用户确认后再批量修
3. **引用必带路径**：`/query` 答题必须用相对链接，方便用户跳转校验
4. **幂等可重入**：`/bootstrap` 二次运行只增量同步新内容，不覆盖已有

## 关联连接

- [LLM-Wiki](LLM-Wiki.md) — 服务的知识库形态
- [Claude Code](../entities/ClaudeCode.md) — 宿主工具
- [LLM-Wiki 工作流综述](../syntheses/llm-wiki-工作流综述.md) — 整体使用方式
