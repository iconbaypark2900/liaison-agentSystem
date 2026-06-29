"""Workstation project profile loading for Liaison v0.2.0.

Implements the profile layer described in:
    docs/v0.2.0/PORTFOLIO_TASK_GENERATION.md

Responsibilities:
    - Safely load DGX and EVO project profile YAML.
    - Resolve which profile applies to a project.
    - Merge project registry fields with workstation defaults.
    - Enforce "stricter safety wins" behavior.

CLI integration:
    - Used by `liaison portfolio validate`.
    - Used by `liaison portfolio generate-tasks`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from .portfolio_registry import ProjectRecord


DEFAULT_DGX_PROFILE = Path("config/project_profiles/dgx_compute_projects.yaml")
DEFAULT_EVOX2_PROFILE = Path("config/project_profiles/evox2_lightweight_projects.yaml")


class PortfolioProfileError(ValueError):
    """Raised when portfolio profile loading or resolution fails."""


@dataclass(frozen=True)
class WorkstationProfile:
    """A normalized workstation-level project profile."""

    profile_id: str
    workstation: str
    display_name: str
    projects: list[str]
    workstation_defaults: dict[str, Any]
    routing_rules: dict[str, Any]
    validation_defaults: dict[str, Any]
    project_class_validation: dict[str, Any]
    safety_gates: dict[str, Any]
    task_generation_priorities: dict[str, Any]
    exclusions: dict[str, Any]
    promotion_policy: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(cls, path: Path, payload: Mapping[str, Any]) -> "WorkstationProfile":
        required = [
            "profile_id",
            "workstation",
            "display_name",
            "projects",
            "workstation_defaults",
            "routing_rules",
            "validation_defaults",
            "safety_gates",
            "task_generation_priorities",
            "exclusions",
            "promotion_policy",
        ]
        missing = [key for key in required if key not in payload]
        if missing:
            raise PortfolioProfileError(
                f"{path} is missing required profile fields: {', '.join(missing)}"
            )

        projects = payload["projects"]
        if not isinstance(projects, list):
            raise PortfolioProfileError(f"{path}: 'projects' must be a list.")

        return cls(
            profile_id=str(payload["profile_id"]),
            workstation=str(payload["workstation"]),
            display_name=str(payload["display_name"]),
            projects=[str(project) for project in projects],
            workstation_defaults=dict(payload["workstation_defaults"]),
            routing_rules=dict(payload["routing_rules"]),
            validation_defaults=dict(payload["validation_defaults"]),
            project_class_validation=dict(payload.get("project_class_validation", {})),
            safety_gates=dict(payload["safety_gates"]),
            task_generation_priorities=dict(payload["task_generation_priorities"]),
            exclusions=dict(payload["exclusions"]),
            promotion_policy=dict(payload["promotion_policy"]),
            raw=dict(payload),
        )

    def validate_for_project(self, project: ProjectRecord) -> None:
        if self.workstation != project.workstation:
            raise PortfolioProfileError(
                f"Profile {self.profile_id!r} workstation {self.workstation!r} "
                f"does not match project {project.project_id!r} workstation {project.workstation!r}."
            )
        if project.project_id not in self.projects:
            raise PortfolioProfileError(
                f"Project {project.project_id!r} is not listed in profile {self.profile_id!r}."
            )

    def default_for(self, key: str, fallback: Any = None) -> Any:
        return self.workstation_defaults.get(key, fallback)


@dataclass(frozen=True)
class ResolvedProjectProfile:
    """Project registry data merged with workstation profile defaults."""

    project: ProjectRecord
    profile: WorkstationProfile
    preferred_host: str
    preferred_executor: str
    fallback_executor: str
    default_model_route: str
    fallback_model_route: str | None
    validation_profiles: list[str]
    safety_gates: list[str]
    production_allowed: bool
    customer_release_allowed: bool
    live_allowed: bool
    requires_human_approval: bool

    def to_template_context(self) -> dict[str, Any]:
        return {
            "project_id": self.project.project_id,
            "project_path": self.project.path,
            "priority": self.project.priority,
            "default_host": self.preferred_host,
            "preferred_executor": self.preferred_executor,
            "fallback_executor": self.fallback_executor,
            "default_model_route": self.default_model_route,
            "fallback_model_route": self.fallback_model_route or "",
            "validation_profiles": self.validation_profiles,
            "safety_gates": self.safety_gates,
            "production_allowed": self.production_allowed,
            "customer_release_allowed": self.customer_release_allowed,
            "live_allowed": self.live_allowed,
            "requires_human_approval": self.requires_human_approval,
            "category": self.project.category,
            "tags": self.project.tags,
            "workstation": self.project.workstation,
        }


def safe_load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PortfolioProfileError(f"Missing profile YAML: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise PortfolioProfileError(f"Invalid YAML in profile {path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise PortfolioProfileError(f"Profile YAML root must be a mapping: {path}")
    return loaded


def load_workstation_profile(path: Path) -> WorkstationProfile:
    payload = safe_load_yaml(path)
    profile = WorkstationProfile.from_mapping(path, payload)
    validate_profile_safety(profile)
    return profile


def load_all_profiles(
    dgx_path: Path = DEFAULT_DGX_PROFILE,
    evox2_path: Path = DEFAULT_EVOX2_PROFILE,
) -> dict[str, WorkstationProfile]:
    profiles = {
        "dgx_spark": load_workstation_profile(dgx_path),
        "evox2_windows": load_workstation_profile(evox2_path),
    }

    for workstation, profile in profiles.items():
        if profile.workstation != workstation:
            raise PortfolioProfileError(
                f"Profile {profile.profile_id!r} declared workstation={profile.workstation!r}, "
                f"expected {workstation!r}."
            )

    return profiles


def resolve_project_profile(
    project: ProjectRecord,
    profiles: Mapping[str, WorkstationProfile],
) -> ResolvedProjectProfile:
    try:
        profile = profiles[project.workstation]
    except KeyError as exc:
        raise PortfolioProfileError(
            f"No workstation profile loaded for {project.workstation!r}."
        ) from exc

    profile.validate_for_project(project)

    default_host = str(project.default_host or profile.default_for("default_host", project.workstation))
    preferred_executor = str(
        project.preferred_executor or profile.default_for("preferred_executor", "shell")
    )
    fallback_executor = str(
        project.fallback_executor or profile.default_for("fallback_executor", "shell")
    )
    default_model_route = str(
        project.default_model_route or profile.default_for("default_model_route", "local_planner")
    )
    fallback_model_route = profile.default_for("fallback_model_route", None)

    validation_profiles = merge_unique(
        _list_from_any(profile.validation_defaults.get("required_profiles")),
        _list_from_any(profile.validation_defaults.get("recommended_profiles")),
        project.validation_profiles,
    )
    safety_gates = merge_unique(
        _list_from_any(profile.safety_gates.get("default")),
        project.safety_gates,
    )

    # Stricter safety wins. Any false from either project/profile means false.
    promotion_policy = profile.promotion_policy
    production_allowed = bool(project.production_allowed) and bool(
        promotion_policy.get("production_allowed", False)
    )
    customer_release_allowed = bool(project.customer_release_allowed) and bool(
        promotion_policy.get("customer_release_allowed", False)
    )
    live_allowed = bool(project.live_allowed) and bool(promotion_policy.get("live_allowed", False))
    requires_human_approval = bool(project.requires_human_approval) or bool(
        promotion_policy.get("requires_human_approval", True)
    )

    if production_allowed or customer_release_allowed or live_allowed:
        raise PortfolioProfileError(
            f"Resolved profile for {project.project_id!r} weakened promotion safety."
        )
    if not requires_human_approval:
        raise PortfolioProfileError(
            f"Resolved profile for {project.project_id!r} removed human approval."
        )

    return ResolvedProjectProfile(
        project=project,
        profile=profile,
        preferred_host=default_host,
        preferred_executor=preferred_executor,
        fallback_executor=fallback_executor,
        default_model_route=default_model_route,
        fallback_model_route=str(fallback_model_route) if fallback_model_route else None,
        validation_profiles=validation_profiles,
        safety_gates=safety_gates,
        production_allowed=production_allowed,
        customer_release_allowed=customer_release_allowed,
        live_allowed=live_allowed,
        requires_human_approval=requires_human_approval,
    )


def validate_profile_safety(profile: WorkstationProfile) -> None:
    policy = profile.promotion_policy
    unsafe_true_fields = [
        "production_allowed",
        "customer_release_allowed",
        "live_allowed",
    ]
    for field_name in unsafe_true_fields:
        if bool(policy.get(field_name, False)):
            raise PortfolioProfileError(
                f"Profile {profile.profile_id!r} has unsafe promotion_policy.{field_name}=true."
            )
    if not bool(policy.get("requires_human_approval", True)):
        raise PortfolioProfileError(
            f"Profile {profile.profile_id!r} must require human approval."
        )

    forbidden_actions = set(profile.exclusions.get("forbidden_default_actions", []))
    required_forbidden = {
        "production_deploy",
        "customer_release",
        "live_trade",
        "capital_allocation",
        "push_main",
        "force_push",
        "read_secrets",
        "approve_own_work",
    }
    missing = sorted(required_forbidden - forbidden_actions)
    if missing:
        raise PortfolioProfileError(
            f"Profile {profile.profile_id!r} missing forbidden default actions: {', '.join(missing)}"
        )


def merge_unique(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


def _list_from_any(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [str(value)]
    return [str(item) for item in value]
