"""Centralized policy loader for Liaison v0.2.0.

Loads all 6 policy YAML files into frozen dataclasses and provides a single
`load_policies(root)` entrypoint returning a `PolicyBundle`.

This module replaces the hardcoded constants scattered across
portfolio_registry.py, portfolio_profiles.py, and worker.py with values
sourced from the canonical YAML files under policies/.

Usage:
    from liaison.policies import load_policies
    bundle = load_policies(root=Path("."))
    if bundle.agent_safety.production_allowed_by_default:
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


POLICIES_DIR = Path("policies")


def _safe_load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class AgentSafetyPolicy:
    """policies/agent_safety.yaml — global agent action boundaries."""
    production_allowed_by_default: bool
    customer_release_allowed_by_default: bool
    live_allowed_by_default: bool
    requires_human_approval: bool
    forbidden_actions: list[str]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "AgentSafetyPolicy":
        section = data.get("agent_safety", data) if isinstance(data, Mapping) else {}
        return cls(
            production_allowed_by_default=_as_bool(section.get("production_allowed_by_default"), False),
            customer_release_allowed_by_default=_as_bool(section.get("customer_release_allowed_by_default"), False),
            live_allowed_by_default=_as_bool(section.get("live_allowed_by_default"), False),
            requires_human_approval=_as_bool(section.get("requires_human_approval"), True),
            forbidden_actions=_as_list(section.get("forbidden_actions")),
        )


@dataclass(frozen=True)
class OperatorPreferencesPolicy:
    """policies/operator_preferences.yaml — behavioral guidance for operators/agents."""
    do_not_modify_attached_plan_file: bool
    use_existing_todos: bool
    mark_todos_in_progress_instead_of_recreating: bool
    prefer_consolidation_into_primary_clone: bool
    do_not_publish_cursor_dir: bool
    if_cursor_dir_committed: str
    prefer_extending_existing_structure: bool
    create_reviewable_artifacts: bool

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "OperatorPreferencesPolicy":
        section = data.get("operator_preferences", data) if isinstance(data, Mapping) else {}
        cursor = section.get("cursor_plans", {}) or {}
        worktrees = section.get("worktrees", {}) or {}
        git_hygiene = section.get("git_hygiene", {}) or {}
        impl = section.get("implementation_style", {}) or {}
        return cls(
            do_not_modify_attached_plan_file=_as_bool(cursor.get("do_not_modify_attached_plan_file"), True),
            use_existing_todos=_as_bool(cursor.get("use_existing_todos"), True),
            mark_todos_in_progress_instead_of_recreating=_as_bool(cursor.get("mark_todos_in_progress_instead_of_recreating"), True),
            prefer_consolidation_into_primary_clone=_as_bool(worktrees.get("prefer_consolidation_into_primary_clone"), True),
            do_not_publish_cursor_dir=_as_bool(git_hygiene.get("do_not_publish_cursor_dir"), True),
            if_cursor_dir_committed=str(git_hygiene.get("if_cursor_dir_committed", "git rm -r --cached .cursor")),
            prefer_extending_existing_structure=_as_bool(impl.get("prefer_extending_existing_structure"), True),
            create_reviewable_artifacts=_as_bool(impl.get("create_reviewable_artifacts"), True),
        )


@dataclass(frozen=True)
class SecretHandlingPolicy:
    """policies/secret_handling.yaml — secret access and logging rules."""
    raw_secret_values_forbidden_in_prompts: bool
    raw_secret_values_forbidden_in_artifacts: bool
    raw_secret_values_forbidden_in_logs: bool
    forbidden_secret_types: list[str]
    allowed_references: list[str]
    forbidden_paths: list[str]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SecretHandlingPolicy":
        section = data.get("secret_handling", data) if isinstance(data, Mapping) else {}
        return cls(
            raw_secret_values_forbidden_in_prompts=_as_bool(section.get("raw_secret_values_forbidden_in_prompts"), True),
            raw_secret_values_forbidden_in_artifacts=_as_bool(section.get("raw_secret_values_forbidden_in_artifacts"), True),
            raw_secret_values_forbidden_in_logs=_as_bool(section.get("raw_secret_values_forbidden_in_logs"), True),
            forbidden_secret_types=_as_list(section.get("forbidden_secret_types")),
            allowed_references=_as_list(section.get("allowed_references")),
            forbidden_paths=_as_list(section.get("forbidden_paths")),
        )


@dataclass(frozen=True)
class ProductionReadinessPolicy:
    """policies/production_readiness.yaml — gates before production deploy."""
    production_allowed_by_default: bool
    required_before_production: list[str]
    forbidden: list[str]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ProductionReadinessPolicy":
        section = data.get("production_readiness", data) if isinstance(data, Mapping) else {}
        return cls(
            production_allowed_by_default=_as_bool(section.get("production_allowed_by_default"), False),
            required_before_production=_as_list(section.get("required_before_production")),
            forbidden=_as_list(section.get("forbidden")),
        )


@dataclass(frozen=True)
class CustomerReleasePolicy:
    """policies/customer_release.yaml — gates before customer release."""
    customer_release_allowed_by_default: bool
    required_before_customer_release: list[str]
    forbidden: list[str]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "CustomerReleasePolicy":
        section = data.get("customer_release", data) if isinstance(data, Mapping) else {}
        return cls(
            customer_release_allowed_by_default=_as_bool(section.get("customer_release_allowed_by_default"), False),
            required_before_customer_release=_as_list(section.get("required_before_customer_release")),
            forbidden=_as_list(section.get("forbidden")),
        )


@dataclass(frozen=True)
class ConfidenceCalibrationPolicy:
    """policies/confidence_calibration.yaml — trading/prediction calibration gates."""
    live_allowed_by_default: bool
    production_allowed_by_default: bool
    customer_release_allowed_by_default: bool
    applies_to_projects: list[str]
    applies_to_task_types: list[str]
    forbidden_patterns: list[str]
    minimum_samples: dict[str, int]
    required_before_live: list[str]
    blocked_actions: list[str]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ConfidenceCalibrationPolicy":
        section = data.get("confidence_calibration", data) if isinstance(data, Mapping) else {}
        raw_samples = section.get("minimum_samples", {}) or {}
        samples = {str(k): _as_int(v, 0) for k, v in raw_samples.items()} if isinstance(raw_samples, Mapping) else {}
        return cls(
            live_allowed_by_default=_as_bool(section.get("live_allowed_by_default"), False),
            production_allowed_by_default=_as_bool(section.get("production_allowed_by_default"), False),
            customer_release_allowed_by_default=_as_bool(section.get("customer_release_allowed_by_default"), False),
            applies_to_projects=_as_list(section.get("applies_to_projects")),
            applies_to_task_types=_as_list(section.get("applies_to_task_types")),
            forbidden_patterns=_as_list(section.get("forbidden_patterns")),
            minimum_samples=samples,
            required_before_live=_as_list(section.get("required_before_live")),
            blocked_actions=_as_list(section.get("blocked_actions")),
        )

    def applies_to_project(self, project_name: str) -> bool:
        """Check if this policy applies to a given project name."""
        name_lower = project_name.lower()
        return any(pattern.lower() in name_lower for pattern in self.applies_to_projects)

    def applies_to_task_type(self, task_type: str) -> bool:
        """Check if this policy applies to a given task type."""
        type_lower = task_type.lower()
        return any(pattern.lower() in type_lower for pattern in self.applies_to_task_types)

    def scan_for_fabricated_edges(self, text: str) -> list[str]:
        """Scan text for forbidden fabricated-edge patterns. Returns list of matched patterns."""
        text_lower = text.lower()
        return [p for p in self.forbidden_patterns if p.lower() in text_lower]


@dataclass(frozen=True)
class PolicyBundle:
    """All 6 policy files loaded into frozen dataclasses."""
    agent_safety: AgentSafetyPolicy
    operator_preferences: OperatorPreferencesPolicy
    secret_handling: SecretHandlingPolicy
    production_readiness: ProductionReadinessPolicy
    customer_release: CustomerReleasePolicy
    confidence_calibration: ConfidenceCalibrationPolicy


_cache: dict[str, PolicyBundle] = {}


def load_policies(root: Path = Path(".")) -> PolicyBundle:
    """Load all policy YAML files from root/policies/ into a PolicyBundle.

    Results are cached per root path. Missing files yield safe defaults.
    """
    cache_key = str(root.resolve())
    if cache_key in _cache:
        return _cache[cache_key]

    policies_dir = root / POLICIES_DIR

    bundle = PolicyBundle(
        agent_safety=AgentSafetyPolicy.from_mapping(
            _safe_load_yaml(policies_dir / "agent_safety.yaml")
        ),
        operator_preferences=OperatorPreferencesPolicy.from_mapping(
            _safe_load_yaml(policies_dir / "operator_preferences.yaml")
        ),
        secret_handling=SecretHandlingPolicy.from_mapping(
            _safe_load_yaml(policies_dir / "secret_handling.yaml")
        ),
        production_readiness=ProductionReadinessPolicy.from_mapping(
            _safe_load_yaml(policies_dir / "production_readiness.yaml")
        ),
        customer_release=CustomerReleasePolicy.from_mapping(
            _safe_load_yaml(policies_dir / "customer_release.yaml")
        ),
        confidence_calibration=ConfidenceCalibrationPolicy.from_mapping(
            _safe_load_yaml(policies_dir / "confidence_calibration.yaml")
        ),
    )
    _cache[cache_key] = bundle
    return bundle


def clear_cache() -> None:
    """Clear the policy cache (useful for tests)."""
    _cache.clear()


__all__: Sequence[str] = (
    "AgentSafetyPolicy",
    "ConfidenceCalibrationPolicy",
    "CustomerReleasePolicy",
    "OperatorPreferencesPolicy",
    "PolicyBundle",
    "ProductionReadinessPolicy",
    "SecretHandlingPolicy",
    "clear_cache",
    "load_policies",
)
