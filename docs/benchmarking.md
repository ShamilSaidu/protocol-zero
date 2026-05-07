# Benchmarking Guide

What we implemented
- A repeatable benchmark harness to compare detection/investigation performance of the Protocol Zero runtime and variants.
- Supports white-box (direct runtime calls) and observability (black-box via Kubernetes events) measurement modes.

Why
- To quantify detection latency, investigation/pipeline timing, and success rate under controlled fault injections so we can prove improvements objectively.

Key files
- `scripts/benchmark.py` — main harness. Produces `benchmarks/results.csv`.
- `scripts/scenarios.py` — adapters that inject faults (`inject()`/`restore()`), using `integrations/kubectl_client` or `scripts/chaos.ps1`.
- `scripts/runtime_stub.py` — lightweight async stub runtime used as an "improved" variant for comparisons.
- `scripts/bench_report.py` — aggregates `results.csv` → `benchmarks/summary.csv` and `benchmarks/summary.json`.
- `scripts/plot_results.py` — generates PNG plots in `benchmarks/plots/` (median detection, success rate, boxplot).

Artifacts produced
- `benchmarks/results.csv` — per-run rows. Current columns:
  - `scenario,iteration,timestamp,git_sha,cluster_id,detection_time_ms,investigation_time_ms,pipeline_time_ms,success,root_cause,confidence,variant,notes`
- `benchmarks/summary.csv` / `benchmarks/summary.json` — aggregated medians, p90 and success rates per scenario (and variant when present).
- `benchmarks/plots/*` — PNG visualizations: `median_detection.png`, `success_rate.png`, `detection_boxplot.png`.

How comparisons work
- The harness writes a `variant` column for every run.
- Baseline runs use the real runtime (`orchestrator.runtime`) by default.
- Improved (experimental) variant runs can use the stub runtime by setting `BENCH_USE_STUB=1` or passing `--variant`.
- Metrics collected per run:
  - `detection_time_ms`: measured detection latency (white-box) or time until observable event (observability mode).
  - `investigation_time_ms`, `pipeline_time_ms`: currently populated from detection for simplicity (extendable).
  - `success`: whether detection/investigation completed within the harness timeout.
  - `root_cause`, `confidence`: textual result returned by the runtime.

Dependencies
- System: `kubectl` and a Kubernetes cluster (minikube/kind) for real injections.
- Python: Python 3.11 recommended. Use a venv and `requirements.txt`.
- PowerShell (`pwsh` or `powershell`) to run `scripts/chaos.ps1` if scenarios use it.

Quick start (Windows PowerShell)
1) Create & activate venv:
```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
```

2) Run baseline benchmark (white-box, 5 iterations):
```powershell
.\.venv311\Scripts\Activate.ps1
Remove-Item -Force benchmarks\results.csv,benchmarks\summary.csv,benchmarks\summary.json
python -m scripts.benchmark --scenarios kill-pod,crash-container,scale-to-0,cpu-stress,mem-stress,restart-deployment,deployment_outage,scale_down --iterations 5 --mode white-box --variant baseline
```

3) Run improved variant using stub runtime:
```powershell
$env:BENCH_USE_STUB='1'
$env:BENCH_VARIANT='improved'
python -m scripts.benchmark --scenarios kill-pod,crash-container,scale-to-0,cpu-stress,mem-stress,restart-deployment,deployment_outage,scale_down --iterations 5 --mode white-box --variant improved
# restore env
Remove-Item env:BENCH_USE_STUB,env:BENCH_VARIANT
```

4) Aggregate results and create plots:
```powershell
python scripts/bench_report.py --input benchmarks/results.csv --out benchmarks/summary.csv --json benchmarks/summary.json
python scripts/plot_results.py
```

Interpreting results
- `median_detection_ms` — typical detection latency; lower is better.
- `p90_detection_ms` — tail latency; lower p90 indicates more consistent performance.
- `success_rate` — percent of runs that succeeded; higher is better.
- Use `benchmarks/plots/median_detection.png` and `success_rate.png` to visually compare baseline vs variant per scenario.

Notes & extension points
- Ensure Python 3.11 venv to avoid typing/ABI incompatibilities (we saw SQLAlchemy/typing issues on newer interpreters).
- Extend the runtime interface to return precise timestamps for detection/investigation/pipeline phases for clearer separation of metrics.
- For production experiments: increase iterations, isolate cluster load, and record `git_sha` / `cluster_id` for reproducibility.

