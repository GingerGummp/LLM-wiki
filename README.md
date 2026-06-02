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

# 2. 用 Claude Code 打开（它会自动加载 CLAUDE.md 契约）
claude

# 3. 体验三件套
/ingest raw/01-articles/karpathy-llm-wiki.md   # 摄入一份资料
/query LLM-Wiki 的核心不变量是什么              # AI 在 wiki 里查询并引用回答
/lint                                          # 健康度检查

# 4. 直接跑脚本（不需要 AI 也能用）
python3 scripts/lint.py
python3 scripts/stats.py
```

打开浏览器看 [`docs/index.html`](docs/index.html) 是项目可视化总览页。

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

## 三大 Skill

| Skill | 角色 | 触发 | 代码 |
|---|---|---|---|
| `/ingest` | 编译器：摄入 raw/inbox 到 wiki | 摄入资料时 | [SKILL.md](.claude/skills/ingest/SKILL.md) |
| `/query` | 检索器：在 wiki 中查询并引用 | 问业务问题时 | [SKILL.md](.claude/skills/query/SKILL.md) |
| `/lint` | 健康度扫描：死链 / 游离 / 索引 / 冲突 | 周度维护 | [SKILL.md](.claude/skills/lint/SKILL.md) |

少一个都不行：
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

### 4. 摄入第一份资料

随便挑一篇你常翻的文章扔进 `raw/01-articles/`，然后：

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
demo/
├── CLAUDE.md                 # 全局契约（Claude Code 启动自动加载）
├── README.md                 # 本文件
├── .claude/skills/           # 三大 Skill
│   ├── ingest/SKILL.md
│   ├── query/SKILL.md
│   └── lint/SKILL.md
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
├── scripts/                  # 离线工具
│   ├── lint.py               # 死链 / 游离 / 索引扫描
│   └── stats.py              # 规模与密度统计
└── docs/
    └── index.html            # 项目可视化总览
```

---

## License

MIT — fork / 改名 / 商用都欢迎。

---

## 想交流

- 评论区留下你的目录结构，我帮看怎么改造成 LLM-Wiki schema
- Issue 提需求：希望加什么 Skill / 什么场景

—— 让 AI 在你的知识里，和你一起思考。
