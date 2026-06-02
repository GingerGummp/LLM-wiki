# 我想用 Claude Code 重做一遍 Notion

随手记，2026-06-02：

我用 Notion 三年了，最大问题是搜索答非所问 + AI 不知道我业务背景。
试过把所有内容导出喂给 ChatGPT，但 context window 撑不住。

想法：
- 本地 markdown，按 source/entity/concept/synthesis 分四类
- 强制双链，禁止孤岛
- 用 Claude Code 当主入口，CLAUDE.md 锁住契约
- 写三个 skill：ingest（摄入）/ query（检索）/ lint（健康度）

下一步：先建个 demo 试试。
