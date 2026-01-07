# Repository Guidelines

## Project Structure & Module Organization
- `index.html` contains the full UI, styles, and JavaScript for the tool.
- `asciinema-player.min.js` and `asciinema-player.css` are optional local assets; the page falls back to the CDN if they are missing.
- `server.py` is a tiny helper to fetch assets and run a local server.
- `README.md` documents usage and workflow tips.

## Build, Test, and Development Commands
- `python3 -m http.server 8000` serves the project locally so browser fetches work; open `http://localhost:8000/index.html`.
- `python3 server.py` downloads Asciinema assets if missing and then serves the site.
- `python3 server.py --no-fetch` serves without downloading assets.
No build step or package manager is required.

## Coding Style & Naming Conventions
- Indentation: 2 spaces in HTML/CSS/JS to match existing formatting in `index.html`.
- JavaScript is embedded in `index.html`; keep helpers small and documented with brief comments only when logic is non-obvious.
- CSS classes are short and descriptive (`.panel`, `.dropzone`, `.twoCol`); prefer lowercase with no underscores.
- Use double quotes for HTML attributes and JavaScript strings to stay consistent with existing code.

## Testing Guidelines
There is no automated test suite. Validate changes manually:
- Load a local `.cast` file and a remote URL.
- Verify start/end insertion, preview looping, and snippet generation.
- Confirm Ghost snippet output still works with local and CDN player assets.

## Commit & Pull Request Guidelines
- Commit messages are simple, sentence-style summaries (see `git log --oneline`); keep them concise and action-oriented.
- PRs should describe the change, include the reason, and note any manual testing performed.
- UI changes should include a screenshot or short GIF.

## Configuration & Hosting Notes
- Local files are supported for preview, but Ghost embeds require public URLs.
- Avoid adding new build tooling unless it materially improves the single-file workflow.
