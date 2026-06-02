---
name: lint
description: 知识库全局健康度检查。扫描 wiki/ 目录，检测死链（引用不存在的页面）、游离页（无任何页面引用）、未同步索引（文件存在但未在 index.md 注册）和知识冲突。当用户输入 /lint、/scan、/health 或要求"检查知识库状态"、"检查健康"时调用。
user-invocable: true
---

# lint 技能

## 检查项

### 1. 死链 (broken-link)
扫描所有 wiki 页面，提取 Markdown 链接 `[text](path)`，验证 path 是否真实存在。

### 2. 游离页 (orphan)
任何 wiki 页面如果没有被其他页面引用，且未在 `index.md` 中注册，标记为游离。

### 3. 索引未同步 (index-stale)
- 文件系统中存在但 `index.md` 未注册 → 漏挂
- `index.md` 注册但文件不存在 → 死索引

### 4. 知识冲突 (conflict)
扫描所有页面，列出含 `## 知识冲突` 区块的页面，提示用户复核。

### 5. Frontmatter 缺失 (frontmatter-missing)
检查每页是否有合法 `title / type / tags / sources / last_updated` 五个字段。

## 触发模式

- `/lint` — 全量扫描
- `/lint <category>` — 仅扫指定子目录（如 `/lint concepts`）

## 输出格式

```markdown
# Lint Report — YYYY-MM-DD

## ❌ 死链 (3)
- `wiki/concepts/A.md` → `[B](../entities/B.md)` 不存在

## ⚠️ 游离页 (1)
- `wiki/concepts/X.md` 无人引用，未在 index.md 注册

## 📋 索引未同步 (2)
- `wiki/entities/Y.md` 存在但 index.md 未注册
- `index.md` 中 `[Z](concepts/Z.md)` 文件已删除

## ⚖️ 知识冲突 (1)
- `wiki/concepts/M.md` 含未解决冲突

## ✅ Frontmatter (全部通过)

## 建议
1. 先修死链（高优先级）
2. 把游离页挂到 index 或删除
3. 复核冲突
```

## 后续动作

输出报告后**询问用户**是否需要自动修复（追加到 index.md / 修死链），不擅自修改。
