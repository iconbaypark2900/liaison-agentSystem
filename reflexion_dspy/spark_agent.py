"""
ReflexionAgent as a liaison reporter-mode participant.

This is the real integration: the agent reads spark-flow context bundles,
uses MCP tools to do the work, and writes outbox artifacts in the standard
task lifecycle format (plan → build → patch → review → close).

Flow:
  1. spark-flow init <task-id> "description"    # human sets up task
  2. spark-flow context <phase> --show          # generates context bundle
  3. reflexion-agent attach <task-id> <phase>   # THIS FILE — agent does work
  4. spark-flow approve <phase>                 # human approves
     OR
     spark-flow reject <phase> "reason"         # → reflexion-agent reflect → retry
  5. spark-flow validate --profile <profile>    # validation
  6. spark-flow close-task                      # closeout

Self-improvement:
  - Rejection: reflexion stores the reason, retries with that context
  - Approval: trace saved → DSPy optimizer improves prompts over time
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any

import dspy

from .evaluator import default_evaluator
from .memory import export_learning, load_reflections, save_reflection, save_trace
from .rules import (
    BudgetGuard,
    CapabilityRouter,
    ModelRouter,
    MCPToolPolicy,
    approve_artifact,
    budget_guard,
    capability_router,
    model_router,
    tool_policy,
    write_objective,
    write_to_outbox,
    REPO_ROOT,
)
from .tools import MCPToolRegistry, format_tool_list

FLOW_DIR = Path(".spark-flow")
PHASES = ["plan", "build", "patch", "review", "close"]

# MCP tool priorities by project domain (from registry/repos.yaml default_profile)
DOMAIN_TOOL_PRIORITY: dict[str, list[str]] = {
    "quantum": ["coda", "arxiv", "pubmed", "wikipedia", "memory", "tavily", "exa"],
    "python":  ["code", "arxiv", "tavily", "exa", "context7", "memory", "github"],
    "sigma":   ["alpaca", "yahoo", "tavily", "exa", "code", "github", "memory"],
    "rag":     ["arxiv", "tavily", "exa", "context7", "memory", "wikipedia", "code"],
    "none":    ["arxiv", "tavily", "brave", "exa", "memory", "wikipedia", "pubmed"],
}

# Phase → capability capability_routes.yaml key
PHASE_CAPABILITY: dict[str, str] = {
    "plan":   "local_review",
    "build":  "local_implementation",
    "patch":  "local_implementation",
    "review": "local_review",
    "close":  "local_review",
}


# ── Context bundle reader ─────────────────────────────────────────────────────

class ContextBundle:
    """Parsed spark-flow context bundle from .spark-flow/tasks/<id>/context/<phase>.md"""

    def __init__(self, task_id: str, phase: str, task_root: Path) -> None:
        self.task_id = task_id
        self.phase = phase
        self.task_root = task_root

        context_path = task_root / "context" / f"{phase}.md"
        manifest_path = task_root / "context" / f"{phase}.manifest.json"

        if context_path.exists():
            self.raw = context_path.read_text()
        else:
            self.raw = ""

        if manifest_path.exists():
            self.manifest: dict = json.loads(manifest_path.read_text())
        else:
            self.manifest = {}

        self.task_description = self._extract("Task Description", "Requested Phase")
        self.handoff = self._extract("Handoff File for Phase", "Resolved Skills")
        self.approved_prior = self._extract("Approved Prior Outputs", "Handoff File for Phase")
        self.skills = self._extract("Resolved Skills", "Relevant Policies")
        self.output_path = self.manifest.get("required_output_file", "")

        # Fall back to TASK.md if context not yet generated
        if not self.task_description.strip():
            task_md = task_root / "TASK.md"
            if task_md.exists():
                self.task_description = task_md.read_text()

        # Load handoff instructions for this phase
        handoff_md = task_root / "handoff" / f"{phase}.md"
        if handoff_md.exists() and not self.handoff.strip():
            self.handoff = handoff_md.read_text()

    def _extract(self, start_heading: str, end_heading: str) -> str:
        """Extract text between two ### headings."""
        pattern = rf"### {re.escape(start_heading)}\n(.*?)(?=### {re.escape(end_heading)}|\Z)"
        m = re.search(pattern, self.raw, re.DOTALL)
        return m.group(1).strip() if m else ""

    @property
    def outbox_path(self) -> Path:
        if self.output_path:
            return Path(self.output_path)
        return self.task_root / "outbox" / f"{self.phase}.md"

    @property
    def rejection_log(self) -> Path:
        return self.task_root / "feedback" / f"{self.phase}_rejections.jsonl"

    def load_rejections(self) -> list[dict]:
        """Load previous rejection feedback for this phase (Reflexion signal)."""
        if not self.rejection_log.exists():
            return []
        records = []
        for line in self.rejection_log.read_text().splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return records

    def save_rejection(self, reason: str) -> None:
        self.rejection_log.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "task_id": self.task_id,
            "phase": self.phase,
            "reason": reason,
        }
        with self.rejection_log.open("a") as f:
            f.write(json.dumps(record) + "\n")

    def as_agent_prompt(self) -> str:
        """Build the full task prompt for the agent from the context bundle."""
        rejections = self.load_rejections()
        rejection_block = ""
        if rejections:
            notes = "\n".join(f"  - Attempt {i+1}: {r['reason']}" for i, r in enumerate(rejections))
            rejection_block = f"\n\n### Previous rejections (fix these)\n{notes}"

        return (
            f"## Task\n{self.task_description}\n\n"
            f"## Phase\n{self.phase}\n\n"
            f"## Handoff instructions\n{self.handoff or 'See task description.'}\n\n"
            f"## Approved prior work\n{self.approved_prior or 'None yet.'}"
            f"{rejection_block}"
        )


