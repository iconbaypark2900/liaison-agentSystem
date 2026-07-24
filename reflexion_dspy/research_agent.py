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
OPTIONS_HARNESS = SIGMA_API / "scripts" / "options_income_harness.py"

# ── Fixed OOS split — NEVER change during a research run ─────────────────────
TRAIN_END = "2022-12-31"   # train window: everything on/before this date
OOS_START = "2023-01-01"   # OOS window: everything after (agent never sees this)

MAX_ATTEMPTS = 6

AVAILABLE_STRATEGIES = (
    "momentum, mean_reversion, breakout, regime, macd, fourier, "
    "gbm, ou, heston, ict"
)

# ── Options config parameter space ────────────────────────────────────────────
OPTIONS_PARAM_SPACE = """
PARAMETERS (combine 1-2 at most — NOT 3+):
otm_pct (float 0.02-0.10): how far OTM the short put (default 0.05)
width_pct (float 0.002-0.03): spread width as % of spot (default 0.02)
vix_min (float): skip entry when VIX < this (try 12, 13, 15; 0 = no filter)
stop_mult (float): close when spread costs stop_mult × credit (default 2.0; try 3.0, 4.0, or 1e9 for no stop)
profit_target (float): close at this fraction of credit received (default 0.50; try 0.35, 0.65)
exit_mode (str): "live" (stop+PT exits, default) or "expiry" (hold all to expiration)
condor (bool): add a call credit spread above spot (iron condor)
sleeve_frac (float): fraction of equity at risk per trade (ALWAYS 0.02 with weekly)

TRADE COUNT ARITHMETIC — READ BEFORE PROPOSING ANY CONFIG:
- entry_freq="weekly" + NO filters → ~186 OOS trades (2023-2026) → gate CAN pass
- entry_freq="weekly" + vix_min=15 ONLY → ~131 OOS trades → PASSES (verified)
- entry_freq="weekly" + vix_min=15 + min_credit_frac=0.15 → ~23 OOS trades → FAILS n<100
- entry_freq="weekly" + vix_min=12 + min_credit_frac=0.18 → ~10 OOS trades → FAILS n<100
- entry_freq="weekly" + vix_min=15 + vix_pctile_min=any → even fewer trades → FAILS

OOS REGIME (2023-2026): VIX spent most of 2023-2024 between 12-18. This is historically LOW.
Any VIX filter removes a large fraction of entries. min_credit_frac stacks on top of that.

RULE: Use AT MOST ONE entry filter (vix_min OR min_credit_frac, never both).
ALWAYS include: entry_freq="weekly", sleeve_frac=0.02
NEVER combine: vix_min + min_credit_frac (kills trade count)
NEVER combine: vix_min + vix_pctile_min (double filter = almost no trades)

GOOD SINGLE-FILTER CONFIGS TO TRY:
- {"entry_freq": "weekly", "sleeve_frac": 0.02, "vix_min": 15.0} — already VERIFIED to PASS gate
- {"entry_freq": "weekly", "sleeve_frac": 0.02, "stop_mult": 4.0} — softer stop
- {"entry_freq": "weekly", "sleeve_frac": 0.02, "exit_mode": "expiry"} — hold to expiry
- {"entry_freq": "weekly", "sleeve_frac": 0.02, "vix_min": 13.0, "stop_mult": 4.0} — mild VIX + soft stop
- {"entry_freq": "weekly", "sleeve_frac": 0.02, "condor": true, "exit_mode": "expiry"} — iron condor

DO NOT re-propose any config already tried in past_reflections.
"""


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


