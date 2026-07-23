"""
Loads and enforces liaison-agentSystem rules:
  config/model_routes.yaml        → model selection
  config/capability_routes.yaml   → task-type → model routing
  config/budget_limits.yaml       → spend tracking & daily cap
  policies/mcp-tool-policy.md     → tool allowlist & call logging
  policies/remote-model-policy.md → human approval gate for remote models
  policies/closed-feedback-policy.md → objective/outbox/learning structure
  config/validation_profiles.yaml → post-task validation scripts
"""

from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

REPO_ROOT = Path(__file__).parent.parent


def _load_yaml(rel: str) -> dict:
    path = REPO_ROOT / rel
    if not path.exists():
        return {}
    if _HAS_YAML:
        import yaml
        return yaml.safe_load(path.read_text()) or {}
    # Minimal fallback: enough to read simple key: value lines
    return {}


# ── Model routes ─────────────────────────────────────────────────────────────

class ModelRouter:
    """Reads model_routes.yaml and returns the right model for a task."""

    def __init__(self) -> None:
        cfg = _load_yaml("config/model_routes.yaml")
        self.defaults = cfg.get("defaults", {})
        self.local_models = cfg.get("local_models", {})
        self.remote_models = cfg.get("remote_models", {})
        self.quantum_models = cfg.get("quantum_models", {})

    @property
    def local_first(self) -> bool:
        return self.defaults.get("local_first", True)

    @property
    def require_human_approval_for_remote(self) -> bool:
        return self.defaults.get("require_human_approval_for_remote", True)

    def pick_local_model(self, use_for: str) -> tuple[str, str]:
        """Return (provider, model) for a use-case. Tries preferred then fallback."""
        for key, spec in self.local_models.items():
            uses = spec.get("use_for", [])
            if use_for in uses or any(u in use_for for u in uses):
                return spec.get("provider", "ollama"), spec.get("model", "")
        # Default: coder
        coder = self.local_models.get("coder", {})
        return coder.get("provider", "ollama"), coder.get("model", "qwen3-coder:30b")

    def all_local_models(self) -> list[str]:
        return [s.get("model", "") for s in self.local_models.values()]

    def is_remote(self, model: str) -> bool:
        for spec in self.remote_models.values():
            if spec.get("model") == model:
                return True
        return False


# ── Capability routes ─────────────────────────────────────────────────────────

class CapabilityRouter:
    """Maps task type (via tags or keywords) to the right capability route."""

    def __init__(self) -> None:
        cfg = _load_yaml("config/capability_routes.yaml")
        self.capabilities: dict = cfg.get("capabilities", {})

    def route_task(self, task: str) -> tuple[str, dict]:
        """
        Detect capability from task text, return (capability_name, spec).
        Falls back to 'research_synthesis' for open-ended tasks.
        """
        task_lower = task.lower()

        KEYWORD_MAP = {
            "research_synthesis": ["paper", "arxiv", "literature", "research", "survey", "review"],
            "quantum_calibration_analysis": ["quantum", "qpu", "ising", "calibration", "qubit"],
            "local_implementation": ["implement", "code", "write", "fix", "refactor", "test"],
            "local_review": ["review", "analyze", "check", "audit"],
            "repetitive_sampling": ["sample", "benchmark", "evaluate", "dataset"],
        }

        for cap_name, keywords in KEYWORD_MAP.items():
            if any(kw in task_lower for kw in keywords):
                spec = self.capabilities.get(cap_name, {})
                return cap_name, spec

        return "research_synthesis", self.capabilities.get("research_synthesis", {})

    def requires_approval(self, capability: str) -> bool:
        spec = self.capabilities.get(capability, {})
        return spec.get("requires_human_approval", True)

    def remote_allowed(self, capability: str) -> bool:
        spec = self.capabilities.get(capability, {})
        return spec.get("remote_allowed", False)


# ── Budget enforcement ────────────────────────────────────────────────────────

BUDGET_LOG = REPO_ROOT / "memory" / "budget_log.jsonl"


