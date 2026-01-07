#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_URL = "https://api.github.com/search/commits"
REPO_URL = "https://api.github.com/repos/"
ACCEPT_HEADER = "application/vnd.github.cloak-preview+json"
REPO_ACCEPT_HEADER = "application/vnd.github+json"
REPO_API_VERSION = "2022-11-28"


def parse_day(value):
  return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def to_iso(dt):
  return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_window(day):
  start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
  end = start + timedelta(days=1) - timedelta(seconds=1)
  return start, end


def build_query(base, date_field, start, end):
  return f"{base} {date_field}-date:{to_iso(start)}..{to_iso(end)}"


def request_json(url, token, accept_header=None, extra_headers=None):
  headers = {
    "Accept": accept_header or ACCEPT_HEADER,
    "User-Agent": "surepl-commit-census"
  }
  if token:
    headers["Authorization"] = f"Bearer {token}"
  if extra_headers:
    headers.update(extra_headers)
  req = Request(url, headers=headers)
  with urlopen(req) as resp:
    payload = json.loads(resp.read().decode("utf-8"))
    return payload, resp.headers


def respect_rate_limit(headers, min_delay):
  try:
    remaining = int(headers.get("X-RateLimit-Remaining", "1"))
  except ValueError:
    remaining = 1
  reset = headers.get("X-RateLimit-Reset")
  if remaining <= 0 and reset:
    try:
      reset_at = int(reset)
      wait_for = max(0, reset_at - int(time.time())) + 2
      time.sleep(wait_for)
      return
    except ValueError:
      pass
  if min_delay:
    time.sleep(min_delay)


def split_window(start, end):
  midpoint = start + (end - start) / 2
  midpoint = midpoint.replace(microsecond=0)
  if midpoint <= start:
    midpoint = start + timedelta(seconds=1)
  left_end = midpoint
  right_start = midpoint + timedelta(seconds=1)
  if right_start > end:
    right_start = end
  return (start, left_end), (right_start, end)


def fetch_window(start, end, base_query, date_field, token, per_page, min_delay, max_pages, depth=0):
  query = build_query(base_query, date_field, start, end)
  params = {"q": query, "per_page": per_page, "page": 1}
  url = API_URL + "?" + urlencode(params)
  data, headers = request_json(url, token, accept_header=ACCEPT_HEADER)
  total = int(data.get("total_count", 0))
  respect_rate_limit(headers, min_delay)

  if total > 1000 and (end - start) > timedelta(hours=1):
    left, right = split_window(start, end)
    return (
      fetch_window(left[0], left[1], base_query, date_field, token, per_page, min_delay, max_pages, depth + 1) +
      fetch_window(right[0], right[1], base_query, date_field, token, per_page, min_delay, max_pages, depth + 1)
    )

  items = data.get("items", [])
  results = list(items)
  page = 1
  while len(items) == per_page and page < max_pages:
    page += 1
    params["page"] = page
    url = API_URL + "?" + urlencode(params)
    data, headers = request_json(url, token, accept_header=ACCEPT_HEADER)
    items = data.get("items", [])
    results.extend(items)
    respect_rate_limit(headers, min_delay)

  if total > 1000 and (end - start) <= timedelta(hours=1):
    print("warning: window still exceeds 1000 results, output may be truncated", file=sys.stderr)

  return results


def extract_commit(item):
  repo = item.get("repository") or {}
  commit = item.get("commit") or {}
  commit_author = commit.get("author") or {}
  commit_committer = commit.get("committer") or {}
  author = item.get("author") or {}

  return {
    "sha": item.get("sha"),
    "repo": repo.get("full_name"),
    "repo_url": repo.get("html_url"),
    "commit_url": item.get("html_url"),
    "message": commit.get("message"),
    "author_login": author.get("login"),
    "author_url": author.get("html_url"),
    "author_name": commit_author.get("name"),
    "author_date": commit_author.get("date"),
    "committer_date": commit_committer.get("date")
  }


def load_repo_cache(path):
  if not path or not os.path.exists(path):
    return {}
  try:
    with open(path, "r", encoding="utf-8") as f:
      data = json.load(f)
      return data if isinstance(data, dict) else {}
  except (OSError, json.JSONDecodeError):
    return {}


def save_repo_cache(path, cache):
  if not path:
    return
  try:
    with open(path, "w", encoding="utf-8") as f:
      json.dump(cache, f, indent=2)
  except OSError:
    pass


def extract_repo(repo_data, topics):
  owner = repo_data.get("owner") or {}
  license_obj = repo_data.get("license") or {}
  return {
    "full_name": repo_data.get("full_name"),
    "html_url": repo_data.get("html_url"),
    "description": repo_data.get("description"),
    "homepage": repo_data.get("homepage"),
    "topics": topics or repo_data.get("topics") or [],
    "language": repo_data.get("language"),
    "owner_login": owner.get("login"),
    "owner_type": owner.get("type"),
    "created_at": repo_data.get("created_at"),
    "updated_at": repo_data.get("updated_at"),
    "pushed_at": repo_data.get("pushed_at"),
    "stargazers_count": repo_data.get("stargazers_count"),
    "forks_count": repo_data.get("forks_count"),
    "archived": repo_data.get("archived"),
    "is_template": repo_data.get("is_template"),
    "license": license_obj.get("spdx_id")
  }


