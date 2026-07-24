"""
DSPy-compatible tool wrappers around the MCP gateway.

Builds a curated set of tools from the 29-server gateway and wraps them as
dspy.Tool objects (or plain callables) that the ReAct agent can invoke.
"""

from __future__ import annotations

import json
from typing import Any

from .mcp_client import MCPSession, GATEWAY_URL

# Tool name format from MCPHub: "server-tool_name" e.g. "arxiv-search_papers"
# Enabled server prefixes (all safe for agent use)
ENABLED_SERVER_PREFIXES = {
    "arxiv", "brave", "tavily", "exa", "pubmed", "wikipedia",
    "fetch", "context7",
    "code",
    "memory", "sequential",
    "time",
    "git",
    "sqlite",
    "redis", "qdrant", "postgres",
    "docker",
    "youtube",
    "yahoo",
    "coda",
}

# Read-only subset of servers with broad tool access (including filesystem + alpaca)
ENABLED_TOOL_SUBSTRINGS = [
    # Filesystem — read-only ops
    "filesystem-read_", "filesystem-list_", "filesystem-search_", "filesystem-directory_",
    "filesystem-get_file_info",
    # GitHub — read-only ops
    "github-search_", "github-get_", "github-list_",
    # Alpaca — market data & account reads (no order placement)
    "alpaca-get_", "alpaca-list_",
]

# Operations allowed when CodingAgent is active (write-enabled mode)
CODING_ALLOWED_SUBSTRINGS = [
    "filesystem-write_file",
    "filesystem-edit_file",
    "filesystem-create_directory",
    "code-executor-execute_code",
    "code-executor-execute_code_file",
    "shell-shell_execute",
    "git-commit",
    "git-add",
]

# Always block these regardless of mode
APPROVAL_REQUIRED_SUBSTRINGS = [
    "filesystem-delete_", "filesystem-move_",
    "git-push",
    "github-create_", "github-update_", "github-delete_", "github-merge_",
    "alpaca-place_order", "alpaca-cancel_order", "alpaca-submit_",
    "docker-run",
    "redis-del", "redis-hset",
    "postgres-execute", "sqlite-write",
]

# Thread-local-ish flag: set to True by CodingToolSession
_CODING_MODE_ACTIVE: bool = False


def enable_coding_mode() -> None:
    global _CODING_MODE_ACTIVE
    _CODING_MODE_ACTIVE = True


def disable_coding_mode() -> None:
    global _CODING_MODE_ACTIVE
    _CODING_MODE_ACTIVE = False


def _is_enabled(tool_name: str) -> bool:
    name = tool_name.lower()
    # Check enabled server prefix
    server = name.split("-")[0] if "-" in name else ""
    if server in ENABLED_SERVER_PREFIXES:
        return True
    # Check specific allowed substrings
    return any(sub in name for sub in ENABLED_TOOL_SUBSTRINGS)


def _needs_approval(tool_name: str) -> bool:
    name = tool_name.lower()
    return any(sub in name for sub in APPROVAL_REQUIRED_SUBSTRINGS)


def _is_coding_allowed(tool_name: str) -> bool:
    """Returns True for write/exec tools when coding mode is active."""
    if not _CODING_MODE_ACTIVE:
        return False
    name = tool_name.lower()
    return any(sub in name for sub in CODING_ALLOWED_SUBSTRINGS)


class MCPToolRegistry:
    """Discovers tools from the gateway and exposes them as callables."""

    def __init__(self, url: str = GATEWAY_URL) -> None:
        self.url = url
        self._session: MCPSession | None = None
        self._tools: dict[str, dict] = {}
        self._initialized = False

    def connect(self) -> None:
        self._session = MCPSession(self.url)
        self._session.initialize()
        for tool in self._session.list_tools():
            self._tools[tool["name"]] = tool
        self._initialized = True

    def disconnect(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    def get_tool_schemas(self, filter_enabled: bool = True) -> list[dict]:
        if not self._initialized:
            self.connect()
        tools = list(self._tools.values())
        if filter_enabled:
            tools = [t for t in tools if _is_enabled(t["name"])]
        return tools

    def call(self, name: str, task_id: str = "unknown", **kwargs: Any) -> str:
        from .rules import tool_policy as get_policy
        policy = get_policy()

        if not self._initialized:
            self.connect()
        if name not in self._tools:
            result = f"[tool_error] Unknown tool: {name}"
            policy.log_call(task_id, name, kwargs, result, allowed=False)
            return result

        # policies/mcp-tool-policy.md: check allowlist
        # Coding mode unlocks write/exec tools scoped to feature branches
        if not policy.is_allowed(name) and not _is_coding_allowed(name):
            if _needs_approval(name):
                result = f"[approval_required] Tool '{name}' requires human approval."
            else:
                result = f"[policy_blocked] Tool '{name}' is not in the MCP allowlist."
            policy.log_call(task_id, name, kwargs, result, allowed=False)
            return result

        try:
            raw = self._session.call_tool(name, kwargs)
            # policies/mcp-tool-policy.md: scrub secrets from responses
            result = policy.scrub_secrets(raw)
            policy.log_call(task_id, name, kwargs, result[:200], allowed=True)
            return result
        except Exception as e:
            result = f"[tool_error] {name} failed: {e}"
            policy.log_call(task_id, name, kwargs, result, allowed=True)
            return result

    def as_dspy_tools(self) -> list:
        """Return list of dspy.Tool wrappers (requires dspy installed)."""
        import dspy

        schemas = self.get_tool_schemas()
        dspy_tools = []
        for schema in schemas:
            name = schema["name"]
            description = schema.get("description", name)
            input_schema = schema.get("inputSchema", {})
            props = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            registry_ref = self  # closure capture

            def make_fn(tool_name: str, tool_props: dict, tool_required: list):
                def tool_fn(**kwargs: Any) -> str:
                    # Validate required args
                    missing = [r for r in tool_required if r not in kwargs]
                    if missing:
                        return f"[tool_error] Missing required args: {missing}"
                    return registry_ref.call(tool_name, **kwargs)

                tool_fn.__name__ = tool_name
                tool_fn.__doc__ = description
                return tool_fn

            fn = make_fn(name, props, required)

            # Build arg descriptions for dspy.Tool
            args_desc = {k: v.get("description", k) for k, v in props.items()}
            try:
                dspy_tools.append(
                    dspy.Tool(fn, name=name, desc=description, args=args_desc)
                )
            except Exception:
                # Fallback: older dspy API
                dspy_tools.append(dspy.Tool(fn))

        return dspy_tools


def format_tool_list(schemas: list[dict]) -> str:
    lines = []
    for t in schemas:
        name = t["name"]
        desc = t.get("description", "")[:100]
        approval = " [APPROVAL REQUIRED]" if _needs_approval(name) else ""
        lines.append(f"- {name}{approval}: {desc}")
    return "\n".join(lines)
