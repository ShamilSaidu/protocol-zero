"""Simple reporting utilities for benchmark results.

Produces `benchmarks/summary.csv` and `benchmarks/summary.json` from results CSV.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from statistics import median
from typing import List, Dict


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_json(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def summarize(rows: List[Dict[str, str]]):
    by_scenario = {}
    for r in rows:
        s = r["scenario"]
        by_scenario.setdefault(s, []).append(r)

    summary = []
    for s, rs in by_scenario.items():
        nums = [int(r.get("detection_time_ms") or 0) for r in rs]
        succ = [r for r in rs if (r.get("success") or "False").lower() in ("true", "1")]
        obj = {
            "scenario": s,
            "count": len(rs),
            "median_detection_ms": int(median(nums)) if nums else None,
            "p90_detection_ms": int(sorted(nums)[max(0, int(len(nums) * 0.9) - 1)]) if nums else None,
            "success_rate": round(100.0 * len(succ) / len(rs), 2) if rs else 0.0,
        }
        summary.append(obj)
    return summary


def write_summary_csv(path: str, summary):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        for s in summary:
            writer.writerow(s)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="benchmarks/summary.csv")
    parser.add_argument("--json", default="benchmarks/summary.json")
    args = parser.parse_args(argv)

    rows = read_csv(args.input)
    summary = summarize(rows)
    write_summary_csv(args.out, summary)
    write_json(args.json, summary)
    print(f"Wrote summary to {args.out} and {args.json}")


if __name__ == "__main__":
    main()
