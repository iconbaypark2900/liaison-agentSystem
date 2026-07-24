"""
reflexion-agent CLI — liaison reporter-mode participant.

Commands:
  attach   <task-id> <phase>    Read context bundle, do the work, write outbox artifact
  reflect  <task-id> <phase>    Record a human rejection for Reflexion memory
  approve  <task-id> <phase>    Record approval (promotes DSPy trace score)
  projects                      List all registered repos from registry/repos.yaml
  status   [task-id]            Show task state and pending phases
  optimize                      Compile DSPy modules from accumulated approved traces
  history                       Show trace and reflection stats
  tools    [--all]              List available MCP tools
  run      <task>               One-shot task (standalone, no spark-flow lifecycle)

Lifecycle (with spark-flow):
  spark-flow init my-task-001 "Build RAG eval pipeline for adaptive-graph-rag"
  spark-flow context plan --show
  reflexion-agent attach my-task-001 plan --domain rag
  spark-flow approve plan
     OR
  spark-flow reject plan "missing acceptance criteria"
  reflexion-agent reflect my-task-001 plan --reason "missing acceptance criteria"
  reflexion-agent attach my-task-001 plan --domain rag   ← retries with rejection in context
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reflexion_dspy.config import configure_dspy
from reflexion_dspy.tools import MCPToolRegistry, format_tool_list
from reflexion_dspy.optimizer import trace_summary, compile_agent
from reflexion_dspy.memory import load_reflections
from reflexion_dspy.spark_agent import (
    attach as spark_attach,
    reflect as spark_reflect,
    approve as spark_approve,
    list_projects,
    detect_domain,
)

PHASES = ["plan", "build", "patch", "review", "close"]

# Project registry — shorthand keys → full paths
PROJECT_SHORTCUTS: dict[str, str] = {
    "adaptive-graph-rag":    str(Path.home() / "creatorsByChoice/adaptive-graph-rag"),
    "clinical-suite":        str(Path.home() / "creatorsByChoice/clinical-suite"),
    "quantumRX":             str(Path.home() / "creatorsByChoice/quantumRX"),
    "sigma":                 str(Path.home() / "quantumGlobalGroup/sigma"),
    "hybrid-qml":            str(Path.home() / "quantumGlobalGroup/hybrid-qml-kg-poc"),
    "polymarket-btc":        str(Path.home() / "polymarket_btc"),
    "polymarket-calc":       str(Path.home() / "polymarket_calculator"),
}


def _load_hf_token() -> None:
    env_file = Path(__file__).parent.parent.parent / "chat-ui" / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("HF_TOKEN="):
                os.environ.setdefault("HF_TOKEN", line.strip().split("=", 1)[1])


def _configure(use_for: str = "implementation") -> str:
    return configure_dspy(use_for=use_for, temperature=0.3)


# ── attach ─────────────────────────────────────────────────────────────────────

def cmd_attach(args: argparse.Namespace) -> None:
    from reflexion_dspy.rules import capability_router as cr

    # Detect domain for tool priority
    repo_path = Path(args.repo) if args.repo else Path.cwd()
    domain = args.domain or detect_domain(repo_path)

    # Route to right model for this phase (model_routes.yaml)
    phase_use_for = {
        "plan": "review", "build": "implementation",
        "patch": "implementation", "review": "review", "close": "summaries",
    }.get(args.phase, "implementation")

    model = _configure(use_for=phase_use_for)
    print(f"[model_routes.yaml] {model} | phase={args.phase} | domain={domain}")

    result = spark_attach(
        task_id=args.task_id,
        phase=args.phase,
        repo_path=repo_path,
        domain=domain,
        max_attempts=args.max_attempts,
        verbose=not args.quiet,
    )

    if result["ok"]:
        print(f"\nArtifact: {result['outbox']}")
        print(f"Tool calls: {result['tool_calls']}")
        print(f"\nPreview:\n{result['content_preview']}")
    else:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)


# ── reflect ────────────────────────────────────────────────────────────────────

def cmd_reflect(args: argparse.Namespace) -> None:
    repo_path = Path(args.repo) if args.repo else Path.cwd()
    spark_reflect(
        task_id=args.task_id,
        phase=args.phase,
        reason=args.reason,
        repo_path=repo_path,
    )
    print(f"\nNow re-run: reflexion-agent attach {args.task_id} {args.phase}")


# ── approve ────────────────────────────────────────────────────────────────────

def cmd_approve(args: argparse.Namespace) -> None:
    repo_path = Path(args.repo) if args.repo else Path.cwd()
    spark_approve(
        task_id=args.task_id,
        phase=args.phase,
        repo_path=repo_path,
    )


# ── projects ───────────────────────────────────────────────────────────────────

def cmd_projects(args: argparse.Namespace) -> None:
    projects = list_projects()
    if not projects:
        print("No projects found in registry/repos.yaml")
        return

    print(f"\nRegistered projects ({len(projects)}):\n")
    for p in projects:
        status = "✓" if p["exists"] else "✗"
        print(f"  {status} [{p['profile']:8}] {p['key']}")
        print(f"           {p['path']}")
        if p["role"]:
            print(f"           {p['role'][:80]}")
        print()


# ── status ─────────────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> None:
    repo_path = Path(args.repo) if args.repo else Path.cwd()
    flow_dir = repo_path / ".spark-flow"

    if not flow_dir.exists():
        print(f"No .spark-flow directory in {repo_path}")
        print("Run: spark-flow init <task-id> 'description'")
        return

    current_file = flow_dir / "current"
    current_task = current_file.read_text().strip() if current_file.exists() else None

    tasks_dir = flow_dir / "tasks"
    if not tasks_dir.exists():
        print("No tasks found.")
        return

    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        task_id = task_dir.name
        state_file = task_dir / "STATE.txt"
        state = state_file.read_text().strip() if state_file.exists() else "unknown"

        marker = " ← current" if task_id == current_task else ""
        print(f"\n  Task: {task_id}{marker}")
        print(f"  State: {state}")

        # Show what's in outbox vs approved
        outbox = task_dir / "outbox"
        approved = task_dir / "approved"
        feedback = task_dir / "feedback"

        if outbox.exists():
            pending = [f.name for f in outbox.glob("*.md")
                       if not f.name.startswith("test.")]
            print(f"  Outbox (awaiting approval): {pending}")

        if approved.exists():
            done = [f.name for f in approved.glob("*.md")]
            print(f"  Approved: {done}")

        # Show rejection history
        if feedback and feedback.exists():
            for rf in feedback.glob("*_rejections.jsonl"):
                phase = rf.stem.replace("_rejections", "")
                count = len(rf.read_text().splitlines())
                print(f"  Rejections [{phase}]: {count}")

        # Show available context bundles
        context_dir = task_dir / "context"
        if context_dir.exists():
            bundles = [f.stem for f in context_dir.glob("*.md")]
            print(f"  Context bundles: {bundles}")

        print(f"  Next: reflexion-agent attach {task_id} <phase>")


# ── optimize ───────────────────────────────────────────────────────────────────

def cmd_optimize(args: argparse.Namespace) -> None:
    from reflexion_dspy.agent import ReflexionAgent

    stats = trace_summary()
    print(f"Trace stats: {json.dumps(stats, indent=2)}")

    if not stats["compilation_ready"]:
        print(
            f"\nNeed at least 5 passing traces. Currently {stats['passing']} passing."
        )
        return

    model = _configure(use_for="implementation")
    registry = MCPToolRegistry()
    agent = ReflexionAgent(tool_registry=registry, verbose=False)

    save_dir = str(Path(__file__).parent.parent / "memory" / "compiled")
    compiled = compile_agent(
        agent,
        strategy=args.strategy,
        save_path=f"{save_dir}/compiled_agent.pkl" if args.save else None,
    )
    registry.disconnect()
    print("Compilation complete.")


# ── history ────────────────────────────────────────────────────────────────────

def cmd_history(args: argparse.Namespace) -> None:
    from reflexion_dspy.memory import REFLECTION_DIR, TRACE_DIR

    stats = trace_summary()
    print(f"\nTrace Statistics")
    print(f"  Total:         {stats['total']}")
    print(f"  Approved:      {stats['passing']}")
    print(f"  Avg score:     {stats['avg_score']:.2f}")
    print(f"  Unique tasks:  {stats['task_count']}")
    print(f"  Ready to compile: {'YES — run: reflexion-agent optimize' if stats['compilation_ready'] else 'No'}")

    ref_files = sorted(REFLECTION_DIR.glob("*.reflection.md"), reverse=True)[:5] if REFLECTION_DIR.exists() else []
    if ref_files:
        print(f"\nRecent Rejections/Reflections:")
        for f in ref_files:
            print(f"  {f.name}")

    budget_log = Path(__file__).parent.parent / "memory" / "budget_log.jsonl"
    if budget_log.exists():
        lines = budget_log.read_text().splitlines()
        print(f"\nBudget log entries: {len(lines)}")

    tool_log = Path(__file__).parent.parent / "memory" / "tool_call_log.jsonl"
    if tool_log.exists():
        lines = tool_log.read_text().splitlines()
        blocked = sum(1 for l in lines if '"allowed": false' in l)
        print(f"Tool calls logged: {len(lines)} ({blocked} blocked by policy)")


# ── tools ──────────────────────────────────────────────────────────────────────

def cmd_tools(args: argparse.Namespace) -> None:
    registry = MCPToolRegistry()
    print("Connecting to MCP gateway...")
    registry.connect()
    schemas = registry.get_tool_schemas(filter_enabled=not args.all)
    from collections import Counter
    servers = Counter(s["name"].split("-")[0] for s in schemas)
    print(f"\nMCP tools available: {len(schemas)} across {len(servers)} servers\n")
    if args.server:
        schemas = [s for s in schemas if s["name"].startswith(args.server)]
        print(f"Filtered to server '{args.server}': {len(schemas)} tools\n")
    print(format_tool_list(schemas[:60] if not args.all else schemas))
    registry.disconnect()


# ── run (standalone) ───────────────────────────────────────────────────────────

def cmd_code(args: argparse.Namespace) -> None:
    """
    Real coding agent: reads a project, writes code, runs tests, iterates.
    Like Claude Code / Codex — but uses MCP tools + Reflexion + DSPy.
    All changes go to a git feature branch; tests must pass before commit.
    """
    from reflexion_dspy.coder import CodingAgent, write_coding_artifact

    # Resolve project path
    repo_path_str = args.repo or PROJECT_SHORTCUTS.get(args.project)
    if not repo_path_str:
        # Try to find in list_projects()
        projects = list_projects()
        match = next((p for p in projects if p["key"] == args.project and p["exists"]), None)
        if match:
            repo_path_str = match["path"]
        else:
            print(
                f"Unknown project '{args.project}'. "
                f"Known shortcuts: {list(PROJECT_SHORTCUTS.keys())}\n"
                f"Or use: reflexion-agent code --repo /full/path 'task description'"
            )
            sys.exit(1)

    repo_path = Path(repo_path_str).expanduser().resolve()
    if not (repo_path / ".git").exists():
        print(f"ERROR: {repo_path} is not a git repo (no .git dir)")
        sys.exit(1)

    # Generate task_id from task text (slug)
    import hashlib, re
    slug = re.sub(r'\W+', '-', args.task.lower())[:30].strip('-')
    task_id = f"code-{slug}-{hashlib.md5(args.task.encode()).hexdigest()[:6]}"

    # Select model
    model = _configure(use_for="implementation")
    print(f"[model_routes.yaml] {model}")
    print(f"[task_id] {task_id}")
    print(f"[repo] {repo_path}")

    agent = CodingAgent(
        max_attempts=args.max_attempts,
        max_fix_rounds=args.fix_rounds,
        verbose=not args.quiet,
    )

    result = agent.run(task=args.task, repo_path=repo_path, task_id=task_id)

    # Write outbox artifact
    outbox_dir = repo_path / ".spark-flow" / "tasks" / task_id / "outbox"
    artifact = write_coding_artifact(result, task_id, outbox_dir)

    print("\n" + "=" * 60)
    if result.success:
        print(f"✓ SUCCESS — {len(result.files_written)} file(s) written, tests passing")
        print(f"  Branch: {result.branch}")
        print(f"  Artifact: {artifact}")
        print(f"\n  Review and merge:")
        print(f"  cd {repo_path} && git diff main..{result.branch}")
        print(f"  git checkout main && git merge {result.branch}")
    else:
        print(f"✗ FAILED after {result.attempts} attempt(s)")
        print(f"  Reflections saved — re-run to retry with learned context:")
        print(f"  reflexion-agent code {args.project!r} {args.task!r}")
        print(f"  Artifact: {artifact}")
    print("=" * 60)


def cmd_run(args: argparse.Namespace) -> None:
    from reflexion_dspy.agent import ReflexionAgent
    from reflexion_dspy.rules import capability_router as cr

    capability, _ = cr().route_task(args.task)
    model = _configure(use_for=capability)
    print(f"Model: {model} | Capability: {capability}\n")

    registry = MCPToolRegistry()
    agent = ReflexionAgent(
        tool_registry=registry,
        max_attempts=args.max_attempts,
        pass_threshold=args.threshold,
        verbose=not args.quiet,
    )

    result = agent(task=args.task, context=args.context or "")
    agent.close()

    print("\n" + "=" * 60)
    print(f"RESULT: {'SUCCESS' if result.success else 'PARTIAL'}")
    print(f"Score: {result.final_score:.2f} | Attempts: {result.total_attempts}")
    print("=" * 60)
    print(result.final_answer)

    if args.json:
        out = {
            "success": result.success, "score": result.final_score,
            "attempts": result.total_attempts, "answer": result.final_answer,
        }
        print("\n--- JSON ---")
        print(json.dumps(out, indent=2))


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    _load_hf_token()

    parser = argparse.ArgumentParser(
        prog="reflexion-agent",
        description="Self-improving agent — liaison reporter-mode participant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # attach
    p = sub.add_parser("attach", help="Read context bundle, do work, write outbox artifact")
    p.add_argument("task_id")
    p.add_argument("phase", choices=PHASES)
    p.add_argument("--repo", default=None, help="Repo path (default: cwd)")
    p.add_argument("--domain", default=None, choices=["python","quantum","sigma","rag","none"])
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_attach)

    # reflect
    p = sub.add_parser("reflect", help="Record human rejection for Reflexion memory")
    p.add_argument("task_id")
    p.add_argument("phase", choices=PHASES)
    p.add_argument("--reason", required=True, help="Rejection reason from human")
    p.add_argument("--repo", default=None)
    p.set_defaults(func=cmd_reflect)

    # approve
    p = sub.add_parser("approve", help="Record approval — updates DSPy trace")
    p.add_argument("task_id")
    p.add_argument("phase", choices=PHASES)
    p.add_argument("--repo", default=None)
    p.set_defaults(func=cmd_approve)

    # projects
    p = sub.add_parser("projects", help="List registered repos from registry/repos.yaml")
    p.set_defaults(func=cmd_projects)

    # status
    p = sub.add_parser("status", help="Show task state and pending phases")
    p.add_argument("task_id", nargs="?", default=None)
    p.add_argument("--repo", default=None)
    p.set_defaults(func=cmd_status)

    # optimize
    p = sub.add_parser("optimize", help="Compile agent from approved traces")
    p.add_argument("--strategy", choices=["bootstrap","mipro"], default="bootstrap")
    p.add_argument("--save", action="store_true")
    p.set_defaults(func=cmd_optimize)

    # history
    p = sub.add_parser("history", help="Show trace, reflection, and budget stats")
    p.set_defaults(func=cmd_history)

    # tools
    p = sub.add_parser("tools", help="List available MCP tools")
    p.add_argument("--all", action="store_true")
    p.add_argument("--server", default=None, help="Filter by server prefix (e.g. arxiv)")
    p.set_defaults(func=cmd_tools)

    # code — real coding agent
    p = sub.add_parser(
        "code",
        help="Write code, run tests, iterate — like Claude Code but with Reflexion",
    )
    p.add_argument("project", help="Project key (e.g. adaptive-graph-rag) or use --repo")
    p.add_argument("task", help="What to implement, e.g. 'Add Kelly criterion position sizing'")
    p.add_argument("--repo", default=None, help="Override project path")
    p.add_argument("--max-attempts", type=int, default=4,
                   help="Max Reflexion retry attempts (default 4)")
    p.add_argument("--fix-rounds", type=int, default=3,
                   help="Max test-fix rounds per attempt (default 3)")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_code)

    # run (standalone)
    p = sub.add_parser("run", help="One-shot task without spark-flow lifecycle")
    p.add_argument("task")
    p.add_argument("--context", default="")
    p.add_argument("--max-attempts", type=int, default=4)
    p.add_argument("--threshold", type=float, default=0.55)
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
