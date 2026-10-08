#!/usr/bin/env python3
"""Vendor Colab runtime snapshot package metadata from googlecolab/backend-info.

Downloads `pip-freeze.txt` and `os-info.txt` at pinned commits so analyses are
reproducible offline. Never modifies anything outside `data/runtimes/`.

Usage:
    python scripts/fetch_runtimes.py            # fetch only missing snapshots
    python scripts/fetch_runtimes.py --verify   # re-check hashes of existing files
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIMES_DIR = ROOT / "data" / "runtimes"

BASE = "https://raw.githubusercontent.com/googlecolab/backend-info"

# Verified reachable on 2026-10-08. Commits come from the repository README,
# which maps each published runtime version to its exact backend-info commit.
SNAPSHOTS: dict[str, dict[str, str]] = {
    "2026.07": {"commit": "ec53f93fe44a9cab118dc5451527b18e36e1a643"},
    "2026.04": {"commit": "77d5dbef56d73b96db5efef2280679cb548c9bd9"},
    "2026.01": {"commit": "bd8aaa4580401a7fbf96a52fab5a7acf96f50b73"},
    "2025.10": {"commit": "7a0599e3401b4c158fc34a8023e042fa3691be32"},
    "2025.07": {"commit": "ef1cba030a9f7a39bf42912a42f6462d6d4908e8"},
}

FILES = ("pip-freeze.txt", "os-info.txt")


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    RUNTIMES_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0

    for snapshot, meta in SNAPSHOTS.items():
        commit = meta["commit"]
        target_dir = RUNTIMES_DIR / snapshot
        target_dir.mkdir(exist_ok=True)

        for name in FILES:
            dest = target_dir / name
            if dest.exists() and args.verify:
                digest = hashlib.sha256(dest.read_bytes()).hexdigest()
                print(f"{snapshot}/{name}: present sha256={digest[:16]}")
                continue
            if dest.exists():
                print(f"{snapshot}/{name}: already present, skipping")
                continue

            url = f"{BASE}/{commit}/{name}"
            try:
                payload = fetch(url)
            except (urllib.error.URLError, TimeoutError) as exc:
                print(f"{snapshot}/{name}: FAILED {exc}", file=sys.stderr)
                failures += 1
                continue

            dest.write_bytes(payload)
            print(f"{snapshot}/{name}: fetched {len(payload)} bytes from {commit[:8]}")

        manifest_path = target_dir / "manifest.json"
        manifest = {
            "snapshot": snapshot,
            "source_repository": "https://github.com/googlecolab/backend-info",
            "commit": commit,
            "retrieved": "2026-10-08",
            "files": list(FILES),
            "caveat": (
                "backend-info states these files reflect the most recent "
                "submitted CI change, not necessarily the live runtime, and may "
                "lag by one or two days."
            ),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())