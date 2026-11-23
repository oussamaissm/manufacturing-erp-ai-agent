"""python -m industrial_ai.cli eval [--only O03 rag trap:guessed_order_id] [--sleep 2]"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..config import Settings
from .runner import DEFAULT_CASES, load_cases, markdown, run_eval, select, write_results


def main(argv: list[str] | None = None) -> None:
    from ..agent.graph import build_default_agent

    p = argparse.ArgumentParser(description="Score the agent on the golden question set")
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    p.add_argument("--only", nargs="*", help="case ids, categories or tags, e.g. O03 rag trap:guessed_item_code")
    p.add_argument("--skip-needs", nargs="*", default=[], help="skip cases needing seed parts, e.g. manufacturing")
    p.add_argument("--sleep", type=float, default=0.0, help="seconds between questions (free-tier rate limits)")
    p.add_argument("--out", type=Path, default=Path("results"))
    a = p.parse_args(argv)

    s = Settings.from_env()
    cases = select(load_cases(a.cases), a.only, a.skip_needs)
    label = f"{s.llm_provider}:{s.llm_model}"
    print(f"Evaluating {label} on {len(cases)} cases\n")
    rows = run_eval(build_default_agent(s), cases, sleep_s=a.sleep)
    jp, mp = write_results(label, rows, a.out)
    print("\n" + markdown(label, rows))
    print(f"Written: {jp}, {mp}")
