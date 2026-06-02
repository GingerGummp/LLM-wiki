# LLM-Wiki Bundled Plugins

本目录捆绑了 LLM-Wiki 开箱即用所需的 Claude Code MCP 插件，保证 `/bootstrap` 等需要外部数据源的 skill 直接可用。

## 已捆绑插件

| 插件 | 版本 | 作用 | 适用范围 |
|---|---|---|---|
| [`docs-mcp`](docs-mcp/) | 0.3.12 | 读写公司内部 Docs 页面（docs.corp.kuaishou.com），支持 `docs_list_tree` / `docs_read` / `docs_write` / `docs_search` | Kuaishou 内网员工 |

## 安装方式（任选其一）

### 方式 A：作为本地 marketplace 安装（推荐）

```bash
cd LLM-wiki
claude
```

在 Claude Code 中执行：

```
/plugin marketplace add ./plugins
/plugin install docs-mcp@llm-wiki
```

### 方式 B：手动注册到 user-scope settings

编辑 `~/.claude/settings.json`，把插件路径加入 `plugins`：

```json
{
  "plugins": {
    "docs-mcp": {
      "path": "<本地 LLM-wiki 绝对路径>/plugins/docs-mcp"
    }
  }
}
```

重启 Claude Code 即可。

### 方式 C：直接拷贝到 user plugin 目录

```bash
cp -r plugins/docs-mcp ~/.claude/plugins/
```

## 前置条件

- **uv**：`docs-mcp` 用 `uv run` 启动 MCP server，按需安装依赖。装 uv：`brew install uv` 或 `pip install uv`
- **Chrome**：`docs_read` 通过 Chrome headless + CDP 抓取页面，确保已安装 Chrome
- **内网登录态**：在 Chrome 中登录过 docs.corp.kuaishou.com，插件会自动从浏览器读 cookie；也可通过 `DOCS_COOKIES` / `DOCS_COOKIE` 环境变量手动指定

## 验证安装

启动 Claude Code 后执行：

```
/mcp
```

应该能看到 `docs` server 处于 connected 状态。然后试试：

```
列一下 https://docs.corp.kuaishou.com/k/home/<你的-kBase-id> 的文档树
```

如果返回文档列表，说明插件工作正常，可以接着跑 `/bootstrap <url>` 一键迁移。

## 加新插件

把第三方插件目录 copy 进 `plugins/<plugin-name>/`，确保有 `.claude-plugin/plugin.json`，然后更新本 README 的「已捆绑插件」表。

## 注意

- `docs-mcp` 仅对**有内网访问权限的 Kuaishou 员工**有效；外部用户需要替换为自己环境对应的 doc 后端（Notion MCP、Lark API 等），详见 `.claude/skills/bootstrap/SKILL.md` 的「后端适配」段落。
- 插件包含的代码、auth 逻辑均来源于公司内部 agent-tools 工具链，仅作员工分享使用。
