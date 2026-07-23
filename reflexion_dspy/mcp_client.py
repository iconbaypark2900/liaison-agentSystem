"""
MCP gateway HTTP client.

Manages MCP sessions against the local MCPHub gateway at localhost:3001.
Supports tool listing and tool calling via the JSON-RPC 2.0 / MCP protocol.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import requests

GATEWAY_URL = "http://localhost:3001/mcp"
GATEWAY_HEADERS = {
    "Authorization": "Bearer local-mcp-key",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
TIMEOUT = 60


class MCPSession:
    """Stateful MCP session (initialize → use → close)."""

    def __init__(self, url: str = GATEWAY_URL, headers: dict | None = None) -> None:
        self.url = url
        self.headers = {**GATEWAY_HEADERS, **(headers or {})}
        self.session_id: str | None = None
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _post(self, body: dict) -> dict:
        h = dict(self.headers)
        if self.session_id:
            h["mcp-session-id"] = self.session_id
        resp = requests.post(self.url, json=body, headers=h, timeout=TIMEOUT)
        resp.raise_for_status()
        # Capture session id from response headers
        if "mcp-session-id" in resp.headers:
            self.session_id = resp.headers["mcp-session-id"]
        ct = resp.headers.get("content-type", "")
        if "text/event-stream" in ct:
            return self._parse_sse(resp.text)
        return resp.json()

    def _parse_sse(self, text: str) -> dict:
        for line in text.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    return json.loads(payload)
        return {}

    def initialize(self) -> None:
        body = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "reflexion-dspy", "version": "1.0.0"},
            },
            "id": self._next_id(),
        }
        self._post(body)
        # Send initialized notification
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        h = dict(self.headers)
        if self.session_id:
            h["mcp-session-id"] = self.session_id
        try:
            requests.post(self.url, json=notif, headers=h, timeout=TIMEOUT)
        except Exception:
            pass

    def list_tools(self) -> list[dict]:
        body = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": self._next_id()}
        resp = self._post(body)
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> Any:
        body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
            "id": self._next_id(),
        }
        resp = self._post(body)
        result = resp.get("result", {})
        # Flatten content array into a string
        content = result.get("content", [])
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text", str(item)))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        return str(result)

    def close(self) -> None:
        if not self.session_id:
            return
        body = {"jsonrpc": "2.0", "method": "shutdown", "params": {}, "id": self._next_id()}
        try:
            self._post(body)
        except Exception:
            pass
        self.session_id = None


def get_available_tools(url: str = GATEWAY_URL) -> list[dict]:
    """One-shot tool listing without maintaining a session."""
    session = MCPSession(url)
    session.initialize()
    tools = session.list_tools()
    session.close()
    return tools


def call_mcp_tool(name: str, arguments: dict, url: str = GATEWAY_URL) -> str:
    """One-shot tool call (opens, calls, closes session)."""
    session = MCPSession(url)
    session.initialize()
    result = session.call_tool(name, arguments)
    session.close()
    return result
