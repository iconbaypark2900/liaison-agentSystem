"""Remote NIM endpoint execution module for Liaison v0.2.0.

Implements Phase 8B: real read-only NIM calls behind:
- approved remote request
- capability validation
- provider validation
- budget check
- NVIDIA_API_KEY presence
- outbox-only output
- JSONL logging

All execution is gated. When NVIDIA_API_KEY is absent or the policy is
disabled, functions return gracefully without making network calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


PROVIDER_REGISTRY_PATH = Path("config/provider_registry.yaml")
CAPABILITY_ROUTES_PATH = Path("config/capability_routes.yaml")
MODEL_ROUTES_PATH = Path("config/model_routes.yaml")
BUDGETS_PATH = Path("config/budgets.yaml")
BUDGET_LIMITS_PATH = Path("config/budget_limits.yaml")
REMOTE_LOG_PATH = Path("logs/remote_call_log.jsonl")
APPROVED_REMOTE_DIR = Path(".spark-flow/tasks") / "remote"


class RemoteExecutionError(RuntimeError):
    """Raised when a remote execution gate fails."""


@dataclass(frozen=True)
class RemoteCallResult:
    capability: str
    provider: str
    model: str
    status: str
    exit_code: int
    response_text: str
    latency_seconds: float
    estimated_cost_usd: float
    output_path: str | None
    log_path: str
    reason: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BudgetCheck:
    allowed: bool
    reason: str
    daily_spend_usd: float
    monthly_spend_usd: float
    daily_limit_usd: float
    monthly_limit_usd: float


def _safe_load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def load_provider_registry(root: Path = Path(".")) -> dict[str, Any]:
    return _safe_load_yaml(root / PROVIDER_REGISTRY_PATH)


def load_capability_routes(root: Path = Path(".")) -> dict[str, Any]:
    return _safe_load_yaml(root / CAPABILITY_ROUTES_PATH)


def load_model_routes(root: Path = Path(".")) -> dict[str, Any]:
    return _safe_load_yaml(root / MODEL_ROUTES_PATH)


def load_budgets(root: Path = Path(".")) -> dict[str, Any]:
    return _safe_load_yaml(root / BUDGETS_PATH)


def load_budget_limits(root: Path = Path(".")) -> dict[str, Any]:
    return _safe_load_yaml(root / BUDGET_LIMITS_PATH)


def resolve_capability(capability: str, root: Path = Path(".")) -> dict[str, Any]:
    routes = load_capability_routes(root)
    capabilities = routes.get("capabilities", {})
    cap_config = capabilities.get(capability)
    if cap_config is None:
        return {}
    return dict(cap_config)


def resolve_route(route_name: str, root: Path = Path(".")) -> dict[str, Any]:
    routes = load_model_routes(root)
    for section in ("local_models", "remote_models", "quantum_models"):
        section_models = routes.get(section, {})
        if route_name in section_models:
            return {"name": route_name, "provider": section_models[route_name].get("provider", ""),
                    "model": section_models[route_name].get("model", ""), "section": section,
                    **section_models[route_name]}
    return {}


def resolve_provider(provider_name: str, root: Path = Path(".")) -> dict[str, Any]:
    registry = load_provider_registry(root)
    providers = registry.get("providers", {})
    return dict(providers.get(provider_name, {}))


def check_approved_request(capability: str, root: Path = Path(".")) -> tuple[bool, str]:
    approved_path = root / APPROVED_REMOTE_DIR / f"approved.{capability}.md"
    if not approved_path.exists():
        return False, f"No approved remote request for capability '{capability}' at {approved_path}"
    return True, "Approved"


def check_nvidia_api_key() -> tuple[bool, str]:
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        return False, "NVIDIA_API_KEY environment variable not set"
    if len(key) < 10:
        return False, "NVIDIA_API_KEY appears invalid (too short)"
    return True, "Present"


def check_budget(root: Path = Path(".")) -> BudgetCheck:
    limits = load_budget_limits(root)
    defaults = limits.get("defaults", {})
    daily_limit = float(defaults.get("daily_remote_budget_usd", 2.0))
    monthly_limit = float(defaults.get("monthly_remote_budget_usd", 60.0))

    log_path = root / REMOTE_LOG_PATH
    daily_spend = 0.0
    monthly_spend = 0.0
    if log_path.exists():
        now = datetime.now(timezone.utc)
        for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            cost = float(entry.get("estimated_cost_usd", 0.0))
            ts = entry.get("timestamp", "")
            try:
                entry_date = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if entry_date.year == now.year and entry_date.month == now.month:
                monthly_spend += cost
            if entry_date.date() == now.date():
                daily_spend += cost

    allowed = daily_spend < daily_limit and monthly_spend < monthly_limit
    if not allowed:
        reason = f"Budget exceeded: daily ${daily_spend:.2f}/${daily_limit:.2f}, monthly ${monthly_spend:.2f}/${monthly_limit:.2f}"
    else:
        reason = "Within budget"
    return BudgetCheck(
        allowed=allowed,
        reason=reason,
        daily_spend_usd=round(daily_spend, 4),
        monthly_spend_usd=round(monthly_spend, 4),
        daily_limit_usd=daily_limit,
        monthly_limit_usd=monthly_limit,
    )


def validate_remote_call(
    capability: str, root: Path = Path(".")
) -> tuple[bool, str, dict[str, Any]]:
    """Run all pre-call validation gates. Returns (allowed, reason, context)."""
    cap_config = resolve_capability(capability, root)
    if not cap_config:
        return False, f"Unknown capability: {capability}", {}

    if not cap_config.get("remote_allowed", False):
        return False, f"Capability '{capability}' is not remote-allowed", cap_config

    if not cap_config.get("remote_read_only", False):
        return False, f"Capability '{capability}' is not read-only", cap_config

    preferred = cap_config.get("preferred_routes", [])
    if not preferred:
        return False, f"Capability '{capability}' has no preferred routes", cap_config

    route = resolve_route(preferred[0], root)
    if not route:
        return False, f"Route '{preferred[0]}' not found in model_routes.yaml", cap_config

    provider_name = route.get("provider", "")
    if provider_name != "nvidia_nim":
        return False, f"Provider '{provider_name}' is not nvidia_nim", cap_config

    provider = resolve_provider(provider_name, root)
    if not provider:
        return False, f"Provider '{provider_name}' not found in provider_registry.yaml", cap_config

    if provider.get("kind") != "remote":
        return False, f"Provider '{provider_name}' is not remote kind", cap_config

    approved, approval_msg = check_approved_request(capability, root)
    if not approved:
        return False, approval_msg, cap_config

    key_ok, key_msg = check_nvidia_api_key()
    if not key_ok:
        return False, key_msg, cap_config

    budget = check_budget(root)
    if not budget.allowed:
        return False, budget.reason, cap_config

    context = {
        "capability": capability,
        "cap_config": cap_config,
        "route": route,
        "provider": provider,
        "budget": asdict(budget),
    }
    return True, "All gates passed", context


def _build_nim_payload(
    model: str, messages: list[dict[str, str]], max_tokens: int = 4096,
    temperature: float = 0.2,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }


def _make_nim_request(
    base_url: str, chat_path: str, api_key: str, payload: dict[str, Any],
    timeout: int = 120,
) -> tuple[int, str, float]:
    """Make HTTP POST to NIM endpoint. Returns (status_code, response_text, latency)."""
    url = base_url.rstrip("/") + chat_path
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.status
            response_text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        response_text = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
    except urllib.error.URLError as exc:
        return -1, str(exc.reason), time.monotonic() - started
    except OSError as exc:
        return -1, str(exc), time.monotonic() - started
    latency = time.monotonic() - started
    return status_code, response_text, latency


def _estimate_cost(response_text: str, model: str) -> float:
    """Estimate cost based on response token count (rough heuristic)."""
    try:
        resp = json.loads(response_text)
        usage = resp.get("usage", {})
        completion_tokens = int(usage.get("completion_tokens", 0))
    except (json.JSONDecodeError, ValueError, TypeError):
        completion_tokens = len(response_text) // 4
    if "deepseek" in model:
        return round(completion_tokens * 0.00000014, 6)
    if "qwen" in model:
        return round(completion_tokens * 0.00000012, 6)
    if "nemotron" in model:
        return round(completion_tokens * 0.00000010, 6)
    return round(completion_tokens * 0.00000010, 6)


def _write_jsonl_log(log_path: Path, entry: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def _write_outbox(outbox_dir: Path, capability: str, content: str, suffix: str = "md") -> Path:
    outbox_dir.mkdir(parents=True, exist_ok=True)
    out_path = outbox_dir / f"remote_result.{capability}.{suffix}"
    out_path.write_text(content, encoding="utf-8")
    return out_path


def run_nim_endpoint(
    capability: str,
    messages: list[dict[str, str]] | None = None,
    *,
    root: Path = Path("."),
    outbox_dir: Path | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    timeout: int = 120,
) -> RemoteCallResult:
    """Execute a real NIM endpoint call with all safety gates.

    Gates (all must pass):
    1. Capability must be remote_allowed and remote_read_only
    2. Preferred route must resolve to an nvidia_nim provider
    3. Provider must be registered and remote kind
    4. Approved request file must exist
    5. NVIDIA_API_KEY must be present
    6. Budget must not be exceeded

    If any gate fails, returns a RemoteCallResult with status='blocked'.
    """
    log_path = root / REMOTE_LOG_PATH

    allowed, reason, context = validate_remote_call(capability, root)
    if not allowed:
        result = RemoteCallResult(
            capability=capability,
            provider="",
            model="",
            status="blocked",
            exit_code=1,
            response_text="",
            latency_seconds=0.0,
            estimated_cost_usd=0.0,
            output_path=None,
            log_path=str(log_path),
            reason=reason,
        )
        _write_jsonl_log(log_path, {
            **result.to_json(),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        return result

    route = context["route"]
    provider = context["provider"]
    model = route.get("model", "")
    base_url = provider.get("base_url", "")
    chat_path = provider.get("chat_completions_path", "/chat/completions")
    api_key = os.environ.get("NVIDIA_API_KEY", "")

    if messages is None:
        messages = [{"role": "user", "content": f"Analyze capability: {capability}"}]

    payload = _build_nim_payload(model, messages, max_tokens, temperature)

    status_code, response_text, latency = _make_nim_request(
        base_url, chat_path, api_key, payload, timeout,
    )

    cost = _estimate_cost(response_text, model)
    call_status = "success" if 200 <= status_code < 300 else "http_error"

    out_dir = outbox_dir or (root / ".spark-flow" / "tasks" / "default" / "outbox")
    output_path = _write_outbox(out_dir, capability, response_text, "json")

    result = RemoteCallResult(
        capability=capability,
        provider="nvidia_nim",
        model=model,
        status=call_status,
        exit_code=status_code,
        response_text=response_text[:4000],
        latency_seconds=round(latency, 3),
        estimated_cost_usd=cost,
        output_path=str(output_path),
        log_path=str(log_path),
        reason="NIM endpoint call completed",
    )

    _write_jsonl_log(log_path, {
        **result.to_json(),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "task_id": os.environ.get("LIAISON_TASK_ID", ""),
        "phase": os.environ.get("LIAISON_PHASE", ""),
        "approved_by": "human",
        "trigger_tags": context.get("cap_config", {}).get("trigger_tags", []),
        "prompt_file": None,
    })

    return result


def cmd_remote_run(args) -> int:
    """Handle `liaison remote run <capability>`."""
    root = Path(getattr(args, "root", "."))
    if getattr(args, "dry_run", False):
        allowed, reason, context = validate_remote_call(args.capability, root)
        print(json.dumps({
            "capability": args.capability,
            "dry_run": True,
            "allowed": allowed,
            "reason": reason,
            "context": context if allowed else {},
        }, indent=2, sort_keys=True))
        return 0 if allowed else 1

    result = run_nim_endpoint(args.capability, root=root)
    if getattr(args, "json", False):
        print(json.dumps(result.to_json(), indent=2, sort_keys=True))
    else:
        print(f"Capability:  {result.capability}")
        print(f"Provider:    {result.provider}")
        print(f"Model:       {result.model}")
        print(f"Status:      {result.status}")
        print(f"Exit code:   {result.exit_code}")
        print(f"Latency:     {result.latency_seconds}s")
        print(f"Cost:        ${result.estimated_cost_usd:.6f}")
        print(f"Output:      {result.output_path or 'N/A'}")
        print(f"Reason:      {result.reason}")
    return 0 if result.status == "success" else 1


def cmd_remote_validate(args) -> int:
    """Handle `liaison remote validate <capability>`."""
    root = Path(getattr(args, "root", "."))
    allowed, reason, context = validate_remote_call(args.capability, root)
    payload = {"capability": args.capability, "allowed": allowed, "reason": reason}
    if allowed:
        payload["route"] = context.get("route", {})
        payload["provider"] = context.get("provider", {})
        payload["budget"] = context.get("budget", {})
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Capability: {args.capability}")
        print(f"Allowed:    {allowed}")
        print(f"Reason:     {reason}")
    return 0 if allowed else 1


def cmd_remote_budget(args) -> int:
    """Handle `liaison remote budget`."""
    root = Path(getattr(args, "root", "."))
    budget = check_budget(root)
    if getattr(args, "json", False):
        print(json.dumps(asdict(budget), indent=2, sort_keys=True))
    else:
        print(f"Daily spend:   ${budget.daily_spend_usd:.4f} / ${budget.daily_limit_usd:.2f}")
        print(f"Monthly spend: ${budget.monthly_spend_usd:.4f} / ${budget.monthly_limit_usd:.2f}")
        print(f"Allowed:       {budget.allowed}")
        print(f"Reason:        {budget.reason}")
    return 0 if budget.allowed else 1


def register_remote_subparser(subparsers) -> None:
    """Register `liaison remote ...` commands."""
    parser = subparsers.add_parser(
        "remote",
        help="Remote NIM endpoint execution (Phase 8B).",
    )
    remote_subparsers = parser.add_subparsers(dest="remote_command", required=True)

    validate_parser = remote_subparsers.add_parser(
        "validate",
        help="Validate gates for a remote capability without calling the endpoint.",
    )
    validate_parser.add_argument("capability", help="Capability to validate.")
    validate_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    validate_parser.set_defaults(func=cmd_remote_validate)

    run_parser = remote_subparsers.add_parser(
        "run",
        help="Execute a real NIM endpoint call (requires all gates to pass).",
    )
    run_parser.add_argument("capability", help="Capability to execute.")
    run_parser.add_argument("--dry-run", action="store_true", help="Validate gates only, no HTTP call.")
    run_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    run_parser.set_defaults(func=cmd_remote_run)

    budget_parser = remote_subparsers.add_parser(
        "budget",
        help="Check remote call budget status.",
    )
    budget_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    budget_parser.set_defaults(func=cmd_remote_budget)


__all__: Sequence[str] = (
    "RemoteCallResult",
    "BudgetCheck",
    "RemoteExecutionError",
    "check_approved_request",
    "check_budget",
    "check_nvidia_api_key",
    "cmd_remote_budget",
    "cmd_remote_run",
    "cmd_remote_validate",
    "load_budget_limits",
    "load_budgets",
    "load_capability_routes",
    "load_model_routes",
    "load_provider_registry",
    "register_remote_subparser",
    "resolve_capability",
    "resolve_provider",
    "resolve_route",
    "run_nim_endpoint",
    "validate_remote_call",
)
