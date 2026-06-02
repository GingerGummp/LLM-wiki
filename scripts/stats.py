#!/usr/bin/env python3
"""
LLM-Wiki Stats — 统计知识库规模与互链密度

输出：
- 总页面数（按类型）
- 总外链数
- 平均双链密度
- 游离页 / 死链摘要

用法：
    python3 scripts/stats.py
"""
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "wiki"
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")


def type_of(path):
    parts = path.relative_to(WIKI).parts
    if not parts:
        return "root"
    return parts[0]


def main():
    pages = [p for p in WIKI.rglob("*.md") if p.name not in {"index.md", "log.md"}]
    by_type = Counter(type_of(p) for p in pages)

    total_links = 0
    for p in pages:
        text = p.read_text(encoding="utf-8")
        total_links += len(LINK_RE.findall(text))

    print("# Wiki Stats\n")
    print(f"- 总页面数: **{len(pages)}**")
    for t, n in by_type.most_common():
        print(f"  - {t}: {n}")
    print(f"- 总链接数: **{total_links}**")
    if pages:
        print(f"- 平均双链密度: **{total_links / len(pages):.2f}** 链/页")


if __name__ == "__main__":
    main()
