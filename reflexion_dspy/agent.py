"""
Reflexion + DSPy self-improving agent.

Architecture:
  ┌─────────────────────────────────────────────────────────────┐
  │                    ReflexionAgent                           │
  │                                                             │
  │  ┌──────────┐    ┌──────────────┐    ┌────────────────┐    │
  │  │  Memory  │───▶│  DSPy ReAct  │───▶│   Evaluator    │    │
  │  │ (past    │    │  (MCP tools) │    │ (score result) │    │
  │  │  refls.) │    └──────┬───────┘    └───────┬────────┘    │
  │  └──────────┘           │                    │             │
  │       ▲                 │ fail               │ pass        │
  │       │      ┌──────────▼────────────┐       │             │
  │       └──────│   Reflector module    │       ▼             │
  │              │ (what went wrong?)    │  save trace         │
  │              └───────────────────────┘  (DSPy optimizer)   │
  └─────────────────────────────────────────────────────────────┘

Self-improvement happens at two timescales:
  Short-term  — Reflexion: verbal reflections injected into next attempt
  Long-term   — DSPy:      optimizer compiles better prompts from traces
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import dspy

from .evaluator import EvalResult, default_evaluator
from .memory import (
    count_reflections,
    export_learning,
    load_reflections,
    save_reflection,
    save_trace,
)
from .rules import (
    capability_router,
    budget_guard,
    write_objective,
    write_to_outbox,
    approve_artifact,
)
from .tools import MCPToolRegistry, format_tool_list


# ── DSPy signatures ───────────────────────────────────────────────────────────

class PlanSignature(dspy.Signature):
    """Create a step-by-step plan for solving the task using available tools."""

    task: str = dspy.InputField(desc="The task to accomplish")
    available_tools: str = dspy.InputField(desc="List of MCP tools available")
    past_reflections: str = dspy.InputField(
        desc="Lessons from previous failed attempts (empty on first try)"
    )
    context: str = dspy.InputField(desc="Background context relevant to the task")
    plan: str = dspy.OutputField(
        desc="Numbered step-by-step plan specifying which tools to use and why"
    )


class ExecuteSignature(dspy.Signature):
    """Execute the plan by calling tools and synthesizing a final answer."""

    task: str = dspy.InputField()
    plan: str = dspy.InputField()
    past_reflections: str = dspy.InputField()
    tool_results: str = dspy.InputField(desc="JSON array of tool call results")
    answer: str = dspy.OutputField(
        desc="Complete, detailed answer synthesized from tool results"
    )
    confidence: str = dspy.OutputField(
        desc="high / medium / low — how confident you are in this answer"
    )


class ReflectSignature(dspy.Signature):
    """Generate an actionable reflection on a failed attempt."""

    task: str = dspy.InputField()
    plan: str = dspy.InputField(desc="The plan that was executed")
    tool_results: str = dspy.InputField(desc="What the tools returned")
    answer: str = dspy.InputField(desc="The answer that was produced")
    eval_feedback: str = dspy.InputField(desc="Why the evaluator said it failed")
    reflection: str = dspy.OutputField(
        desc=(
            "Specific, actionable lessons: what went wrong, which tools to try differently, "
            "what information was missing. Be concrete — vague lessons don't help."
        )
    )


class SynthesisSignature(dspy.Signature):
    """Synthesize learnings from multiple successful traces into a reusable insight."""

    task_pattern: str = dspy.InputField()
    successful_traces: str = dspy.InputField()
    learning: str = dspy.OutputField(
        desc="Generalized insight about how to solve this class of task efficiently"
    )


# ── Modules ───────────────────────────────────────────────────────────────────

class Planner(dspy.Module):
    def __init__(self) -> None:
        self.plan = dspy.ChainOfThought(PlanSignature)

    def forward(self, task: str, tools: str, reflections: str, context: str = "") -> str:
        pred = self.plan(
            task=task,
            available_tools=tools,
            past_reflections=reflections,
            context=context,
        )
        return pred.plan


class Executor(dspy.Module):
    """Executes a plan by calling MCP tools then synthesizing with the LM."""

    def __init__(self, tool_registry: MCPToolRegistry) -> None:
        self.registry = tool_registry
        self.synthesize = dspy.ChainOfThought(ExecuteSignature)

    def forward(
        self,
        task: str,
        plan: str,
        reflections: str,
        max_tool_calls: int = 8,
        task_id: str = "unknown",
    ) -> tuple[str, list[dict]]:
        # Let LM decide which tools to call via ReAct-style loop
        tool_calls: list[dict] = []
        call_count = 0

        # Use DSPy's Predict to extract tool calls from the plan
        class ToolCallSignature(dspy.Signature):
            """Extract tool calls needed from the plan."""
            plan: str = dspy.InputField()
            available_tools: str = dspy.InputField()
            tool_name: str = dspy.OutputField(
                desc="Name of MCP tool to call, or 'done' if no tool needed"
            )
            tool_args: str = dspy.OutputField(
                desc="JSON object of arguments for the tool, or '{}'"
            )

        schemas = self.registry.get_tool_schemas()
        tool_summary = format_tool_list(schemas[:30])  # top 30 tools

        call_extractor = dspy.Predict(ToolCallSignature)

        remaining_plan = plan
        for _ in range(max_tool_calls):
            pred = call_extractor(plan=remaining_plan, available_tools=tool_summary)
            tool_name = pred.tool_name.strip()
            if not tool_name or tool_name.lower() == "done":
                break
            try:
                args = json.loads(pred.tool_args or "{}")
            except json.JSONDecodeError:
                args = {}

            result = self.registry.call(tool_name, task_id=task_id, **args)
            call_record = {"tool": tool_name, "args": args, "result": result[:500]}
            tool_calls.append(call_record)
            call_count += 1

            # Update plan context with what we got
            remaining_plan = (
                f"{remaining_plan}\n\n[Tool {tool_name} returned]: {result[:300]}"
            )

        # Synthesize final answer
        tool_results_str = json.dumps(tool_calls, indent=2)
        pred = self.synthesize(
            task=task,
            plan=plan,
            past_reflections=reflections,
            tool_results=tool_results_str,
        )
        return pred.answer, tool_calls


class Reflector(dspy.Module):
    def __init__(self) -> None:
        self.reflect = dspy.ChainOfThought(ReflectSignature)

    def forward(
        self, task: str, plan: str, tool_results: list[dict], answer: str, feedback: str
    ) -> str:
        pred = self.reflect(
            task=task,
            plan=plan,
            tool_results=json.dumps(tool_results, indent=2)[:1000],
            answer=answer[:500],
            eval_feedback=feedback,
        )
        return pred.reflection


# ── Main agent ────────────────────────────────────────────────────────────────

@dataclass
class AttemptRecord:
    attempt: int
    plan: str
    answer: str
    tool_calls: list[dict]
    eval_result: EvalResult
    reflection: str = ""
    duration_s: float = 0.0


@dataclass
class AgentResult:
    task: str
    success: bool
    final_answer: str
    attempts: list[AttemptRecord] = field(default_factory=list)
    total_attempts: int = 0
    final_score: float = 0.0


class ReflexionAgent(dspy.Module):
    """
    Self-improving agent: DSPy ReAct planning + Reflexion episodic memory.

    On each attempt:
      1. Load past reflections from memory
      2. Plan using those reflections
      3. Execute with MCP tools
      4. Evaluate the result
      5. If failed: reflect, save reflection, retry
      6. If passed: save trace for DSPy optimization
    """

    def __init__(
        self,
        tool_registry: MCPToolRegistry | None = None,
        evaluator: Callable | None = None,
        max_attempts: int = 4,
        pass_threshold: float = 0.55,
        verbose: bool = True,
    ) -> None:
        self.registry = tool_registry or MCPToolRegistry()
        self.evaluator = evaluator or default_evaluator(pass_threshold)
        self.max_attempts = max_attempts
        self.verbose = verbose

        self.planner = Planner()
        self.executor = Executor(self.registry)
        self.reflector = Reflector()

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def forward(self, task: str, context: str = "") -> AgentResult:
        # ── capability_routes.yaml: route task to right capability ────────────
        cap_router = capability_router()
        capability, cap_spec = cap_router.route_task(task)
        remote_allowed = cap_router.remote_allowed(capability)

        # Generate a stable task_id for logging
        task_id = hashlib.md5(f"{task}{time.time()}".encode()).hexdigest()[:8]

        # ── closed-feedback-policy.md: record objective ───────────────────────
        write_objective(task_id, task, capability)
        self._log(f"[capability_routes.yaml] Routed to: {capability}")

        # Connect tools if not already connected
        if not self.registry._initialized:
            self._log("Connecting to MCP gateway...")
            self.registry.connect()

        schemas = self.registry.get_tool_schemas()
        # Surface most useful tools prominently: research + memory + code first
        priority_servers = {"arxiv", "tavily", "brave", "exa", "pubmed", "wikipedia",
                           "memory", "code", "fetch", "context7", "time"}
        priority = [s for s in schemas if s["name"].split("-")[0] in priority_servers]
        others = [s for s in schemas if s["name"].split("-")[0] not in priority_servers]
        ordered_schemas = priority + others
        tool_list_str = format_tool_list(ordered_schemas[:50])

        attempts: list[AttemptRecord] = []
        prior_reflections = load_reflections(task)
        reflections_text = (
            "\n\n".join(f"Attempt {i+1} reflection:\n{r}" for i, r in enumerate(prior_reflections))
            if prior_reflections
            else ""
        )

        self._log(
            f"\n{'='*60}\n"
            f"Task: {task[:120]}\n"
            f"Capability: {capability}\n"
            f"Prior reflections loaded: {len(prior_reflections)}\n"
            f"Available tools: {len(schemas)}\n"
            f"{'='*60}"
        )

        for attempt_num in range(1, self.max_attempts + 1):
            self._log(f"\n── Attempt {attempt_num}/{self.max_attempts} ──")
            t0 = time.time()

            # Plan
            self._log("Planning...")
            plan = self.planner(
                task=task,
                tools=tool_list_str,
                reflections=reflections_text,
                context=context,
            )
            self._log(f"Plan: {plan[:200]}...")

            # Execute (pass task_id for mcp-tool-policy.md logging)
            self._log("Executing with MCP tools...")
            answer, tool_calls = self.executor(
                task=task, plan=plan, reflections=reflections_text, task_id=task_id
            )
            self._log(f"Tool calls: {len(tool_calls)} | Answer preview: {answer[:150]}...")

            # Evaluate
            eval_result = self.evaluator(task, answer)
            duration = time.time() - t0

            rec = AttemptRecord(
                attempt=attempt_num,
                plan=plan,
                answer=answer,
                tool_calls=tool_calls,
                eval_result=eval_result,
                duration_s=duration,
            )

            self._log(
                f"Score: {eval_result.score:.2f} ({'PASS' if eval_result.passed else 'FAIL'}) "
                f"| {eval_result.feedback[:100]}"
            )

            if eval_result.passed:
                # ── promotion-policy.md: outbox → approved flow ───────────────
                outbox_path = write_to_outbox(task_id, answer, label="result")
                approved_path = approve_artifact(task_id, label="result")
                self._log(
                    f"[promotion-policy.md] outbox: {outbox_path.name} "
                    f"→ approved: {approved_path.name if approved_path else 'pending'}"
                )

                # Save trace for future DSPy optimization
                save_trace(
                    task=task,
                    inputs={"task": task, "context": context, "reflections": reflections_text},
                    outputs={"answer": answer, "plan": plan},
                    tool_calls=tool_calls,
                    score=eval_result.score,
                    metadata={
                        "attempts": attempt_num,
                        "duration_s": duration,
                        "capability": capability,
                        "task_id": task_id,
                    },
                )
                attempts.append(rec)
                self._log(f"\n✓ Success on attempt {attempt_num}!")
                return AgentResult(
                    task=task,
                    success=True,
                    final_answer=answer,
                    attempts=attempts,
                    total_attempts=attempt_num,
                    final_score=eval_result.score,
                )

            # Failed — reflect
            self._log("Reflecting on failure...")
            reflection = self.reflector(
                task=task,
                plan=plan,
                tool_results=tool_calls,
                answer=answer,
                feedback=eval_result.feedback,
            )
            rec.reflection = reflection
            self._log(f"Reflection: {reflection[:150]}...")

            # Persist reflection
            save_reflection(
                task=task,
                attempt=attempt_num + count_reflections(task),
                reflection=reflection,
                outcome=f"score={eval_result.score:.2f}",
            )

            # Update reflections context for next attempt
            reflections_text = (
                reflections_text
                + f"\n\nAttempt {attempt_num} reflection:\n{reflection}"
            ).strip()

            attempts.append(rec)

        # All attempts exhausted
        best = max(attempts, key=lambda r: r.eval_result.score)
        self._log(
            f"\n✗ Max attempts ({self.max_attempts}) reached. "
            f"Best score: {best.eval_result.score:.2f}"
        )

        # Export as learning for liaison memory system
        if attempts:
            lessons = "\n".join(
                f"- Attempt {r.attempt}: {r.reflection[:120]}" for r in attempts if r.reflection
            )
            export_learning(
                task=task,
                learning=f"Task '{task[:80]}' failed after {self.max_attempts} attempts.\n\nLessons:\n{lessons}",
                tags=["reflexion", "failed-task"],
            )

        return AgentResult(
            task=task,
            success=False,
            final_answer=best.answer,
            attempts=attempts,
            total_attempts=self.max_attempts,
            final_score=best.eval_result.score,
        )

    def close(self) -> None:
        self.registry.disconnect()
