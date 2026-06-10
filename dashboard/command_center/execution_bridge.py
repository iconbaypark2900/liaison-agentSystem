"""Execution bridge — record executor session outcomes into task artifacts."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any

from dashboard.command_center.operator_session import write_operator_session
from dashboard.command_center.workstation import load_workstation_profile


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _append_md(path: Path, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(block if block.startswith("\n") else "\n" + block)
        if not block.endswith("\n"):
            f.write("\n")


def task_dir_for(repo_path: str | Path, task_id: str) -> Path:
    return Path(repo_path).expanduser() / ".spark-flow" / "tasks" / task_id


def append_task_event(task_path: Path, event: str, command: str | None = None, details: dict | None = None) -> None:
    events_file = task_path / "events.jsonl"
    row: dict[str, Any] = {
        "timestamp": _now(),
        "event": event,
        "task_id": task_path.name,
    }
    if command:
        row["command"] = command
    if details:
        row["details"] = details
    with events_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def infer_outcome(exit_code: int | None, outcome: str | None) -> str:
    if outcome in ("success", "failure"):
        return outcome
    if exit_code is None:
        return "unknown"
    return "success" if exit_code == 0 else "failure"


def truncate_excerpt(text: str, max_chars: int | None = None) -> str:
    profile = load_workstation_profile()
    limit = max_chars or int(profile.get("defaults", {}).get("log_excerpt_max_chars", 4000))
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def read_log_tail(log_file: str | Path | None, lines: int = 40) -> str:
    if not log_file:
        return ""
    path = Path(log_file).expanduser()
    if not path.exists() or not path.is_file():
        return ""
    try:
        content = path.read_text(errors="replace").splitlines()
        return "\n".join(content[-lines:])
    except OSError:
        return ""


def record_executor_outcome(
    repo_path: str | Path,
    task_id: str,
    *,
    agent: str,
    outcome: str | None = None,
    exit_code: int | None = None,
    excerpt: str = "",
    pattern_id: str = "",
    project_key: str = "",
    log_file: str | Path | None = None,
    log_lines: int = 40,
) -> dict[str, Any]:
    """Write observation, event, and on failure evaluation + learning."""
    repo_path = Path(repo_path).expanduser()
    task_path = task_dir_for(repo_path, task_id)
    if not task_path.is_dir():
        raise FileNotFoundError(f"Task directory not found: {task_path}")

    resolved_outcome = infer_outcome(exit_code, outcome)
    body = excerpt.strip() or read_log_tail(log_file, log_lines)
    body = truncate_excerpt(body)
    title = f"Executor session end — {agent}"
    source_label = "executor_session"

    _append_md(
        task_path / "OBSERVATIONS.md",
        f"\n## {title}\n\n"
        f"- Captured: {_now()}\n"
        f"- Source: `{agent}`\n"
        f"- Outcome: `{resolved_outcome}`\n"
        f"- Exit code: `{exit_code if exit_code is not None else 'n/a'}`\n"
        f"- Project: `{project_key or 'n/a'}`\n"
        f"- Pattern: `{pattern_id or 'n/a'}`\n\n"
        f"{body or '(no log excerpt)'}\n",
    )

    append_task_event(
        task_path,
        "executor_session_end",
        command="observe-session",
        details={
            "agent": agent,
            "outcome": resolved_outcome,
            "exit_code": exit_code,
            "project_key": project_key,
            "pattern_id": pattern_id,
            "excerpt_chars": len(body),
        },
    )

    wrote_eval = False
    wrote_learning = False
    if resolved_outcome == "failure":
        _append_md(
            task_path / "EVALUATIONS.md",
            f"\n## Evaluation: {_now()}\n\n"
            f"- Rubric: `executor_session`\n"
            f"- Score: 0/5\n"
            f"- Pass threshold: 3/5\n"
            f"- Status: fail\n\n"
            f"### Assessment\n\n"
            f"Executor `{agent}` session ended with exit code `{exit_code}`.\n\n"
            f"{body or 'No excerpt provided.'}\n",
        )
        append_task_event(
            task_path,
            "evaluate",
            command="observe-session",
            details={"rubric": "executor_session", "score": 0, "status": "fail"},
        )
        wrote_eval = True
        learning = (
            f"Executor `{agent}` failed on task `{task_id}`"
            f"{f' (project {project_key})' if project_key else ''}"
            f" with exit code {exit_code}. "
            f"Review log excerpt in OBSERVATIONS.md before retrying; "
            f"consider smaller scope or different specialist."
        )
        _append_md(task_path / "LEARNINGS.md", f"\n## Learning: {_now()}\n\n{learning}\n")
        append_task_event(
            task_path,
            "learn",
            command="observe-session",
            details={"text": learning[:200]},
        )
        wrote_learning = True

    return {
        "task_id": task_id,
        "task_path": str(task_path),
        "outcome": resolved_outcome,
        "wrote_evaluation": wrote_eval,
        "wrote_learning": wrote_learning,
    }


def latest_executor_outcome(task_path: Path) -> str | None:
    events_file = task_path / "events.jsonl"
    if not events_file.exists():
        return None
    last: str | None = None
    for line in events_file.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event") == "executor_session_end" or row.get("command") == "observe-session":
            details = row.get("details") or {}
            last = details.get("outcome") or row.get("outcome")
    return last


def bind_session_to_operator_session(
    repo_path: str | Path,
    project_key: str,
    task_id: str,
    pattern_id: str = "",
) -> dict[str, Any]:
    return write_operator_session(
        str(Path(repo_path).expanduser()),
        project_key=project_key,
        task_id=task_id,
        pattern_id=pattern_id,
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "report"


def attach_report_to_outbox(
    repo_path: str | Path,
    task_id: str,
    *,
    agent: str,
    file_path: str | Path | None = None,
    text: str | None = None,
    title: str = "",
) -> dict[str, Any]:
    """Write an agent report to task outbox (minimal attach bridge)."""
    if bool(file_path) == bool(text):
        raise ValueError("Provide exactly one of file_path or text")

    task_path = task_dir_for(repo_path, task_id)
    if not task_path.is_dir():
        raise FileNotFoundError(f"Task directory not found: {task_path}")

    report_title = title or f"{agent} report"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifact_name = f"{timestamp}-{_slugify(agent)}-{_slugify(report_title)}.md"
    artifact = task_path / "outbox" / artifact_name
    artifact.parent.mkdir(parents=True, exist_ok=True)

    if file_path:
        source = Path(file_path).expanduser()
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Attachment source not found: {source}")
        body = source.read_text(errors="replace")
        source_note = f"file: `{source}`"
        attachments_dir = task_path / "attachments"
        attachments_dir.mkdir(exist_ok=True)
        shutil.copyfile(source, attachments_dir / f"{timestamp}-{_slugify(source.name)}")
    else:
        body = text or ""
        source_note = "inline text"

    artifact.write_text(
        dedent(
            f"""\
            # {report_title}

            ## Metadata

            - Task: `{task_id}`
            - Agent/source: `{agent}`
            - Captured: {_now()}
            - Source: {source_note}

            ## Report

            {body}
            """
        ),
        encoding="utf-8",
    )
    handoffs = task_path / "HANDOFFS.md"
    _append_md(
        handoffs,
        f"\n## Attached: {artifact.name}\n\n"
        f"- Agent/source: `{agent}`\n"
        f"- Title: {report_title}\n"
        f"- Captured: {_now()}\n"
        f"- Outbox: `{artifact}`\n",
    )
    append_task_event(
        task_path,
        "attach",
        command="attach",
        details={"agent": agent, "artifact": str(artifact)},
    )
    return {"artifact": str(artifact), "agent": agent, "title": report_title}


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def task_has_executor_end_since(task_path: Path, since: datetime | None) -> bool:
    events_file = task_path / "events.jsonl"
    if not events_file.exists():
        return False
    for line in events_file.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event") != "executor_session_end":
            continue
        ts = _parse_iso(str(row.get("timestamp") or ""))
        if since is None or (ts and ts >= since):
            return True
    return False


def detect_stale_executor_sessions(
    sessions: list[dict],
    *,
    stale_hours: float | None = None,
) -> list[dict]:
    """Running venture-bound sessions missing observe-session complete."""
    profile = load_workstation_profile()
    hours = stale_hours
    if hours is None:
        hours = float(profile.get("defaults", {}).get("executor_session_stale_hours", 4))

    now = datetime.now()
    stale: list[dict] = []
    for sess in sessions:
        if sess.get("status") == "ended":
            continue
        task_id = (sess.get("task_id") or "").strip()
        if not task_id:
            continue

        repo = sess.get("repo_path") or ""
        project_key = sess.get("project_key") or ""
        if project_key and not repo:
            try:
                from dashboard.command_center.project_plans import resolve_project_key_and_path

                _, repo = resolve_project_key_and_path(project_key)
            except Exception:
                repo = ""

        if not repo:
            continue

        task_path = task_dir_for(repo, task_id)
        if not task_path.is_dir():
            continue

        started = _parse_iso(str(sess.get("started_at") or ""))
        if task_has_executor_end_since(task_path, started):
            continue

        reason = ""
        if started and (now - started).total_seconds() > hours * 3600:
            reason = f"running>{hours}h_without_complete"
        elif sess.get("alive") is False and sess.get("pid"):
            reason = "process_ended_without_observe_complete"
        else:
            continue

        stale.append({**sess, "stale_reason": reason})

    return stale
