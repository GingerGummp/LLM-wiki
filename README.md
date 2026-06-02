# LLM-Wiki — 把碎片信息变成可对话的第二大脑

> Anthropic Claude Code + Karpathy LLM-Wiki schema 的最小可运行样例。
> Clone 下来 5 分钟，让 AI 在你的私有知识库里替你做业务判断。

[![status](https://img.shields.io/badge/status-demo-blue)]()
[![license](https://img.shields.io/badge/license-MIT-green)]()
[![claude--code](https://img.shields.io/badge/Claude_Code-ready-orange)]()

---

## 如何使用

```bash
# 1. clone
git clone https://github.com/GingerGummp/LLM-wiki && cd LLM-wiki

# 2. 安装捆绑的 docs-mcp 插件（一次性，让 /bootstrap 能读云文档）
claude
/plugin marketplace add ./plugins
/plugin install docs-mcp@llm-wiki

# 3. 一键迁移现有云文档知识库（最快路径，5 分钟拥有自己的 wiki）
/bootstrap https://docs.corp.kuaishou.com/k/home/<你的-kBase-id>

# 4. 日常体验三件套
/ingest raw/01-articles/karpathy-llm-wiki.md   # 摄入一份资料
/query LLM-Wiki 的核心不变量是什么              # AI 在 wiki 里查询并引用回答
/lint                                          # 健康度检查

# 5. 直接跑脚本（不需要 AI 也能用）
python3 scripts/lint.py
python3 scripts/stats.py
```

可视化项目总览页位于本仓库**外**的 `../展示/index.html`（参赛展示用），打开浏览器直接查看即可。插件安装详情见 [`plugins/README.md`](plugins/README.md)。

---

## 为什么需要这个

AI 提效的真正瓶颈，**不是 Prompt 写得好不好**，而是有没有一份：

- 结构化、可被 AI 高效检索
- 双向链接、不会变成孤岛
- 持续更新、自动检测熵增

的**私有知识库**。

否则你给 AI 的永远是「上下文窗口里临时塞的几段话」，AI 给你的永远是「网上能找到的通用答案」。

---

## 四层目录契约

```
raw/        不可变源（剪藏 / 论文 / 转写）— 只读
inbox/      长期 prompt 输入层 — 碎片想法的收件箱
project/    可变工作层 — 日常任务 / 实验 / 草稿
wiki/       编译输出层（你的第二大脑）
  ├── sources/    资料摘要（kebab-case）
  ├── entities/   人物 / 工具 / 公司（TitleCase）
  ├── concepts/   框架 / 方法论（TitleCase）
  └── syntheses/  综述类长文（kebab-case）
```

详见 [`CLAUDE.md`](CLAUDE.md) — 这份文件就是 Claude Code 的全局契约。

---

## 三大 Skill + 一键启动

| Skill | 角色 | 触发 | 代码 |
|---|---|---|---|
| `/bootstrap` | **一键迁移**：把云端知识库（kBase / Notion / Lark）批量导入并编译 | 首次启动 / 增量同步 | [SKILL.md](.claude/skills/bootstrap/SKILL.md) |
| `/ingest` | 编译器：摄入 raw/inbox 到 wiki | 摄入资料时 | [SKILL.md](.claude/skills/ingest/SKILL.md) |
| `/query` | 检索器：在 wiki 中查询并引用 | 问业务问题时 | [SKILL.md](.claude/skills/query/SKILL.md) |
| `/lint` | 健康度扫描：死链 / 游离 / 索引 / 冲突 | 周度维护 | [SKILL.md](.claude/skills/lint/SKILL.md) |

**典型使用节奏**：
- **首次启动**：跑一次 `/bootstrap <你的云文档父链接>`，5 分钟把现有知识库整体迁过来
- **日常**：`/ingest` 增量摄入新资料
- **每周**：`/lint` 维护健康度，知识库不熵增
- **每月**：再跑一次 `/bootstrap` 同步云端新增内容

少一个都不行：
- 没有 `/bootstrap` → 冷启动太痛，从零喂资料劝退
- 只摄入不查询 → 知识库变冷启动垃圾桶
- 只查询不维护 → 半年后死链一片

---

## Demo 知识库当前规模

跑 `python3 scripts/stats.py` 实时统计：

| 指标 | 值 |
|---|---|
| 总页面数 | 7 |
| 类型分布 | concepts × 2 / entities × 2 / sources × 2 / syntheses × 1 |
| 总链接数 | 25 |
| 平均双链密度 | 3.57 链 / 页 |
| 死链 / 游离 / 冲突 | 0 / 0 / 0 |

（生产仓库当前规模：60+ 页面，密度 3.5+/页。这套方案在真实业务中已持续运转。）

---

## 5 步上手

### 1. 装 Claude Code

参考 [Anthropic 官方文档](https://docs.claude.com/claude-code)。

### 2. clone 本仓库

```bash
git clone https://github.com/GingerGummp/LLM-wiki
cd LLM-wiki
rm -rf .git && git init
```

### 3. 改 `CLAUDE.md`

把里面提到的领域 / 业务背景替换成你自己的（例：从「激励广告 owner」换成「前端工程师」）。

### 4. 二选一：冷启动 or 一键迁移

**方式 A — 一键迁移（推荐，5 分钟有完整知识库）**：
```
/bootstrap https://docs.example.com/k/home/<你的-kBase-id>
```
skill 自动遍历整棵文档树、抓取所有页面到 `raw/`、按 schema 编译进 `wiki/`，结束给你一份导入报告。

**方式 B — 从单篇资料起步**：
随便挑一篇文章扔进 `raw/01-articles/`，然后：
```
/ingest raw/01-articles/your-article.md
```
体验完整闭环：source 摘要 → 实体 / 概念页 → 双链 → index / log 全部自动更新。

### 5. 一周后问第一个问题

```
/query 我上周看的那篇关于 X 的文章主要讲什么
```

对比同一个问题问通用 ChatGPT —— 差别立现。

之后每周五跑一次 `/lint`，让知识库不熵增。

---

## Before / After

| 任务 | Before（无知识库） | After（有 wiki） |
|---|---|---|
| 找历史实验结论 | 翻 Doc 30 分钟 + 自己回忆 | `/query` 5 秒，AI 引用具体页面 |
| 周报草稿 | 翻 10 个 doc 拼接 2 小时 | Agent 在 wiki 上跑模板 + 润色 20 分钟 |
| 论文调研 | 一篇一天 | 一篇 2 小时，结论可追溯 |
| 老板灵魂提问 | 临场翻资料 | Agent 当陪练，提前压测 5 个问题 |

---

## 适合谁 / 不适合谁

**适合**：
- 长期 owner 一块业务、需要积累的人
- 写代码 / 做研究 / 做策略、希望 AI 真正帮你做判断的人
- 希望借助大模型能力对知识做记忆和整理的人

**不适合**：
- 一次性小项目、一周后不再回头的工作
- 不愿意维护目录、不写双链的人
- 强依赖跨部门协作、内容必须留在公司内部 Doc 系统的人

---

## 项目结构

```
LLM-wiki/
├── CLAUDE.md                 # 全局契约（Claude Code 启动自动加载）
├── README.md                 # 本文件
├── LICENSE                   # MIT
├── .claude/skills/           # Skill 集合
│   ├── bootstrap/SKILL.md    #   一键迁移云文档知识库
│   ├── ingest/SKILL.md       #   增量摄入单篇资料
│   ├── query/SKILL.md        #   wiki 检索 + 引用回答
│   └── lint/SKILL.md         #   健康度扫描
├── plugins/                  # 捆绑的 MCP 插件 marketplace
│   ├── README.md             #   插件安装说明
│   ├── .claude-plugin/
│   │   └── marketplace.json
│   └── docs-mcp/             #   公司内部 Docs 读写（供 /bootstrap 使用）
│       ├── .claude-plugin/plugin.json
│       ├── docs_mcp_server.py
│       ├── _agent_tools_auth.py
│       └── skills/docs/SKILL.md
├── wiki/                     # 编译输出层（你的第二大脑）
│   ├── index.md              # 总目录
│   ├── log.md                # Append-only 操作日志
│   ├── concepts/             # 概念
│   ├── entities/             # 实体
│   ├── sources/              # 资料摘要
│   └── syntheses/            # 综述
├── raw/                      # 不可变源
├── inbox/                    # 长期 prompt 输入
├── project/                  # 可变工作层
└── scripts/                  # 离线工具
    ├── lint.py               # 死链 / 游离 / 索引扫描
    └── stats.py              # 规模与密度统计
```

> 项目可视化总览页 `index.html` 在仓库**外**（参赛展示文件夹），不随仓库一起发布。

---

## License

MIT — fork / 改名 / 商用都欢迎。

---

## 想交流

- 评论区留下你的目录结构，我帮看怎么改造成 LLM-Wiki schema
- Issue 提需求：希望加什么 Skill / 什么场景

—— 让 AI 在你的知识里，和你一起思考。
