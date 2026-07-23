"""
Task evaluators for the Reflexion loop.

An evaluator takes (task, result) and returns a score 0.0–1.0 plus feedback.
Multiple evaluator strategies are supported so they can be composed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class EvalResult:
    score: float  # 0.0 = total failure, 1.0 = perfect
    passed: bool
    feedback: str
    details: dict = field(default_factory=dict)


# ── Rule-based evaluators ─────────────────────────────────────────────────────

def keyword_evaluator(
    required_keywords: list[str],
    threshold: float = 0.6,
) -> Callable[[str, str], EvalResult]:
    """Pass if the result contains a minimum fraction of required keywords."""
    def evaluate(task: str, result: str) -> EvalResult:
        result_lower = result.lower()
        found = [kw for kw in required_keywords if kw.lower() in result_lower]
        score = len(found) / len(required_keywords) if required_keywords else 1.0
        passed = score >= threshold
        missing = [kw for kw in required_keywords if kw.lower() not in result_lower]
        feedback = (
            f"Found {len(found)}/{len(required_keywords)} keywords."
            + (f" Missing: {missing}" if missing else " All keywords present.")
        )
        return EvalResult(score=score, passed=passed, feedback=feedback)
    return evaluate


def length_evaluator(
    min_chars: int = 50,
    max_chars: int = 10_000,
) -> Callable[[str, str], EvalResult]:
    """Pass if the result is within the expected length range."""
    def evaluate(task: str, result: str) -> EvalResult:
        n = len(result.strip())
        if n < min_chars:
            return EvalResult(
                score=n / min_chars * 0.5,
                passed=False,
                feedback=f"Result too short ({n} chars, need ≥{min_chars}).",
            )
        if n > max_chars:
            return EvalResult(
                score=0.7,
                passed=True,
                feedback=f"Result very long ({n} chars). Consider trimming.",
            )
        return EvalResult(score=1.0, passed=True, feedback=f"Length OK ({n} chars).")
    return evaluate


def no_error_evaluator() -> Callable[[str, str], EvalResult]:
    """Fail if the result contains obvious error markers."""
    ERROR_PATTERNS = [
        r"\[tool_error\]",
        r"\[approval_required\]",
        r"error:",
        r"exception:",
        r"traceback",
        r"failed to",
        r"could not",
    ]
    compiled = [re.compile(p, re.IGNORECASE) for p in ERROR_PATTERNS]

    def evaluate(task: str, result: str) -> EvalResult:
        errors = [p.pattern for p in compiled if p.search(result)]
        if errors:
            return EvalResult(
                score=0.2,
                passed=False,
                feedback=f"Result contains error markers: {errors[:3]}",
            )
        return EvalResult(score=1.0, passed=True, feedback="No error markers detected.")
    return evaluate


def task_completion_evaluator() -> Callable[[str, str], EvalResult]:
    """Heuristic: does the result seem to address the task?"""
    def evaluate(task: str, result: str) -> EvalResult:
        # Extract key nouns from task and check they appear in result
        task_words = set(re.findall(r"\b\w{4,}\b", task.lower()))
        result_words = set(re.findall(r"\b\w{4,}\b", result.lower()))
        overlap = task_words & result_words
        score = min(1.0, len(overlap) / max(len(task_words), 1) * 2)
        passed = score >= 0.3
        feedback = (
            f"Task-result overlap: {len(overlap)}/{len(task_words)} key terms. "
            f"Score: {score:.2f}"
        )
        return EvalResult(score=score, passed=passed, feedback=feedback)
    return evaluate


# ── LLM-judge evaluator ───────────────────────────────────────────────────────

def llm_judge_evaluator(
    threshold: float = 0.6,
) -> Callable[[str, str], EvalResult]:
    """
    Use DSPy's LM to judge result quality.
    Falls back to heuristic if DSPy is unavailable.
    """
    def evaluate(task: str, result: str) -> EvalResult:
        try:
            import dspy

            class JudgeSignature(dspy.Signature):
                """Judge whether a result successfully completes the task."""
                task: str = dspy.InputField()
                result: str = dspy.InputField()
                score: float = dspy.OutputField(
                    desc="Float 0.0-1.0: how well the result solves the task"
                )
                feedback: str = dspy.OutputField(
                    desc="Specific feedback on what is good or missing"
                )

            judge = dspy.Predict(JudgeSignature)
            pred = judge(task=task, result=result[:2000])
            try:
                score = float(pred.score)
            except (ValueError, TypeError):
                score = 0.5
            score = max(0.0, min(1.0, score))
            return EvalResult(
                score=score,
                passed=score >= threshold,
                feedback=pred.feedback,
            )
        except Exception as e:
            # Fallback to heuristic
            base = task_completion_evaluator()
            ev = base(task, result)
            ev.feedback = f"LLM judge unavailable ({e}). Heuristic: {ev.feedback}"
            return ev

    return evaluate


# ── Composite evaluator ───────────────────────────────────────────────────────

class CompositeEvaluator:
    """Combines multiple evaluators with weights."""

    def __init__(
        self,
        evaluators: list[tuple[Callable, float]],  # (evaluator, weight)
        pass_threshold: float = 0.6,
    ) -> None:
        self.evaluators = evaluators
        self.pass_threshold = pass_threshold

    def __call__(self, task: str, result: str) -> EvalResult:
        weighted_score = 0.0
        total_weight = sum(w for _, w in self.evaluators)
        feedbacks = []
        details = {}

        for evaluator, weight in self.evaluators:
            ev = evaluator(task, result)
            weighted_score += ev.score * weight
            feedbacks.append(ev.feedback)
            details[evaluator.__name__ if hasattr(evaluator, "__name__") else str(evaluator)] = {
                "score": ev.score,
                "passed": ev.passed,
            }

        final_score = weighted_score / total_weight if total_weight > 0 else 0.0
        return EvalResult(
            score=final_score,
            passed=final_score >= self.pass_threshold,
            feedback=" | ".join(feedbacks),
            details=details,
        )


def default_evaluator(pass_threshold: float = 0.55) -> CompositeEvaluator:
    """Default evaluator for general tasks."""
    return CompositeEvaluator(
        evaluators=[
            (no_error_evaluator(), 2.0),
            (length_evaluator(min_chars=30), 1.0),
            (task_completion_evaluator(), 2.0),
            (llm_judge_evaluator(threshold=pass_threshold), 3.0),
        ],
        pass_threshold=pass_threshold,
    )
