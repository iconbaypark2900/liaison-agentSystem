"""Tests for Liaison v0.2.0 portfolio task-generation stubs.

These tests cover:
  - active registry loading
  - workstation profile loading
  - merge/archive exclusion
  - first representative batch selection
  - task template validation
  - dry-run behavior
  - generated task safety checks
  - validate_portfolio JSON output

Assumptions:
  - The implementation stubs live under src/liaison/.
  - Tests are run from the repository root with pytest.
  - PyYAML is installed.
"""

from __future__ import annotations

from pathlib import Path
import textwrap

import pytest
import yaml

from liaison.portfolio_registry import (
    ActivePortfolioRegistry,
    PortfolioRegistryError,
    load_active_registry,
    load_archive_registry,
    load_merge_source_registry,
    load_portfolio_registries,
    validate_exclusions,
)
from liaison.portfolio_profiles import (
    PortfolioProfileError,
    load_all_profiles,
    load_workstation_profile,
    resolve_project_profile,
)
from liaison.task_generation import (
    FIRST_REPRESENTATIVE_BATCH,
    GenerationRequest,
    choose_default_task_type,
    generate_tasks,
    select_projects,
    validate_portfolio,
)
from liaison.task_templates import (
    REQUIRED_ARTIFACTS,
    REQUIRED_FORBIDDEN_ACTIONS,
    REQUIRED_FORBIDDEN_FILES,
    TaskTemplate,
    TaskTemplateError,
)


DGX_PROJECTS = [
    "clinical-suite",
    "adaptive-graph-rag",
    "quantumRX",
    "sigma",
    "materialScience",
    "hybrid-qml-kg-poc",
    "qgg_quantum_dispatch",
    "qcrypt-rng",
    "qgq-platform",
    "biomedical",
    "quantum-practitioner-lab",
    "quantum-hybrid-portfolio",
    "qgg_research",
    "financial_alpha_risk_research_lab",
    "medical_evidence_graph_outcomes_lab",
    "quantum_hybrid_research_optimization_lab",
    "secure_ai_data_governance_control_plane",
    "tokenized_infra_rwa_intel_platform",
]

EVO_PROJECTS = [
    "docuQuery",
    "parkSafe",
    "predictEdgeapi",
    "rewardSync",
    "brightCommons",
    "printCost",
    "nautiWatch",
    "orbTrack",
    "event-market-alpha-evolved",
    "setup",
    "ag_news_nlp_project",
    "co2_predictions",
    "b2b_revenue_procurement_network",
    "cipherChat",
    "fractalVoyager",
    "bioLock",
    "docuchainVerify",
    "chainStoreipfs",
    "synthoCast",
    "privanon",
    "skySightanalyzer",
    "guardianShield",
    "qids",
]

MERGE_SOURCES = [
    "lexFind",
    "qRandomizer",
    "chainCheck",
    "cyberSentinel",
    "mediScope",
    "finGuard",
    "qOptiSolve",
]

ARCHIVES = [
    "Grain",
    "razorBill",
    "tradeFluxsimulator",
    "trendy",
    "brsuite",
    "crm",
    "questionnaire",
]


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def project_record(
    project_id: str,
    *,
    workstation: str,
    priority: str = "medium",
    tags: list[str] | None = None,
    category: str = "Test Project",
) -> dict:
    tags = list(tags or ["docs"])
    safety_gates = ["agent_safety", "production_readiness"]

    calibration_tags = {"trading", "event_market", "prediction", "calibration", "finance", "confidence", "financial_portfolio", "portfolio_optimization", "scoring", "ranking"}
    if any(tag in tags for tag in calibration_tags):
        safety_gates.append("confidence_calibration")

    if any(tag in tags for tag in ["medical", "clinical", "healthcare", "customer_facing", "ecommerce"]):
        safety_gates.append("customer_release")

    return {
        "enabled": True,
        "active": True,
        "workstation": workstation,
        "path": f"/tmp/{project_id}",
        "category": category,
        "priority": priority,
        "tags": tags,
        "default_host": workstation,
        "preferred_executor": "opencode" if workstation == "dgx_spark" else "codex",
        "fallback_executor": "shell",
        "default_model_route": "dgx_heavy_coder" if workstation == "dgx_spark" else "local_coder",
        "validation_profiles": ["docs", "security"],
        "safety_gates": safety_gates,
        "status": "active",
        "production_allowed": False,
        "customer_release_allowed": False,
        "live_allowed": False,
        "requires_human_approval": True,
    }


