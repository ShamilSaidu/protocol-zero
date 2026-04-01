# MVP Overview

Protocol Zero now includes the phases beyond detection as a durable MVP:

- multi-agent investigation
- reasoning and correlation workflow
- safe remediation planning
- code-fix artifact generation with optional GitHub PR creation
- post-mortem generation
- API and dashboard layer
- chaos script for failure injection
- end-to-end dry-run test coverage

## Important runtime notes

- If Docker Desktop or the PostgreSQL container is unavailable, the app falls back to `protocol_zero.db` via SQLite.
- Prometheus-backed detection requires the Prometheus service to be reachable at `PROMETHEUS_URL`.
- Actual GitHub PR creation is opt-in through `ALLOW_GITHUB_WRITE=true`.
- Remediation defaults to dry-run mode until you explicitly change `.env`.
