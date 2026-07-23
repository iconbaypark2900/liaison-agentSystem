"""
CLI entry point for the ReflexionAgent.

Usage:
  python -m reflexion_dspy.cli run "Research the latest papers on quantum error correction"
  python -m reflexion_dspy.cli run "Search arxiv for DSPy papers and summarize top 3"
  python -m reflexion_dspy.cli optimize            # compile from traces
  python -m reflexion_dspy.cli history             # show trace stats
  python -m reflexion_dspy.cli tools               # list available MCP tools
  python -m reflexion_dspy.cli demo                # run a built-in demo task
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure parent directory is on path when running as module
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from reflexion_dspy.config import configure_dspy
from reflexion_dspy.tools import MCPToolRegistry, format_tool_list
from reflexion_dspy.optimizer import trace_summary, compile_agent
from reflexion_dspy.memory import load_reflections


DEMO_TASKS = [
    "Search arxiv for the 3 most recent papers on 'reflexion language agents' and summarize each in 2 sentences.",
    "Find the current Bitcoin price and recent market news. Provide a brief analysis.",
    "Use memory tools to store the fact that 'reflexion_dspy was initialized today' and then retrieve it.",
    "Search Wikipedia for 'DSPy programming framework' and extract the key concepts.",
]


def cmd_run(args: argparse.Namespace) -> None:
    from reflexion_dspy.agent import ReflexionAgent

    # capability_routes.yaml: detect use_for from task
    from reflexion_dspy.rules import capability_router
    capability, _ = capability_router().route_task(args.task)
    model = configure_dspy(use_for=capability, temperature=0.3)
    print(f"Model: {model} | Capability: {capability}\n")

    registry = MCPToolRegistry()
    agent = ReflexionAgent(
        tool_registry=registry,
        max_attempts=args.max_attempts,
        pass_threshold=args.threshold,
        verbose=not args.quiet,
    )

    task = args.task
    context = args.context or ""

    # Load any existing reflections
    prior = load_reflections(task)
    if prior:
        print(f"Loaded {len(prior)} prior reflections for this task.")

    result = agent(task=task, context=context)
    agent.close()

    print("\n" + "=" * 60)
    print(f"RESULT: {'SUCCESS' if result.success else 'PARTIAL'}")
    print(f"Score: {result.final_score:.2f} | Attempts: {result.total_attempts}")
    print("=" * 60)
    print(result.final_answer)

    if args.json:
        output = {
            "task": result.task,
            "success": result.success,
            "score": result.final_score,
            "attempts": result.total_attempts,
            "answer": result.final_answer,
            "reflections": [
                {"attempt": r.attempt, "reflection": r.reflection}
                for r in result.attempts
                if r.reflection
            ],
        }
        print("\n--- JSON ---")
        print(json.dumps(output, indent=2))


def cmd_optimize(args: argparse.Namespace) -> None:
    from reflexion_dspy.agent import ReflexionAgent

    stats = trace_summary()
    print(f"Trace stats: {json.dumps(stats, indent=2)}")

    if not stats["compilation_ready"]:
        print(
            f"\nNeed at least 5 passing traces to compile. "
            f"Currently {stats['passing']} passing traces."
        )
        return

    model = configure_dspy(use_for="implementation")
    registry = MCPToolRegistry()
    agent = ReflexionAgent(tool_registry=registry, verbose=False)

    save_dir = args.save_dir or str(
        __import__("pathlib").Path(__file__).parent.parent / "memory" / "compiled"
    )

    print(f"\nCompiling with strategy: {args.strategy}")
    compiled = compile_agent(
        agent,
        strategy=args.strategy,
        save_path=f"{save_dir}/compiled_agent.pkl" if args.save else None,
    )
    registry.disconnect()
    print("Compilation complete.")


def cmd_history(args: argparse.Namespace) -> None:
    from reflexion_dspy.memory import load_all_traces, REFLECTION_DIR, TRACE_DIR

    stats = trace_summary()
    print(f"\nTrace Statistics")
    print(f"  Total traces:  {stats['total']}")
    print(f"  Passing (≥0.7): {stats['passing']}")
    print(f"  Avg score:     {stats['avg_score']:.2f}")
    print(f"  Unique tasks:  {stats['task_count']}")
    print(f"  Ready to compile: {'YES' if stats['compilation_ready'] else 'NO'}")

    # Recent reflections
    ref_files = sorted(REFLECTION_DIR.glob("*.reflection.md"), reverse=True)[:5] if REFLECTION_DIR.exists() else []
    if ref_files:
        print(f"\nRecent Reflections ({len(ref_files)} shown):")
        for f in ref_files:
            print(f"  {f.name}")

    # Recent traces
    trace_files = sorted(TRACE_DIR.glob("*.trace.jsonl"), reverse=True)[:5] if TRACE_DIR.exists() else []
    if trace_files:
        print(f"\nTrace Files:")
        for f in trace_files:
            line_count = len(f.read_text().splitlines())
            print(f"  {f.name} ({line_count} entries)")


def cmd_tools(args: argparse.Namespace) -> None:
    registry = MCPToolRegistry()
    print("Connecting to MCP gateway...")
    registry.connect()
    schemas = registry.get_tool_schemas(filter_enabled=not args.all)
    print(f"\nAvailable tools ({len(schemas)}):\n")
    print(format_tool_list(schemas))
    registry.disconnect()


def cmd_demo(args: argparse.Namespace) -> None:
    import random

    task = DEMO_TASKS[args.index if args.index is not None else 0]
    print(f"Running demo task:\n  {task}\n")

    # Temporarily set max_attempts=2 for demo
    args.task = task
    args.context = ""
    args.max_attempts = 2
    args.threshold = 0.4
    args.quiet = False
    args.json = False
    cmd_run(args)


def main() -> None:
    # Inject HF token if available in .env.local
    env_file = __import__("pathlib").Path(__file__).parent.parent.parent / "chat-ui" / ".env.local"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("HF_TOKEN="):
                os.environ.setdefault("HF_TOKEN", line.split("=", 1)[1].strip())

    parser = argparse.ArgumentParser(
        prog="reflexion-agent",
        description="Reflexion + DSPy self-improving agent with MCP tools",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # run
    p_run = sub.add_parser("run", help="Run the agent on a task")
    p_run.add_argument("task", help="Task description")
    p_run.add_argument("--context", default="", help="Background context")
    p_run.add_argument("--max-attempts", type=int, default=4)
    p_run.add_argument("--threshold", type=float, default=0.55)
    p_run.add_argument("--quiet", action="store_true")
    p_run.add_argument("--json", action="store_true", help="Output JSON result")
    p_run.set_defaults(func=cmd_run)

    # optimize
    p_opt = sub.add_parser("optimize", help="Compile agent from accumulated traces")
    p_opt.add_argument("--strategy", choices=["bootstrap", "mipro"], default="bootstrap")
    p_opt.add_argument("--save", action="store_true", help="Save compiled agent")
    p_opt.add_argument("--save-dir", default=None)
    p_opt.set_defaults(func=cmd_optimize)

    # history
    p_hist = sub.add_parser("history", help="Show trace and reflection stats")
    p_hist.set_defaults(func=cmd_history)

    # tools
    p_tools = sub.add_parser("tools", help="List available MCP tools")
    p_tools.add_argument("--all", action="store_true", help="Show all tools (incl. disabled)")
    p_tools.set_defaults(func=cmd_tools)

    # demo
    p_demo = sub.add_parser("demo", help="Run a built-in demo task")
    p_demo.add_argument("--index", type=int, default=None, help="Demo task index (0-3)")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