def active_registry_payload() -> dict:
    projects: dict[str, dict] = {}

    for project_id in DGX_PROJECTS:
        tags = ["docs", "research"]
        category = "DGX Test Project"
        priority = "high"

        if project_id == "clinical-suite":
            tags = ["clinical", "medical", "customer_facing", "privacy"]
            category = "Clinical / medical document processing"
        elif project_id == "adaptive-graph-rag":
            tags = ["rag", "graph", "retrieval"]
            category = "Graph RAG"
        elif project_id == "sigma":
            tags = ["trading", "event_market", "prediction", "calibration", "finance"]
            category = "Trading intelligence"
            priority = "critical"
        elif project_id in {"quantum-hybrid-portfolio", "financial_alpha_risk_research_lab", "tokenized_infra_rwa_intel_platform"}:
            tags = ["finance", "portfolio", "calibration"]
            priority = "critical" if project_id == "financial_alpha_risk_research_lab" else "high"

        projects[project_id] = project_record(
            project_id,
            workstation="dgx_spark",
            priority=priority,
            tags=tags,
            category=category,
        )

    for project_id in EVO_PROJECTS:
        tags = ["docs", "app"]
        category = "EVO Test Project"
        priority = "medium"

        if project_id == "docuQuery":
            tags = ["rag", "document", "customer_facing"]
            category = "Document/RAG app"
            priority = "high"
        elif project_id == "guardianShield":
            tags = ["security", "privacy", "compliance"]
            category = "Security platform"
            priority = "high"
        elif project_id == "event-market-alpha-evolved":
            tags = ["event_market", "trading", "prediction", "calibration", "finance"]
            category = "Event-market app"
            priority = "critical"
        elif project_id == "qids":
            tags = ["security", "privacy", "cryptography"]
            priority = "critical"
        elif project_id in {"predictEdgeapi", "co2_predictions"}:
            tags = ["prediction", "calibration"]
            priority = "high" if project_id == "predictEdgeapi" else "low"
        elif project_id in {"brightCommons", "b2b_revenue_procurement_network"}:
            tags = ["customer_facing", "ecommerce", "business"]
            priority = "high" if project_id == "b2b_revenue_procurement_network" else "medium"

        projects[project_id] = project_record(
            project_id,
            workstation="evox2_windows",
            priority=priority,
            tags=tags,
            category=category,
        )

    return {
        "version": "0.2.0",
        "portfolio": {
            "active_project_count": 41,
            "dgx_active_count": 18,
            "evox2_active_count": 23,
            "merge_sources_excluded": 7,
            "archive_candidates_excluded": 7,
            "production_allowed_by_default": False,
            "customer_release_allowed_by_default": False,
            "live_allowed_by_default": False,
            "requires_human_approval": True,
        },
        "projects": projects,
    }


def merge_sources_payload() -> dict:
    return {
        "version": "0.2.0",
        "registry_type": "merge_sources",
        "merge_sources": {
            project_id: {
                "enabled": True,
                "active": False,
                "source": project_id,
                "target": "target-project",
                "count_as_active_project": False,
                "worker_allowed": False,
                "requires_human_approval": True,
            }
            for project_id in MERGE_SOURCES
        },
    }


def archives_payload() -> dict:
    return {
        "version": "0.2.0",
        "registry_type": "archives",
        "archives": {
            project_id: {
                "enabled": True,
                "active": False,
                "archived": True,
                "project": project_id,
                "count_as_active_project": False,
                "worker_allowed": False,
                "requires_human_approval": True,
            }
            for project_id in ARCHIVES
        },
    }


