# Sean's Tech Notes

Hands-on technical notes, architecture decisions, and engineering insights.

**[Read online →](https://sean70653.github.io/Note/)**

## What's Here

| Category | Description |
|----------|-------------|
| **Engineering** | Systems, networking, performance, infrastructure -- with real commands and benchmarks |
| **Architecture** | Design decisions, trade-off analyses, and architecture decision records |
| **AI & Tools** | AI prompts, developer tooling, and workflow optimizations |
| **Leadership** | Engineering management, team building, hiring, and organizational insights |

All content is available in **English** and **中文**, with a language switcher on every page.

## How Deployment Works

**You don't need to run `mkdocs build` locally.** Just push to `main` and everything happens automatically:

```
git add . && git commit -m "new article" && git push
```

GitHub Actions will:

1. Generate `llms.txt` from your articles (for AI discoverability)
2. Run `mkdocs build --strict`
3. Deploy the built site to GitHub Pages

The site will be live at `https://sean70653.github.io/Note/` within a minute or two.

> **First-time setup**: Go to your GitHub repo → Settings → Pages → Source → select "GitHub Actions".

## Local Development

```bash
pip install -r requirements.txt

# Preview with hot reload
mkdocs serve

# Full build (optional, CI does this for you)
mkdocs build
```

## Writing a New Article

1. Pick a category (e.g., `engineering`)
2. Copy the template into docs:
   ```bash
   cp templates/engineering/_template.en.md docs/engineering/my-article.en.md
   cp templates/engineering/_template.zh.md docs/engineering/my-article.zh.md
   ```
3. Write your content in one language, translate the other
4. Add the article to `nav` in `mkdocs.yml`:
   ```yaml
   nav:
     - Engineering:
         - engineering/index.md
         - engineering/my-article.md   # no .en/.zh suffix in nav
   ```
5. `git push` to `main` -- done

## Project Structure

```
Note/
├── mkdocs.yml                 # Site config (theme, plugins, nav)
├── requirements.txt           # Python deps
├── scripts/
│   └── generate-llms-txt.py   # Auto-generates llms.txt for AI discoverability
├── .github/workflows/
│   └── deploy.yml             # CI: generate llms.txt → build → deploy
├── .cursor/rules/
│   └── writing-style.mdc      # AI writing style guide (Taiwan-engineer style)
├── docs/                      # All content lives here
│   ├── index.en.md / .zh.md   # Landing page
│   ├── about.en.md / .zh.md   # About page
│   ├── tags.en.md / .zh.md    # Tags index
│   ├── llms.txt               # Auto-generated, don't edit manually
│   ├── engineering/            # Technical deep-dives
│   ├── architecture/           # Architecture decisions
│   ├── ai-and-tools/           # AI prompts & tooling
│   └── leadership/             # Engineering management
├── templates/                  # Article templates (not published)
│   ├── engineering/
│   ├── architecture/
│   ├── ai-and-tools/
│   └── leadership/
└── README.md
```

## AI Discoverability (llms.txt)

This site includes a [`/llms.txt`](https://sean70653.github.io/Note/llms.txt) file following the [llmstxt.org](https://llmstxt.org/) spec. It provides a structured summary of all published articles so AI tools (ChatGPT, Claude, Perplexity, etc.) can discover and reference the content.

The file is **auto-generated** by `scripts/generate-llms-txt.py` during CI -- you never need to update it manually. Every time you push a new article, `llms.txt` is regenerated to include it.

## License

See [LICENSE](LICENSE).
