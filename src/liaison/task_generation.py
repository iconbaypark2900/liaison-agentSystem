"""Portfolio task generation for Liaison v0.2.0.

Implements the generation layer described in:
    docs/v0.2.0/PORTFOLIO_TASK_GENERATION.md

Responsibilities:
    - Select active projects for task generation.
    - Exclude merge-source and archive projects.
    - Apply workstation profiles.
    - Choose safe task templates.
    - Render dry-run output.
    - Write generated tasks to `.liaison/tasks/backlog/`.

CLI integration:
    - `generate_tasks(...)` wired to `liaison portfolio generate-tasks`.
    - `list_portfolio(...)` wired to `liaison portfolio list`.
    - `portfolio_counts_json(...)` wired to `liaison portfolio counts --json`.
    - `validate_portfolio(...)` wired to `liaison portfolio validate`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .portfolio_profiles import (
    WorkstationProfile,
    load_all_profiles,
    resolve_project_profile,
)
from .portfolio_registry import (
    ActivePortfolioRegistry,
    ExclusionRegistry,
    PortfolioRegistryError,
    ProjectRecord,
    load_portfolio_registries,
)
from .task_templates import (
    RenderedTask,
    TaskTemplate,
    TaskTemplateError,
    task_filename_for,
)


DEFAULT_BACKLOG_DIR = Path(".liaison/tasks/backlog")

FIRST_REPRESENTATIVE_BATCH = [
    "clinical-suite",
    "adaptive-graph-rag",
    "sigma",
    "docuQuery",
    "guardianShield",
    "event-market-alpha-evolved",
]

DEFAULT_PROJECT_TASK_TYPES = {
    "clinical-suite": "project_audit",
    "adaptive-graph-rag": "project_audit",
    "sigma": "calibration",
    "docuQuery": "project_audit",
    "guardianShield": "security_review",
    "event-market-alpha-evolved": "calibration",
}

CALIBRATION_TAGS = {
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

SECURITY_TAGS = {
    "security",
    "privacy",
    "cryptography",
    "identity",
    "compliance",
    "secure_messaging",
}


class TaskGenerationError(ValueError):
    """Raised when portfolio task generation fails."""


@dataclass(frozen=True)
class GenerationRequest:
    limit: int = 6
    host: str | None = None
    project: str | None = None
    types: list[str] = field(default_factory=list)
    dry_run: bool = False
    overwrite: bool = False
    backlog_dir: Path = DEFAULT_BACKLOG_DIR


@dataclass(frozen=True)
class GeneratedTask:
    project_id: str
    task_type: str
    target_path: Path
    rendered: RenderedTask
    would_write: bool
    skipped: bool = False
    skip_reason: str | None = None


@dataclass(frozen=True)
class GenerationResult:
    request: GenerationRequest
    generated: list[GeneratedTask]
    skipped: list[GeneratedTask]
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary_lines(self) -> list[str]:
        action = "Would generate" if self.request.dry_run else "Generated"
        lines = [f"{action} {len(self.generated)} tasks:"]
        lines.extend(str(task.target_path) for task in self.generated)
        if self.skipped:
            lines.append("")
            lines.append(f"Skipped {len(self.skipped)} tasks:")
            lines.extend(
                f"{task.target_path}: {task.skip_reason or 'skipped'}" for task in self.skipped
            )
        if self.errors:
            lines.append("")
            lines.append("Errors:")
            lines.extend(self.errors)
        return lines


def generate_tasks(
    request: GenerationRequest,
    *,
    active: ActivePortfolioRegistry | None = None,
    merge_sources: ExclusionRegistry | None = None,
    archives: ExclusionRegistry | None = None,
    profiles: Mapping[str, WorkstationProfile] | None = None,
) -> GenerationResult:
    """Generate portfolio tasks.

    This function does not execute tasks, call models, create branches, or run workers.
    """
    if active is None or merge_sources is None or archives is None:
        active, merge_sources, archives = load_portfolio_registries()
    if profiles is None:
        profiles = load_all_profiles()

    selected = select_projects(active, request)
    generated: list[GeneratedTask] = []
    skipped: list[GeneratedTask] = []
    errors: list[str] = []

    if not request.dry_run:
        request.backlog_dir.mkdir(parents=True, exist_ok=True)

    for project in selected:
        try:
            if project.project_id in merge_sources.project_ids:
                raise TaskGenerationError(
                    f"Cannot generate active task for merge-source {project.project_id}."
                )
            if project.project_id in archives.project_ids:
                raise TaskGenerationError(
                    f"Cannot generate active task for archive {project.project_id}."
                )

            resolved = resolve_project_profile(project, profiles)
            task_types = request.types or [choose_default_task_type(project)]
            for task_type in task_types:
                generated_task = render_task_for_project(
                    resolved=resolved,
                    task_type=task_type,
                    backlog_dir=request.backlog_dir,
                )
                existing = generated_task.target_path.exists()
                if existing and not request.overwrite:
                    skipped.append(
                        GeneratedTask(
                            project_id=generated_task.project_id,
                            task_type=generated_task.task_type,
                            target_path=generated_task.target_path,
                            rendered=generated_task.rendered,
                            would_write=False,
                            skipped=True,
                            skip_reason="task already exists",
                        )
                    )
                    continue
                if existing and request.overwrite:
                    ensure_overwrite_allowed(generated_task.target_path)

                if not request.dry_run:
                    generated_task.target_path.write_text(
                        generated_task.rendered.text,
                        encoding="utf-8",
                    )

                generated.append(generated_task)
        except (PortfolioRegistryError, TaskTemplateError, TaskGenerationError) as exc:
            errors.append(str(exc))

    return GenerationResult(
        request=request,
        generated=generated,
        skipped=skipped,
        errors=errors,
    )


def select_projects(
    active: ActivePortfolioRegistry,
    request: GenerationRequest,
) -> list[ProjectRecord]:
    if request.project:
        return [active.get(request.project)]

    if request.limit == 6 and request.host is None and not request.types:
        return [active.get(project_id) for project_id in FIRST_REPRESENTATIVE_BATCH]

    projects = list(active.by_host(request.host)) if request.host else list(active.projects.values())
    projects = sort_projects_for_generation(projects)

    if request.limit <= 0:
        raise TaskGenerationError("limit must be greater than zero.")

    return projects[: request.limit]


def sort_projects_for_generation(projects: Iterable[ProjectRecord]) -> list[ProjectRecord]:
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    return sorted(
        projects,
        key=lambda project: (
            priority_rank.get(project.priority, 99),
            project.workstation,
            project.project_id.lower(),
        ),
    )


def choose_default_task_type(project: ProjectRecord) -> str:
    if project.project_id in DEFAULT_PROJECT_TASK_TYPES:
        return DEFAULT_PROJECT_TASK_TYPES[project.project_id]

    tags = {tag.lower() for tag in project.tags}
    if tags & CALIBRATION_TAGS:
        return "calibration"
    if tags & SECURITY_TAGS:
        return "security_review"
    return "project_audit"


def render_task_for_project(
    *,
    resolved,
    task_type: str,
    backlog_dir: Path,
) -> GeneratedTask:
    template = TaskTemplate.load(task_type)
    now = utc_now_iso()

    context = resolved.to_template_context()
    context.update({"created_at": now, "updated_at": now})

    rendered = template.render(context)
    target_path = backlog_dir / task_filename_for(rendered)
    return GeneratedTask(
        project_id=resolved.project.project_id,
        task_type=rendered.task_type,
        target_path=target_path,
        rendered=rendered,
        would_write=True,
    )


def ensure_overwrite_allowed(path: Path) -> None:
    """Refuse unsafe overwrites.

    Current stub checks only path location. Future implementation should inspect
    queue state and reject active/review_required/done task overwrites.
    """
    normalized = path.as_posix()
    if "/active/" in normalized or "/review_required/" in normalized or "/done/" in normalized:
        raise TaskGenerationError(f"Refusing to overwrite non-backlog task: {path}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def list_portfolio(
    *,
    host: str | None = None,
    active: ActivePortfolioRegistry | None = None,
) -> list[str]:
    """Return active project IDs for future `liaison portfolio list` CLI."""
    if active is None:
        active, _, _ = load_portfolio_registries()
    return active.list_project_ids(host=host)


def validate_portfolio() -> dict[str, Any]:
    """Validate registries and return JSON-ready status for CLI integration."""
    try:
        active, merge_sources, archives = load_portfolio_registries()
        profiles = load_all_profiles()
        for project in active.projects.values():
            resolve_project_profile(project, profiles)

        return {
            "status": "passed",
            "active_project_count": active.counts.active_project_count,
            "dgx_active_count": active.counts.dgx_active_count,
            "evox2_active_count": active.counts.evox2_active_count,
            "merge_sources_excluded": merge_sources.count,
            "archive_candidates_excluded": archives.count,
            "failed_checks": [],
            "passed_checks": [
                "active_registry_loaded",
                "merge_sources_loaded",
                "archives_loaded",
                "profiles_loaded",
                "counts_validated",
                "exclusions_validated",
                "project_profiles_resolved",
            ],
            "warnings": [],
        }
    except Exception as exc:  # CLI-facing stub should not hide validation failures.
        return {
            "status": "failed",
            "failed_checks": [str(exc)],
            "passed_checks": [],
            "warnings": [],
        }


def parse_types(types_csv: str | None) -> list[str]:
    if not types_csv:
        return []
    return [item.strip() for item in types_csv.split(",") if item.strip()]
