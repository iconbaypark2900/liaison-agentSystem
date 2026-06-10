"""Canonical Liaison control plane and operator docs path resolution."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_liaison_root() -> Path:
    """Resolve live control plane root: LIAISON_ROOT env, canonical dir, then legacy."""
    env = os.environ.get("LIAISON_ROOT")
    if env:
        return Path(env).expanduser()
    canonical = Path.home() / "spark/liaison_agentSystem"
    if canonical.is_dir():
        return canonical
    return Path.home() / "spark/agent-system"


def resolve_liaison_docs_dir() -> Path:
    """Resolve operator docs slug: liaison/ (L7) with legacy fallback."""
    canonical = Path.home() / "spark/docs/local-agents/liaison"
    if canonical.is_dir():
        return canonical
    return Path.home() / "spark/docs/local-agents/agent-system"


AGENT_SYSTEM_DIR = resolve_liaison_root()
LIAISON_DOCS_DIR = resolve_liaison_docs_dir()
