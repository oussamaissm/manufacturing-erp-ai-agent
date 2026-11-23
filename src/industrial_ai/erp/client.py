"""Thin REST client for ERPNext / Frappe.

Only the handful of endpoints this project needs:
  GET  /api/resource/<DocType>            list documents
  GET  /api/resource/<DocType>/<name>     one document
  POST /api/resource/<DocType>            create (docstatus=1 submits it)
  PUT  /api/resource/<DocType>/<name>     update
  POST /api/method/frappe.client.get_list list child-table rows (needs `parent`)
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx


class ERPError(RuntimeError):
    """Raised for any failed call to ERPNext (network, auth, validation...)."""


class ERPNextClient:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        api_secret: str = "",
        username: str = "",
        password: str = "",
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"Accept": "application/json"}
        self._token_auth = bool(api_key and api_secret)
        if self._token_auth:
            headers["Authorization"] = f"token {api_key}:{api_secret}"
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport
        )
        self._username = username
        self._password = password
        self._logged_in = self._token_auth

    @classmethod
    def from_settings(cls, s) -> "ERPNextClient":
        return cls(
            s.erp_url,
            api_key=s.erp_api_key,
            api_secret=s.erp_api_secret,
            username=s.erp_user,
            password=s.erp_password,
        )

    # ------------------------------------------------------------------ plumbing
    def _login(self) -> None:
        if not (self._username and self._password):
            raise ERPError("No ERPNext credentials configured (set ERP_USER/ERP_PASSWORD or ERP_API_KEY/SECRET).")
        try:
            r = self._http.post("/api/method/login", json={"usr": self._username, "pwd": self._password})
        except httpx.HTTPError as e:
            raise ERPError(f"Cannot reach ERPNext at {self._http.base_url}: {e}") from e
        if r.status_code >= 400:
            raise ERPError(f"ERPNext login failed ({r.status_code}): {_error_message(r)}")
        self._logged_in = True

    def _request(self, method: str, path: str, *, _retry: bool = True, **kwargs: Any) -> Any:
        if not self._logged_in:
            self._login()
        try:
            r = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise ERPError(f"Cannot reach ERPNext at {self._http.base_url}: {e}") from e
        if r.status_code in (401, 403) and not self._token_auth and _retry:
            # session cookie expired: log in again once
            self._logged_in = False
            return self._request(method, path, _retry=False, **kwargs)
        if r.status_code >= 400:
            raise ERPError(f"ERPNext {method} {path} -> {r.status_code}: {_error_message(r)}")
        try:
            body = r.json()
        except ValueError as e:
            raise ERPError(f"ERPNext returned non-JSON for {method} {path}") from e
        if "data" in body:
            return body["data"]
        return body.get("message", body)

    # ------------------------------------------------------------------ API
    def ping(self) -> bool:
        try:
            r = self._http.get("/api/method/ping")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def get_list(
        self,
        doctype: str,
        *,
        fields: list[str] | None = None,
        filters: list | dict | None = None,
        order_by: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit_page_length": limit}
        if fields:
            params["fields"] = json.dumps(fields)
        if filters:
            params["filters"] = json.dumps(filters)
        if order_by:
            params["order_by"] = order_by
        return self._request("GET", f"/api/resource/{quote(doctype, safe='')}", params=params)

    def get_doc(self, doctype: str, name: str) -> dict:
        return self._request("GET", f"/api/resource/{quote(doctype, safe='')}/{quote(name, safe='')}")

    def get_child_list(
        self,
        parent_doctype: str,
        child_doctype: str,
        *,
        fields: list[str] | None = None,
        filters: list | dict | None = None,
        limit: int = 50,
    ) -> list[dict]:
        payload = {
            "doctype": child_doctype,
            "parent": parent_doctype,
            "fields": fields or ["*"],
            "filters": filters or [],
            "limit_page_length": limit,
        }
        return self._request("POST", "/api/method/frappe.client.get_list", json=payload)

    def exists(self, doctype: str, name: str) -> bool:
        return bool(self.get_list(doctype, fields=["name"], filters=[["name", "=", name]], limit=1))

    def insert(self, doctype: str, doc: dict, *, submit: bool = False) -> dict:
        created = self._request("POST", f"/api/resource/{quote(doctype, safe='')}", json=dict(doc))
        if submit and created.get("docstatus") != 1:
            # some ERPNext versions ignore docstatus=1 on insert: submit explicitly
            created = self._request("POST", "/api/method/frappe.client.submit", json={"doc": created})
        return created

    def update(self, doctype: str, name: str, values: dict) -> dict:
        return self._request(
            "PUT", f"/api/resource/{quote(doctype, safe='')}/{quote(name, safe='')}", json=values
        )

    def close(self) -> None:
        self._http.close()


def _error_message(r: httpx.Response) -> str:
    """Extract a readable message from a Frappe error response."""
    try:
        body = r.json()
    except ValueError:
        return r.text[:300]
    msgs = body.get("_server_messages")
    if msgs:
        try:
            parts = [json.loads(m).get("message", "") for m in json.loads(msgs)]
            return " | ".join(p for p in parts if p)[:500]
        except (ValueError, AttributeError):
            pass
    for key in ("exception", "message", "exc_type"):
        if body.get(key):
            return str(body[key])[:500]
    return r.text[:300]