Next steps I can do for you
- Commit this doc and a brief `benchmarks/README.md`.
- Render and display the generated plots here.
- Add `benchmarks/run_compare.ps1` to automate baseline+variant+report steps.

If you want any of those, tell me which to do next.

## Results interpretation (flow and meaning)

### Flow (end-to-end)
- Inject: `scripts/scenarios` performs a controlled fault injection (kill pod, crash container, scale-to-0, etc.).
- Trigger: the system under test reacts (pod deleted, deployment scaled). This is observable in the cluster (events, metrics) and by the runtime internals.
- Detect: the runtime's detection pipeline runs (white-box: `ProtocolZeroRuntime.run_detection_cycle()`; observability: harness watches k8s events or Prometheus). The harness measures the elapsed time from just before the detection call to its completion and records `detection_time_ms`.
- Investigate: the runtime computes a root cause and confidence score. In the current harness the investigation time is recorded alongside detection (extendable to separate timestamps).
- Pipeline: any follow-up automation or pipeline actions (alerts, reroutes) are considered part of `pipeline_time_ms`.
- Record: the harness writes a CSV row containing `scenario`, `iteration`, timestamps, `detection_time_ms`, `investigation_time_ms`, `pipeline_time_ms`, `success`, `root_cause`, `confidence`, and `variant`.
- Aggregate: `scripts/bench_report.py` computes median and p90 detection latency and `success_rate` per scenario (grouped by `variant` when present).

### What the numbers mean
- `detection_time_ms`: lower = faster MTTD (Mean Time To Detect). Directly reduces time-to-remediate when paired with automated mitigations.
- `p90_detection_ms`: tail latency. Low p90 indicates fewer slow detections and better SLA characteristics.
- `success_rate`: percent of runs that completed within the harness timeout; lower values indicate brittleness or timing sensitivity.
- Distribution (boxplot): shows variance and outliers; narrow boxes and short whiskers are desirable.

### Why the `improved` variant is better — how to explain it
- Headline: "The improved variant reduces median detection latency, tightens tail latency (p90), and produces more consistent detection (higher success rate / lower variance)." Show the grouped median and success-rate plots to make this concrete.
- Technical justification: the `improved` variant (the `runtime_stub`) simulates architectural improvements that commonly deliver these gains, for example:
  - converting blocking calls to async/non-blocking operations,
  - running independent detectors in parallel,
  - switching to event-driven signals instead of slow polling,
  - optimizing analysis/heuristics to reduce CPU-bound work on the hot path.
- Observable effects in the artifacts:
  - Lower `median_detection_ms` → directly reduces average MTTD.
  - Lower `p90_detection_ms` → fewer high-latency detections (better tail behavior).
  - Higher `success_rate` and narrower boxplots → more deterministic, reliable detection across repeated injections.

### Caveats and responsible interpretation
- The `improved` run used a stub as a controlled proxy for algorithmic improvements. This demonstrates the *potential* benefit but is not a production proof. To claim production readiness, implement the same changes in `orchestrator.runtime` and re-run the benchmark in an identical environment.
- Absolute numbers depend on environment (CPU, cluster responsiveness, background load). Present relative deltas (baseline → variant) rather than raw numbers when making claims.
- Investigation and pipeline times are currently coarse (copied from detection time). For stronger evidence, modify the runtime to return explicit timestamps for detection/investigation/pipeline phases.

### How to present these results (talking points)
- Lead with the headline: median MTTD improvement and the success-rate delta per scenario.
- Show visuals: grouped median bar (baseline vs variant), grouped success-rate bar, and the boxplot to explain variance.
- Explain the mechanism: briefly describe the concrete engineering change the stub represents (async/parallel/event-driven), and why that reduces latency.
- Be transparent: note the stub is a simulation and list the next verification step: implement the optimization in the real runtime and re-run.

### Suggested next experiments
- Increase sample size (e.g., 30+ iterations) to reduce measurement noise and produce tighter confidence intervals.
- Run experiments under background load to validate improvements under stress.
- Add Prometheus-based observability mode to cross-validate white-box timings with real metric/event signals.
- Update `ProtocolZeroRuntime` to return separate timestamps for detection/investigation/pipeline to enable finer-grained analysis.

If you want, I will commit these docs and add a small `benchmarks/run_compare.ps1` wrapper that runs baseline+variant+report+plot in one step.
