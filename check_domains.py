#!/usr/bin/env python3
"""Bulk-check .com, .io, and .app using RDAP/WHOIS registry aggregation."""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

TLDS = ("com", "io", "app")
API_BASE = "https://rdap.cloud/api/v1/"
HEADERS = {
    "User-Agent": "ImpactHealth-DomainResearch/1.0",
    "Accept": "application/json",
}


def chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def fetch_chunk(domains: list[str]) -> dict[str, dict[str, str]]:
    url = API_BASE + quote(",".join(domains), safe=".,-")
    last_error = ""
    for attempt in range(7):
        try:
            time.sleep(random.uniform(0.0, 0.15))
            response = requests.get(url, headers=HEADERS, timeout=60)
            if response.status_code == 200:
                payload = response.json()
                raw_results = payload.get("results", {})
                output: dict[str, dict[str, str]] = {}
                for domain in domains:
                    item = raw_results.get(domain) or raw_results.get(domain.lower()) or {}
                    success = item.get("success")
                    message = str(item.get("message", ""))
                    if success is True and item.get("data"):
                        output[domain] = {"status": "taken", "source": "rdap.cloud_registry_lookup"}
                    elif success is False and "does not appear to be a registered domain" in message.lower():
                        output[domain] = {"status": "available", "source": "rdap.cloud_registry_lookup"}
                    elif success is False and "does not appear to be a registered domain name" in message.lower():
                        output[domain] = {"status": "available", "source": "rdap.cloud_registry_lookup"}
                    else:
                        output[domain] = {"status": "unknown", "source": f"rdap.cloud:{message or 'unrecognized_response'}"}
                return output
            last_error = f"http_{response.status_code}"
            if response.status_code not in (429, 500, 502, 503, 504):
                break
        except (requests.RequestException, ValueError) as exc:
            last_error = type(exc).__name__
        time.sleep(min(35, (2 ** attempt) + random.uniform(0.5, 2.0)))
    return {domain: {"status": "unknown", "source": f"rdap.cloud_error:{last_error}"} for domain in domains}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="candidate_pool.csv")
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-index", type=int, required=True)
    parser.add_argument("--batch-count", type=int, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))
    rows = [row for row in all_rows if (int(row["rank"]) - 1) % args.batch_count == args.batch_index]

    domains = []
    domain_keys = {}
    for row in rows:
        rank = int(row["rank"])
        label = row["label"].strip().lower()
        for tld in TLDS:
            domain = f"{label}.{tld}"
            domains.append(domain)
            domain_keys[domain] = (rank, tld)

    results_by_domain: dict[str, dict[str, str]] = {}
    domain_chunks = list(chunks(domains, 10))
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(fetch_chunk, chunk): chunk for chunk in domain_chunks}
        completed = 0
        for future in as_completed(future_map):
            chunk = future_map[future]
            try:
                results_by_domain.update(future.result())
            except Exception as exc:
                for domain in chunk:
                    results_by_domain[domain] = {"status": "unknown", "source": f"worker_error:{type(exc).__name__}"}
            completed += 1
            if completed % 10 == 0 or completed == len(domain_chunks):
                print(f"batch {args.batch_index}: {completed}/{len(domain_chunks)} API batches", flush=True)

    results = {}
    for domain, key in domain_keys.items():
        results[key] = results_by_domain.get(domain, {"status": "unknown", "source": "missing_result"})

    checked = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    fields = [
        "rank", "display", "label", "category", "score",
        "com_status", "io_status", "app_status",
        "com_source", "io_source", "app_source", "checked_utc",
    ]
    output_rows = []
    for row in sorted(rows, key=lambda item: int(item["rank"])):
        rank = int(row["rank"])
        output = {key: row[key] for key in ("rank", "display", "label", "category", "score")}
        output["checked_utc"] = checked
        for tld in TLDS:
            result = results.get((rank, tld), {"status": "unknown", "source": "missing_result"})
            output[f"{tld}_status"] = result.get("status", "unknown")
            output[f"{tld}_source"] = result.get("source", "")
        output_rows.append(output)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    counts = {}
    for row in output_rows:
        for tld in TLDS:
            key = f"{tld}:{row[f'{tld}_status']}"
            counts[key] = counts.get(key, 0) + 1
    print(json.dumps({"batch": args.batch_index, "rows": len(output_rows), "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
