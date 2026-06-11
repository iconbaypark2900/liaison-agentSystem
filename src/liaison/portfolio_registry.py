"""Portfolio registry loading and validation for Liaison v0.2.0.

This module is an implementation stub for:
    docs/v0.2.0/PORTFOLIO_TASK_GENERATION.md

Responsibilities:
    - Safely load YAML registry files.
    - Parse active project records.
    - Parse merge-source and archive exclusions.
    - Validate portfolio counts.
    - Ensure merge/archive projects are excluded from active automation.
    - Provide project lookup helpers for future CLI commands.

CLI integration TODOs:
    - `liaison portfolio list`
    - `liaison portfolio list --host <host>`
    - `liaison portfolio counts`
    - `liaison portfolio counts --json`
    - `liaison portfolio validate`
    - `liaison portfolio validate --json`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


DEFAULT_ACTIVE_REGISTRY = Path("config/project_registry.active.yaml")
DEFAULT_MERGE_SOURCES_REGISTRY = Path("config/project_registry.merge_sources.yaml")
DEFAULT_ARCHIVES_REGISTRY = Path("config/project_registry.archives.yaml")

EXPECTED_ACTIVE_PROJECT_COUNT = 41
EXPECTED_DGX_ACTIVE_COUNT = 18
EXPECTED_EVOX2_ACTIVE_COUNT = 23
EXPECTED_MERGE_SOURCE_COUNT = 7
EXPECTED_ARCHIVE_COUNT = 7

VALID_WORKSTATIONS = {"dgx_spark", "evox2_windows"}


class PortfolioRegistryError(ValueError):
    """Raised when portfolio registry loading or validation fails."""


@dataclass(frozen=True)
class ProjectRecord:
    """A normalized active project registry record."""

    project_id: str
    enabled: bool
    active: bool
    workstation: str
    path: str
    category: str
    priority: str
    tags: list[str]
    default_host: str
    preferred_executor: str
    default_model_route: str
    validation_profiles: list[str]
    safety_gates: list[str]
    status: str
    fallback_executor: str | None = None
    production_allowed: bool = False
    customer_release_allowed: bool = False
    live_allowed: bool = False
    requires_human_approval: bool = True
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(cls, project_id: str, payload: Mapping[str, Any]) -> "ProjectRecord":
        required = [
            "enabled",
            "active",
            "workstation",
            "path",
            "category",
            "priority",
            "tags",
            "default_host",
            "preferred_executor",
            "default_model_route",
            "validation_profiles",
            "safety_gates",
            "status",
        ]
        missing = [key for key in required if key not in payload]
        if missing:
            raise PortfolioRegistryError(
                f"Project {project_id!r} is missing required fields: {', '.join(missing)}"
            )

        return cls(
            project_id=project_id,
            enabled=bool(payload["enabled"]),
            active=bool(payload["active"]),
            workstation=str(payload["workstation"]),
            path=str(payload["path"]),
            category=str(payload["category"]),
            priority=str(payload["priority"]),
            tags=_as_str_list(payload.get("tags"), field_name=f"{project_id}.tags"),
            default_host=str(payload["default_host"]),
            preferred_executor=str(payload["preferred_executor"]),
            default_model_route=str(payload["default_model_route"]),
            validation_profiles=_as_str_list(
                payload.get("validation_profiles"),
                field_name=f"{project_id}.validation_profiles",
            ),
            safety_gates=_as_str_list(
                payload.get("safety_gates"), field_name=f"{project_id}.safety_gates"
            ),
            status=str(payload["status"]),
            fallback_executor=(
                str(payload["fallback_executor"]) if payload.get("fallback_executor") is not None else None
            ),
            production_allowed=bool(payload.get("production_allowed", False)),
            customer_release_allowed=bool(payload.get("customer_release_allowed", False)),
            live_allowed=bool(payload.get("live_allowed", False)),
            requires_human_approval=bool(payload.get("requires_human_approval", True)),
            raw=dict(payload),
        )

    def validate_safety(self) -> None:
        if self.workstation not in VALID_WORKSTATIONS:
            raise PortfolioRegistryError(
                f"Project {self.project_id!r} has invalid workstation {self.workstation!r}."
            )
        if self.default_host != self.workstation:
            raise PortfolioRegistryError(
                f"Project {self.project_id!r} default_host={self.default_host!r} "
                f"does not match workstation={self.workstation!r}."
            )
        if not self.enabled or not self.active or self.status != "active":
            raise PortfolioRegistryError(
                f"Project {self.project_id!r} must be enabled, active, and status=active."
            )
        if self.production_allowed:
            raise PortfolioRegistryError(f"Project {self.project_id!r} enables production by default.")
        if self.customer_release_allowed:
            raise PortfolioRegistryError(
                f"Project {self.project_id!r} enables customer release by default."
            )
        if self.live_allowed:
            raise PortfolioRegistryError(f"Project {self.project_id!r} enables live/capital behavior.")
        if not self.requires_human_approval:
            raise PortfolioRegistryError(
                f"Project {self.project_id!r} must require human approval."
            )

        lower_tags = {tag.lower() for tag in self.tags}
        calibration_tags = {
            "trading",
            "event_market",
            "prediction",
            "calibration",
            "finance",
            "confidence",
            "financial_portfolio",
            "portfolio_optimization",
            "scoring",
            "ranking",
        }
        if lower_tags & calibration_tags:
            if "confidence_calibration" not in self.safety_gates:
                raise PortfolioRegistryError(
                    f"Project {self.project_id!r} is prediction/trading-related but lacks "
                    "confidence_calibration safety gate."
                )

        if lower_tags & {"medical", "clinical", "healthcare", "customer_facing", "ecommerce"}:
            if "customer_release" not in self.safety_gates:
                raise PortfolioRegistryError(
                    f"Project {self.project_id!r} is medical/customer-facing but lacks "
                    "customer_release safety gate."
                )


@dataclass(frozen=True)
class PortfolioCounts:
    active_project_count: int
    dgx_active_count: int
    evox2_active_count: int
    merge_sources_excluded: int
    archive_candidates_excluded: int
    production_allowed_by_default: bool
    customer_release_allowed_by_default: bool
    live_allowed_by_default: bool
    requires_human_approval: bool

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PortfolioCounts":
        return cls(
            active_project_count=int(payload.get("active_project_count", 0)),
            dgx_active_count=int(payload.get("dgx_active_count", 0)),
            evox2_active_count=int(payload.get("evox2_active_count", 0)),
            merge_sources_excluded=int(payload.get("merge_sources_excluded", 0)),
            archive_candidates_excluded=int(payload.get("archive_candidates_excluded", 0)),
            production_allowed_by_default=bool(payload.get("production_allowed_by_default", False)),
            customer_release_allowed_by_default=bool(
                payload.get("customer_release_allowed_by_default", False)
            ),
            live_allowed_by_default=bool(payload.get("live_allowed_by_default", False)),
            requires_human_approval=bool(payload.get("requires_human_approval", True)),
        )


@dataclass(frozen=True)
class ExclusionRegistry:
    """Merge-source or archive exclusion registry."""

    registry_type: str
    project_ids: set[str]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def count(self) -> int:
        return len(self.project_ids)


@dataclass(frozen=True)
class ActivePortfolioRegistry:
    version: str
    counts: PortfolioCounts
    projects: dict[str, ProjectRecord]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def by_host(self, host: str) -> list[ProjectRecord]:
        if host not in VALID_WORKSTATIONS:
            raise PortfolioRegistryError(f"Unknown workstation/host: {host!r}")
        return sorted(
            (project for project in self.projects.values() if project.workstation == host),
            key=lambda project: project.project_id.lower(),
        )

    def get(self, project_id: str) -> ProjectRecord:
        try:
            return self.projects[project_id]
        except KeyError as exc:
            raise PortfolioRegistryError(f"Unknown active project: {project_id!r}") from exc

    def list_project_ids(self, host: str | None = None) -> list[str]:
        if host is None:
            return sorted(self.projects)
        return [project.project_id for project in self.by_host(host)]

    def computed_counts(self) -> dict[str, int]:
        dgx = sum(1 for project in self.projects.values() if project.workstation == "dgx_spark")
        evo = sum(1 for project in self.projects.values() if project.workstation == "evox2_windows")
        return {
            "active_project_count": len(self.projects),
            "dgx_active_count": dgx,
            "evox2_active_count": evo,
        }


def safe_load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML with yaml.safe_load and return an object mapping."""
    if not path.exists():
        raise PortfolioRegistryError(f"Missing YAML file: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise PortfolioRegistryError(f"Invalid YAML in {path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise PortfolioRegistryError(f"YAML root must be a mapping: {path}")
    return loaded


def load_active_registry(path: Path = DEFAULT_ACTIVE_REGISTRY) -> ActivePortfolioRegistry:
    raw = safe_load_yaml(path)

    if "portfolio" not in raw:
        raise PortfolioRegistryError(f"{path} is missing top-level 'portfolio'.")
    if "projects" not in raw:
        raise PortfolioRegistryError(f"{path} is missing top-level 'projects'.")

    projects_raw = raw["projects"]
    if not isinstance(projects_raw, dict):
        raise PortfolioRegistryError(f"{path}: 'projects' must be a mapping.")

    projects = {
        project_id: ProjectRecord.from_mapping(project_id, payload)
        for project_id, payload in projects_raw.items()
    }
    counts = PortfolioCounts.from_mapping(raw["portfolio"])

    registry = ActivePortfolioRegistry(
        version=str(raw.get("version", "0.2.0")),
        counts=counts,
        projects=projects,
        raw=raw,
    )
    validate_active_registry(registry)
    return registry


def load_merge_source_registry(path: Path = DEFAULT_MERGE_SOURCES_REGISTRY) -> ExclusionRegistry:
    raw = safe_load_yaml(path)
    records = raw.get("merge_sources", {})
    if not isinstance(records, dict):
        raise PortfolioRegistryError(f"{path}: 'merge_sources' must be a mapping.")
    return ExclusionRegistry(
        registry_type=str(raw.get("registry_type", "merge_sources")),
        project_ids=set(records.keys()),
        raw=raw,
    )


def load_archive_registry(path: Path = DEFAULT_ARCHIVES_REGISTRY) -> ExclusionRegistry:
    raw = safe_load_yaml(path)
    records = raw.get("archives", {})
    if not isinstance(records, dict):
        raise PortfolioRegistryError(f"{path}: 'archives' must be a mapping.")
    return ExclusionRegistry(
        registry_type=str(raw.get("registry_type", "archives")),
        project_ids=set(records.keys()),
        raw=raw,
    )


def validate_active_registry(registry: ActivePortfolioRegistry) -> None:
    """Validate active registry internal consistency and v0.2.0 safety defaults."""
    counts = registry.computed_counts()

    expected = {
        "active_project_count": registry.counts.active_project_count,
        "dgx_active_count": registry.counts.dgx_active_count,
        "evox2_active_count": registry.counts.evox2_active_count,
    }
    for key, expected_value in expected.items():
        if counts[key] != expected_value:
            raise PortfolioRegistryError(
                f"Registry count mismatch for {key}: expected {expected_value}, computed {counts[key]}."
            )

    if registry.counts.active_project_count != EXPECTED_ACTIVE_PROJECT_COUNT:
        raise PortfolioRegistryError(
            f"Expected active_project_count={EXPECTED_ACTIVE_PROJECT_COUNT}, "
            f"found {registry.counts.active_project_count}."
        )
    if registry.counts.dgx_active_count != EXPECTED_DGX_ACTIVE_COUNT:
        raise PortfolioRegistryError(
            f"Expected dgx_active_count={EXPECTED_DGX_ACTIVE_COUNT}, "
            f"found {registry.counts.dgx_active_count}."
        )
    if registry.counts.evox2_active_count != EXPECTED_EVOX2_ACTIVE_COUNT:
        raise PortfolioRegistryError(
            f"Expected evox2_active_count={EXPECTED_EVOX2_ACTIVE_COUNT}, "
            f"found {registry.counts.evox2_active_count}."
        )

    if registry.counts.production_allowed_by_default:
        raise PortfolioRegistryError("Portfolio cannot allow production by default.")
    if registry.counts.customer_release_allowed_by_default:
        raise PortfolioRegistryError("Portfolio cannot allow customer release by default.")
    if registry.counts.live_allowed_by_default:
        raise PortfolioRegistryError("Portfolio cannot allow live/capital behavior by default.")
    if not registry.counts.requires_human_approval:
        raise PortfolioRegistryError("Portfolio must require human approval.")

    for project in registry.projects.values():
        project.validate_safety()


def validate_exclusions(
    active: ActivePortfolioRegistry,
    merge_sources: ExclusionRegistry,
    archives: ExclusionRegistry,
) -> None:
    """Ensure excluded projects are not present in the active project registry."""
    active_ids = set(active.projects)
    merge_overlap = sorted(active_ids & merge_sources.project_ids)
    archive_overlap = sorted(active_ids & archives.project_ids)

    if merge_overlap:
        raise PortfolioRegistryError(
            "Merge-source projects must not be active: " + ", ".join(merge_overlap)
        )
    if archive_overlap:
        raise PortfolioRegistryError(
            "Archive projects must not be active: " + ", ".join(archive_overlap)
        )

    if merge_sources.count != EXPECTED_MERGE_SOURCE_COUNT:
        raise PortfolioRegistryError(
            f"Expected {EXPECTED_MERGE_SOURCE_COUNT} merge sources, found {merge_sources.count}."
        )
    if archives.count != EXPECTED_ARCHIVE_COUNT:
        raise PortfolioRegistryError(
            f"Expected {EXPECTED_ARCHIVE_COUNT} archives, found {archives.count}."
        )


def load_portfolio_registries(
    active_path: Path = DEFAULT_ACTIVE_REGISTRY,
    merge_path: Path = DEFAULT_MERGE_SOURCES_REGISTRY,
    archive_path: Path = DEFAULT_ARCHIVES_REGISTRY,
) -> tuple[ActivePortfolioRegistry, ExclusionRegistry, ExclusionRegistry]:
    """Load all registries and validate merge/archive exclusions."""
    active = load_active_registry(active_path)
    merge_sources = load_merge_source_registry(merge_path)
    archives = load_archive_registry(archive_path)
    validate_exclusions(active, merge_sources, archives)
    return active, merge_sources, archives


def portfolio_counts_json(active: ActivePortfolioRegistry) -> dict[str, Any]:
    """Return JSON-ready counts for `liaison portfolio counts --json`."""
    return {
        "active_project_count": active.counts.active_project_count,
        "dgx_active_count": active.counts.dgx_active_count,
        "evox2_active_count": active.counts.evox2_active_count,
        "merge_sources_excluded": active.counts.merge_sources_excluded,
        "archive_candidates_excluded": active.counts.archive_candidates_excluded,
        "production_allowed_by_default": active.counts.production_allowed_by_default,
        "customer_release_allowed_by_default": active.counts.customer_release_allowed_by_default,
        "live_allowed_by_default": active.counts.live_allowed_by_default,
        "requires_human_approval": active.counts.requires_human_approval,
    }


def iter_active_projects(
    active: ActivePortfolioRegistry,
    host: str | None = None,
) -> Iterable[ProjectRecord]:
    """Yield active projects, optionally filtered by workstation/host."""
    if host is None:
        yield from (active.projects[project_id] for project_id in sorted(active.projects))
        return

    yield from active.by_host(host)


def _as_str_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PortfolioRegistryError(f"{field_name} must be a list.")
    return [str(item) for item in value]
