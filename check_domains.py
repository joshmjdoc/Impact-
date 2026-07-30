#!/usr/bin/env python3
"""Check .com, .io, and .app availability against authoritative registry RDAP."""

from __future__ import annotations

import argparse
import csv
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

TLDS = ("com", "io", "app")
RDAP_BASES = {
    "com": "https://rdap.verisign.com/com/v1/",
    "io": "https://rdap.identitydigital.services/rdap/",
    "app": "https://rdap.nic.google/",
}
HEADERS = {
    "User-Agent": "ImpactHealth-DomainResearch/1.0 (domain availability research)",
    "Accept": "application/rdap+json, application/json;q=0.9, */*;q=0.1",
}
_thread_local = threading.local()


def session() -> requests.Session:
    value = getattr(_thread_local, "session", None)
    if value is None:
        value = requests.Session()
        value.headers.update(HEADERS)
        _thread_local.session = value
    return value


def rdap_url(tld: str, domain: str) -> str:
    return RDAP_BASES[tld].rstrip("/") + "/domain/" + quote(domain, safe=".-")


def dns_fallback(domain: str) -> tuple[str, str]:
    """Conservative fallback: DNS can confirm use, but not registrar inventory."""
    try:
        response = session().get(
            "https://dns.google/resolve",
            params={"name": domain, "type": "NS"},
            timeout=20,
        )
        if response.status_code != 200:
            return "unknown", f"doh_http_{response.status_code}"
        payload = response.json()
        status = payload.get("Status")
        answers = payload.get("Answer") or []
        authority = payload.get("Authority") or []
        if status == 0 and any(item.get("type") == 2 for item in answers):
            return "taken", "google_doh_ns"
        if status == 3 and any(item.get("type") == 6 for item in authority):
            return "likely_available", "google_doh_nxdomain"
        return "unknown", f"google_doh_status_{status}"
    except Exception as exc:
        return "unknown", f"google_doh_error:{type(exc).__name__}"


def check_domain(domain: str, tld: str) -> dict[str, str]:
    url = rdap_url(tld, domain)
    last_error = ""
    for attempt in range(6):
        try:
            if attempt == 0:
                time.sleep(random.uniform(0.0, 0.25))
            response = session().get(url, timeout=25, allow_redirects=True)
            code = response.status_code
            if code == 200:
                return {"status": "taken", "source": f"authoritative_rdap:{RDAP_BASES[tld]}", "http": "200"}
            if code == 404:
                return {"status": "available", "source": f"authoritative_rdap:{RDAP_BASES[tld]}", "http": "404"}
            if code in (429, 500, 502, 503, 504):
                last_error = f"http_{code}"
                time.sleep(min(25, (2 ** attempt) + random.uniform(0.3, 1.5)))
                continue
            last_error = f"http_{code}"
            break
        except requests.RequestException as exc:
            last_error = type(exc).__name__
            time.sleep(min(20, (2 ** attempt) + random.uniform(0.3, 1.2)))

    try:
        proxy = "https://rdap.org/domain/" + quote(domain, safe=".-")
        response = session().get(proxy, timeout=25, allow_redirects=True)
        if response.status_code == 200:
            return {"status": "taken", "source": "rdap.org_proxy", "http": "200"}
        if response.status_code == 404:
            return {"status": "available", "source": "rdap.org_proxy", "http": "404"}
    except requests.RequestException:
        pass

    status, source = dns_fallback(domain)
    return {"status": status, "source": f"{source};rdap_error={last_error}", "http": ""}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="candidate_pool.csv")
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-index", type=int, required=True)
    parser.add_argument("--batch-count", type=int, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))
    rows = [row for row in all_rows if (int(row["rank"]) - 1) % args.batch_count == args.batch_index]

    futures: dict[Any, tuple[int, str]] = {}
    results: dict[tuple[int, str], dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for row in rows:
            rank = int(row["rank"])
            label = row["label"].strip().lower()
            for tld in TLDS:
                futures[executor.submit(check_domain, f"{label}.{tld}", tld)] = (rank, tld)
        completed = 0
        for future in as_completed(futures):
            rank, tld = futures[future]
            try:
                results[(rank, tld)] = future.result()
            except Exception as exc:
                results[(rank, tld)] = {"status": "unknown", "source": f"worker_error:{type(exc).__name__}"}
            completed += 1
            if completed % 50 == 0 or completed == len(futures):
                print(f"batch {args.batch_index}: {completed}/{len(futures)}", flush=True)

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

    counts: dict[str, int] = {}
    for row in output_rows:
        for tld in TLDS:
            key = f"{tld}:{row[f'{tld}_status']}"
            counts[key] = counts.get(key, 0) + 1
    print(json.dumps({"batch": args.batch_index, "rows": len(output_rows), "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
