#!/usr/bin/env python3
"""
LLM-Wiki Lint Tool — 简化 Python 版

扫描 wiki/ 目录，检测：
1. 死链（[text](path) 指向不存在的文件）
2. 游离页（无人引用且未在 index.md 注册）
3. 索引未同步（文件存在但 index 未挂 / index 挂了但文件不存在）
4. 知识冲突（含 ## 知识冲突 区块）

用法：
    python3 scripts/lint.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "wiki"
INDEX = WIKI / "index.md"

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")
CONFLICT_RE = re.compile(r"^##\s*知识冲突", re.M)


def all_md_files():
    return sorted(p for p in WIKI.rglob("*.md") if p.name not in {"index.md", "log.md"})


def parse_links(md_path):
    text = md_path.read_text(encoding="utf-8")
    for m in LINK_RE.finditer(text):
        yield m.group(1), m.group(2)


def resolve(base, link):
    try:
        return (base.parent / link).resolve()
    except Exception:
        return None


def main():
    pages = all_md_files()
    page_set = {p.resolve() for p in pages}

    broken = []     # (page, link_text, link_path)
    referenced = set()
    conflicts = []

    for page in pages:
        text = page.read_text(encoding="utf-8")
        if CONFLICT_RE.search(text):
            conflicts.append(page.relative_to(ROOT))
        for text_, link in parse_links(page):
            target = resolve(page, link)
            if target and target in page_set:
                referenced.add(target)
            else:
                broken.append((page.relative_to(ROOT), text_, link))

    # index.md 注册情况
    index_links = set()
    if INDEX.exists():
        for _, link in parse_links(INDEX):
            target = resolve(INDEX, link)
            if target:
                index_links.add(target)

    orphans = [p.relative_to(ROOT) for p in pages
               if p.resolve() not in referenced and p.resolve() not in index_links]

    stale_index = [link for link in index_links if link not in page_set]
    missing_in_index = [p.relative_to(ROOT) for p in pages if p.resolve() not in index_links]

    # 输出
    print(f"# Lint Report — wiki/ ({len(pages)} pages)\n")

    print(f"## ❌ 死链 ({len(broken)})")
    for page, text_, link in broken:
        print(f"- `{page}` → `[{text_}]({link})`")

    print(f"\n## ⚠️ 游离页 ({len(orphans)})")
    for o in orphans:
        print(f"- {o}")

    print(f"\n## 📋 索引未挂 ({len(missing_in_index)})")
    for m in missing_in_index:
        print(f"- {m}")

    print(f"\n## 📋 索引死链 ({len(stale_index)})")
    for s in stale_index:
        print(f"- {s}")

    print(f"\n## ⚖️ 知识冲突 ({len(conflicts)})")
    for c in conflicts:
        print(f"- {c}")

    total_issues = len(broken) + len(orphans) + len(missing_in_index) + len(stale_index) + len(conflicts)
    print(f"\n---\n总计 {total_issues} 个待处理项")
    sys.exit(1 if total_issues else 0)


if __name__ == "__main__":
    main()
