---
title: "ClaudeCode"
type: entity
tags: [AI工具, IDE, Anthropic]
sources: [raw/01-articles/claude-code-intro.md]
last_updated: 2026-06-02
---

# Claude Code

## 定义

Anthropic 出品的官方 CLI 助手，把 Claude 模型能力直接接入终端 / IDE 工作流，支持 skill / hook / MCP 插件三层扩展。

## 关键信息

- **三层扩展**：Skill（提示词模板）+ Hook（事件触发的 shell 脚本）+ MCP（外部工具调用）
- **上下文契约**：项目根目录的 `CLAUDE.md` 自动加载为全局指令
- **模型**：默认 Sonnet，可切到 Opus 长上下文模式
- **可结合 Codex 使用**：思考层用 Claude，落地层用 Codex

## 在本知识库中的角色

[Claude Code](ClaudeCode.md) 与 [Codex](Codex.md) 分工：
- Claude Code 负责思考、综述、长文阅读
- Codex 负责批量整理、目录维护、文件操作

## 关联连接

- [Codex](Codex.md) — 协作伙伴
- [LLM-Wiki](../concepts/LLM-Wiki.md) — 服务的知识库形态
- [Skill 三件套](../concepts/Skill三件套.md) — 在本仓库使用的核心 Skill
- [摘要-claude-code-intro](../sources/摘要-claude-code-intro.md) — 源材料
