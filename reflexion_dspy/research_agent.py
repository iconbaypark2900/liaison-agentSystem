"""
StrategyResearchAgent — Reflexion-based edge research for sigma.

Same Reflexion loop as CodingAgent (coder.py) but the "test" is sigma's
edge_eval.gate() on a FIXED out-of-sample window, not a pytest run.

The agent:
  1. Generates a testable edge hypothesis conditioned on past failures
  2. Runs sigma's edge_research_harness.py on the TRAIN window only
  3. The OOS gate is authoritative — the agent cannot override it
  4. On failure: reflects on WHY and generates a different hypothesis
  5. On success: writes to the research journal

The OOS window is hardcoded in this agent and never passed to the
hypothesis generator — the agent never sees OOS data during hypothesis
generation, only after the gate runs.

Loop:
  hypothesis → harness (train + OOS, gate) → FAIL → reflect → new hypothesis
                                            → PASS → journal + outbox
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import dspy

from .config import configure_dspy
from .memory import load_reflections, save_reflection
from .research_journal import (
    append_attempt,
    close_journal,
    get_past_attempts_summary,
)

logger = logging.getLogger(__name__)

SIGMA_API = Path("/home/iconbaypark2900/quantumGlobalGroup/sigma/apps/api")
SIGMA_VENV = SIGMA_API / ".venv" / "bin" / "python"
HARNESS = SIGMA_API / "scripts" / "edge_research_harness.py"

# ── Fixed OOS split — NEVER change during a research run ─────────────────────
TRAIN_END = "2022-12-31"   # train window: everything on/before this date
OOS_START = "2023-01-01"   # OOS window: everything after (agent never sees this)

MAX_ATTEMPTS = 6

AVAILABLE_STRATEGIES = (
    "momentum, mean_reversion, breakout, regime, macd, fourier, "
    "gbm, ou, heston, ict"
)


# ── DSPy Signatures ───────────────────────────────────────────────────────────

class EdgeHypothesisSignature(dspy.Signature):
    """Generate a testable edge hypothesis for sigma's strategy combiner.

    You are a quantitative researcher. Your goal is to find a strategy +
    universe combination that shows durable, net-of-cost edge on HELD-OUT
    data. You only see training data during hypothesis generation.

    RULES:
    - You must propose a DIFFERENT approach than anything in past_reflections
    - Smaller, focused universes (3-6 tickers) produce more interpretable results
    - Regime-conditional strategies beat unconditional ones out-of-sample
    - Costs are real: equity = 2bps, crypto = 8bps round-trip
    - The gate requires 100+ OOS trades — choose liquid symbols with daily bars
    """

    research_question: str = dspy.InputField()
    asset_class: str = dspy.InputField()
    available_strategies: str = dspy.InputField()
    available_universe: str = dspy.InputField(
        desc="Tickers available to select from"
    )
    train_window: str = dspy.InputField(
        desc="The only period visible during hypothesis generation"
    )
    past_reflections: str = dspy.InputField(
        desc="What was already tried, why it failed — do NOT repeat these"
    )

    hypothesis: str = dspy.OutputField(
        desc="Why this edge should exist mechanically — name the counterparty or structural reason"
    )
    strategy_names: str = dspy.OutputField(
        desc="Comma-separated sigma strategy names from available_strategies"
    )
    symbols: str = dspy.OutputField(
        desc="Comma-separated tickers from available_universe (3-8 liquid names)"
    )
    rationale: str = dspy.OutputField(
        desc="Why this specific combination should show edge in the training window"
    )


class EdgeReflectionSignature(dspy.Signature):
    """Diagnose why an edge hypothesis failed OOS and determine the next direction.

    You are analyzing a FAILED backtest. Be specific and honest about the
    failure mode. Do not suggest the same approach in a different skin.
    """

    research_question: str = dspy.InputField()
    hypothesis: str = dspy.InputField()
    strategy_names: str = dspy.InputField()
    symbols: str = dspy.InputField()
    train_stats_json: str = dspy.InputField(
        desc="Per-strategy stats on training window"
    )
    oos_stats_json: str = dspy.InputField(
        desc="Per-strategy stats on OOS window — this is the ground truth"
    )
    gate_failure_reasons: str = dspy.InputField()
    previous_reflections: str = dspy.InputField()

    failure_mode: str = dspy.OutputField(
        desc="One of: regime_specific | costs_too_high | sample_too_small | "
             "overfit_to_train | no_structural_edge | wrong_universe | correlated_with_beta"
    )
    regime_insight: str = dspy.OutputField(
        desc="Which market period drove the OOS failure and why (e.g. '2023 rate-hike regime crushed momentum')"
    )
    next_hypothesis_direction: str = dspy.OutputField(
        desc="Specific, different approach to try next — not a restatement of what failed"
    )
    reflection: str = dspy.OutputField(
        desc="2-3 sentences: what was tried, what failed, what the failure reveals, what to try next"
    )


# ── Backtest runner ───────────────────────────────────────────────────────────

def _run_harness(
    asset_class: str,
    symbols: list[str],
    strategies: list[str],
) -> dict[str, Any]:
    """Run edge_research_harness.py and return parsed JSON result."""
    cmd = [
        str(SIGMA_VENV), str(HARNESS),
        "--asset-class", asset_class,
        "--symbols", *symbols,
        "--strategies", ",".join(strategies),
        "--train-end", TRAIN_END,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(SIGMA_API),
        env={
            **__import__("os").environ,
            "PYTHONPATH": f"{SIGMA_API}:{SIGMA_API.parent.parent}",
        },
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Harness failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Harness output is not JSON: {e}\n{result.stdout[:500]}")


def _extract_best_result(harness_output: dict) -> dict[str, Any]:
    """Pull out the best-performing strategy from harness output."""
    results = harness_output.get("results", {})
    best_name, best = None, None
    for name, r in results.items():
        if "error" in r:
            continue
        oos = r.get("oos", {})
        if best is None or oos.get("net_bps", -999) > best.get("oos", {}).get("net_bps", -999):
            best_name, best = name, r
    return best or {}


# ── Main agent ────────────────────────────────────────────────────────────────

@dataclass
class ResearchOutcome:
    research_question: str
    edge_found: bool
    attempts: int
    winning_strategy: str = ""
    winning_symbols: list[str] = field(default_factory=list)
    oos_stats: dict = field(default_factory=dict)
    journal_path: str = ""
    summary: str = ""


class StrategyResearchAgent:
    """
    Reflexion-based agent that searches for durable OOS edge in sigma's
    strategy library, accumulating structured knowledge with each failed attempt.

    Usage:
        agent = StrategyResearchAgent(
            research_question="Does momentum work on quantum computing stocks?",
            asset_class="equity",
            universe="IONQ,RGTI,QBTS,QUBT,RKLB,JOBY",
        )
        outcome = agent.run()
    """

    def __init__(
        self,
        research_question: str,
        asset_class: str = "equity",
        universe: str = "AAPL,MSFT,NVDA,AMZN,GOOG,META,TSLA,JPM",
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self.research_question = research_question
        self.asset_class = asset_class
        self.universe = universe
        self.max_attempts = max_attempts
        self._lm_configured = False

    def _ensure_lm(self) -> None:
        if not self._lm_configured:
            configure_dspy(use_for="implementation", temperature=0.4, max_tokens=4096)
            self._lm_configured = True

    def _log(self, msg: str) -> None:
        print(f"[ResearchAgent] {msg}", flush=True)

    def run(self) -> ResearchOutcome:
        self._ensure_lm()
        hypothesis_module = dspy.ChainOfThought(EdgeHypothesisSignature)
        reflection_module = dspy.ChainOfThought(EdgeReflectionSignature)

        train_window = f"All data from earliest available through {TRAIN_END}"
        self._log(f"Research question: {self.research_question}")
        self._log(f"Train window: {train_window} | OOS starts: {OOS_START}")
        self._log(f"Universe: {self.universe}")

        for attempt in range(1, self.max_attempts + 1):
            self._log(f"\n── Attempt {attempt}/{self.max_attempts} ──")

            past_reflections = get_past_attempts_summary(self.research_question)
            memory_reflections = load_reflections(self.research_question)
            all_reflections = (
                past_reflections
                + ("\n\nMemory reflections:\n" + "\n".join(memory_reflections)
                   if memory_reflections else "")
            )

            # Step 1 — Generate hypothesis
            self._log("Generating hypothesis...")
            try:
                hyp = hypothesis_module(
                    research_question=self.research_question,
                    asset_class=self.asset_class,
                    available_strategies=AVAILABLE_STRATEGIES,
                    available_universe=self.universe,
                    train_window=train_window,
                    past_reflections=all_reflections or "None yet — first attempt.",
                )
            except Exception as e:
                self._log(f"Hypothesis generation failed: {e}")
                continue

            strategies = [s.strip() for s in hyp.strategy_names.split(",") if s.strip()]
            symbols = [s.strip().upper() for s in hyp.symbols.split(",") if s.strip()]

            self._log(f"Hypothesis: {hyp.hypothesis[:120]}...")
            self._log(f"Strategies: {strategies} | Symbols: {symbols}")

            # Step 2 — Run harness (train + OOS + gate)
            self._log("Running backtest harness...")
            try:
                harness_result = _run_harness(self.asset_class, symbols, strategies)
            except Exception as e:
                self._log(f"Harness error: {e}")
                save_reflection(
                    self.research_question, attempt,
                    f"Harness failed to run: {e}", "error"
                )
                continue

            results = harness_result.get("results", {})
            skipped = harness_result.get("symbols_skipped", [])
            if skipped:
                self._log(f"Skipped: {skipped}")

            # Step 3 — Check if any strategy passed
            passed_strategies = {
                name: r for name, r in results.items()
                if r.get("gate_passed") and not r.get("error")
            }

            if passed_strategies:
                winner_name = max(
                    passed_strategies,
                    key=lambda n: passed_strategies[n]["oos"].get("sharpe", 0),
                )
                winner = passed_strategies[winner_name]
                oos_stats = winner["oos"]
                self._log(
                    f"EDGE FOUND — {winner_name} | "
                    f"OOS net_bps={oos_stats.get('net_bps'):.2f} | "
                    f"sharpe={oos_stats.get('sharpe'):.3f} | "
                    f"n_trades={oos_stats.get('n_trades')}"
                )

                append_attempt(
                    self.research_question,
                    attempt=attempt,
                    hypothesis=hyp.hypothesis,
                    strategies=strategies,
                    symbols=symbols,
                    train_end=TRAIN_END,
                    asset_class=self.asset_class,
                    train_stats={winner_name: winner["train"]},
                    oos_stats={winner_name: oos_stats},
                    gate_passed=True,
                    gate_reasons=[],
                    reflection="Gate passed — edge found.",
                )
                close_journal(
                    self.research_question,
                    outcome="edge_found",
                    final_finding=(
                        f"Strategy '{winner_name}' on {symbols} passed OOS gate. "
                        f"OOS: net_bps={oos_stats.get('net_bps'):.2f}, "
                        f"sharpe={oos_stats.get('sharpe'):.3f}, "
                        f"n_trades={oos_stats.get('n_trades')}. "
                        f"Hypothesis: {hyp.hypothesis}"
                    ),
                )
                return ResearchOutcome(
                    research_question=self.research_question,
                    edge_found=True,
                    attempts=attempt,
                    winning_strategy=winner_name,
                    winning_symbols=symbols,
                    oos_stats=oos_stats,
                    summary=(
                        f"Edge found on attempt {attempt}: {winner_name} "
                        f"on {symbols} | OOS net {oos_stats.get('net_bps'):.2f}bps, "
                        f"Sharpe {oos_stats.get('sharpe'):.3f}"
                    ),
                )

            # Step 4 — Reflect on failure
            self._log("Gate failed. Reflecting...")

            # Summarise all gate failures
            all_failures = []
            all_train = {}
            all_oos = {}
            for name, r in results.items():
                if r.get("error"):
                    continue
                reasons = r.get("gate_reasons", ["unknown"])
                all_failures.append(f"{name}: {'; '.join(reasons)}")
                all_train[name] = r.get("train", {})
                all_oos[name] = r.get("oos", {})

            try:
                ref = reflection_module(
                    research_question=self.research_question,
                    hypothesis=hyp.hypothesis,
                    strategy_names=", ".join(strategies),
                    symbols=", ".join(symbols),
                    train_stats_json=json.dumps(all_train, indent=2)[:1500],
                    oos_stats_json=json.dumps(all_oos, indent=2)[:1500],
                    gate_failure_reasons="\n".join(all_failures),
                    previous_reflections=all_reflections or "None.",
                )
                failure_mode = ref.failure_mode
                next_direction = ref.next_hypothesis_direction
                reflection_text = ref.reflection
            except Exception as e:
                self._log(f"Reflection failed: {e}")
                failure_mode = "unknown"
                next_direction = "Try a different strategy combination"
                reflection_text = f"Reflection error: {e}. Gate reasons: {all_failures}"

            self._log(f"Failure mode: {failure_mode}")
            self._log(f"Next direction: {next_direction[:100]}")

            # Persist
            save_reflection(
                self.research_question, attempt, reflection_text, "failed"
            )
            append_attempt(
                self.research_question,
                attempt=attempt,
                hypothesis=hyp.hypothesis,
                strategies=strategies,
                symbols=symbols,
                train_end=TRAIN_END,
                asset_class=self.asset_class,
                train_stats=all_train,
                oos_stats=all_oos,
                gate_passed=False,
                gate_reasons=all_failures,
                failure_mode=failure_mode,
                next_direction=next_direction,
                reflection=reflection_text,
            )

        # All attempts exhausted
        self._log(f"\nAll {self.max_attempts} attempts exhausted — no edge found.")
        close_journal(
            self.research_question,
            outcome="no_edge_found",
            final_finding=(
                f"No durable OOS edge found after {self.max_attempts} attempts. "
                f"See research journal for failure modes and lessons."
            ),
        )
        return ResearchOutcome(
            research_question=self.research_question,
            edge_found=False,
            attempts=self.max_attempts,
            summary=f"No edge found after {self.max_attempts} attempts. Journal saved.",
        )
