#!/usr/bin/env python3
"""Headless Textual mount test for the command center.

Reproduces the BadIdentifier crash path (list-item ids with ':') without a TTY.
Requires Textual (run with the project venv: .venv/bin/python).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.command_center.app import CommandCenterApp, safe_id  # noqa: E402
from dashboard.command_center.data import collect_command_center_state  # noqa: E402


def test_safe_id():
    assert safe_id("hermes:airtable") == "hermes_airtable"
    assert safe_id("handoff:t:a") == "handoff_t_a"
    used: set[str] = set()
    a = safe_id("x:y", used)
    b = safe_id("x:y", used)
    assert a != b  # collisions disambiguated
    assert safe_id("1bad")[0].isalpha() or safe_id("1bad")[0] == "_"


async def _mount_and_cycle() -> None:
    state = collect_command_center_state(refresh=False)
    app = CommandCenterApp(state, refresh_on_start=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Every rolodex category builds ListItems with sanitized ids.
        for category in ("skills", "subagents", "projects", "commands", "tools"):
            app._set_category(category)
            await pilot.pause()
        # Re-render all panels (hub, workstream, ops, focus bar).
        app._render_all_panels()
        await pilot.pause()
        assert app.query_one("#overview-project") is not None
        # Exercise the focus path: focus bar + recommended markers.
        app.state["focus"] = {
            "project": "demo",
            "lifecycle": "classified",
            "phase": "alpha",
            "validation": "required",
            "recommended_agents": ["hermes"],
            "exit_criteria": ["Repo-native validation profile passes"],
        }
        app._render_focusbar()
        if app.state["agent_rows"]:
            app.state["agent_rows"][0]["recommended"] = True
        app._render_hub()
        await pilot.pause()


def test_mount_headless():
    asyncio.run(_mount_and_cycle())


if __name__ == "__main__":
    test_safe_id()
    test_mount_headless()
    print("ok")
