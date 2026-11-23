"""Deterministic scoring of one agent answer against a golden case. No LLM judge.

A case passes only if ALL of these hold:
  tools      every expected tool was called (with matching arguments); or, for no_tools cases, none was
  grounded   ids/codes/names passed to tools came from the question or an earlier tool result (not guessed)
  facts      every fact group has at least one of its alternatives in the answer
  forbidden  none of the `must_not` strings is in the answer
  budget     the agent did not exceed the tool-call budget (loop guard)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# tool -> the argument that must be grounded (never invented by the model)
GROUNDED_ARGS = {
    "get_order_details": "order_id",
    "get_stock_level": "item_code",
    "get_machine_status": "machine_name",
    "get_item_demand": "item_code",
}
MAX_TOOL_CALLS = 6

_TRANSLATE = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    " ": " ", " ": " ", "’": "'", "‘": "'", "“": '"', "”": '"',
})


def norm(text) -> str:
    """Lowercase and unify the typographic dashes/quotes models like to emit (e.g. non-breaking hyphens)."""
    return str(text).translate(_TRANSLATE).lower()


def _fact_in(fact: str, text: str) -> bool:
    """Is one expected fact in the answer?

    Numbers must appear as whole numbers: "50" is not found in "150" or "500".
    Words ignore hyphens: "feed hold" also matches "feed-hold".
    """
    fact = fact.strip()
    if re.fullmatch(r"\d+(?:[.,]\d+)?", fact):
        return re.search(r"(?<!\d)" + re.escape(fact) + r"(?!\d)", text) is not None
    return fact.replace("-", " ") in text.replace("-", " ")


@dataclass
class CaseScore:
    id: str
    tools_ok: bool = True
    grounded_ok: bool = True
    facts_ok: bool = True
    forbidden_ok: bool = True
    budget_ok: bool = True
    reasons: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all((self.tools_ok, self.grounded_ok, self.facts_ok, self.forbidden_ok, self.budget_ok))


def _call_matches(spec: dict, call: dict) -> bool:
    if call["name"] != spec["name"]:
        return False
    args = call.get("args") or {}
    for k, v in (spec.get("args") or {}).items():
        if norm(args.get(k, "")).strip() != norm(v).strip():
            return False
    for k, v in (spec.get("args_contains") or {}).items():
        if norm(v) not in norm(args.get(k, "")):
            return False
    return True


def score_case(case: dict, answer: str, tool_calls: list[dict]) -> CaseScore:
    s = CaseScore(case["id"])
    calls = tool_calls or []

    # tools
    if case.get("no_tools"):
        if calls:
            s.tools_ok = False
            s.reasons.append("called tools but none expected: " + ", ".join(c["name"] for c in calls))
    else:
        for spec in case.get("tools", []):
            if not any(_call_matches(spec, c) for c in calls):
                s.tools_ok = False
                want = spec["name"] + (str(spec.get("args") or spec.get("args_contains") or ""))
                s.reasons.append(f"missing tool call: {want}")

    # budget
    if len(calls) > MAX_TOOL_CALLS:
        s.budget_ok = False
        s.reasons.append(f"{len(calls)} tool calls (> {MAX_TOOL_CALLS})")

    # grounding: the value must be in the question/setup or in the result of an EARLIER call
    seen_text = norm(" ".join([*case.get("setup", []), case["question"]]))
    for c in calls:
        param = GROUNDED_ARGS.get(c["name"])
        if param:
            value = norm((c.get("args") or {}).get(param, "")).strip()
            if value and value not in seen_text:
                s.grounded_ok = False
                s.reasons.append(f"guessed {c['name']}.{param}={value!r} (not in question or earlier results)")
        # every call's result (not only grounded tools') becomes valid evidence for LATER calls
        seen_text += " " + norm(c.get("result", c.get("result_preview", "")))

    # facts
    text = norm(answer)
    for group in case.get("facts") or []:
        if not any(_fact_in(norm(alt), text) for alt in group):
            s.facts_ok = False
            s.reasons.append("answer lacks any of: " + " | ".join(group[:4]))

    # forbidden
    for bad in case.get("must_not") or []:
        if norm(bad) in text:
            s.forbidden_ok = False
            s.reasons.append(f"answer contains forbidden text: {bad!r}")
    return s