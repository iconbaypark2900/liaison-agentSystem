"""Task template loading, validation, and rendering for Liaison v0.2.0.

Implements the template layer described in:
    docs/v0.2.0/PORTFOLIO_TASK_GENERATION.md

Responsibilities:
    - Safely load YAML task templates as text and parsed YAML.
    - Validate required safety sections are present in templates.
    - Render Jinja-like placeholders without introducing a Jinja dependency.
    - Validate generated task packets before writing them.

The placeholder renderer intentionally supports a small safe subset
({{ variable }} substitution only). This is a deliberate security boundary:
templates cannot inject logic, conditionals, or loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Mapping

import yaml


DEFAULT_TEMPLATE_DIR = Path("templates/tasks")

TEMPLATE_BY_TYPE = {
    "audit": "project_audit_task.yaml",
    "project_audit": "project_audit_task.yaml",
    "validation": "project_validation_task.yaml",
    "project_validation": "project_validation_task.yaml",
    "security": "project_security_scan_task.yaml",
    "security_review": "project_security_scan_task.yaml",
    "security-scan": "project_security_scan_task.yaml",
    "release-gap": "project_release_gap_task.yaml",
    "release_review": "project_release_gap_task.yaml",
    "calibration": "project_calibration_gate_task.yaml",
    "calibration-gate": "project_calibration_gate_task.yaml",
}

REQUIRED_TEMPLATE_KEYS = {
    "id",
    "project",
    "title",
    "type",
    "priority",
    "status",
    "repo",
    "routing",
    "allowed_executors",
    "allowed_actions",
    "forbidden_actions",
    "forbidden_files",
    "validation",
    "required_artifacts",
    "done_when",
    "safety",
}

REQUIRED_FORBIDDEN_ACTIONS = {
    "push_main",
    "force_push",
    "deploy_production",
    "live_trade",
    "allocate_capital",
    "read_secrets",
    "approve_own_work",
}

REQUIRED_FORBIDDEN_FILES = {
    ".env",
    ".env.*",
    "secrets/**",
    "credentials/**",
    "customer_data/**",
    "prod_dumps/**",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    ".cursor/**",
}

REQUIRED_ARTIFACTS = {
    "task.yaml",
    "context.md",
    "command.txt",
    "stdout.log",
    "stderr.log",
    "patch.diff",
    "validation.log",
    "security.log",
    "data_quality.log",
    "compliance.md",
    "debrief.md",
    "promotion_gate.json",
    "run_metadata.json",
}


class TaskTemplateError(ValueError):
    """Raised when task template loading, rendering, or validation fails."""


@dataclass(frozen=True)
class TaskTemplate:
    template_type: str
    path: Path
    text: str
    parsed: dict[str, Any] = field(repr=False)

    @classmethod
    def load(cls, template_type: str, template_dir: Path = DEFAULT_TEMPLATE_DIR) -> "TaskTemplate":
        filename = TEMPLATE_BY_TYPE.get(template_type)
        if not filename:
            raise TaskTemplateError(f"Unknown task template type: {template_type!r}")

        path = template_dir / filename
        if not path.exists():
            raise TaskTemplateError(f"Missing task template: {path}")

        text = path.read_text(encoding="utf-8")
        parsed = safe_parse_yaml_text(text, path=path)
        template = cls(template_type=template_type, path=path, text=text, parsed=parsed)
        validate_template(template)
        return template

    def render(self, context: Mapping[str, Any]) -> "RenderedTask":
        text = render_template_text(self.text, context)
        parsed = safe_parse_yaml_text(text, path=self.path)
        validate_generated_task(parsed)
        return RenderedTask(template=self, text=text, parsed=parsed)


@dataclass(frozen=True)
class RenderedTask:
    template: TaskTemplate
    text: str
    parsed: dict[str, Any]

    @property
    def task_id(self) -> str:
        return str(self.parsed["id"])

    @property
    def project(self) -> str:
        return str(self.parsed["project"])

    @property
    def priority(self) -> str:
        return str(self.parsed["priority"])

    @property
    def task_type(self) -> str:
        return str(self.parsed["type"])


def safe_parse_yaml_text(text: str, *, path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TaskTemplateError(f"Invalid YAML in task template {path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise TaskTemplateError(f"Task template root must be a mapping: {path}")
    return loaded


def validate_template(template: TaskTemplate) -> None:
    missing = sorted(REQUIRED_TEMPLATE_KEYS - set(template.parsed))
    if missing:
        raise TaskTemplateError(
            f"Template {template.path} missing required keys: {', '.join(missing)}"
        )

    validate_safety_block(template.parsed, label=f"template {template.path}")
    validate_required_artifacts(template.parsed, label=f"template {template.path}")


def validate_generated_task(task: Mapping[str, Any]) -> None:
    missing = sorted(REQUIRED_TEMPLATE_KEYS - set(task))
    if missing:
        raise TaskTemplateError(f"Generated task missing required keys: {', '.join(missing)}")

    if str(task.get("status")) != "backlog":
        raise TaskTemplateError("Generated task must have status=backlog.")
    if not task.get("project"):
        raise TaskTemplateError("Generated task missing project.")
    if not task.get("id"):
        raise TaskTemplateError("Generated task missing id.")

    repo = task.get("repo")
    if not isinstance(repo, dict) or not repo.get("path"):
        raise TaskTemplateError("Generated task must include repo.path.")

    routing = task.get("routing")
    if not isinstance(routing, dict):
        raise TaskTemplateError("Generated task must include routing mapping.")
    for key in ["preferred_host", "model_route", "executor"]:
        if not routing.get(key):
            raise TaskTemplateError(f"Generated task must include routing.{key}.")

    validate_safety_block(task, label=f"generated task {task.get('id')}")
    validate_required_artifacts(task, label=f"generated task {task.get('id')}")


def validate_safety_block(task: Mapping[str, Any], *, label: str) -> None:
    safety = task.get("safety")
    if not isinstance(safety, dict):
        raise TaskTemplateError(f"{label} missing safety mapping.")

    unsafe_truthy_fields = [
        "production_allowed",
        "customer_release_allowed",
        "live_allowed",
        "capital_allocation_allowed",
    ]
    for field_name in unsafe_truthy_fields:
        if bool(safety.get(field_name, False)):
            raise TaskTemplateError(f"{label} has unsafe safety.{field_name}=true.")

    if not bool(safety.get("requires_human_approval", True)):
        raise TaskTemplateError(f"{label} must require human approval.")

    forbidden_actions = set(map(str, task.get("forbidden_actions", [])))
    missing_actions = sorted(REQUIRED_FORBIDDEN_ACTIONS - forbidden_actions)
    if missing_actions:
        raise TaskTemplateError(f"{label} missing forbidden actions: {', '.join(missing_actions)}")

    forbidden_files = set(map(str, task.get("forbidden_files", [])))
    missing_files = sorted(REQUIRED_FORBIDDEN_FILES - forbidden_files)
    if missing_files:
        raise TaskTemplateError(f"{label} missing forbidden files: {', '.join(missing_files)}")


def validate_required_artifacts(task: Mapping[str, Any], *, label: str) -> None:
    artifacts = set(map(str, task.get("required_artifacts", [])))
    missing = sorted(REQUIRED_ARTIFACTS - artifacts)
    if missing:
        raise TaskTemplateError(f"{label} missing required artifacts: {', '.join(missing)}")


def render_template_text(text: str, context: Mapping[str, Any]) -> str:
    """Render a deliberately small subset of {{ placeholders }}."""
    normalized = normalize_template_context(context)

    def replace(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        if "| default(" in expr:
            field_name = expr.split("|", 1)[0].strip()
            fallback = _extract_default(expr)
            value = normalized.get(field_name, fallback)
            return stringify_template_value(value)
        if expr not in normalized:
            raise TaskTemplateError(f"Missing template context value: {expr}")
        return stringify_template_value(normalized[expr])

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, text)


def normalize_template_context(context: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(context)
    if "project_path" not in normalized and "path" in normalized:
        normalized["project_path"] = normalized["path"]
    normalized.setdefault("priority", "medium")
    normalized.setdefault("default_host", normalized.get("workstation", "evox2_windows"))
    normalized.setdefault("preferred_executor", "shell")
    normalized.setdefault("fallback_executor", "shell")
    normalized.setdefault("default_model_route", "local_planner")
    normalized.setdefault("validation_profiles", [])
    normalized.setdefault("safety_gates", [])
    return normalized


def stringify_template_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _extract_default(expr: str) -> str:
    match = re.search(r"default\((['\"])(.*?)\1\)", expr)
    if not match:
        return ""
    return match.group(2)


def task_filename_for(rendered: RenderedTask) -> str:
    slug = _slug_from_task_type(rendered.task_type)
    project = sanitize_path_token(rendered.project)
    priority = sanitize_path_token(rendered.priority.lower())
    return f"{priority}-{project}-{slug}-001.yaml"


def sanitize_path_token(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    sanitized = sanitized.strip("-")
    if not sanitized:
        raise TaskTemplateError("Cannot create path token from empty value.")
    return sanitized


def _slug_from_task_type(task_type: str) -> str:
    mapping = {
        "project_audit": "audit",
        "project_validation": "validation",
        "security_review": "security-scan",
        "release_review": "release-gap",
        "calibration": "calibration-gate",
    }
    return mapping.get(task_type, sanitize_path_token(task_type))