# ── DSPy signatures for lifecycle phases ─────────────────────────────────────

class PlanSignature(dspy.Signature):
    """Create an implementation plan for the BUILD phase. Be precise and scoped."""
    task_context: str = dspy.InputField(desc="Full context bundle content")
    available_tools: str = dspy.InputField(desc="MCP tools available for research")
    past_reflections: str = dspy.InputField(desc="Lessons from rejected attempts")
    plan: str = dspy.OutputField(
        desc="Numbered implementation plan with specific files, commands, and acceptance criteria"
    )
    risks: str = dspy.OutputField(desc="Known risks and open questions")
    next_action: str = dspy.OutputField(desc="Exact recommended next step for the human")


class BuildSignature(dspy.Signature):
    """Produce implementation code/config/tests based on the approved plan."""
    task_context: str = dspy.InputField()
    available_tools: str = dspy.InputField()
    past_reflections: str = dspy.InputField()
    implementation: str = dspy.OutputField(
        desc="Complete implementation: code, configs, commands, and test results"
    )
    evidence: str = dspy.OutputField(desc="Commands run and their outputs as evidence")
    risks: str = dspy.OutputField(desc="Remaining risks or follow-up items")


class ReviewSignature(dspy.Signature):
    """Review the implementation for correctness, risks, and quality."""
    task_context: str = dspy.InputField()
    available_tools: str = dspy.InputField()
    past_reflections: str = dspy.InputField()
    summary: str = dspy.OutputField(desc="What was reviewed and what was found")
    verdict: str = dspy.OutputField(desc="PASS or FAIL with clear rationale")
    risks: str = dspy.OutputField(desc="Specific risks, gaps, or improvements needed")
    next_action: str = dspy.OutputField(desc="Recommended next step")


class ResearchSignature(dspy.Signature):
    """Research topic using available tools, synthesize findings into a report."""
    task_context: str = dspy.InputField()
    available_tools: str = dspy.InputField(desc="Research MCP tools (arxiv, tavily, pubmed, etc.)")
    past_reflections: str = dspy.InputField()
    tool_results: str = dspy.InputField(desc="Results from tool calls made")
    summary: str = dspy.OutputField(desc="Synthesized findings with sources")
    evidence: str = dspy.OutputField(desc="Key sources and data points")
    next_action: str = dspy.OutputField(desc="Recommended next step")


# ── Tool call loop ────────────────────────────────────────────────────────────

