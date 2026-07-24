"""
SkillRouter — matches a task to the right SKILL.md guidance and hub agents.

Reads:
  registry/skills.yaml   — skill name → owner / use_for
  skills/*/SKILL.md      — full skill guidance text
  registry/hub_skills.yaml — per-agent capabilities and project patterns
  registry/agents.yaml   — agent roles

Returns structured context to inject into ReflexionAgent / CodingAgent prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ── constants ─────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent  # liaison-agentSystem/

_SKILLS_REGISTRY = _REPO_ROOT / "registry" / "skills.yaml"
_HUB_SKILLS = _REPO_ROOT / "registry" / "hub_skills.yaml"
_AGENTS_REGISTRY = _REPO_ROOT / "registry" / "agents.yaml"
_SKILLS_DIR = _REPO_ROOT / "skills"

# keyword → skill names (order matters: first hit wins for top-1)
_SKILL_KEYWORDS: dict[str, list[str]] = {
    # testing-hardening
    "test": ["testing-hardening"],
    "pytest": ["testing-hardening"],
    "coverage": ["testing-hardening"],
    "assertion": ["testing-hardening"],
    "unit test": ["testing-hardening"],
    "spec": ["testing-hardening"],
    "validate": ["testing-hardening"],
    "regression": ["testing-hardening"],
    # systematic-debugging
    "debug": ["systematic-debugging"],
    " bug ": ["systematic-debugging"],
    "error": ["systematic-debugging"],
    "traceback": ["systematic-debugging"],
    "exception": ["systematic-debugging"],
    "failure": ["systematic-debugging"],
    "investigate": ["systematic-debugging"],
    "root cause": ["systematic-debugging"],
    # github-pr-workflow
    "pull request": ["github-pr-workflow"],
    " pr ": ["github-pr-workflow"],
    "ci/cd": ["github-pr-workflow"],
    "merge": ["github-pr-workflow"],
    "branch": ["github-pr-workflow"],
    "pipeline check": ["github-pr-workflow"],
    "ci check": ["github-pr-workflow"],
    # kanban-orchestrator
    "kanban": ["kanban-orchestrator"],
    "card lifecycle": ["kanban-orchestrator"],
    "sprint": ["kanban-orchestrator"],
    "backlog": ["kanban-orchestrator"],
    "multi-agent board": ["kanban-orchestrator"],
    # nvidia-ising-review
    "ising": ["nvidia-ising-review"],
    "calibration": ["nvidia-ising-review"],
    "qpu": ["nvidia-ising-review"],
    "cuda-q": ["nvidia-ising-review"],
    "qec": ["nvidia-ising-review"],
    "quantum error correction": ["nvidia-ising-review"],
    "decoding": ["nvidia-ising-review"],
    "benchmark_plan": ["nvidia-ising-review"],
    "experiment_log": ["nvidia-ising-review"],
    # synthetic-data-designer
    "synthetic data": ["synthetic-data-designer"],
    "dataset": ["synthetic-data-designer"],
    "fine-tune": ["synthetic-data-designer"],
    "fine tune": ["synthetic-data-designer"],
    "jsonl": ["synthetic-data-designer"],
    "data-flywheel": ["synthetic-data-designer"],
    "data flywheel": ["synthetic-data-designer"],
    "schema-first": ["synthetic-data-designer"],
    "lora": ["synthetic-data-designer"],
    "evaluation set": ["synthetic-data-designer"],
    # spark-flow-review
    "spark-flow": ["spark-flow-review"],
    "spark flow": ["spark-flow-review"],
    "artifact review": ["spark-flow-review"],
    "closeout": ["spark-flow-review"],
    "phase review": ["spark-flow-review"],
}

# keyword → agent names
_AGENT_KEYWORDS: dict[str, list[str]] = {
    # hermes (default engineer)
    "implement": ["hermes"],
    "integration": ["hermes"],
    "git commit": ["hermes"],
    "deploy": ["hermes"],
    "pull request": ["hermes"],
    "kanban": ["hermes"],
    "product feature": ["hermes"],
    "vllm": ["hermes"],
    # qca
    "ising": ["qca"],
    "calibration": ["qca"],
    "qpu": ["qca"],
    "cuda-q": ["qca"],
    "qec": ["qca"],
    "quantum": ["qca"],
    "vlm plot": ["qca"],
    "qcaleval": ["qca"],
    "nvidia ising": ["qca"],
    # ml_intern
    "research paper": ["ml_intern"],
    "arxiv": ["ml_intern"],
    "hugging face": ["ml_intern"],
    "hf dataset": ["ml_intern"],
    "model card": ["ml_intern"],
    "benchmark": ["ml_intern"],
    "literature": ["ml_intern"],
    "paper review": ["ml_intern"],
    "hf hub": ["ml_intern"],
    # unsloth_studio
    "fine-tune": ["unsloth_studio"],
    "qlora": ["unsloth_studio"],
    "gguf": ["unsloth_studio"],
    "training run": ["unsloth_studio"],
    "data designer": ["unsloth_studio"],
    "synthetic dataset": ["unsloth_studio"],
    "export model": ["unsloth_studio"],
    # reflexion_dspy (self)
    "autonomous": ["reflexion_dspy"],
    "self-improving": ["reflexion_dspy"],
    "mcp tool": ["reflexion_dspy"],
    "trading": ["reflexion_dspy"],
    "web search": ["reflexion_dspy"],
    # data_flywheel
    "flywheel": ["data_flywheel"],
    "trace curation": ["data_flywheel"],
    "scorecard": ["data_flywheel"],
    "production feedback": ["data_flywheel"],
}

# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class SkillMatch:
    name: str
    owner: str
    use_for: str
    content: str          # full SKILL.md body
    score: int = 0        # number of keyword hits


@dataclass
class AgentMatch:
    name: str
    role: str
    launch: str
    score: int = 0


@dataclass
class WorkflowPattern:
    id: str
    label: str
    agents: list[str]
    when: str


@dataclass
class SkillRoutingResult:
    skills: list[SkillMatch]
    agents: list[AgentMatch]
    workflow_pattern: WorkflowPattern | None
    context_block: str    # formatted text ready to inject into agent prompts


# ── SkillRouter ───────────────────────────────────────────────────────────────

class SkillRouter:
    """
    Loads skill and agent registries once at init, then answers routing queries.

    Usage:
        router = SkillRouter()
        result = router.route(task_description)
        # inject result.context_block into the agent's planning context
    """

    def __init__(self) -> None:
        self._skills: dict[str, dict[str, Any]] = {}   # name → {owner, use_for, content}
        self._agents: dict[str, dict[str, Any]] = {}   # name → {role, launch, ...}
        self._workflow_patterns: list[dict[str, Any]] = []
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return

        # --- skills ---
        if _SKILLS_REGISTRY.exists():
            raw = yaml.safe_load(_SKILLS_REGISTRY.read_text()) or {}
            for name, meta in raw.get("skills", {}).items():
                skill_md = _SKILLS_DIR / name / "SKILL.md"
                content = ""
                if skill_md.exists():
                    content = skill_md.read_text()
                self._skills[name] = {
                    "owner": meta.get("owner", ""),
                    "use_for": meta.get("use_for", ""),
                    "content": content,
                }

        # --- hub_skills workflow patterns ---
        if _HUB_SKILLS.exists():
            raw = yaml.safe_load(_HUB_SKILLS.read_text()) or {}
            for p in raw.get("project_agent_patterns", []):
                self._workflow_patterns.append(p)

        # --- agents ---
        if _AGENTS_REGISTRY.exists():
            raw = yaml.safe_load(_AGENTS_REGISTRY.read_text()) or {}
            for name, meta in raw.get("agents", {}).items():
                self._agents[name] = {
                    "role": meta.get("role", ""),
                    "launch": meta.get("launch", ""),
                    "status": meta.get("status", ""),
                }

        self._loaded = True

    # ── public API ────────────────────────────────────────────────────────────

    def route(self, task: str, top_skills: int = 2, top_agents: int = 3) -> SkillRoutingResult:
        """
        Match task to skills, agents, and workflow pattern.
        Returns a SkillRoutingResult with a pre-formatted context_block.
        """
        self._load()
        skills = self.match_skills(task, top_n=top_skills)
        agents = self.suggest_agents(task, top_n=top_agents)
        pattern = self.match_workflow_pattern(task, agents)
        context_block = self._format_context(task, skills, agents, pattern)
        return SkillRoutingResult(
            skills=skills,
            agents=agents,
            workflow_pattern=pattern,
            context_block=context_block,
        )

    def match_skills(self, task: str, top_n: int = 2) -> list[SkillMatch]:
        """Return up to top_n skills sorted by keyword hit count."""
        self._load()
        task_lower = task.lower()
        scores: dict[str, int] = {name: 0 for name in self._skills}

        for keyword, skill_names in _SKILL_KEYWORDS.items():
            if keyword in task_lower:
                for sname in skill_names:
                    if sname in scores:
                        scores[sname] += 1

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for name, score in ranked[:top_n]:
            if score == 0:
                break
            meta = self._skills[name]
            results.append(SkillMatch(
                name=name,
                owner=meta["owner"],
                use_for=meta["use_for"],
                content=meta["content"],
                score=score,
            ))
        return results

    def suggest_agents(self, task: str, top_n: int = 3) -> list[AgentMatch]:
        """Return top hub agents for this task sorted by keyword hit count."""
        self._load()
        task_lower = task.lower()
        scores: dict[str, int] = {name: 0 for name in self._agents}

        for keyword, agent_names in _AGENT_KEYWORDS.items():
            if keyword in task_lower:
                for aname in agent_names:
                    if aname in scores:
                        scores[aname] += 1

        # Always include hermes as fallback with score 0 if nothing matched
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        seen_agents: set[str] = set()
        for name, score in ranked:
            if len(results) >= top_n:
                break
            meta = self._agents.get(name, {})
            if meta.get("status") not in ("active", "ready"):
                continue
            results.append(AgentMatch(
                name=name,
                role=meta.get("role", ""),
                launch=meta.get("launch", ""),
                score=score,
            ))
            seen_agents.add(name)

        # Always include hermes if not already in list
        if "hermes" not in seen_agents and len(results) < top_n:
            meta = self._agents.get("hermes", {})
            results.append(AgentMatch(
                name="hermes",
                role=meta.get("role", ""),
                launch=meta.get("launch", ""),
                score=0,
            ))

        return results

    def match_workflow_pattern(
        self, task: str, agents: list[AgentMatch]
    ) -> WorkflowPattern | None:
        """Pick the most fitting project_agent_pattern from hub_skills.yaml."""
        self._load()
        if not self._workflow_patterns:
            return None

        task_lower = task.lower()
        agent_names = {a.name for a in agents}

        best: dict[str, Any] | None = None
        best_score = -1

        for p in self._workflow_patterns:
            score = 0
            # Agent overlap
            for a in p.get("agents", []) + p.get("specialists", []):
                if a in agent_names:
                    score += 2
            # Keyword match in 'when' description
            when = p.get("when", "").lower()
            for word in re.findall(r"\w+", task_lower):
                if word in when and len(word) > 4:
                    score += 1
            if score > best_score:
                best_score = score
                best = p

        if best is None or best_score == 0:
            return None

        return WorkflowPattern(
            id=best.get("id", ""),
            label=best.get("label", ""),
            agents=best.get("agents", []) + best.get("specialists", []),
            when=best.get("when", ""),
        )

    def get_skill_content(self, skill_name: str) -> str:
        """Return raw SKILL.md content for a specific skill by name."""
        self._load()
        return self._skills.get(skill_name, {}).get("content", "")

    # ── formatting ────────────────────────────────────────────────────────────

    def _format_context(
        self,
        task: str,
        skills: list[SkillMatch],
        agents: list[AgentMatch],
        pattern: WorkflowPattern | None,
    ) -> str:
        parts: list[str] = []

        if skills:
            parts.append("## Matched Skills (structured guidance)")
            for s in skills:
                parts.append(f"\n### Skill: {s.name}")
                parts.append(f"Use for: {s.use_for}")
                if s.content:
                    # Trim very long SKILL.md files to avoid bloating the prompt
                    body = s.content.strip()
                    if len(body) > 2000:
                        body = body[:2000] + "\n... [skill content truncated]"
                    parts.append(body)

        if agents:
            parts.append("\n## Suggested Hub Agents")
            for a in agents:
                launch_hint = f" | launch: `{a.launch}`" if a.launch else ""
                parts.append(f"- **{a.name}**: {a.role}{launch_hint}")

        if pattern:
            parts.append(f"\n## Recommended Workflow Pattern: {pattern.label}")
            parts.append(f"When: {pattern.when}")
            parts.append(f"Agents: {', '.join(pattern.agents)}")

        return "\n".join(parts).strip()


# ── module-level singleton ────────────────────────────────────────────────────

_router: SkillRouter | None = None


def skill_router() -> SkillRouter:
    """Return the shared SkillRouter (lazy-loaded, singleton)."""
    global _router
    if _router is None:
        _router = SkillRouter()
    return _router


def route_task_skills(task: str) -> SkillRoutingResult:
    """Convenience: route a task and return the full SkillRoutingResult."""
    return skill_router().route(task)
