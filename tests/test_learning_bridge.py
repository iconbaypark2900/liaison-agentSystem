#!/usr/bin/env python3
"""Learning bridge export tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_export_learning_bridge_dry_run(tmp_path):
    memory = tmp_path / "memory"
    memory.mkdir()
    learning = memory / "sigma-slice.learning.md"
    learning.write_text(
        "# Promoted learning\n\n- Tags: sigma,hermes\n\n## Learning source\n\nTest hint\n",
        encoding="utf-8",
    )
    repo = tmp_path / "sigma_repo"
    repo.mkdir()
    (repo / ".spark-flow" / "memory").mkdir(parents=True)

    import dashboard.command_center.learning_bridge as lb

    original = lb.AGENT_SYSTEM_DIR
    lb.AGENT_SYSTEM_DIR = tmp_path
    try:
        from dashboard.command_center.learning_bridge import export_learning_bridge

        result = export_learning_bridge("sigma", repo_path=repo, dry_run=True)
        assert result["ok"] is True
        assert result["appended"] == 1

        result2 = export_learning_bridge("sigma", repo_path=repo, dry_run=False)
        assert result2["ok"] is True
        dest = repo / ".spark-flow" / "memory" / "hermes_hints.md"
        assert dest.exists()
        assert "Test hint" in dest.read_text(encoding="utf-8")
    finally:
        lb.AGENT_SYSTEM_DIR = original


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_export_learning_bridge_dry_run(Path(tmp))
    print("ok")
