"""
DSPy optimizer — compiles the ReflexionAgent from accumulated successful traces.

Run this periodically (e.g. after 10+ successful traces) to improve the agent's
prompts and few-shot examples using BootstrapFewShot or MIPROv2.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .memory import load_all_traces, export_learning, TRACE_DIR


def _build_dspy_examples(traces: list[dict]) -> list:
    """Convert stored traces to dspy.Example objects."""
    import dspy

    examples = []
    for t in traces:
        inp = t.get("inputs", {})
        out = t.get("outputs", {})
        ex = dspy.Example(
            task=inp.get("task", t.get("task", "")),
            context=inp.get("context", ""),
            past_reflections=inp.get("reflections", ""),
            answer=out.get("answer", ""),
            plan=out.get("plan", ""),
        ).with_inputs("task", "context", "past_reflections")
        examples.append(ex)
    return examples


def _score_fn(example: Any, pred: Any, trace: Any = None) -> float:
    """DSPy metric: non-empty answer with reasonable length."""
    answer = getattr(pred, "answer", "") or ""
    if len(answer.strip()) < 20:
        return 0.0
    # Penalize error markers
    if "[tool_error]" in answer or "[approval_required]" in answer:
        return 0.2
    return 1.0 if len(answer) >= 50 else 0.5


def compile_agent(
    agent,
    strategy: str = "bootstrap",
    min_traces: int = 5,
    max_bootstrapped: int = 4,
    save_path: str | None = None,
) -> Any:
    """
    Compile (optimize) the agent's DSPy modules from stored successful traces.

    Args:
        agent:              ReflexionAgent instance to optimize
        strategy:           'bootstrap' (fast) or 'mipro' (better but slower)
        min_traces:         Skip if fewer than this many traces available
        max_bootstrapped:   Max few-shot examples per module
        save_path:          If given, save compiled state to this path

    Returns:
        Compiled agent (or original if insufficient traces)
    """
    import dspy
    from dspy.teleprompt import BootstrapFewShot

    traces = load_all_traces(min_score=0.7)
    if len(traces) < min_traces:
        print(f"Only {len(traces)} traces available (need {min_traces}). Skipping compilation.")
        return agent

    print(f"Compiling from {len(traces)} successful traces...")
    examples = _build_dspy_examples(traces)

    if strategy == "mipro":
        try:
            from dspy.teleprompt import MIPROv2
            optimizer = MIPROv2(
                metric=_score_fn,
                auto="light",
                num_threads=2,
            )
            compiled = optimizer.compile(
                agent,
                trainset=examples,
                requires_permission_to_run=False,
            )
        except ImportError:
            print("MIPROv2 not available, falling back to BootstrapFewShot")
            strategy = "bootstrap"

    if strategy == "bootstrap":
        optimizer = BootstrapFewShot(
            metric=_score_fn,
            max_bootstrapped_demos=max_bootstrapped,
            max_labeled_demos=max_bootstrapped,
        )
        compiled = optimizer.compile(agent, trainset=examples)

    if save_path:
        compiled.save(save_path)
        print(f"Compiled agent saved to {save_path}")

    # Export learning about what the compilation improved
    export_learning(
        task="DSPy compilation run",
        learning=(
            f"Compiled agent from {len(traces)} traces using {strategy}. "
            f"Examples used: {len(examples)}. "
            f"Saved to: {save_path or 'memory only'}."
        ),
        tags=["dspy", "compilation", "optimization"],
    )

    return compiled


def auto_compile_if_ready(
    agent,
    threshold: int = 10,
    save_dir: str | None = None,
) -> tuple[Any, bool]:
    """
    Compile the agent if enough new traces have accumulated.
    Returns (agent, was_compiled).
    """
    traces = load_all_traces(min_score=0.7)
    if len(traces) < threshold:
        return agent, False

    save_path = None
    if save_dir:
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        save_path = str(Path(save_dir) / "compiled_agent.pkl")

    compiled = compile_agent(agent, save_path=save_path)
    return compiled, True


def load_compiled_agent(agent, path: str) -> Any:
    """Load a previously compiled agent state."""
    if Path(path).exists():
        agent.load(path)
        print(f"Loaded compiled agent from {path}")
    return agent


def trace_summary() -> dict:
    """Return stats about stored traces."""
    traces = load_all_traces(min_score=0.0)
    if not traces:
        return {"total": 0, "passing": 0, "avg_score": 0.0, "task_count": 0}
    passing = [t for t in traces if t.get("score", 0) >= 0.7]
    task_keys = {t.get("task_key") for t in traces}
    return {
        "total": len(traces),
        "passing": len(passing),
        "avg_score": sum(t.get("score", 0) for t in traces) / len(traces),
        "task_count": len(task_keys),
        "compilation_ready": len(passing) >= 5,
    }
