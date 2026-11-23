"""LLM-facing tools.

`build_tools` is a factory: it closes over an ERPService (and optional retriever)
so the same tool definitions work against ERPNext, a fake in tests, etc.

Design rules that matter for small local models:
  * few tools, each with a precise docstring (the docstring IS the prompt),
  * flat, simple arguments,
  * errors are returned as data ({"error": ...}) so the model can recover.
"""
from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import BaseTool, tool

from ..erp.client import ERPError


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _safe(fn, *args, **kwargs) -> str:
    try:
        return _dump(fn(*args, **kwargs))
    except ERPError as e:
        return _dump({"error": str(e)})
    except KeyError as e:  # unexpected shape from the ERP
        return _dump({"error": f"Unexpected ERP response, missing field {e}"})


def build_tools(erp, retriever=None) -> list[BaseTool]:
    @tool
    def list_machines() -> str:
        """List all machines (workstations) in the plant with their description and hourly rate."""
        return _safe(erp.machines)

    @tool
    def get_machine_status(machine_name: str) -> str:
        """Get the current status of ONE machine, e.g. 'CNC-01': running, idle or in maintenance, \
plus the operations it is running and the ones queued. Use list_machines first if unsure of the name."""
        return _safe(erp.machine_status, machine_name)

    @tool
    def list_sales_orders(open_only: bool = False, customer: Optional[str] = None, status: Optional[str] = None,
                          limit: int = 10) -> str:
        """Find customer sales orders, soonest delivery first, with the items in each order and how much is \
delivered. Set open_only=true for orders still waiting for delivery. Optional: customer (partial name \
match), status (exact ERPNext status), limit. Use the items to pick the right order when a customer has \
several. Do NOT add up quantities across orders from this list: for the total demand of an item across \
all orders, call get_item_demand."""
        def run():
            rows = erp.sales_orders(status, customer, limit + 1, open_only=open_only)
            if len(rows) > limit:
                return {"orders": rows[:limit],
                        "note": f"Only the first {limit} orders are shown and more exist. Use a higher limit, "
                                "a customer filter, or get_item_demand for item totals."}
            return rows
        return _safe(run)

    @tool
    def get_order_details(order_id: str) -> str:
        """Get full details of ONE sales order by id (e.g. 'SAL-ORD-2026-00001'): lines, delivery date, \
and whether current stock can fulfil it (with shortages per item)."""
        return _safe(erp.order_details, order_id)

    @tool
    def find_items(query: str) -> str:
        """Find items by part of their name or code, e.g. 'hydraulic oil' or 'steel'. Returns the exact \
item codes. Call this BEFORE get_stock_level whenever the user does not give an exact item code."""
        return _safe(erp.find_items, query)

    @tool
    def get_stock_level(item_code: str) -> str:
        """Get the stock level of ONE item by item code (e.g. 'STEEL-BAR-20'), per warehouse, \
and whether it is below its safety stock."""
        return _safe(erp.stock_level, item_code)

    @tool
    def list_low_stock_items() -> str:
        """List every item whose total stock is below its safety stock, biggest shortfall first. \
Use for questions like 'what do we need to reorder?'"""
        return _safe(erp.low_stock)

    @tool
    def list_work_orders(status: Optional[str] = None, limit: int = 10) -> str:
        """List production work orders. Optional status filter: 'Not Started', 'In Process', 'Completed'."""
        return _safe(erp.work_orders, status, limit)

    tools: list[BaseTool] = [
        list_machines, get_machine_status, list_sales_orders, get_order_details,
        find_items, get_stock_level, list_low_stock_items, list_work_orders,
    ]

    if retriever is not None:
        @tool
        def search_documents(query: str) -> str:
            """Search the plant's internal documents. They cover: suppliers (who supplies an item, lead \
times, contacts, ratings), customers (tier, payment terms, contacts, special requirements), item and \
product datasheets (description, bill of materials, routing, list price, packaging), machine \
technical sheets (model, specs, hourly cost), CNC alarm codes, maintenance procedures and schedules, \
safety rules, quality control plans, purchasing, pricing and planning policies, and an ERP glossary. \
Returns passages with their source file. Use it for any question the ERP tools cannot answer, before \
saying you do not have the information."""
            try:
                hits = retriever.search(query)
            except Exception as e:  # embedding server down, empty index...
                return _dump({"error": f"Document search failed: {e}"})
            if not hits:
                return _dump({"results": [], "note": "No relevant document found."})
            return _dump({"results": [h.as_dict() for h in hits]})

        tools.append(search_documents)
    return tools
