"""Run the golden set against an agent and write JSON + Markdown reports."""
from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from pathlib import Path

from ..config import ROOT
from .scorer import score_case

DEFAULT_CASES = ROOT / "data" / "eval" / "golden.jsonl"


def load_cases(path: Path = DEFAULT_CASES) -> list[dict]:
    cases = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids in " + str(path))
    return cases


def select(cases, only: list[str] | None = None, skip_needs: list[str] | None = None):
    out = []
    for c in cases:
        if only and not (c["id"] in only or c["category"] in only or any(t in only for t in c.get("tags", []))):
            continue
        if skip_needs and set(c.get("needs", [])) & set(skip_needs):
            continue
        out.append(c)
    return out


def run_eval(agent, cases: list[dict], sleep_s: float = 0.0, log=print) -> list[dict]:
    rows = []
    for n, case in enumerate(cases, 1):
        thread = "eval-" + uuid.uuid4().hex[:8]
        error = None
        answer, calls, elapsed = "", [], 0.0
        try:
            for turn in case.get("setup", []):
                agent.ask(turn, thread_id=thread)
            r = agent.ask(case["question"], thread_id=thread)
            answer, calls, elapsed = r.answer, r.tool_calls, r.elapsed_s
        except Exception as e:  # provider down, rate limit...
            error = f"{type(e).__name__}: {e}"
        sc = score_case(case, answer, calls)
        if error:
            sc.tools_ok = sc.facts_ok = False
            sc.reasons.append("agent error: " + error[:200])
        rows.append({
            "id": case["id"], "category": case["category"], "tags": case.get("tags", []),
            "question": case["question"], "passed": sc.passed,
            "tools_ok": sc.tools_ok, "grounded_ok": sc.grounded_ok, "facts_ok": sc.facts_ok,
            "forbidden_ok": sc.forbidden_ok, "budget_ok": sc.budget_ok, "reasons": sc.reasons,
            "tools_called": [{"name": c["name"], "args": c["args"]} for c in calls],
            "answer": answer, "latency_s": round(elapsed, 2), "error": error,
        })
        log(f"[{n}/{len(cases)}] {case['id']:<4} {'PASS' if sc.passed else 'FAIL'}  {elapsed:5.1f}s  {case['question'][:60]}")
        if not sc.passed:
            for r_ in sc.reasons:
                log(f"        - {r_}")
        if sleep_s and n < len(cases):
            time.sleep(sleep_s)
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows) or 1
    by_cat: dict[str, list[dict]] = defaultdict(list)
    by_tag: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
        for t in r["tags"]:
            by_tag[t].append(r)
    rate = lambda rs, k="passed": round(sum(1 for r in rs if r[k]) / (len(rs) or 1), 3)  # noqa: E731
    lat = sorted(r["latency_s"] for r in rows)
    return {
        "cases": len(rows),
        "pass_rate": rate(rows),
        "tools_ok": rate(rows, "tools_ok"), "grounded_ok": rate(rows, "grounded_ok"),
        "facts_ok": rate(rows, "facts_ok"), "forbidden_ok": rate(rows, "forbidden_ok"),
        "median_latency_s": lat[len(lat) // 2] if lat else 0.0,
        "by_category": {k: {"n": len(v), "pass_rate": rate(v)} for k, v in sorted(by_cat.items())},
        "by_tag": {k: {"n": len(v), "pass_rate": rate(v)} for k, v in sorted(by_tag.items()) if k.startswith(("trap:", "safety", "hard"))},
    }


def markdown(model: str, rows: list[dict]) -> str:
    s = summarize(rows)
    pct = lambda x: f"{x:.0%}"  # noqa: E731
    L = [f"# Evaluation: {model}", "",
         f"**{s['cases']} cases, pass rate {pct(s['pass_rate'])}**, median latency {s['median_latency_s']} s", "",
         "| Check | Rate |", "|---|---|",
         f"| Right tools called | {pct(s['tools_ok'])} |", f"| Arguments grounded (not guessed) | {pct(s['grounded_ok'])} |",
         f"| Expected facts in answer | {pct(s['facts_ok'])} |", f"| No forbidden / invented content | {pct(s['forbidden_ok'])} |", "",
         "## By category", "", "| Category | Cases | Pass rate |", "|---|---|---|"]
    L += [f"| {k} | {v['n']} | {pct(v['pass_rate'])} |" for k, v in s["by_category"].items()]
    if s["by_tag"]:
        L += ["", "## Known failure modes", "", "| Trap | Cases | Pass rate |", "|---|---|---|"]
        L += [f"| {k} | {v['n']} | {pct(v['pass_rate'])} |" for k, v in s["by_tag"].items()]
    fails = [r for r in rows if not r["passed"]]
    if fails:
        L += ["", "## Failures", ""]
        for r in fails:
            L += [f"### {r['id']}: {r['question']}", *(f"- {x}" for x in r["reasons"]), "",
                  "> " + (r["answer"] or "(no answer)").replace("\n", "\n> ")[:600], ""]
    return "\n".join(L) + "\n"


def write_results(model: str, rows: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = model.replace("/", "_").replace(":", "_")
    jp, mp = out_dir / f"eval_{safe}.json", out_dir / f"eval_{safe}.md"
    jp.write_text(json.dumps({"model": model, "summary": summarize(rows), "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    mp.write_text(markdown(model, rows), encoding="utf-8")
    return jp, mp
