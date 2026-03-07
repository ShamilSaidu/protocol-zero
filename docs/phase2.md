# Phase 2 Notes

Phase 2 introduces the first working detection engine for Protocol Zero.

Implemented components:

- `monitoring.models`: incident and threshold data structures
- `monitoring.metrics_collector`: Prometheus queries for restart, CPU, memory, and unavailable replica metrics
- `monitoring.detector`: threshold-based incident generation
- `monitoring.service`: polling loop entrypoint
- `scripts/test_prometheus.py`: Prometheus connectivity smoke test
- `tests/test_detector.py`: unit coverage for incident generation

Current detector rules:

- pod restart loop when restart count is at least 3
- CPU spike when pod CPU usage is at least 85 percent
- memory spike when pod memory working set is at least 500 MB
- deployment unavailable when unavailable replicas is at least 1

Next likely extensions:

- deduplicate repeated incidents across polling windows
- enrich incidents with Kubernetes metadata and logs
- persist incidents to PostgreSQL
- expose detector output through the API/dashboard
