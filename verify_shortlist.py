#!/usr/bin/env python3
"""Verify shortlisted domains directly against authoritative RDAP registries."""

from __future__ import annotations

import argparse
import csv
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

TLDS = ("com", "io", "app")
RDAP_BASES = {
    "com": "https://rdap.verisign.com/com/v1/",
    "io": "https://rdap.identitydigital.services/rdap/",
    "app": "https://rdap.nic.google/",
}
HEADERS = {
    "User-Agent": "ImpactHealth-DomainResearch/1.0",
    "Accept": "application/rdap+json, application/json;q=0.9, */*;q=0.1",
}


def verify(domain: str, tld: str) -> tuple[str, str]:
    url = RDAP_BASES[tld].rstrip("/") + "/domain/" + quote(domain, safe=".-")
    last = ""
    for attempt in range(5):
        try:
            time.sleep(random.uniform(0.04, 0.13))
            response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
            if response.status_code == 200:
                return "taken", url
            if response.status_code == 404:
                return "available", url
            last = f"http_{response.status_code}"
            if response.status_code not in (429, 500, 502, 503, 504):
                break
        except requests.RequestException as exc:
            last = type(exc).__name__
        time.sleep(min(18, (2 ** attempt) + random.uniform(0.3, 1.0)))
    return "unknown", f"{url};error={last}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="shortlist_400.csv")
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-index", type=int, required=True)
    parser.add_argument("--batch-count", type=int, required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))
    rows = [row for row in all_rows if (int(row["rank"]) - 1) % args.batch_count == args.batch_index]

    futures = {}
    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for row in rows:
            rank = int(row["rank"])
            for tld in TLDS:
                domain = f"{row['label']}.{tld}"
                futures[executor.submit(verify, domain, tld)] = (rank, tld)
        done = 0
        for future in as_completed(futures):
            rank, tld = futures[future]
            try:
                results[(rank, tld)] = future.result()
            except Exception as exc:
                results[(rank, tld)] = ("unknown", f"worker_error:{type(exc).__name__}")
            done += 1
            if done % 25 == 0 or done == len(futures):
                print(f"batch {args.batch_index}: {done}/{len(futures)}", flush=True)

    checked = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    fields = [
        "rank", "display", "label",
        "com_status", "io_status", "app_status",
        "com_source", "io_source", "app_source", "checked_utc",
    ]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in sorted(rows, key=lambda value: int(value["rank"])):
            rank = int(row["rank"])
            out = {"rank": row["rank"], "display": row["display"], "label": row["label"], "checked_utc": checked}
            for tld in TLDS:
                status, source = results.get((rank, tld), ("unknown", "missing_result"))
                out[f"{tld}_status"] = status
                out[f"{tld}_source"] = source
            writer.writerow(out)


if __name__ == "__main__":
    main()