class OptionsEdgeHypothesisSignature(dspy.Signature):
    """Generate a testable options strategy configuration hypothesis.

    You are testing configurations of the DEPLOYED SPY put credit spread
    brain (sell 5% OTM puts, defined-risk spread, monthly/weekly cadence).
    You are NOT looking for a new strategy — you are finding the BEST CONFIG
    for the existing strategy by adjusting entry filters, sizing, and exit rules.

    CRITICAL CONSTRAINT:
    - Monthly entry on SPY from 2023 onward yields ~42 trades in the OOS window.
    - The gate requires n_trades >= 100. Monthly entry CANNOT pass the n-trades gate.
    - You MUST use entry_freq="weekly" to generate enough OOS trades (≥5x more).
    - With weekly entry at sleeve_frac=0.02 (10%/5 rungs), you get ~180+ OOS trades.

    RULES:
    - Always include entry_freq: "weekly" and sleeve_frac: 0.02 unless testing monthly on its own
    - Combine 2-3 parameters — single tweaks rarely show edge
    - Costs are already baked in; the gate is net-of-cost
    - Do NOT repeat anything in past_reflections
    """

    research_question: str = dspy.InputField()
    param_space: str = dspy.InputField(desc="Available configuration parameters")
    train_window: str = dspy.InputField(desc="Period visible during hypothesis generation")
    past_reflections: str = dspy.InputField(desc="What was tried and failed — do NOT repeat")

    hypothesis: str = dspy.OutputField(
        desc="WHY this configuration should improve OOS edge — name the structural reason"
    )
    config_json: str = dspy.OutputField(
        desc="Valid JSON dict only. MUST include entry_freq='weekly' and sleeve_frac=0.02. Use AT MOST ONE entry filter. NEVER combine vix_min with min_credit_frac or vix_pctile_min."
    )
    variant_name: str = dspy.OutputField(
        desc="Short snake_case label for this config (e.g. 'weekly_vix15_nocr')"
    )
    rationale: str = dspy.OutputField(
        desc="Which failure modes from past_reflections this config specifically avoids"
    )


class OptionsEdgeReflectionSignature(dspy.Signature):
    """Diagnose why an options config hypothesis failed OOS gate."""

    research_question: str = dspy.InputField()
    hypothesis: str = dspy.InputField()
    config_json: str = dspy.InputField()
    train_stats_json: str = dspy.InputField()
    oos_stats_json: str = dspy.InputField()
    gate_failure_reasons: str = dspy.InputField()
    previous_reflections: str = dspy.InputField()

    failure_mode: str = dspy.OutputField(
        desc="One of: n_trades_too_low | costs_too_high | premium_not_persistent | "
             "regime_specific | entry_filter_too_strict | weekly_needed"
    )
    regime_insight: str = dspy.OutputField(
        desc="Which regime (2022 crash, 2023 rate-hikes, 2024 vol crush) drove the failure"
    )
    next_hypothesis_direction: str = dspy.OutputField(
        desc="Specific different config to try — not a restatement of what failed"
    )
    reflection: str = dspy.OutputField(
        desc="2-3 sentences: what config was tried, why gate failed, what the failure reveals"
    )


# ── Backtest runners ──────────────────────────────────────────────────────────

def _subprocess_env() -> dict[str, str]:
    """Environment for sigma harness subprocesses. Loads .env if .env.local absent."""
    import os
    env = {**os.environ, "PYTHONPATH": f"{SIGMA_API}:{SIGMA_API.parent.parent}"}
    env_local = SIGMA_API / ".env.local"
    env_file = SIGMA_API / ".env"
    if not env_local.exists() and env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                if k.strip() and v.strip() and k.strip() not in env:
                    env[k.strip()] = v.strip()
    return env


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
        env=_subprocess_env(),
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


