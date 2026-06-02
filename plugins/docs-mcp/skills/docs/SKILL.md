---
name: docs
description: Read and write Kuaishou internal Docs pages via MCP. Use when the user wants to read, summarize, analyze, create, or update a docs.corp.kuaishou.com document.
---

# docs MCP Server

## Implementation Notes

- `docs_read` extracts content via Chrome headless + CDP — triggers the editor's select-all, then reads from `clipboardContentProvider.getClips()` for full document text regardless of virtual rendering/scroll position.
- Preserved: headings, bold, tables, math symbols (unicode), code blocks, lists. Omitted: images.
- `docs_write` strips YAML front-matter before uploading, uses the Docs import API (upload token → file upload → confirm import).

## Prerequisites

- Google Chrome installed (macOS default path, or set `CHROME_PATH`) — needed for `docs_read`
- Internal network access to docs.corp.kuaishou.com

## Cookie Setup

Priority order (first match wins):

1. `DOCS_COOKIES` env var — JSON dict: `'{"ks_fid":"abc"}'`
2. `DOCS_COOKIE` env var — raw cookie string
3. Auto-extract from Chrome via `browser_cookie3` (zero-config if logged in)
