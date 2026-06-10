"""JSON export for Liaison command center state (web dashboard + CI)."""

from __future__ import annotations

import json
from typing import Any


def dump_command_center_json(state: dict[str, Any]) -> str:
    """Serialize command center state for APIs and smoke tests."""
    return json.dumps(state, indent=2, default=str, ensure_ascii=False)