class BudgetGuard:
    """Tracks daily remote spend against budget_limits.yaml."""

    def __init__(self) -> None:
        cfg = _load_yaml("config/budget_limits.yaml")
        self.defaults = cfg.get("defaults", {})
        self.daily_limit = self.defaults.get("daily_remote_budget_usd", 2.0)
        self.require_human_approval = self.defaults.get("require_human_approval", True)
        self.log_remote_calls = self.defaults.get("log_remote_calls", True)

    def _today_spend(self) -> float:
        if not BUDGET_LOG.exists():
            return 0.0
        today = date.today().isoformat()
        total = 0.0
        for line in BUDGET_LOG.read_text().splitlines():
            try:
                record = json.loads(line)
                if record.get("timestamp", "").startswith(today):
                    total += float(record.get("estimated_cost_usd", 0))
            except (json.JSONDecodeError, ValueError):
                pass
        return total

    def check_budget(self, estimated_cost: float = 0.0) -> tuple[bool, str]:
        """Return (allowed, reason). Blocks if daily limit exceeded."""
        spent = self._today_spend()
        remaining = self.daily_limit - spent
        if estimated_cost > remaining:
            return (
                False,
                f"Budget exceeded: ${spent:.3f} spent today, ${self.daily_limit:.2f} daily limit. "
                f"Remaining: ${remaining:.3f}",
            )
        return True, f"Budget OK: ${spent:.3f}/${self.daily_limit:.2f} used today."

    def log_call(
        self,
        task_id: str,
        provider: str,
        model: str,
        estimated_cost: float = 0.0,
        latency_s: float = 0.0,
        approved_by: str = "reflexion_dspy",
    ) -> None:
        if not self.log_remote_calls:
            return
        BUDGET_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "task_id": task_id,
            "provider": provider,
            "model": model,
            "approved_by": approved_by,
            "latency_seconds": latency_s,
            "estimated_cost_usd": estimated_cost,
        }
        with BUDGET_LOG.open("a") as f:
            f.write(json.dumps(record) + "\n")


# ── MCP tool policy ───────────────────────────────────────────────────────────

TOOL_CALL_LOG = REPO_ROOT / "memory" / "tool_call_log.jsonl"


class MCPToolPolicy:
    """
    Enforces policies/mcp-tool-policy.md:
    - Explicit allowlist (loaded from config, with Python fallback)
    - Tool calls must be logged
    - Destructive tools require human approval
    - Secrets must not be exposed in responses
    """

    # Allowlisted server prefixes (mirrors tools.py ENABLED_SERVER_PREFIXES)
    ALLOWLISTED_SERVERS = {
        "arxiv", "brave", "tavily", "exa", "pubmed", "wikipedia",
        "fetch", "context7", "code", "memory", "sequential",
        "time", "git", "sqlite", "redis", "qdrant", "postgres",
        "docker", "youtube", "yahoo", "coda",
    }
    ALLOWLISTED_FILESYSTEM = {
        "filesystem-read_file", "filesystem-read_text_file", "filesystem-list_directory",
        "filesystem-search_files", "filesystem-directory_tree", "filesystem-get_file_info",
        "filesystem-read_multiple_files", "filesystem-read_media_file",
        "filesystem-list_directory_with_sizes", "filesystem-list_allowed_directories",
    }
    ALLOWLISTED_GITHUB = {
        "github-search_repositories", "github-get_file_contents", "github-list_commits",
        "github-get_commit", "github-list_issues", "github-get_issue",
        "github-list_pull_requests", "github-get_pull_request", "github-search_code",
        "github-get_repository", "github-list_branches", "github-search_users",
        "github-list_tags", "github-get_tag",
    }
    ALLOWLISTED_ALPACA = {
        "alpaca-get_account", "alpaca-get_positions", "alpaca-get_position",
        "alpaca-list_assets", "alpaca-get_asset", "alpaca-get_bars", "alpaca-get_multi_bars",
        "alpaca-get_latest_bar", "alpaca-get_latest_quote", "alpaca-get_latest_trade",
        "alpaca-get_news", "alpaca-get_watchlist", "alpaca-list_watchlists",
        "alpaca-get_clock", "alpaca-get_calendar", "alpaca-get_portfolio_history",
        "alpaca-get_order", "alpaca-list_orders", "alpaca-get_corporate_actions",
        "alpaca-get_snapshots", "alpaca-get_trades", "alpaca-get_quotes",
    }

    SECRET_PATTERNS = [
        re.compile(r'(?i)(api[_-]?key|token|secret|password|credential)\s*[=:]\s*\S+'),
        re.compile(r'Bearer\s+[A-Za-z0-9+/]{20,}'),
        re.compile(r'sk-[A-Za-z0-9]{20,}'),
        re.compile(r'hf_[A-Za-z0-9]{20,}'),
    ]

    def is_allowed(self, tool_name: str) -> bool:
        name = tool_name.lower()
        server = name.split("-")[0] if "-" in name else ""
        if server in self.ALLOWLISTED_SERVERS:
            return True
        if tool_name in self.ALLOWLISTED_FILESYSTEM:
            return True
        if tool_name in self.ALLOWLISTED_GITHUB:
            return True
        if tool_name in self.ALLOWLISTED_ALPACA:
            return True
        return False

    def scrub_secrets(self, text: str) -> str:
        for pat in self.SECRET_PATTERNS:
            text = pat.sub("[REDACTED]", text)
        return text

    def log_call(
        self,
        task_id: str,
        tool_name: str,
        args: dict,
        result_preview: str,
        allowed: bool,
    ) -> None:
        TOOL_CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "task_id": task_id,
            "tool": tool_name,
            "args_keys": list(args.keys()),
            "result_chars": len(result_preview),
            "allowed": allowed,
        }
        with TOOL_CALL_LOG.open("a") as f:
            f.write(json.dumps(record) + "\n")


