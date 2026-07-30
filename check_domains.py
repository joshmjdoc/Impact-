#!/usr/bin/env python3
"""Check .com, .io, and .app availability against authoritative RDAP registries."""

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
IANA_BOOTSTRAP = "https://data.iana.org/rdap/dns.json"
HEADERS = {
    "User-Agent": "ImpactHealth-DomainResearch/1.0 (domain availability research)",
    "Accept": "application/rdap+json, application/json;q=0.9, */*;q=0.1",
}
FALLBACK_RDAP = {
    "com": "https://rdap.verisign.com/com/v1/",
    "app": "https://rdap.nic.google/",
}
_thread_local = threading.local()


def session() -> requests.Session:
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        _thread_local.session = s
    return s


def fetch_rdap_map() -> dict[str, str]:
    response = requests.get(IANA_BOOTSTRAP, headers=HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    mapping: dict[str, str] = {}
    for tlds, servers in payload.get("services", []):
        if not servers:
            continue
        base = str(servers[0]).rstrip("/") + "/"
        for tld in tlds:
            mapping[str(tld).lower()] = base
    for tld, base in FALLBACK_RDAP.items():
        mapping.setdefault(tld, base)
    return mapping


def query_url(base: str, domain: str) -> str:
    return base.rstrip("/") + "/domain/" + quote(domain, safe=".-")


def google_doh(domain: str) -> tuple[str, str]:
    """Conservative DNS fallback. Never labels DNS-only NXDOMAIN as confirmed available."""
    try:
        response = session().get(
            "https://dns.google/resolve",
            params={"name": domain, "type": "NS"},
            timeout=20,
        )
        if response.status_code != 200:
            return "unknown", f"doh_http_{response.status_code}"
        data = response.json()
        status = data.get("Status")
        answers = data.get("Answer") or []
        authority = data.get("Authority") or []
        has_ns = any(item.get("type") == 2 for item in answers)
        has_soa = any(item.get("type") == 6 for item in authority)
        if status == 0 and has_ns:
            return "taken", "google_doh_ns"
        if status == 3 and has_soa:
            return "likely_available", "google_doh_nxdomain"
        return "unknown", f"google_doh_status_{status}"
    except Exception as exc:
        return "unknown", f"google_doh_error:{type(exc).__name__}"


def check_domain(domain: str, base: str | None) -> dict[str, str]:
    if not base:
        return {"status": "unknown", "source": "no_rdap_server", "http": ""}

    url = query_url(base, domain)
    last_error = ""
    for attempt in range(5):
        try:
            if attempt == 0:
                time.sleep(random.uniform(0.0, 0.18))
            response = session().get(url, timeout=25, allow_redirects=True)
            code = response.status_code
            if code == 200:
                return {"status": "taken", "source": f"authoritative_rdap:{base}", "http": "200"}
            if code == 404:
                return {"status": "available", "source": f"authoritative_rdap:{base}", "http": "404"}
            if code in (429, 500, 502, 503, 504):
                wait = min(18, (2 ** attempt) + random.uniform(0.2, 1.2))
                last_error = f"http_{code}"
                time.sleep(wait)
                continue
            last_error = f"http_{code}"
            break
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}"
            time.sleep(min(15, (2 ** attempt) + random.uniform(0.2, 1.0)))

    try:
        proxy = "https://rdap.org/domain/" + quote(domain, safe=".-")
        response = session().get(proxy, timeout=25, allow_redirects=True)
        if response.status_code == 200:
            return {"status": "taken", "source": "rdap.org_proxy", "http": "200"}
        if response.status_code == 404:
            return {"status": "available", "source": "rdap.org_proxy", "http": "404"}
    except requests.RequestException:
        pass

    dns_status, dns_source = google_doh(domain)
    return {
        "status": dns_status,
        "source": f"{dns_source};rdap_error={last_error}",
        "http": "",
    }


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

    rows = [
        row for row in all_rows
        if (int(row["rank"]) - 1) % args.batch_count == args.batch_index
    ]

    rdap_map = fetch_rdap_map()
    missing = [tld for tld in TLDS if not rdap_map.get(tld)]
    if missing:
        raise RuntimeError(f"IANA RDAP bootstrap had no server for: {missing}")

    tasks: dict[Any, tuple[int, str, str]] = {}
    results: dict[tuple[int, str], dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for row in rows:
            rank = int(row["rank"])
            label = row["label"].strip().lower()
            for tld in TLDS:
                domain = f"{label}.{tld}"
                future = executor.submit(check_domain, domain, rdap_map.get(tld))
                tasks[future] = (rank, tld, domain)

        completed = 0
        for future in as_completed(tasks):
            rank, tld, domain = tasks[future]
            try:
                outcome = future.result()
            except Exception as exc:
                outcome = {
                    "status": "unknown",
                    "source": f"worker_error:{type(exc).__name__}",
                    "http": "",
                }
            results[(rank, tld)] = outcome
            completed += 1
            if completed % 50 == 0 or completed == len(tasks):
                print(f"batch {args.batch_index}: {completed}/{len(tasks)} lookups complete", flush=True)

    checked = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    fieldnames = [
        "rank", "display", "label", "category", "score",
        "com_status", "io_status", "app_status",
        "com_source", "io_source", "app_source",
        "checked_utc",
    ]
    output_rows: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda item: int(item["rank"])):
        rank = int(row["rank"])
        output = {
            "rank": row["rank"],
            "display": row["display"],
            "label": row["label"],
            "category": row["category"],
            "score": row["score"],
            "checked_utc": checked,
        }
        for tld in TLDS:
            outcome = results.get((rank, tld), {"status": "unknown", "source": "missing_result"})
            output[f"{tld}_status"] = outcome.get("status", "unknown")
            output[f"{tld}_source"] = outcome.get("source", "")
        output_rows.append(output)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    counts: dict[str, int] = {}
    for output in output_rows:
        for tld in TLDS:
            key = f"{tld}:{output[f'{tld}_status']}"
            counts[key] = counts.get(key, 0) + 1
    print(json.dumps({"batch": args.batch_index, "rows": len(output_rows), "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
