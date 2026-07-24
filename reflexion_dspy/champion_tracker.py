"""
Champion tracker — records the reigning best config per sigma account.

A "challenger" (new research run result) must beat the champion by at least
IMPROVEMENT_THRESHOLD on Sharpe before an update is proposed. This prevents
noise from triggering constant config churn.

Champions are stored in memory/champions/<account>.json. Proposals (when a
challenger beats the champion) are written to memory/proposals/<account>.json
for human review before deployment.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

MEMORY_DIR   = Path(__file__).parent.parent / "memory"
CHAMPION_DIR = MEMORY_DIR / "champions"
PROPOSAL_DIR = MEMORY_DIR / "proposals"

# Challenger must improve OOS Sharpe by this fraction to trigger a proposal.
# 0.10 = 10% relative improvement required (e.g. 0.047 → 0.052 won't trigger,
# 0.047 → 0.055 will).
IMPROVEMENT_THRESHOLD = 0.10

# Minimum Sharpe the champion must have for comparison to be meaningful.
# Below this, any passing gate result is accepted as an improvement.
MIN_MEANINGFUL_SHARPE = 0.01


def _ensure_dirs() -> None:
    CHAMPION_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_champion(account: str) -> dict[str, Any] | None:
    """Return the current champion record for this account, or None if not set."""
    _ensure_dirs()
    path = CHAMPION_DIR / f"{account}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def save_champion(
    account: str,
    *,
    config: dict[str, Any],
    strategy: str,
    symbols: list[str],
    oos_stats: dict[str, Any],
    research_question: str,
    backtest_type: str = "equity",
    notes: str = "",
) -> None:
    """Overwrite the champion record for this account."""
    _ensure_dirs()
    record = {
        "account": account,
        "set_at": _now(),
        "research_question": research_question,
        "backtest_type": backtest_type,
        "config": config,
        "strategy": strategy,
        "symbols": symbols,
        "oos_stats": oos_stats,
        "notes": notes,
    }
    (CHAMPION_DIR / f"{account}.json").write_text(json.dumps(record, indent=2))


def is_improvement(
    account: str,
    challenger_stats: dict[str, Any],
) -> tuple[bool, str]:
    """Return (True, reason) if challenger beats current champion, else (False, reason)."""
    champion = load_champion(account)
    c_sharpe = float(challenger_stats.get("sharpe", 0))
    c_net    = float(challenger_stats.get("net_bps", 0))
    c_n      = int(challenger_stats.get("n_trades", 0))

    if c_sharpe <= 0 or c_net <= 0 or c_n < 100:
        return False, f"challenger does not pass gate (sharpe={c_sharpe:.4f}, net={c_net:.2f}, n={c_n})"

    if champion is None:
        return True, "no existing champion — first passing result wins automatically"

    ch_sharpe = float(champion["oos_stats"].get("sharpe", 0))

    if ch_sharpe < MIN_MEANINGFUL_SHARPE:
        return True, f"champion Sharpe {ch_sharpe:.4f} below meaningful threshold — challenger accepted"

    required = ch_sharpe * (1 + IMPROVEMENT_THRESHOLD)
    if c_sharpe >= required:
        return True, (
            f"challenger Sharpe {c_sharpe:.4f} beats champion {ch_sharpe:.4f} "
            f"by >{IMPROVEMENT_THRESHOLD*100:.0f}% (required ≥{required:.4f})"
        )
    return False, (
        f"challenger Sharpe {c_sharpe:.4f} does not beat champion {ch_sharpe:.4f} "
        f"by {IMPROVEMENT_THRESHOLD*100:.0f}% (required ≥{required:.4f})"
    )


def write_proposal(
    account: str,
    *,
    config: dict[str, Any],
    strategy: str,
    symbols: list[str],
    oos_stats: dict[str, Any],
    research_question: str,
    backtest_type: str,
    improvement_reason: str,
    champion_stats: dict[str, Any] | None,
) -> Path:
    """Write a config update proposal for human review."""
    _ensure_dirs()
    proposal = {
        "account": account,
        "proposed_at": _now(),
        "status": "pending_review",
        "research_question": research_question,
        "backtest_type": backtest_type,
        "proposed_config": config,
        "proposed_strategy": strategy,
        "proposed_symbols": symbols,
        "challenger_oos": oos_stats,
        "champion_oos": champion_stats,
        "improvement_reason": improvement_reason,
        "action_required": (
            f"Review and apply: update sigma config for {account} "
            f"with strategy={strategy}, config={config}"
        ),
    }
    path = PROPOSAL_DIR / f"{account}.json"
    path.write_text(json.dumps(proposal, indent=2))
    return path


def list_pending_proposals() -> list[dict[str, Any]]:
    """Return all proposals with status=pending_review."""
    _ensure_dirs()
    out = []
    for path in sorted(PROPOSAL_DIR.glob("*.json")):
        try:
            p = json.loads(path.read_text())
            if p.get("status") == "pending_review":
                out.append(p)
        except Exception:
            pass
    return out


def mark_proposal_applied(account: str) -> None:
    path = PROPOSAL_DIR / f"{account}.json"
    if path.exists():
        p = json.loads(path.read_text())
        p["status"] = "applied"
        p["applied_at"] = _now()
        path.write_text(json.dumps(p, indent=2))
