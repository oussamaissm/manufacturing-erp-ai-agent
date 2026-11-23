"""Prompts and tool-calling test cases used by the benchmarks."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.utils.function_calling import convert_to_openai_tool

from ..agent.tools import build_tools

SHORT = "In two sentences, what does a hydraulic press do?"
MEDIUM = (
    "Explain, step by step, how to plan preventive maintenance for a CNC milling machine "
    "in a small factory. Be concrete."
)


def long_context_prompt(docs_dir: Path, target_words: int = 1200) -> str:
    """Stack the plant documents until ~target_words, then ask a question about them."""
    text = ""
    for p in sorted(Path(docs_dir).glob("*.md")):
        text += p.read_text(encoding="utf-8") + "\n\n"
    words = text.split()
    if not words:
        words = ("The plant runs CNC machines and a hydraulic press. " * 200).split()
    while len(words) < target_words:
        words = words + words
    body = " ".join(words[:target_words])
    return f"{body}\n\nQuestion: according to the text above, which machines are mentioned? Answer in one sentence."


def default_prompts(docs_dir: Path) -> dict[str, str]:
    return {"short": SHORT, "medium": MEDIUM, "long_context": long_context_prompt(docs_dir)}


@dataclass(frozen=True)
class ToolCase:
    question: str
    tool: str | None                      # None = no tool should be called
    args: dict = field(default_factory=dict)


TOOL_CASES = [
    ToolCase("What is the status of machine CNC-01?", "get_machine_status", {"machine_name": "CNC-01"}),
    ToolCase("Show me the details of sales order SAL-ORD-2026-00003", "get_order_details", {"order_id": "SAL-ORD-2026-00003"}),
    ToolCase("How much STEEL-BAR-20 do we have in stock?", "get_stock_level", {"item_code": "STEEL-BAR-20"}),
    ToolCase("What do we need to reorder?", "list_low_stock_items"),
    ToolCase("Which machines do we have in the plant?", "list_machines"),
    ToolCase("List the work orders that are in process", "list_work_orders", {"status": "In Process"}),
    ToolCase("What is the procedure to lock out the press before maintenance?", "search_documents"),
    ToolCase("Show me the open orders for customer Atlas", "list_sales_orders", {"customer": "Atlas"}),
    ToolCase("Quel est l'etat de la machine PRESS-01 ?", "get_machine_status", {"machine_name": "PRESS-01"}),
    ToolCase("What is the capital of France?", None),
]


def tool_schemas() -> list[dict]:
    """OpenAI-style schemas of the real tools (the ERP is never called)."""
    return [convert_to_openai_tool(t) for t in build_tools(erp=None, retriever=object())]