def _run_options_harness(
    config: dict[str, Any],
    variant_name: str,
    underlying: str = "SPY",
) -> dict[str, Any]:
    """Run options_income_harness.py and return parsed JSON result."""
    cmd = [
        str(SIGMA_VENV), str(OPTIONS_HARNESS),
        "--train-end", TRAIN_END,
        "--config", json.dumps(config),
        "--variant-name", variant_name,
        "--underlying", underlying,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(SIGMA_API),
        env=_subprocess_env(),
        timeout=600,  # options harness is slower (BS pricing loop)
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Options harness failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Options harness output is not JSON: {e}\n{result.stdout[:500]}")


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
        backtest_type: str = "equity",  # "equity" | "options_income"
        options_underlying: str = "SPY",
    ) -> None:
        self.research_question = research_question
        self.asset_class = asset_class
        self.universe = universe
        self.max_attempts = max_attempts
        self.backtest_type = backtest_type
        self.options_underlying = options_underlying
        self._lm_configured = False

    def _ensure_lm(self) -> None:
        if not self._lm_configured:
            configure_dspy(use_for="implementation", temperature=0.4, max_tokens=4096)
            self._lm_configured = True

    def _log(self, msg: str) -> None:
        print(f"[ResearchAgent] {msg}", flush=True)

    def run(self) -> ResearchOutcome:
        if self.backtest_type == "options_income":
            return self._run_options_loop()
        return self._run_equity_loop()

    # ── Options income Reflexion loop ─────────────────────────────────────────

    def _run_options_loop(self) -> ResearchOutcome:
        self._ensure_lm()
        hypothesis_module = dspy.ChainOfThought(OptionsEdgeHypothesisSignature)
        reflection_module = dspy.ChainOfThought(OptionsEdgeReflectionSignature)

        train_window = f"All data from 2005 through {TRAIN_END}"
        self._log(f"Research question: {self.research_question}")
        self._log(f"Backtest type: options_income | Underlying: {self.options_underlying}")
        self._log(f"Train window: {train_window} | OOS starts: {OOS_START}")

        for attempt in range(1, self.max_attempts + 1):
            self._log(f"\n── Attempt {attempt}/{self.max_attempts} (options) ──")

            past_reflections = get_past_attempts_summary(self.research_question)
            memory_reflections = load_reflections(self.research_question)
            all_reflections = (
                past_reflections
                + ("\n\nMemory reflections:\n" + "\n".join(memory_reflections)
                   if memory_reflections else "")
            )

            # Step 1 — Generate hypothesis
            self._log("Generating options config hypothesis...")
            try:
                hyp = hypothesis_module(
                    research_question=self.research_question,
                    param_space=OPTIONS_PARAM_SPACE,
                    train_window=train_window,
                    past_reflections=all_reflections or "None yet — first attempt.",
                )
            except Exception as e:
                self._log(f"Hypothesis generation failed: {e}")
                continue

            # Parse config JSON from model output
            config_str = hyp.config_json.strip()
            if config_str.startswith("```"):
                config_str = config_str.split("```")[1].strip().lstrip("json").strip()
            try:
                config = json.loads(config_str)
            except json.JSONDecodeError:
                self._log(f"Bad config JSON: {config_str[:200]}")
                config = {"entry_freq": "weekly", "sleeve_frac": 0.02}

            variant_name = hyp.variant_name.strip().replace(" ", "_")[:40] or f"attempt_{attempt}"

            self._log(f"Hypothesis: {hyp.hypothesis[:120]}...")
            self._log(f"Config: {config} | Variant: {variant_name}")

            # Step 2 — Run options harness
            self._log("Running options income harness...")
            try:
                result = _run_options_harness(config, variant_name, self.options_underlying)
            except Exception as e:
                self._log(f"Options harness error: {e}")
                save_reflection(self.research_question, attempt,
                                f"Harness failed: {e}", "error")
                continue

            if "error" in result:
                self._log(f"Harness returned error: {result['error']}")
                continue

            oos_stats = result.get("oos", {})
            gate_passed = result.get("gate_passed", False)
            gate_reasons = result.get("gate_reasons", [])

            self._log(
                f"OOS: n={oos_stats.get('n_trades')} "
                f"net={oos_stats.get('net_bps'):.1f}bps "
                f"sharpe={oos_stats.get('sharpe'):.3f} "
                f"gate={'PASS' if gate_passed else 'FAIL'}"
            )

            if gate_passed:
                self._log(
                    f"EDGE FOUND — {variant_name} | "
                    f"OOS net_bps={oos_stats.get('net_bps'):.2f} | "
                    f"sharpe={oos_stats.get('sharpe'):.3f}"
                )
                append_attempt(
                    self.research_question,
                    attempt=attempt,
                    hypothesis=hyp.hypothesis,
                    strategies=[variant_name],
                    symbols=[self.options_underlying],
                    train_end=TRAIN_END,
                    asset_class="options_income",
                    train_stats={"options": result.get("train", {})},
                    oos_stats={"options": oos_stats},
                    gate_passed=True,
                    gate_reasons=[],
                    reflection="Gate passed — options edge found.",
                )
                close_journal(
                    self.research_question,
                    outcome="edge_found",
                    final_finding=(
                        f"Options config '{variant_name}' on {self.options_underlying} passed gate. "
                        f"Config: {config}. "
                        f"OOS: net_bps={oos_stats.get('net_bps'):.2f}, "
                        f"sharpe={oos_stats.get('sharpe'):.3f}, "
                        f"n_trades={oos_stats.get('n_trades')}."
                    ),
                )
                return ResearchOutcome(
                    research_question=self.research_question,
                    edge_found=True,
                    attempts=attempt,
                    winning_strategy=variant_name,
                    winning_symbols=[self.options_underlying],
                    oos_stats=oos_stats,
                    summary=(
                        f"Options edge found attempt {attempt}: {variant_name} | "
                        f"OOS net {oos_stats.get('net_bps'):.2f}bps, "
                        f"Sharpe {oos_stats.get('sharpe'):.3f}, "
                        f"n={oos_stats.get('n_trades')}"
                    ),
                )

            # Step 3 — Reflect on failure
            self._log("Gate failed. Reflecting...")
            try:
                ref = reflection_module(
                    research_question=self.research_question,
                    hypothesis=hyp.hypothesis,
                    config_json=json.dumps(config),
                    train_stats_json=json.dumps(result.get("train", {}), indent=2)[:1000],
                    oos_stats_json=json.dumps(oos_stats, indent=2)[:1000],
                    gate_failure_reasons="\n".join(gate_reasons),
                    previous_reflections=all_reflections or "None.",
                )
                failure_mode = ref.failure_mode
                next_direction = ref.next_hypothesis_direction
                reflection_text = ref.reflection
            except Exception as e:
                self._log(f"Reflection failed: {e}")
                failure_mode = "unknown"
                next_direction = "Try weekly entry with different filters"
                reflection_text = f"Reflection error: {e}. Gate reasons: {gate_reasons}"

            self._log(f"Failure mode: {failure_mode}")
            self._log(f"Next direction: {next_direction[:100]}")

            save_reflection(self.research_question, attempt, reflection_text, "failed")
            append_attempt(
                self.research_question,
                attempt=attempt,
                hypothesis=hyp.hypothesis,
                strategies=[variant_name],
                symbols=[self.options_underlying],
                train_end=TRAIN_END,
                asset_class="options_income",
                train_stats={"options": result.get("train", {})},
                oos_stats={"options": oos_stats},
                gate_passed=False,
                gate_reasons=gate_reasons,
                failure_mode=failure_mode,
                next_direction=next_direction,
                reflection=reflection_text,
            )

        self._log(f"\nAll {self.max_attempts} attempts exhausted — no options edge found.")
        close_journal(
            self.research_question,
            outcome="no_edge_found",
            final_finding=f"No durable OOS options edge after {self.max_attempts} attempts.",
        )
        return ResearchOutcome(
            research_question=self.research_question,
            edge_found=False,
            attempts=self.max_attempts,
            summary=f"No options edge found after {self.max_attempts} attempts. Journal saved.",
        )

    # ── Equity strategy Reflexion loop ────────────────────────────────────────

    def _run_equity_loop(self) -> ResearchOutcome:
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

            save_reflection(self.research_question, attempt, reflection_text, "failed")
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
