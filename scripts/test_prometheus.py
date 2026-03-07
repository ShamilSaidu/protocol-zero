#!/usr/bin/env python3
"""Quick connectivity test for Prometheus-backed detection."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitoring.metrics_collector import MetricsCollector


def main() -> int:
    load_dotenv()
    collector = MetricsCollector()
    snapshot = collector.collect()

    print("Prometheus snapshot collected successfully.")
    print(f"  pod_restarts: {len(snapshot.pod_restarts)} series")
    print(f"  cpu_usage_pct: {len(snapshot.cpu_usage_pct)} series")
    print(f"  memory_usage_mb: {len(snapshot.memory_usage_mb)} series")
    print(f"  unavailable_replicas: {len(snapshot.unavailable_replicas)} series")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