def profile_payload(*, workstation: str, projects: list[str]) -> dict:
    if workstation == "dgx_spark":
        profile_id = "dgx_compute_projects"
        display_name = "DGX Spark Compute Projects"
        preferred_executor = "opencode"
        default_model_route = "dgx_heavy_coder"
    else:
        profile_id = "evox2_lightweight_projects"
        display_name = "EVO-X2 Windows Lightweight Projects"
        preferred_executor = "codex"
        default_model_route = "local_coder"

    return {
        "version": "0.2.0",
        "profile_id": profile_id,
        "workstation": workstation,
        "display_name": display_name,
        "projects": projects,
        "workstation_defaults": {
            "default_host": workstation,
            "preferred_executor": preferred_executor,
            "fallback_executor": "shell",
            "default_model_route": default_model_route,
            "fallback_model_route": "local_critic" if workstation == "dgx_spark" else "local_planner",
        },
        "routing_rules": {
            "default": {
                "preferred_host": workstation,
                "fallback_host": "evox2_windows" if workstation == "dgx_spark" else "dgx_spark",
                "allow_hosted_fallback": False,
                "requires_human_approval": True,
            }
        },
        "validation_defaults": {
            "required_profiles": ["security", "docs"],
            "recommended_profiles": ["python" if workstation == "dgx_spark" else "node"],
            "optional_profiles": ["data_quality", "calibration", "customer_release"],
        },
        "project_class_validation": {},
        "safety_gates": {
            "default": ["agent_safety", "production_readiness"],
            "trading_or_prediction": ["agent_safety", "confidence_calibration", "production_readiness"],
            "customer_facing": ["agent_safety", "customer_release", "production_readiness"],
        },
        "task_generation_priorities": {
            "first_batch": ["clinical-suite", "adaptive-graph-rag", "sigma"]
            if workstation == "dgx_spark"
            else ["docuQuery", "guardianShield", "event-market-alpha-evolved"],
            "priority_order": {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            },
            "default_task_sequence": ["project_audit"],
        },
        "exclusions": {
            "merge_sources_excluded": MERGE_SOURCES,
            "archives_excluded": ARCHIVES,
            "forbidden_default_actions": [
                "production_deploy",
                "customer_release",
                "live_trade",
                "capital_allocation",
                "push_main",
                "force_push",
                "read_secrets",
                "disable_gates",
                "approve_own_work",
            ],
            "forbidden_default_paths": [
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
            ],
        },
        "promotion_policy": {
            "production_allowed": False,
            "customer_release_allowed": False,
            "live_allowed": False,
            "requires_human_approval": True,
            "default_gate_status": "review_required",
            "missing_evidence_status": "blocked",
        },
    }


def template_text(task_type: str) -> str:
    """Return a valid template matching the implementation's simple renderer.

    Keep list placeholders as quoted scalar values because the stub renderer is intentionally
    minimal and does not expand YAML sequences.
    """
    return textwrap.dedent(
        f"""
        id: "{{{{project_id}}}}-{task_type}-001"
        project: "{{{{project_id}}}}"
        title: "Generated {task_type} task for {{{{project_id}}}}"
        type: "{task_type}"
        priority: "{{{{priority | default('medium')}}}}"
        status: backlog
        created_at: "{{{{created_at}}}}"
        updated_at: "{{{{updated_at}}}}"

        repo:
          path: "{{{{project_path}}}}"
          branch:
            create: false
            name: null

        routing:
          preferred_host: "{{{{default_host}}}}"
          model_route: "{{{{default_model_route}}}}"
          executor: "{{{{preferred_executor}}}}"
          fallback_executor: "{{{{fallback_executor}}}}"

        allowed_executors:
          - shell
          - opencode
          - codex
          - claude_code

        allowed_actions:
          - read_docs
          - inspect_repo
          - run_validation
          - write_artifacts
          - write_debrief

        forbidden_actions:
          - push_main
          - force_push
          - deploy_production
          - customer_release
          - live_trade
          - allocate_capital
          - read_secrets
          - modify_credentials
          - approve_own_work
          - disable_gates

        allowed_files:
          - README.md
          - docs/**
          - src/**
          - tests/**

        forbidden_files:
          - ".env"
          - ".env.*"
          - "secrets/**"
          - "credentials/**"
          - "customer_data/**"
          - "prod_dumps/**"
          - "*.pem"
          - "*.key"
          - "id_rsa"
          - "id_ed25519"
          - ".cursor/**"

        validation:
          - name: git_status
            command: "git status --short"
            required: true

        required_artifacts:
          - task.yaml
          - context.md
          - command.txt
          - stdout.log
          - stderr.log
          - patch.diff
          - validation.log
          - security.log
          - data_quality.log
          - compliance.md
          - debrief.md
          - promotion_gate.json
          - run_metadata.json

        debrief_required_sections:
          - Summary
          - Promotion recommendation

        done_when:
          - "Evidence artifacts are written."
          - "promotion_gate.json is written."

        safety:
          production_allowed: false
          customer_release_allowed: false
          live_allowed: false
          capital_allocation_allowed: false
          requires_human_approval: true
          default_gate_status: review_required
        """
    ).strip() + "\n"


