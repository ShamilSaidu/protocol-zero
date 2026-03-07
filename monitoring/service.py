"""Phase 2 entrypoint for polling Prometheus and printing incidents."""

from __future__ import annotations

import json
import os
import time

from dotenv import load_dotenv

from monitoring.detector import IncidentDetector


def main() -> None:
    load_dotenv()
    detector = IncidentDetector()
    interval = int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))

    print(f"[Detector] Starting Protocol Zero detection loop (interval={interval}s)")
    while True:
        incidents = detector.collect_and_detect()
        if incidents:
            for incident in incidents:
                print(f"[Detector] INCIDENT: {json.dumps(incident)}")
        else:
            print("[Detector] No incidents detected in this interval.")
        time.sleep(interval)


if __name__ == "__main__":
    main()
