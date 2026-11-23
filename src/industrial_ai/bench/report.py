"""Write benchmark results as JSON, CSV, Markdown and a PNG chart."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .metrics import summarize


def write_report(results: dict, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out_dir / "bench.json",
        "csv": out_dir / "bench_generation.csv",
        "md": out_dir / "bench.md",
        "png": out_dir / "bench.png",
    }
    paths["json"].write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = [r for m in results["models"].values() for r in m.get("generation", {}).get("rows", [])]
    if rows:
        with paths["csv"].open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    paths["md"].write_text(markdown(results), encoding="utf-8")
    _chart(results, paths["png"])
    return paths


def markdown(results: dict) -> str:
    lines = ["# Inference benchmark", "", f"Prompts: {', '.join(results.get('prompts', []))}  ", f"Runs per prompt: {results.get('runs')}", ""]
    lines += ["## Generation (median over runs)", "",
              "| Model | Prompt | TTFT (s) | Decode tok/s | Prefill tok/s | Prompt tok | Total (s) |",
              "|---|---|---|---|---|---|---|"]
    for model, m in results["models"].items():
        gen = m.get("generation")
        if not gen:
            continue
        for prompt, s in summarize(gen["rows"]).items():
            lines.append(f"| {model} | {prompt} | {s['ttft_s']} | {s['decode_tps']} | {s['prefill_tps']} | {s['prompt_tokens']} | {s['total_s']} |")
    lines += ["", "## Model footprint", "", "| Model | Cold load (s) | VRAM (MB) |", "|---|---|---|"]
    for model, m in results["models"].items():
        gen = m.get("generation") or {}
        lines.append(f"| {model} | {gen.get('cold_load_s', '-')} | {gen.get('vram_mb', '-')} |")
    if any(m.get("tools") for m in results["models"].values()):
        lines += ["", "## Tool-calling accuracy", "", "| Model | Right tool | Right tool + args | Median latency (s) |", "|---|---|---|---|"]
        for model, m in results["models"].items():
            t = m.get("tools")
            if t:
                lines.append(f"| {model} | {t['name_accuracy']:.0%} | {t['args_accuracy']:.0%} | {t['median_latency_s']} |")
    if any(m.get("concurrency") for m in results["models"].values()):
        lines += ["", "## Concurrency (aggregate throughput)", "", "| Model | Parallel requests | Aggregate tok/s | Median TTFT (s) |", "|---|---|---|---|"]
        for model, m in results["models"].items():
            for c in m.get("concurrency") or []:
                lines.append(f"| {model} | {c['concurrency']} | {c['aggregate_tps']} | {c['median_ttft_s']} |")
    return "\n".join(lines) + "\n"


def _chart(results: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = list(results["models"])
    decode, acc = [], []
    for m in models:
        gen = results["models"][m].get("generation")
        s = summarize(gen["rows"]) if gen else {}
        decode.append(s.get("medium", next(iter(s.values()), {})).get("decode_tps", 0) if s else 0)
        t = results["models"][m].get("tools")
        acc.append(t["args_accuracy"] * 100 if t else 0)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    axes[0].bar(models, decode, color="#3b6ea5")
    axes[0].set_title("Decode speed (tokens/s)")
    axes[1].bar(models, acc, color="#4c9a6a")
    axes[1].set_title("Tool-call accuracy, name + args (%)")
    axes[1].set_ylim(0, 100)
    for ax in axes:
        ax.tick_params(axis="x", rotation=20)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
