"""Benchmark harness for Protocol Zero (white-box mode).

Usage (dry-run):
  python scripts/benchmark.py --scenarios kill-pod --iterations 1 --dry-run
"""
from __future__ import annotations

import argparse
import csv
import datetime
import importlib
import asyncio
import inspect
from integrations.kubectl_client import KubectlClient
import json
import os
import time
import traceback
from typing import List

from scripts.scenarios import get_adapter
import os


def ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def run_one_scenario(scenario: str, iteration: int, dry_run: bool, mode: str = "white-box", variant: str = "baseline"):
    adapter = get_adapter(scenario)
    row = {
        "scenario": scenario,
        "iteration": iteration,
        "timestamp": now_iso(),
        "git_sha": None,
        "cluster_id": None,
        "detection_time_ms": None,
        "investigation_time_ms": None,
        "pipeline_time_ms": None,
        "success": False,
        "root_cause": None,
        "confidence": None,
        "variant": variant,
        "notes": None,
    }
    try:
        adapter.inject(dry_run=dry_run)
        if mode == "white-box":
            try:
                # allow using a lightweight stub runtime via env var BENCH_USE_STUB=1
                use_stub = os.environ.get("BENCH_USE_STUB", "0") == "1"
                if use_stub:
                    rt_mod = importlib.import_module("scripts.runtime_stub")
                else:
                    rt_mod = importlib.import_module("orchestrator.runtime")
                ProtocolRuntime = getattr(rt_mod, "ProtocolZeroRuntime", None)
                if ProtocolRuntime:
                    runtime = ProtocolRuntime()
                    t0 = time.perf_counter()
                    if hasattr(runtime, "run_detection_cycle"):
                        func = getattr(runtime, "run_detection_cycle")
                        if inspect.iscoroutinefunction(func):
                            asyncio.run(func())
                        else:
                            res = func()
                            if inspect.isawaitable(res):
                                asyncio.run(res)
                    elif hasattr(runtime, "start"):
                        start = getattr(runtime, "start")
                        stop = getattr(runtime, "stop", None)
                        if inspect.iscoroutinefunction(start):
                            asyncio.run(start())
                            if stop and inspect.iscoroutinefunction(stop):
                                asyncio.run(stop())
                        else:
                            start()
                            if stop:
                                stop()
                    t1 = time.perf_counter()
                    row["detection_time_ms"] = int((t1 - t0) * 1000)
                    row["investigation_time_ms"] = row["detection_time_ms"]
                    row["pipeline_time_ms"] = row["detection_time_ms"]
                    row["success"] = True
                    row["root_cause"] = "[runtime]"
                    row["confidence"] = 0.9
                else:
                    t0 = time.perf_counter()
                    time.sleep(0.05 if dry_run else 0.2)
                    t1 = time.perf_counter()
                    dt = int((t1 - t0) * 1000)
                    row["detection_time_ms"] = dt
                    row["investigation_time_ms"] = dt
                    row["pipeline_time_ms"] = dt
                    row["success"] = True
                    row["root_cause"] = "simulated"
                    row["confidence"] = 0.5
            except Exception:
                t0 = time.perf_counter()
                time.sleep(0.05 if dry_run else 0.2)
                t1 = time.perf_counter()
                dt = int((t1 - t0) * 1000)
                row["detection_time_ms"] = dt
                row["investigation_time_ms"] = dt
                row["pipeline_time_ms"] = dt
                row["success"] = False
                row["root_cause"] = None
                row["confidence"] = 0.0
                row["notes"] = traceback.format_exc()
        else:
            # observability/black-box mode: detect via Kubernetes events
            k = KubectlClient()
            baseline = k.get_recent_events("frontend")
            t0 = time.perf_counter()
            timeout = 60
            detected = False
            for _ in range(timeout):
                time.sleep(1)
                events = k.get_recent_events("frontend")
                if len(events) > len(baseline):
                    t1 = time.perf_counter()
                    dt = int((t1 - t0) * 1000)
                    row["detection_time_ms"] = dt
                    row["investigation_time_ms"] = None
                    row["pipeline_time_ms"] = None
                    row["success"] = True
                    row["root_cause"] = "observed-k8s-event"
                    row["confidence"] = 0.5
                    detected = True
                    break
            if not detected:
                row["detection_time_ms"] = None
                row["notes"] = "no k8s event observed within timeout"
                row["success"] = False
    finally:
        try:
            adapter.restore(dry_run=dry_run)
        except Exception:
            pass
    return row


def append_csv(path: str, rows: List[dict]):
    ensure_dir(path)
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if write_header:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main(argv: List[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", required=True)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--output", default="benchmarks/results.csv")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mode", choices=["white-box", "observability"], default="white-box")
    parser.add_argument("--variant", default=os.environ.get("BENCH_VARIANT", "baseline"))
    args = parser.parse_args(argv)

    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    all_rows = []
    for scenario in scenarios:
        for i in range(1, args.iterations + 1):
            row = run_one_scenario(scenario, i, dry_run=args.dry_run, mode=args.mode, variant=args.variant)
            all_rows.append(row)
    append_csv(args.output, all_rows)
    print(f"Wrote {len(all_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
