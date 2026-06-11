"""Standalone Liaison CLI stub.

This file is intentionally small. If the real project already has a root CLI,
move `register_portfolio_subparser(...)` from `liaison.portfolio` into that CLI
instead of replacing existing command wiring.
"""

from __future__ import annotations

from .portfolio import main


if __name__ == "__main__":
    raise SystemExit(main())
