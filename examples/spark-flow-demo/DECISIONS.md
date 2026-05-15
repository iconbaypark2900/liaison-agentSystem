# DECISIONS.md

## D001 — Use standard library only

For this demo, the CLI must use only the Python standard library so the workflow tests agent discipline instead of dependency installation.

## D002 — Use spark-flow phase routing

This project is designed to test phase routing:

- Nemotron for planning and review
- Qwen3-Coder for implementation
- GPT-OSS for patch fallback
- Qwen3.6 for stable closeout

## D003 — CLI uses standard library modules only

The `spark-demo-health` CLI uses only: `argparse`, `urllib.request`, `json`, `platform`, `pathlib` (with `os` fallback), and `shutil`. No third-party dependencies.
