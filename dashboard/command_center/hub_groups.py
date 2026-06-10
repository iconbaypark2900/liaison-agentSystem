"""Hub agent grouping — mirrors dashboard/web hub-agent-groups.ts."""

from __future__ import annotations

HUB_AGENT_GROUPS = [
    {
        "id": "executors",
        "label": "Executors",
        "agent_names": ("hermes", "qca", "ml_intern", "unsloth_studio"),
    },
    {
        "id": "liaison_lanes",
        "label": "Liaison lanes",
        "agent_names": ("liaison", "data_flywheel"),
    },
    {
        "id": "exceptional_phase",
        "label": "Exceptional phase CLIs",
        "agent_names": ("codex", "opencode", "claude"),
    },
]

AGENT_DISPLAY_NAMES = {
    "data_flywheel": "Data flywheel (workflow)",
}

NAME_TO_GROUP = {
    name: group["id"]
    for group in HUB_AGENT_GROUPS
    for name in group["agent_names"]
}


def group_agent_rows(agent_rows: list[dict]) -> list[dict]:
    """Return [{id, label, agents: [...]}, ...] preserving group order."""
    by_id: dict[str, list[dict]] = {g["id"]: [] for g in HUB_AGENT_GROUPS}
    other: list[dict] = []
    for row in agent_rows:
        gid = NAME_TO_GROUP.get(row.get("name", ""))
        if gid:
            by_id[gid].append(row)
        else:
            other.append(row)
    out = []
    for group in HUB_AGENT_GROUPS:
        agents = by_id[group["id"]]
        if agents:
            out.append({"id": group["id"], "label": group["label"], "agents": agents})
    if other:
        out.append({"id": "other", "label": "Other", "agents": other})
    return out
