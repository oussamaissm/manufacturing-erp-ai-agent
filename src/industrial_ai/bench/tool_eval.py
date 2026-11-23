"""Tool-calling accuracy: does the model pick the right tool with the right arguments?"""
from __future__ import annotations

import time

from .cases import TOOL_CASES, ToolCase, tool_schemas
from .metrics import _g


def _matches(got: dict, want: dict) -> bool:
    return all(str(got.get(k, "")).strip().lower() == str(v).strip().lower() for k, v in want.items())


def score_case(case: ToolCase, calls: list[tuple[str, dict]]) -> dict:
    if case.tool is None:
        ok = not calls
        return {"name_ok": ok, "args_ok": ok, "called": calls[0][0] if calls else None}
    if not calls:
        return {"name_ok": False, "args_ok": False, "called": None}
    name, args = calls[0]
    name_ok = name == case.tool
    return {"name_ok": name_ok, "args_ok": name_ok and _matches(args, case.args), "called": name}


def run_tool_eval(client, model: str, cases: list[ToolCase] | None = None) -> dict:
    cases = cases or TOOL_CASES
    schemas = tool_schemas()
    rows = []
    for case in cases:
        t0 = time.perf_counter()
        resp = client.chat(
            model=model,
            messages=[{"role": "user", "content": case.question}],
            tools=schemas,
            options={"temperature": 0},
        )
        latency = time.perf_counter() - t0
        raw = _g(_g(resp, "message"), "tool_calls", None) or []
        calls = []
        for c in raw:
            fn = _g(c, "function")
            args = _g(fn, "arguments", {}) or {}
            calls.append((_g(fn, "name"), dict(args)))
        rows.append({"model": model, "question": case.question, "expected": case.tool,
                     "latency_s": round(latency, 3), **score_case(case, calls)})
    n = len(rows)
    return {
        "model": model,
        "name_accuracy": round(sum(r["name_ok"] for r in rows) / n, 3),
        "args_accuracy": round(sum(r["args_ok"] for r in rows) / n, 3),
        "median_latency_s": round(sorted(r["latency_s"] for r in rows)[n // 2], 3),
        "rows": rows,
    }
