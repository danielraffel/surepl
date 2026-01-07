#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.server
import os
import sys
import urllib.request

ASSET_URLS = {
    "asciinema-player.min.js": "https://cdn.jsdelivr.net/npm/asciinema-player@3.14.0/dist/bundle/asciinema-player.min.js",
    "asciinema-player.css": "https://cdn.jsdelivr.net/npm/asciinema-player@3.14.0/dist/bundle/asciinema-player.css",
}


def ensure_assets(fetch: bool) -> None:
    if not fetch:
        return
    for name, url in ASSET_URLS.items():
        if os.path.exists(name):
            continue
        try:
            print(f"Downloading {name}...")
            with urllib.request.urlopen(url, timeout=20) as resp:
                data = resp.read()
            with open(name, "wb") as f:
                f.write(data)
            print(f"Saved {name}")
        except Exception as exc:
            print(f"Warning: failed to download {name}: {exc}")


def run_server(port: int) -> None:
    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.ThreadingHTTPServer(("", port), handler)
    print(f"Serving on http://localhost:{port}/index.html")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the asciinema-ghost tool")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on")
    parser.add_argument("--no-fetch", action="store_true", help="Do not download player assets")
    args = parser.parse_args()

    ensure_assets(fetch=not args.no_fetch)
    run_server(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