def fetch_repo(full_name, token, min_delay, include_topics):
  url = REPO_URL + full_name
  extra_headers = {"X-GitHub-Api-Version": REPO_API_VERSION}
  data, headers = request_json(url, token, accept_header=REPO_ACCEPT_HEADER, extra_headers=extra_headers)
  respect_rate_limit(headers, min_delay)
  topics = data.get("topics") or []
  if include_topics and not topics:
    topics_url = url + "/topics"
    tdata, theaders = request_json(topics_url, token, accept_header=REPO_ACCEPT_HEADER, extra_headers=extra_headers)
    respect_rate_limit(theaders, min_delay)
    topics = tdata.get("names") or []
  return extract_repo(data, topics)


def main():
  parser = argparse.ArgumentParser(description="Fetch GitHub commit search results and export JSON")
  parser.add_argument("--query", default="\"Sure! Pl\"", help="GitHub search query (default: \"Sure! Pl\")")
  parser.add_argument("--start", help="Start date YYYY-MM-DD (default: today-89)")
  parser.add_argument("--end", help="End date YYYY-MM-DD (default: today)")
  parser.add_argument("--date-field", choices=["committer", "author"], default="committer")
  parser.add_argument("--per-page", type=int, default=100)
  parser.add_argument("--min-delay", type=float, default=1.2)
  parser.add_argument("--max-pages", type=int, default=10)
  parser.add_argument("--out", default="surepl-commits.json")
  parser.add_argument("--enrich-repos", action="store_true", help="Fetch repo metadata for clustering")
  parser.add_argument("--repo-cache", default="surepl-repo-cache.json", help="Cache file for repo metadata")
  parser.add_argument("--max-repos", type=int, default=0, help="Limit repo enrichment (0 = no limit)")
  parser.add_argument("--skip-topics", action="store_true", help="Skip fetching repo topics if missing")
  parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
  args = parser.parse_args()

  today = datetime.now(timezone.utc)
  start_day = parse_day(args.start) if args.start else (today - timedelta(days=89)).replace(hour=0, minute=0, second=0, microsecond=0)
  end_day = parse_day(args.end) if args.end else today.replace(hour=0, minute=0, second=0, microsecond=0)
  if end_day < start_day:
    print("end date must be after start date", file=sys.stderr)
    sys.exit(1)

  if args.per_page < 1 or args.per_page > 100:
    print("per-page must be between 1 and 100", file=sys.stderr)
    sys.exit(1)

  if not args.token:
    print("warning: no GITHUB_TOKEN provided, expect heavy rate limiting", file=sys.stderr)
    if args.enrich_repos:
      print("warning: repo enrichment without a token will likely fail", file=sys.stderr)

  all_items = []
  current = start_day
  while current <= end_day:
    window_start, window_end = day_window(current)
    print(f"fetching {window_start.date().isoformat()}...")
    try:
      items = fetch_window(window_start, window_end, args.query, args.date_field, args.token, args.per_page, args.min_delay, args.max_pages)
    except HTTPError as err:
      body = err.read().decode("utf-8") if err.fp else ""
      print(f"HTTP error {err.code}: {body}", file=sys.stderr)
      sys.exit(1)
    except URLError as err:
      print(f"network error: {err}", file=sys.stderr)
      sys.exit(1)
    all_items.extend(items)
    current = current + timedelta(days=1)

  seen = set()
  commits = []
  for item in all_items:
    commit = extract_commit(item)
    key = (commit.get("repo") or "") + ":" + (commit.get("sha") or commit.get("commit_url") or "")
    if key in seen:
      continue
    seen.add(key)
    commits.append(commit)

  repos_payload = None
  if args.enrich_repos:
    repo_cache = load_repo_cache(args.repo_cache)
    repo_names = sorted({commit.get("repo") for commit in commits if commit.get("repo")})
    if args.max_repos and args.max_repos > 0:
      repo_names = repo_names[:args.max_repos]
    for repo_name in repo_names:
      if repo_name in repo_cache:
        continue
      print(f"enriching {repo_name}...")
      try:
        repo_cache[repo_name] = fetch_repo(repo_name, args.token, args.min_delay, not args.skip_topics)
      except HTTPError as err:
        body = err.read().decode("utf-8") if err.fp else ""
        if err.code in (403, 429):
          print(f"rate limit hit while fetching {repo_name}: {body}", file=sys.stderr)
          sys.exit(1)
        print(f"warning: repo fetch failed for {repo_name}: {err.code} {body}", file=sys.stderr)
      except URLError as err:
        print(f"network error while fetching {repo_name}: {err}", file=sys.stderr)
        sys.exit(1)
    save_repo_cache(args.repo_cache, repo_cache)
    repos_payload = [repo_cache[name] for name in repo_names if name in repo_cache]

  meta = {
    "source": "GitHub Search API (commits)",
    "query": args.query,
    "date_field": args.date_field,
    "start": start_day.date().isoformat(),
    "end": end_day.date().isoformat(),
    "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "notes": "Commit search is capped at 1000 results per query. This script splits time windows when needed."
  }
  if args.enrich_repos:
    meta["repo_enriched"] = len(repos_payload or [])
    meta["repo_cache"] = args.repo_cache
    meta["topics_included"] = not args.skip_topics

  payload = {"meta": meta, "commits": commits}
  if repos_payload is not None:
    payload["repos"] = repos_payload
  with open(args.out, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

  print(f"wrote {len(commits)} commits to {args.out}")


if __name__ == "__main__":
  main()