def _run_tool_loop(
    registry: MCPToolRegistry,
    context: str,
    task_id: str,
    domain: str,
    max_calls: int = 6,
) -> list[dict]:
    """Use LM to decide which tools to call based on context and domain."""

    class ToolSelectSignature(dspy.Signature):
        """Select the single most useful tool call to make next, or 'done'."""
        task_context: str = dspy.InputField()
        available_tools: str = dspy.InputField()
        already_called: str = dspy.InputField(desc="Tools already called and their results")
        tool_name: str = dspy.OutputField(
            desc="Exact MCP tool name to call next, or 'done' if enough information"
        )
        tool_args: str = dspy.OutputField(desc="JSON object of arguments, or '{}'")

    priority_servers = DOMAIN_TOOL_PRIORITY.get(domain, DOMAIN_TOOL_PRIORITY["none"])
    schemas = registry.get_tool_schemas()
    priority = [s for s in schemas if s["name"].split("-")[0] in priority_servers]
    others = [s for s in schemas if s["name"].split("-")[0] not in priority_servers]
    tool_list = format_tool_list((priority + others)[:40])

    selector = dspy.Predict(ToolSelectSignature)
    tool_calls: list[dict] = []
    already_called_str = "None yet."

    for _ in range(max_calls):
        pred = selector(
            task_context=context[:1500],
            available_tools=tool_list,
            already_called=already_called_str,
        )
        name = (pred.tool_name or "").strip()
        if not name or name.lower() in ("done", "none", ""):
            break
        try:
            args = json.loads(pred.tool_args or "{}")
        except json.JSONDecodeError:
            args = {}

        result = registry.call(name, task_id=task_id, **args)
        record = {"tool": name, "args": args, "result": result[:600]}
        tool_calls.append(record)
        already_called_str = "\n".join(
            f"[{r['tool']}]: {r['result'][:200]}" for r in tool_calls
        )

    return tool_calls


# ── Outbox artifact writer ────────────────────────────────────────────────────

def _write_outbox(bundle: ContextBundle, content: dict) -> Path:
    """Write structured artifact to .spark-flow/tasks/<id>/outbox/<phase>.md"""
    phase = bundle.phase
    ts = datetime.now().isoformat(timespec="seconds")

    sections = {
        "plan": lambda c: dedent(f"""
            # PLAN: {bundle.task_id}

            ## Metadata
            - Agent: reflexion-dspy
            - Task: {bundle.task_id}
            - Phase: plan
            - Generated: {ts}

            ## Implementation Plan
            {c.get('plan', '')}

            ## Risks
            {c.get('risks', 'None identified.')}

            ## Next Action
            {c.get('next_action', 'Human reviews and approves this plan.')}
        """).strip(),

        "build": lambda c: dedent(f"""
            # BUILD: {bundle.task_id}

            ## Metadata
            - Agent: reflexion-dspy
            - Task: {bundle.task_id}
            - Phase: build
            - Generated: {ts}

            ## Summary
            {c.get('summary', '')}

            ## Implementation
            {c.get('implementation', '')}

            ## Evidence
            {c.get('evidence', 'No commands run.')}

            ## Risks
            {c.get('risks', 'None identified.')}

            ## Next Action
            Human reviews implementation and runs: `spark-flow approve build`
        """).strip(),

        "patch": lambda c: dedent(f"""
            # PATCH: {bundle.task_id}

            ## Metadata
            - Agent: reflexion-dspy
            - Task: {bundle.task_id}
            - Phase: patch
            - Generated: {ts}

            ## Summary
            {c.get('summary', '')}

            ## Changes
            {c.get('implementation', '')}

            ## Evidence
            {c.get('evidence', 'No commands run.')}

            ## Next Action
            Human reviews patch and runs: `spark-flow approve patch`
        """).strip(),

        "review": lambda c: dedent(f"""
            # REVIEW: {bundle.task_id}

            ## Metadata
            - Agent: reflexion-dspy
            - Task: {bundle.task_id}
            - Phase: review
            - Generated: {ts}

            ## Summary
            {c.get('summary', '')}

            ## Verdict
            {c.get('verdict', 'PENDING')}

            ## Risks
            {c.get('risks', 'None identified.')}

            ## Next Action
            {c.get('next_action', 'Human reviews and approves or rejects.')}
        """).strip(),
    }

    formatter = sections.get(phase, sections["build"])
    artifact = formatter(content)

    outbox = bundle.outbox_path
    outbox.parent.mkdir(parents=True, exist_ok=True)
    outbox.write_text(artifact)
    return outbox


# ── Main attach function ──────────────────────────────────────────────────────

