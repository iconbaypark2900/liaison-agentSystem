"""Tests for the unified Liaison root CLI."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout, redirect_stderr

import pytest

from liaison.cli import CLI_VERSION, build_root_parser, main


def test_root_parser_version_flag(capsys) -> None:
    parser = build_root_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert CLI_VERSION in captured.out
    assert "liaison" in captured.out


def test_root_parser_has_all_subcommand_groups() -> None:
    parser = build_root_parser()
    help_text = parser.format_help()
    for subcommand in ("portfolio", "worker", "evidence", "gate", "executor"):
        assert subcommand in help_text, f"Missing subcommand: {subcommand}"


def test_root_parser_accepts_root_flag() -> None:
    parser = build_root_parser()
    args = parser.parse_args(["--root", "/tmp/proj", "executor", "list"])
    assert args.root == "/tmp/proj"
    assert args.command == "executor"


def test_root_parser_default_root_is_cwd() -> None:
    parser = build_root_parser()
    args = parser.parse_args(["executor", "list"])
    assert args.root == "."


def test_root_parser_requires_subcommand() -> None:
    parser = build_root_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])
    assert exc_info.value.code == 2


def test_main_returns_zero_for_help(capsys) -> None:
    parser = build_root_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0


def test_main_executes_executor_list(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    src_dir = tmp_path / "src" / "liaison"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").touch()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "executors.yaml").write_text(
        "version: 0.2.0\nexecutors:\n  shell:\n    enabled: true\n    type: shell\n    command: bash\n    allow_execution: false\n",
        encoding="utf-8",
    )
    rc = main(["executor", "list"])
    assert rc == 0
    output = capsys.readouterr().out
    assert "shell" in output
    assert "Configured executors" in output


def test_main_executor_list_json(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    src_dir = tmp_path / "src" / "liaison"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").touch()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "executors.yaml").write_text(
        "version: 0.2.0\nexecutors:\n  shell:\n    enabled: true\n    type: shell\n    command: bash\n    allow_execution: false\n",
        encoding="utf-8",
    )
    rc = main(["executor", "list", "--json"])
    assert rc == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert "executors" in payload
    assert payload["count"] >= 1


def test_main_unknown_command_exits_nonzero(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["nonexistent-command"])
    assert exc_info.value.code != 0


def test_main_handles_domain_errors(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    src_dir = tmp_path / "src" / "liaison"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").touch()
    (tmp_path / "config").mkdir()
    rc = main(["portfolio", "generate-tasks", "--project", "definitely_nonexistent_project_xyz"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "error:" in err
