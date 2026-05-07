import os
import csv
import subprocess
import sys


def test_benchmark_dry_run(tmp_path):
    out = tmp_path / "results.csv"
    cmd = [sys.executable, "-m", "scripts.benchmark", "--scenarios", "kill-pod", "--iterations", "2", "--dry-run", "--output", str(out)]
    subprocess.check_call(cmd)
    assert out.exists()
    with open(out, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2