def attach(
    task_id: str,
    phase: str,
    repo_path: Path | None = None,
    domain: str = "none",
    max_attempts: int = 3,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    Run the ReflexionAgent for a spark-flow task phase.

    Reads the context bundle, uses MCP tools, writes outbox artifact.
    Reflexion: if the human rejects, call reflect() then re-run attach().
    DSPy: approved artifacts become training traces for optimizer.

    Args:
        task_id:      spark-flow task ID
        phase:        plan / build / patch / review / close
        repo_path:    path to the project repo (overrides cwd)
        domain:       project domain for tool priority (python/quantum/sigma/rag)
        max_attempts: max Reflexion retries within a single attach run
        verbose:      print progress
    """
    root = repo_path or Path.cwd()
    task_root = root / ".spark-flow" / "tasks" / task_id

    if not task_root.exists():
        return {"ok": False, "error": f"Task {task_id} not found in {root}"}

    bundle = ContextBundle(task_id, phase, task_root)
    agent_prompt = bundle.as_agent_prompt()

    # Load Reflexion memory (rejections + past reflections)
    rejections = bundle.load_rejections()
    past_reflections = load_reflections(agent_prompt)
    all_reflections = [r["reason"] for r in rejections] + past_reflections
    reflections_text = "\n".join(f"- {r}" for r in all_reflections) if all_reflections else ""

    def _log(msg: str) -> None:
        if verbose:
            print(msg, flush=True)

    _log(f"\n{'='*60}")
    _log(f"reflexion-dspy attach: {task_id} [{phase}]")
    _log(f"Domain: {domain} | Rejections so far: {len(rejections)} | Reflections: {len(past_reflections)}")
    _log(f"{'='*60}\n")

    # Write objective record (closed-feedback-policy.md)
    write_objective(task_id, agent_prompt[:300], f"spark-flow/{phase}")

    # Connect to MCP gateway
    registry = MCPToolRegistry()
    registry.connect()
    _log(f"MCP tools available: {len(registry.get_tool_schemas())}")

    # ── Tool research loop ────────────────────────────────────────────────────
    _log("Gathering information with MCP tools...")
    tool_calls = _run_tool_loop(
        registry=registry,
        context=agent_prompt,
        task_id=task_id,
        domain=domain,
        max_calls=6,
    )
    tool_results_str = "\n\n".join(
        f"[{c['tool']}]:\n{c['result'][:400]}" for c in tool_calls
    )
    _log(f"Tool calls completed: {len(tool_calls)}")

    # ── Phase-appropriate DSPy module ─────────────────────────────────────────
    if phase == "plan":
        module = dspy.ChainOfThought(PlanSignature)
        pred = module(
            task_context=agent_prompt,
            available_tools=format_tool_list(registry.get_tool_schemas()[:30]),
            past_reflections=reflections_text,
        )
        content = {
            "plan": pred.plan,
            "risks": pred.risks,
            "next_action": pred.next_action,
            "summary": pred.plan[:200],
        }

    elif phase in ("build", "patch"):
        module = dspy.ChainOfThought(BuildSignature)
        pred = module(
            task_context=agent_prompt,
            available_tools=format_tool_list(registry.get_tool_schemas()[:30]),
            past_reflections=reflections_text,
        )
        content = {
            "implementation": pred.implementation,
            "evidence": pred.evidence + "\n\n**Tool results:**\n" + tool_results_str,
            "risks": pred.risks,
            "summary": pred.implementation[:200],
        }

    elif phase == "review":
        module = dspy.ChainOfThought(ReviewSignature)
        pred = module(
            task_context=agent_prompt,
            available_tools=format_tool_list(registry.get_tool_schemas()[:30]),
            past_reflections=reflections_text,
        )
        content = {
            "summary": pred.summary,
            "verdict": pred.verdict,
            "risks": pred.risks,
            "next_action": pred.next_action,
        }

    else:  # close or unknown — research + synthesis
        module = dspy.ChainOfThought(ResearchSignature)
        pred = module(
            task_context=agent_prompt,
            available_tools=format_tool_list(registry.get_tool_schemas()[:30]),
            past_reflections=reflections_text,
            tool_results=tool_results_str or "No tool calls made.",
        )
        content = {
            "summary": pred.summary,
            "evidence": pred.evidence,
            "risks": "",
            "next_action": pred.next_action,
            "implementation": pred.summary,
        }

    registry.disconnect()

    # ── Write outbox artifact ────────────────────────────────────────────────
    outbox_path = _write_outbox(bundle, content)
    _log(f"\n✓ Artifact written: {outbox_path}")
    _log(f"  Review with: cat {outbox_path}")
    _log(f"  Approve:     cd {root} && spark-flow approve {phase}")
    _log(f"  Reject:      reflexion-agent reflect {task_id} {phase} --reason '...'")

    # ── Save trace for DSPy optimizer (pending approval) ────────────────────
    save_trace(
        task=agent_prompt,
        inputs={"task_id": task_id, "phase": phase, "domain": domain},
        outputs=content,
        tool_calls=tool_calls,
        score=0.5,  # pending — updated to 1.0 on approval, 0.0 on rejection
        metadata={"task_id": task_id, "phase": phase, "status": "pending"},
    )

    return {
        "ok": True,
        "task_id": task_id,
        "phase": phase,
        "outbox": str(outbox_path),
        "tool_calls": len(tool_calls),
        "content_preview": content.get("summary", "")[:200],
    }


def reflect(task_id: str, phase: str, reason: str, repo_path: Path | None = None) -> None:
    """
    Record a rejection as Reflexion memory so the next attach() attempt
    incorporates the human's feedback.

    Called after: spark-flow reject <phase> "reason"
    """
    root = repo_path or Path.cwd()
    task_root = root / ".spark-flow" / "tasks" / task_id
    bundle = ContextBundle(task_id, phase, task_root)

    # Save to spark-flow feedback dir
    bundle.save_rejection(reason)

    # Save to Reflexion memory (memory/reflexion/)
    save_reflection(
        task=bundle.agent_prompt if hasattr(bundle, "agent_prompt") else bundle.task_description,
        attempt=len(bundle.load_rejections()),
        reflection=f"Human rejected {phase} with reason: {reason}",
        outcome=f"rejected/{phase}",
    )

    # Export as learning to liaison memory
    export_learning(
        task=bundle.task_description[:100],
        learning=f"Phase '{phase}' was rejected: {reason}",
        tags=["reflexion", f"task-{task_id}", f"phase-{phase}", "rejection"],
    )

    print(f"[reflexion] Rejection recorded for {task_id}/{phase}")
    print(f"[reflexion] Re-run: reflexion-agent attach {task_id} {phase}")


def approve(task_id: str, phase: str, repo_path: Path | None = None) -> None:
    """
    Record an approval — promotes trace score to 1.0 for DSPy compilation.

    Called after: spark-flow approve <phase>
    """
    from .memory import TRACE_DIR
    root = repo_path or Path.cwd()
    task_root = root / ".spark-flow" / "tasks" / task_id

    # Update pending trace to approved
    bundle = ContextBundle(task_id, phase, task_root)
    agent_prompt = bundle.as_agent_prompt()
    save_trace(
        task=agent_prompt,
        inputs={"task_id": task_id, "phase": phase},
        outputs={"status": "approved"},
        tool_calls=[],
        score=1.0,
        metadata={"task_id": task_id, "phase": phase, "status": "approved"},
    )

    export_learning(
        task=bundle.task_description[:100],
        learning=f"Phase '{phase}' approved for task {task_id}.",
        tags=["approval", f"task-{task_id}", f"phase-{phase}"],
    )
    print(f"[dspy] Approval recorded — trace score updated for optimizer.")


# ── Project repo discovery ────────────────────────────────────────────────────

def list_projects() -> list[dict]:
    """Read registry/repos.yaml and return registered projects with their paths."""
    try:
        import yaml
        repos_yaml = REPO_ROOT / "registry" / "repos.yaml"
        if not repos_yaml.exists():
            return []
        data = yaml.safe_load(repos_yaml.read_text()) or {}
        projects = []
        for key, spec in data.get("repos", {}).items():
            raw_path = spec.get("path", "")
            path = Path(raw_path.replace("~", str(Path.home())))
            projects.append({
                "key": key,
                "path": path,
                "role": spec.get("role", ""),
                "profile": spec.get("default_profile", "none"),
                "exists": path.exists(),
            })
        return projects
    except Exception:
        return []


def detect_domain(repo_path: Path) -> str:
    """Detect project domain from repo contents for MCP tool priority."""
    if not repo_path.exists():
        return "none"
    files = {f.name for f in repo_path.iterdir() if repo_path.is_dir()}
    content = " ".join(str(f) for f in repo_path.rglob("*.py") if f.stat().st_size < 10000)[:5000]
    if any(kw in content for kw in ["qiskit", "pennylane", "cirq", "quantum"]):
        return "quantum"
    if any(kw in content for kw in ["alpaca", "trading", "order", "portfolio"]):
        return "sigma"
    if any(kw in content for kw in ["retrieval", "vector", "embedding", "rag"]):
        return "rag"
    return "python"
