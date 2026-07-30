#!/usr/bin/env python3
"""Verify .io availability directly against the authoritative Identity Digital RDAP server."""

import argparse
import csv
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

BASE = "https://rdap.identitydigital.services/rdap/domain/"
HEADERS = {"User-Agent": "ImpactHealth-DomainResearch/1.0", "Accept": "application/rdap+json, application/json"}


def verify(domain: str):
    url = BASE + quote(domain, safe=".-")
    last = ""
    for attempt in range(6):
        try:
            time.sleep(random.uniform(0.06, 0.16))
            response = requests.get(url, headers=HEADERS, timeout=20)
            if response.status_code == 200:
                return "taken", url
            if response.status_code == 404:
                return "available", url
            last = f"http_{response.status_code}"
            if response.status_code not in (429, 500, 502, 503, 504):
                break
        except requests.RequestException as exc:
            last = type(exc).__name__
        time.sleep(min(20, (2 ** attempt) + random.uniform(0.2, 0.8)))
    return "unknown", f"{url};error={last}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="shortlist_400.csv")
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-index", type=int, required=True)
    parser.add_argument("--batch-count", type=int, required=True)
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))
    rows = [row for row in all_rows if (int(row["rank"]) - 1) % args.batch_count == args.batch_index]
    checked = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rank", "display", "label", "io_status", "io_source", "checked_utc"])
        writer.writeheader()
        for index, row in enumerate(rows, 1):
            status, source = verify(f"{row['label']}.io")
            writer.writerow({"rank": row["rank"], "display": row["display"], "label": row["label"], "io_status": status, "io_source": source, "checked_utc": checked})
            if index % 10 == 0 or index == len(rows):
                print(f"batch {args.batch_index}: {index}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
