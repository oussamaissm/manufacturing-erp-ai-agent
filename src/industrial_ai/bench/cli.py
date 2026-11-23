"""python -m industrial_ai.bench --models qwen2.5:7b llama3.1:8b --runs 3"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..config import Settings
from .cases import default_prompts
from .metrics import bench_concurrency, bench_generation
from .report import write_report
from .tool_eval import run_tool_eval


def run(client, client_factory, models, prompts, runs, concurrency, with_tools, num_predict=200, log=print) -> dict:
    results: dict = {"models": {}, "prompts": list(prompts), "runs": runs}
    for model in models:
        log(f"== {model}")
        entry: dict = {}
        log("  generation...")
        entry["generation"] = bench_generation(client, model, prompts, runs, num_predict)
        if concurrency:
            log("  concurrency...")
            entry["concurrency"] = bench_concurrency(client_factory, model, prompts["medium"], concurrency)
        if with_tools:
            log("  tool calling...")
            entry["tools"] = run_tool_eval(client, model)
        results["models"][model] = entry
    return results


def main(argv: list[str] | None = None) -> None:
    import ollama

    s = Settings.from_env()
    p = argparse.ArgumentParser(description="Benchmark local Ollama models")
    p.add_argument("--models", nargs="+", default=[s.llm_model])
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--concurrency", nargs="*", type=int, default=[1, 2, 4])
    p.add_argument("--no-tools", action="store_true", help="skip the tool-calling accuracy eval")
    p.add_argument("--out", type=Path, default=Path("results"))
    a = p.parse_args(argv)

    factory = lambda: ollama.Client(host=s.ollama_host)  # noqa: E731
    results = run(factory(), factory, a.models, default_prompts(s.docs_dir), a.runs, a.concurrency, not a.no_tools)
    paths = write_report(results, a.out)
    print("\n" + paths["md"].read_text(encoding="utf-8"))
    print("Written:", ", ".join(str(v) for v in paths.values()))