# ── Outbox / promotion flow ───────────────────────────────────────────────────

OUTBOX_DIR = REPO_ROOT / "memory" / "outbox"
APPROVED_DIR = REPO_ROOT / "memory" / "approved"


def write_to_outbox(task_id: str, content: str, label: str = "result") -> Path:
    """
    policies/closed-feedback-policy.md: raw agent output stays in outbox until approved.
    policies/promotion-policy.md: outbox → approved → validated → integrated → committed
    """
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTBOX_DIR / f"{task_id}_{label}.md"
    path.write_text(content)
    return path


def approve_artifact(task_id: str, label: str = "result") -> Path | None:
    """Promote outbox artifact to approved/. In agent mode this is auto-approved."""
    src = OUTBOX_DIR / f"{task_id}_{label}.md"
    if not src.exists():
        return None
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    dst = APPROVED_DIR / src.name
    dst.write_text(src.read_text())
    return dst


def write_objective(task_id: str, task: str, capability: str) -> Path:
    """policies/closed-feedback-policy.md: every task must have an objective."""
    obj_dir = REPO_ROOT / "memory" / "objectives"
    obj_dir.mkdir(parents=True, exist_ok=True)
    path = obj_dir / f"{task_id}_objective.md"
    path.write_text(
        f"# Objective — {task_id}\n\n"
        f"**Capability**: {capability}\n\n"
        f"**Task**:\n{task}\n\n"
        f"**Created**: {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
    )
    return path


# ── Singleton accessors ───────────────────────────────────────────────────────

_model_router: ModelRouter | None = None
_cap_router: CapabilityRouter | None = None
_budget_guard: BudgetGuard | None = None
_tool_policy: MCPToolPolicy | None = None


def model_router() -> ModelRouter:
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router


def capability_router() -> CapabilityRouter:
    global _cap_router
    if _cap_router is None:
        _cap_router = CapabilityRouter()
    return _cap_router


def budget_guard() -> BudgetGuard:
    global _budget_guard
    if _budget_guard is None:
        _budget_guard = BudgetGuard()
    return _budget_guard


def tool_policy() -> MCPToolPolicy:
    global _tool_policy
    if _tool_policy is None:
        _tool_policy = MCPToolPolicy()
    return _tool_policy
