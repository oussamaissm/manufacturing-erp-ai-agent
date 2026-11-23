"""Domain queries on top of the ERPNext client.

Every method returns small, JSON-friendly dicts: that is what the LLM sees, so
we keep only the fields a human would care about.  The client is injected, which
makes this layer easy to test with a fake.
"""
from __future__ import annotations

from typing import Any

ORDER_FIELDS = [
    "name", "customer", "transaction_date", "delivery_date", "status",
    "grand_total", "currency", "per_delivered", "po_no",
]
WORK_ORDER_FIELDS = [
    "name", "production_item", "item_name", "qty", "produced_qty", "status",
    "planned_start_date",
]


class ERPService:
    def __init__(self, client) -> None:
        self.client = client

    # ------------------------------------------------------------- machines
    def machines(self) -> list[dict]:
        # name + description only: hour_rate is 0 in ERPNext and made models invent explanations
        rows = self.client.get_list("Workstation", fields=["name", "description"], limit=100)
        return [{"machine": r["name"], "description": r.get("description")} for r in rows]
        

    def machine_status(self, machine: str) -> dict:
        """Status of one machine.

        Uses the Workstation `status` field when this ERPNext version has it
        (v15+); otherwise derives it from open Work Order operations.
        """
        ws = self.client.get_doc("Workstation", machine)
        ops = self.client.get_child_list(
            "Work Order",
            "Work Order Operation",
            fields=["parent", "operation", "status", "time_in_mins", "completed_qty"],
            filters=[["workstation", "=", machine], ["status", "in", ["Pending", "In Progress"]]],
            limit=50,
        )
        parents = sorted({o["parent"] for o in ops})
        wo_status: dict[str, dict] = {}
        if parents:
            for wo in self.client.get_list(
                "Work Order",
                fields=["name", "production_item", "status"],
                filters=[["name", "in", parents]],
                limit=len(parents),
            ):
                wo_status[wo["name"]] = wo
        live = [
            o for o in ops
            if wo_status.get(o["parent"], {}).get("status") not in ("Completed", "Cancelled", "Stopped", "Closed")
        ]
        running = [o for o in live if o.get("status") == "In Progress"]
        queued = [o for o in live if o.get("status") == "Pending"]

        declared = ws.get("status")
        if declared:
            status, source = declared, "workstation.status"
        else:
            status, source = ("Production" if running else "Idle"), "derived from work order operations"
        return {
            "machine": ws["name"],
            "status": status,
            "status_source": source,
            "description": ws.get("description"),
            "hour_rate": ws.get("hour_rate"),
            "running_operations": [_op(o, wo_status) for o in running],
            "queued_operations": len(queued),
            "queued_next": [_op(o, wo_status) for o in queued[:3]],
        }

    # ------------------------------------------------------------- sales orders
    def sales_orders(self, status: str | None = None, customer: str | None = None, limit: int = 10,
                     open_only: bool = False) -> list[dict]:
        filters: list[list[Any]] = [["docstatus", "<", 2]]
        if open_only:  # submitted and not fully delivered, whatever the status label says
            filters = [["docstatus", "=", 1], ["per_delivered", "<", 100],
                       ["status", "not in", ["Closed", "Completed", "On Hold"]]]
        if status:
            filters.append(["status", "=", status])
        if customer:
            filters.append(["customer", "like", f"%{customer}%"])
        rows = self.client.get_list(
            "Sales Order", fields=ORDER_FIELDS, filters=filters, order_by="delivery_date asc", limit=limit
        )
        orders = [_order_summary(r) for r in rows]

        # what is in each order, so the model can pick "the valve body order" without opening every order
        if orders:
            lines = self.client.get_child_list(
                "Sales Order", "Sales Order Item",
                fields=["parent", "item_code", "qty", "delivered_qty"],
                filters=[["parent", "in", [o["order_id"] for o in orders]]],
                limit=500,
            )
            by_order: dict[str, list[str]] = {}
            for line in lines:
                qty = float(line.get("qty") or 0)
                delivered = float(line.get("delivered_qty") or 0)
                text = f"{line['item_code']} x{qty:g}"
                if delivered:
                    text += f" ({delivered:g} delivered)"
                by_order.setdefault(line["parent"], []).append(text)
            for o in orders:
                o["items"] = ", ".join(by_order.get(o["order_id"], []))

        return orders

    def order_details(self, order_id: str) -> dict:
        doc = self.client.get_doc("Sales Order", order_id)
        items = doc.get("items", [])
        stock = self.stock_totals([i["item_code"] for i in items])
        lines = []
        shortages = []
        for i in items:
            remaining = float(i.get("qty", 0)) - float(i.get("delivered_qty", 0))
            available = stock.get(i["item_code"], 0.0)
            line = {
                "item_code": i["item_code"],
                "item_name": i.get("item_name"),
                "qty": i.get("qty"),
                "delivered_qty": i.get("delivered_qty", 0),
                "rate": i.get("rate"),
                "amount": i.get("amount"),
                "stock_available": available,
            }
            lines.append(line)
            if remaining > available:
                shortages.append({"item_code": i["item_code"], "missing": round(remaining - available, 3)})
        summary = _order_summary(doc)
        summary.update(
            {
                "items": lines,
                "can_fulfil_from_stock": not shortages,
                "shortages": shortages,
            }
        )
        return summary

    # ------------------------------ stock -------------------------------
    def stock_totals(self, item_codes: list[str]) -> dict[str, float]:
        if not item_codes:
            return {}
        bins = self.client.get_list(
            "Bin",
            fields=["item_code", "warehouse", "actual_qty"],
            filters=[["item_code", "in", item_codes]],
            limit=500,
        )
        totals: dict[str, float] = {c: 0.0 for c in item_codes}
        for b in bins:
            totals[b["item_code"]] = totals.get(b["item_code"], 0.0) + float(b.get("actual_qty") or 0)
        return totals

    def stock_level(self, item_code: str) -> dict:
        item = self.client.get_doc("Item", item_code)
        bins = self.client.get_list(
            "Bin",
            fields=["warehouse", "actual_qty"],
            filters=[["item_code", "=", item_code]],
            limit=50,
        )
        total = sum(float(b.get("actual_qty") or 0) for b in bins)
        safety = float(item.get("safety_stock") or 0)
        return {
            "item_code": item["name"],
            "item_name": item.get("item_name"),
            "total_actual_qty": total,
            "safety_stock": safety,
            "below_safety_stock": bool(safety) and total < safety,
            "warehouses": bins,
        }

    def find_items(self, query: str, limit: int = 10) -> list[dict]:
        """Items whose code or name contains `query` (case-insensitive), with exact codes."""
        found: dict[str, dict] = {}
        for field in ("item_name", "name"):
            for r in self.client.get_list(
                "Item",
                fields=["name", "item_name", "item_group"],
                filters=[[field, "like", f"%{query}%"], ["disabled", "=", 0]],
                limit=limit,
            ):
                found.setdefault(r["name"], {"item_code": r["name"], "item_name": r.get("item_name"), "group": r.get("item_group")})
        return list(found.values())[:limit]

    def low_stock(self) -> list[dict]:
        items = self.client.get_list(
            "Item",
            fields=["name", "item_name", "safety_stock"],
            filters=[["safety_stock", ">", 0], ["disabled", "=", 0]],
            limit=200,
        )
        totals = self.stock_totals([i["name"] for i in items])
        out = []
        for i in items:
            have = totals.get(i["name"], 0.0)
            need = float(i["safety_stock"])
            if have < need:
                out.append(
                    {
                        "item_code": i["name"],
                        "item_name": i.get("item_name"),
                        "actual_qty": have,
                        "safety_stock": need,
                        "shortfall": round(need - have, 3),
                    }
                )
        return sorted(out, key=lambda x: x["shortfall"], reverse=True)

    # -------------------- production -----------------------------------------
    def work_orders(self, status: str | None = None, limit: int = 10) -> list[dict]:
        filters: list[list[Any]] = [["docstatus", "<", 2]]
        if status:
            filters.append(["status", "=", status])
        rows = self.client.get_list(
            "Work Order", fields=WORK_ORDER_FIELDS, filters=filters, order_by="planned_start_date asc", limit=limit
        )
        return [
            {
                "work_order": r["name"],
                "item": r.get("production_item"),
                "item_name": r.get("item_name"),
                "qty": r.get("qty"),
                "produced_qty": r.get("produced_qty"),
                "status": r.get("status"),
                "planned_start": r.get("planned_start_date"),
            }
            for r in rows
        ]


def _order_summary(r: dict) -> dict:
    return {
        "order_id": r["name"],
        "customer": r.get("customer"),
        "status": r.get("status"),
        "order_date": r.get("transaction_date"),
        "delivery_date": r.get("delivery_date"),
        "total": r.get("grand_total"),
        "currency": r.get("currency"),
        "percent_delivered": r.get("per_delivered"),
        "customer_po": r.get("po_no"),
    }


def _op(o: dict, wo_status: dict[str, dict]) -> dict:
    wo = wo_status.get(o["parent"], {})
    return {
        "work_order": o["parent"],
        "operation": o.get("operation"),
        "item": wo.get("production_item"),
        "status": o.get("status"),
        "minutes": o.get("time_in_mins"),
        "completed_qty": o.get("completed_qty"),
    }
