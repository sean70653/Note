#!/usr/bin/env python3
"""
Generate llms.txt from docs/ content.

Scans all published English .en.md articles, extracts frontmatter,
and produces a llms.txt file following the llmstxt.org spec.

Run: python scripts/generate-llms-txt.py
Output: docs/llms.txt (copied to site root during build)
"""

import re
import yaml
from pathlib import Path

SITE_URL = None
SITE_NAME = None
SITE_DESC = None

CATEGORY_MAP = {
    "engineering": "Engineering",
    "architecture": "Architecture",
    "ai-and-tools": "AI & Tools",
    "leadership": "Leadership",
}


def load_mkdocs_config():
    global SITE_URL, SITE_NAME, SITE_DESC
    config_path = Path(__file__).parent.parent / "mkdocs.yml"
    text = config_path.read_text(encoding="utf-8")
    # yaml.safe_load can't handle !!python/name tags, so strip them
    text = re.sub(r"!!python/\S+", "null", text)
    config = yaml.safe_load(text)
    SITE_URL = config.get("site_url", "").rstrip("/")
    SITE_NAME = config.get("site_name", "Tech Notes")
    SITE_DESC = config.get("site_description", "")


def parse_frontmatter(filepath):
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None


def collect_articles(docs_dir):
    """Collect all published English articles grouped by category."""
    categories = {}
    for md_file in sorted(docs_dir.rglob("*.en.md")):
        rel = md_file.relative_to(docs_dir)
        parts = rel.parts
        if len(parts) < 2:
            continue
        category = parts[0]
        if category not in CATEGORY_MAP:
            continue
        if parts[-1].startswith("index."):
            continue

        fm = parse_frontmatter(md_file)
        if not fm:
            continue
        if fm.get("status") == "draft":
            continue

        slug = md_file.stem.replace(".en", "")
        url = f"{SITE_URL}/{category}/{slug}/"
        title = fm.get("title", slug)
        desc = fm.get("description", "")

        if category not in categories:
            categories[category] = []
        entry = f"- [{title}]({url})"
        if desc:
            entry += f": {desc}"
        categories[category].append(entry)

    return categories


def generate(output_path):
    load_mkdocs_config()
    docs_dir = Path(__file__).parent.parent / "docs"
    categories = collect_articles(docs_dir)

    lines = []
    lines.append(f"# {SITE_NAME}")
    lines.append("")
    lines.append(f"> {SITE_DESC}")
    lines.append("")
    lines.append(
        f"Personal technical notes by Sean. "
        f"Hands-on engineering articles with real commands, real output, and real trade-offs. "
        f"All content available in English and Chinese."
    )
    lines.append("")
    lines.append(f"- [About]({SITE_URL}/about/): About the author")
    lines.append(f"- [Tags]({SITE_URL}/tags/): Browse all articles by tag")
    lines.append("")

    for cat_key, cat_name in CATEGORY_MAP.items():
        if cat_key not in categories:
            continue
        lines.append(f"## {cat_name}")
        lines.append("")
        for entry in categories[cat_key]:
            lines.append(entry)
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {output_path} ({len(lines)} lines)")


if __name__ == "__main__":
    out = Path(__file__).parent.parent / "docs" / "llms.txt"
    generate(out)
