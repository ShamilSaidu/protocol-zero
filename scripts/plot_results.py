"""Generate PNG plots from benchmark results.

Produces `benchmarks/plots/median_detection.png` and
`benchmarks/plots/success_rate.png` and `benchmarks/plots/detection_boxplot.png`.
"""
from __future__ import annotations

import os
import pandas as pd
import matplotlib.pyplot as plt


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def plot_median_detection(df: pd.DataFrame, out_path: str):
    # support multiple possible column names
    for col in ('detection_time_ms', 'detection_time', 'total_time'):
        if col in df.columns:
            numcol = col
            break
    else:
        raise RuntimeError('No detection time column found')
    summary = pd.to_numeric(df[numcol], errors='coerce').groupby(df['scenario']).median().sort_values()
    ensure_dir(os.path.dirname(out_path))
    # if variant column exists, plot grouped bars by variant
    if 'variant' in df.columns:
        med = pd.to_numeric(df[numcol], errors='coerce').groupby([df['scenario'], df['variant']]).median().unstack(fill_value=0)
        ax = med.plot.bar(figsize=(10, 5), title='Median Detection Time (ms)')
        ax.set_ylabel('ms')
    else:
        ax = summary.plot.bar(color='C0', figsize=(8, 4), title='Median Detection Time (ms)')
        ax.set_ylabel('ms')
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def plot_success_rate(df: pd.DataFrame, out_path: str):
    # Determine success column or heuristic
    if 'success' in df.columns:
        def success_rate(g):
            return (g['success'].astype(str).str.lower().isin(['true', '1']).sum() / len(g)) * 100
    else:
        # fallback: consider a run successful if detection_time or total_time is present
        def success_rate(g):
            for col in ('detection_time_ms', 'detection_time', 'total_time'):
                if col in g.columns:
                    return (g[col].notna().sum() / len(g)) * 100
            return 0.0
    succ = df.groupby(['scenario'] + (['variant'] if 'variant' in df.columns else [])).apply(success_rate).unstack(fill_value=0) if 'variant' in df.columns else df.groupby('scenario').apply(success_rate)
    ensure_dir(os.path.dirname(out_path))
    if isinstance(succ, pd.DataFrame):
        ax = succ.plot.bar(figsize=(10, 5), title='Success Rate (%)')
    else:
        succ = succ.sort_values()
        ax = succ.plot.bar(color='C2', figsize=(8, 4), title='Success Rate (%)')
    ax.set_ylabel('%')
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def plot_detection_boxplot(df: pd.DataFrame, out_path: str):
    # Prepare numeric detection times, drop nulls and support multiple column names
    df2 = df.copy()
    for col in ('detection_time_ms', 'detection_time', 'total_time'):
        if col in df2.columns:
            df2['__dt'] = pd.to_numeric(df2[col], errors='coerce')
            break
    else:
        raise RuntimeError('No detection time column found')
    groups = [g.dropna()['__dt'].values for _, g in df2.groupby('scenario')]
    labels = [s for s, _ in df2.groupby('scenario')]
    ensure_dir(os.path.dirname(out_path))
    plt.figure(figsize=(10, 5))
    plt.boxplot(groups, labels=labels, showmeans=True)
    plt.title('Detection Time Distribution by Scenario')
    plt.ylabel('ms')
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def main():
    src = os.path.join('benchmarks', 'results.csv')
    if not os.path.exists(src):
        print('No results.csv found at', src)
        return
    df = pd.read_csv(src)
    out_dir = os.path.join('benchmarks', 'plots')
    plot_median_detection(df, os.path.join(out_dir, 'median_detection.png'))
    plot_success_rate(df, os.path.join(out_dir, 'success_rate.png'))
    plot_detection_boxplot(df, os.path.join(out_dir, 'detection_boxplot.png'))
    print('Wrote plots to', out_dir)


if __name__ == '__main__':
    main()