def write_task_templates(root: Path) -> None:
    template_dir = root / "templates" / "tasks"
    template_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "project_audit_task.yaml": "project_audit",
        "project_validation_task.yaml": "project_validation",
        "project_security_scan_task.yaml": "security_review",
        "project_release_gap_task.yaml": "release_review",
        "project_calibration_gate_task.yaml": "calibration",
    }
    for filename, task_type in mapping.items():
        (template_dir / filename).write_text(template_text(task_type), encoding="utf-8")


@pytest.fixture()
def portfolio_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary mini-repo with all registry/profile/template files."""
    write_yaml(tmp_path / "config" / "project_registry.active.yaml", active_registry_payload())
    write_yaml(tmp_path / "config" / "project_registry.merge_sources.yaml", merge_sources_payload())
    write_yaml(tmp_path / "config" / "project_registry.archives.yaml", archives_payload())
    write_yaml(
        tmp_path / "config" / "project_profiles" / "dgx_compute_projects.yaml",
        profile_payload(workstation="dgx_spark", projects=DGX_PROJECTS),
    )
    write_yaml(
        tmp_path / "config" / "project_profiles" / "evox2_lightweight_projects.yaml",
        profile_payload(workstation="evox2_windows", projects=EVO_PROJECTS),
    )
    write_task_templates(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_active_registry_loading_counts_and_safety(portfolio_repo: Path) -> None:
    registry = load_active_registry(Path("config/project_registry.active.yaml"))

    assert isinstance(registry, ActivePortfolioRegistry)
    assert registry.counts.active_project_count == 41
    assert registry.counts.dgx_active_count == 18
    assert registry.counts.evox2_active_count == 23
    assert len(registry.projects) == 41
    assert registry.get("sigma").workstation == "dgx_spark"
    assert registry.get("event-market-alpha-evolved").workstation == "evox2_windows"
    assert not registry.get("sigma").live_allowed
    assert registry.get("sigma").requires_human_approval is True


def test_profile_loading_and_project_resolution(portfolio_repo: Path) -> None:
    active, _, _ = load_portfolio_registries()
    profiles = load_all_profiles()

    assert set(profiles) == {"dgx_spark", "evox2_windows"}

    sigma = resolve_project_profile(active.get("sigma"), profiles)
    assert sigma.preferred_host == "dgx_spark"
    assert sigma.preferred_executor == "opencode"
    assert "confidence_calibration" in sigma.safety_gates
    assert sigma.production_allowed is False
    assert sigma.customer_release_allowed is False
    assert sigma.live_allowed is False
    assert sigma.requires_human_approval is True

    docuquery = resolve_project_profile(active.get("docuQuery"), profiles)
    assert docuquery.preferred_host == "evox2_windows"
    assert docuquery.preferred_executor == "codex"
    assert "customer_release" in docuquery.safety_gates


def test_merge_and_archive_exclusion_validation(portfolio_repo: Path) -> None:
    active = load_active_registry(Path("config/project_registry.active.yaml"))
    merge_sources = load_merge_source_registry(Path("config/project_registry.merge_sources.yaml"))
    archives = load_archive_registry(Path("config/project_registry.archives.yaml"))

    validate_exclusions(active, merge_sources, archives)

    assert merge_sources.count == 7
    assert archives.count == 7
    assert "lexFind" not in active.projects
    assert "tradeFluxsimulator" not in active.projects


def test_merge_source_in_active_registry_fails(portfolio_repo: Path) -> None:
    payload = active_registry_payload()
    payload["projects"]["lexFind"] = project_record(
        "lexFind",
        workstation="evox2_windows",
        tags=["document_search"],
    )
    del payload["projects"]["setup"]

    write_yaml(Path("config/project_registry.active.yaml"), payload)

    active = load_active_registry(Path("config/project_registry.active.yaml"))
    merge_sources = load_merge_source_registry(Path("config/project_registry.merge_sources.yaml"))
    archives = load_archive_registry(Path("config/project_registry.archives.yaml"))

    with pytest.raises(PortfolioRegistryError, match="Merge-source projects must not be active"):
        validate_exclusions(active, merge_sources, archives)


def test_archive_in_active_registry_fails(portfolio_repo: Path) -> None:
    payload = active_registry_payload()
    payload["projects"]["Grain"] = project_record(
        "Grain",
        workstation="evox2_windows",
        tags=["archive"],
    )
    del payload["projects"]["setup"]

    write_yaml(Path("config/project_registry.active.yaml"), payload)

    active = load_active_registry(Path("config/project_registry.active.yaml"))
    merge_sources = load_merge_source_registry(Path("config/project_registry.merge_sources.yaml"))
    archives = load_archive_registry(Path("config/project_registry.archives.yaml"))

    with pytest.raises(PortfolioRegistryError, match="Archive projects must not be active"):
        validate_exclusions(active, merge_sources, archives)


def test_first_representative_batch_selection(portfolio_repo: Path) -> None:
    active, _, _ = load_portfolio_registries()
    request = GenerationRequest(limit=6)

    selected = select_projects(active, request)

    assert [project.project_id for project in selected] == FIRST_REPRESENTATIVE_BATCH


def test_default_task_type_selection(portfolio_repo: Path) -> None:
    active, _, _ = load_portfolio_registries()

    assert choose_default_task_type(active.get("sigma")) == "calibration"
    assert choose_default_task_type(active.get("event-market-alpha-evolved")) == "calibration"
    assert choose_default_task_type(active.get("guardianShield")) == "security_review"
    assert choose_default_task_type(active.get("docuQuery")) == "project_audit"


def test_task_template_validation_passes(portfolio_repo: Path) -> None:
    template = TaskTemplate.load("project_audit")

    assert template.path.name == "project_audit_task.yaml"
    assert set(template.parsed["required_artifacts"]) >= REQUIRED_ARTIFACTS
    assert set(template.parsed["forbidden_actions"]) >= REQUIRED_FORBIDDEN_ACTIONS
    assert set(template.parsed["forbidden_files"]) >= REQUIRED_FORBIDDEN_FILES
    assert template.parsed["safety"]["production_allowed"] is False
    assert template.parsed["safety"]["customer_release_allowed"] is False
    assert template.parsed["safety"]["live_allowed"] is False
    assert template.parsed["safety"]["requires_human_approval"] is True


def test_task_template_validation_rejects_missing_safety(portfolio_repo: Path) -> None:
    broken_template = Path("templates/tasks/project_audit_task.yaml")
    text = broken_template.read_text(encoding="utf-8")
    text = text.replace("  - push_main\n", "")
    broken_template.write_text(text, encoding="utf-8")

    with pytest.raises(TaskTemplateError, match="missing forbidden actions"):
        TaskTemplate.load("project_audit")


def test_dry_run_generation_writes_no_files(portfolio_repo: Path) -> None:
    result = generate_tasks(GenerationRequest(limit=6, dry_run=True))

    assert result.ok
    assert len(result.generated) == 6
    assert not Path(".liaison/tasks/backlog").exists()
    assert [task.project_id for task in result.generated] == FIRST_REPRESENTATIVE_BATCH
    assert [task.task_type for task in result.generated] == [
        "project_audit",
        "project_audit",
        "calibration",
        "project_audit",
        "security_review",
        "calibration",
    ]


def test_actual_generation_writes_backlog_files(portfolio_repo: Path) -> None:
    result = generate_tasks(GenerationRequest(limit=6, dry_run=False))

    assert result.ok
    assert len(result.generated) == 6

    for generated in result.generated:
        assert generated.target_path.exists()
        parsed = yaml.safe_load(generated.target_path.read_text(encoding="utf-8"))
        assert parsed["project"] == generated.project_id
        assert parsed["safety"]["production_allowed"] is False
        assert parsed["safety"]["customer_release_allowed"] is False
        assert parsed["safety"]["live_allowed"] is False
        assert parsed["safety"]["requires_human_approval"] is True
        assert "promotion_gate.json" in parsed["required_artifacts"]
        assert "validation.log" in parsed["required_artifacts"]
        assert "debrief.md" in parsed["required_artifacts"]
        assert "push_main" in parsed["forbidden_actions"]
        assert "live_trade" in parsed["forbidden_actions"]
        assert "read_secrets" in parsed["forbidden_actions"]


def test_duplicate_generation_is_skipped_by_default(portfolio_repo: Path) -> None:
    first = generate_tasks(GenerationRequest(limit=6, dry_run=False))
    second = generate_tasks(GenerationRequest(limit=6, dry_run=False))

    assert first.ok
    assert second.ok
    assert len(second.generated) == 0
    assert len(second.skipped) == 6
    assert all(task.skip_reason == "task already exists" for task in second.skipped)


def test_host_filtered_generation_dgx_only(portfolio_repo: Path) -> None:
    result = generate_tasks(GenerationRequest(limit=3, host="dgx_spark", dry_run=True))

    assert result.ok
    assert len(result.generated) == 3
    assert all(task.project_id in DGX_PROJECTS for task in result.generated)


def test_host_filtered_generation_evox2_only(portfolio_repo: Path) -> None:
    result = generate_tasks(GenerationRequest(limit=3, host="evox2_windows", dry_run=True))

    assert result.ok
    assert len(result.generated) == 3
    assert all(task.project_id in EVO_PROJECTS for task in result.generated)


def test_project_specific_generation_sigma_calibration(portfolio_repo: Path) -> None:
    result = generate_tasks(GenerationRequest(project="sigma", dry_run=True))

    assert result.ok
    assert len(result.generated) == 1
    generated = result.generated[0]
    assert generated.project_id == "sigma"
    assert generated.task_type == "calibration"
    assert "critical-sigma-calibration-gate-001.yaml" in str(generated.target_path)

    parsed = generated.rendered.parsed
    assert parsed["safety"]["production_allowed"] is False
    assert parsed["safety"]["customer_release_allowed"] is False
    assert parsed["safety"]["live_allowed"] is False


def test_project_specific_multiple_types(portfolio_repo: Path) -> None:
    result = generate_tasks(
        GenerationRequest(
            project="docuQuery",
            types=["project_audit", "security_review", "release_review"],
            dry_run=True,
        )
    )

    assert result.ok
    assert [task.task_type for task in result.generated] == [
        "project_audit",
        "security_review",
        "release_review",
    ]


def test_validate_portfolio_json_output_passes(portfolio_repo: Path) -> None:
    result = validate_portfolio()

    assert result["status"] == "passed"
    assert result["active_project_count"] == 41
    assert result["dgx_active_count"] == 18
    assert result["evox2_active_count"] == 23
    assert result["merge_sources_excluded"] == 7
    assert result["archive_candidates_excluded"] == 7
    assert result["failed_checks"] == []
    assert "active_registry_loaded" in result["passed_checks"]
    assert "project_profiles_resolved" in result["passed_checks"]


def test_validate_portfolio_json_output_fails_for_unsafe_registry(portfolio_repo: Path) -> None:
    payload = active_registry_payload()
    payload["projects"]["sigma"]["live_allowed"] = True
    write_yaml(Path("config/project_registry.active.yaml"), payload)

    result = validate_portfolio()

    assert result["status"] == "failed"
    assert result["failed_checks"]
    assert "live" in result["failed_checks"][0].lower()
