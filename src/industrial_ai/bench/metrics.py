"""Measurements against an Ollama server.

Ollama reports durations in nanoseconds on the final streamed chunk:
  load_duration, prompt_eval_{count,duration}, eval_{count,duration}.
We combine them with our own wall-clock timing for time-to-first-token (TTFT).
"""
from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import Any

NS = 1e9


def _g(obj: Any, key: str, default=None):
    """Read `key` from a dict or an attribute-style response object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


@dataclass
class GenResult:
    model: str
    prompt_name: str
    ttft_s: float
    total_s: float
    prompt_tokens: int
    output_tokens: int
    decode_tps: float    # output tokens / s during generation
    prefill_tps: float   # prompt tokens / s during prompt processing
    load_s: float

    def row(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def run_generation(client, model: str, prompt_name: str, prompt: str, num_predict: int = 200) -> GenResult:
    t0 = time.perf_counter()
    ttft = None
    final = None
    stream = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        options={"temperature": 0, "num_predict": num_predict},
    )
    for chunk in stream:
        content = _g(_g(chunk, "message"), "content", "")
        if ttft is None and content:
            ttft = time.perf_counter() - t0
        if _g(chunk, "done"):
            final = chunk
    total = time.perf_counter() - t0
    out_tok = int(_g(final, "eval_count", 0) or 0)
    out_ns = _g(final, "eval_duration", 0) or 0
    in_tok = int(_g(final, "prompt_eval_count", 0) or 0)
    in_ns = _g(final, "prompt_eval_duration", 0) or 0
    return GenResult(
        model=model,
        prompt_name=prompt_name,
        ttft_s=ttft if ttft is not None else total,
        total_s=total,
        prompt_tokens=in_tok,
        output_tokens=out_tok,
        decode_tps=out_tok / (out_ns / NS) if out_ns else 0.0,
        prefill_tps=in_tok / (in_ns / NS) if in_ns else 0.0,
        load_s=(_g(final, "load_duration", 0) or 0) / NS,
    )


def vram_mb(client, model: str) -> float | None:
    """VRAM used by a loaded model, from `ollama ps` (None if unavailable)."""
    try:
        for m in _g(client.ps(), "models", []) or []:
            name = _g(m, "model") or _g(m, "name")
            if name == model or (name or "").startswith(model):
                return round((_g(m, "size_vram", 0) or 0) / 1e6, 1)
    except Exception:
        return None
    return None


def bench_generation(client, model: str, prompts: dict[str, str], runs: int = 3, num_predict: int = 200) -> dict:
    """Warm up once (loads the model), then time `runs` generations per prompt."""
    warm = run_generation(client, model, "warmup", "Say hello.", num_predict=8)
    rows = []
    for name, text in prompts.items():
        for _ in range(runs):
            rows.append(run_generation(client, model, name, text, num_predict))
    return {"cold_load_s": round(warm.load_s, 3), "vram_mb": vram_mb(client, model), "rows": [r.row() for r in rows]}


def bench_concurrency(client_factory, model: str, prompt: str, levels=(1, 2, 4), num_predict: int = 120) -> list[dict]:
    """Aggregate throughput with N simultaneous requests.

    Note: Ollama only serves requests in parallel if OLLAMA_NUM_PARALLEL >= N;
    otherwise they queue and aggregate throughput stays flat.
    """
    out = []
    for n in levels:
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=n) as pool:
            results = list(pool.map(
                lambda _: run_generation(client_factory(), model, "concurrency", prompt, num_predict), range(n)
            ))
        wall = time.perf_counter() - t0
        tokens = sum(r.output_tokens for r in results)
        out.append({
            "model": model, "concurrency": n, "wall_s": round(wall, 3), "total_output_tokens": tokens,
            "aggregate_tps": round(tokens / wall, 2) if wall else 0.0,
            "median_ttft_s": round(statistics.median(r.ttft_s for r in results), 3),
        })
    return out


def summarize(rows: list[dict]) -> dict[str, dict]:
    """Median per metric, grouped by prompt name."""
    by_prompt: dict[str, list[dict]] = {}
    for r in rows:
        by_prompt.setdefault(r["prompt_name"], []).append(r)
    return {
        p: {
            "runs": len(rs),
            "ttft_s": round(statistics.median(r["ttft_s"] for r in rs), 3),
            "decode_tps": round(statistics.median(r["decode_tps"] for r in rs), 2),
            "prefill_tps": round(statistics.median(r["prefill_tps"] for r in rs), 1),
            "total_s": round(statistics.median(r["total_s"] for r in rs), 3),
            "prompt_tokens": int(statistics.median(r["prompt_tokens"] for r in rs)),
        }
        for p, rs in by_prompt.items()
    }
