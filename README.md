# Sure! Pl Commit Census

Small, exploratory dataset + dashboard tracking public commits that include the message "Sure! Pl".

## Quick start
Open `index.html` in a browser to explore the latest dataset.

## Refresh the data
1. Copy `.env.example` to `.env` and set `GITHUB_TOKEN`.
2. Run:

```bash
python3 fetch_commit_search.py --query "\"Sure! Pl\""
```

This writes `surepl-commits.json`, which `index.html` reads by default.

## Caveats
This was a fast, curiosity-driven experiment, and the author fully expects the methodology to be a little… questionable—proceed accordingly. See the caveats section at the bottom of `index.html`.
