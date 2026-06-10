"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import {
  formatDebriefAge,
  formatGatePhase,
  formatValidationStatus,
  isDebriefStale,
} from "@/lib/command-center-helpers";
import { StatusPill } from "./StatusPill";

export function GateStrip() {
  const { state, isInitialLoading, isRefreshing, refresh } = useCommandCenter();
  if (isInitialLoading || !state) {
    return (
      <div className="panel py-3 mb-4 text-sm text-liaison-on-surface-variant">
        Loading gates…
      </div>
    );
  }

  const validation = formatValidationStatus(state);
  const phase = formatGatePhase(state);
  const flywheelOpen = state.summary.flywheel_open ?? 0;
  const workloadId = state.summary.workload_id?.trim();
  const liveSessions = (state.terminal_sessions ?? []).filter(
    (s) => s.alive !== false && s.status !== "ended"
  );
  const usage = state.workstation_usage;
  const queuePending = state.venture_queue_summary?.pending_count ?? 0;
  const intakeReady = state.summary.intake_ready ?? false;
  const strictReady = state.summary.ready_to_build_strict ?? state.summary.ready_to_build ?? false;
  const softReady = state.summary.ready_to_build_soft ?? false;
  const intakeBlockers = state.project_intake?.blockers ?? [];
  const showIntake = Boolean(state.selected_project && state.project_intake);
  const debriefStale = isDebriefStale(state);
  const debriefAge = formatDebriefAge(state);

  return (
    <div className="panel py-3 mb-4 flex flex-wrap items-center gap-3 text-sm">
      <span className="panel-eyebrow mr-2">Gates</span>
      <StatusPill status="ready">
        Phase <span className="mono ml-1">{phase}</span>
      </StatusPill>
      <StatusPill status={validation}>
        Validate {validation}
      </StatusPill>
      <StatusPill status={state.summary.blockers > 0 ? "fail" : "pass"}>
        Blocked {state.summary.blockers}
      </StatusPill>
      {showIntake ? (
        <StatusPill status={intakeReady ? "pass" : "fail"}>
          Intake {intakeReady ? "ready" : "blocked"}
        </StatusPill>
      ) : null}
      {showIntake && intakeReady && strictReady ? (
        <StatusPill status="pass">
          Build strict-ready
        </StatusPill>
      ) : null}
      {showIntake && intakeReady && !strictReady && softReady ? (
        <StatusPill status="warn">
          Build soft-ready
        </StatusPill>
      ) : null}
      {showIntake && intakeReady && !strictReady && !softReady ? (
        <StatusPill status="warn">
          Build pending
        </StatusPill>
      ) : null}
      {intakeBlockers.slice(0, 2).map((b) => (
        <span
          key={b.id}
          className="text-xs text-liaison-warning truncate max-w-[12rem]"
          title={b.detail}
        >
          {b.label}
        </span>
      ))}
      {flywheelOpen > 0 ? (
        <StatusPill status="warn">
          Flywheel tasks {flywheelOpen}
        </StatusPill>
      ) : null}
      {workloadId ? (
        <StatusPill status="ready" title={workloadId}>
          Workload <span className="mono ml-1">{workloadId}</span>
        </StatusPill>
      ) : null}
      {usage ? (
        <StatusPill status={usage.ventures_free > 0 ? "pass" : "warn"}>
          Slots {usage.running_ventures}/{usage.max_active_ventures}
        </StatusPill>
      ) : null}
      {queuePending > 0 ? (
        <StatusPill status="ready">Queue {queuePending}</StatusPill>
      ) : null}
      {state.summary.executor_session_stale ? (
        <StatusPill status="warn">
          Session stale {state.summary.executor_session_stale_count ?? 1}
        </StatusPill>
      ) : null}
      {liveSessions.map((s) => (
        <StatusPill key={s.id} status="ready">
          {s.agent_name} running
        </StatusPill>
      ))}
      <button
        type="button"
        onClick={() => refresh(true)}
        disabled={isRefreshing}
        className="text-xs px-2 py-1 rounded-md border border-liaison-outline-variant hover:bg-liaison-surface-container text-liaison-primary disabled:opacity-50"
      >
        {isRefreshing ? "Syncing…" : "Sync liaison"}
      </button>
      <StatusPill status={debriefStale ? "fail" : "pass"}>
        Debrief {debriefAge}
        {debriefStale ? " · stale" : ""}
      </StatusPill>
      <span className="text-liaison-on-surface-variant ml-auto mono text-xs">
        {state.env} · {state.user} · {state.generated_at}
      </span>
    </div>
  );
}
