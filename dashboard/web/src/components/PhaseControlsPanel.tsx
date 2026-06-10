"use client";

import { useCallback, useState } from "react";

import { useCommandCenter } from "@/context/CommandCenterContext";
import {
  firstRunnableWorkflowCommand,
  reporterAutoAdvanceOptIn,
  reporterStepAdvanceEnabled,
  suggestedWorkflowCommandEnabled,
  suggestedWorkflowCommandRunnable,
  workflowIntakeGateOpen,
} from "@/lib/command-center-helpers";
import {
  advanceReporterStepFromBrowser,
  runLiaisonFromBrowser,
} from "@/lib/liaison-run-client";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

const PROJECT_CMDS = [
  { label: "Assess", cmd: "liaison assess-project --show" },
  { label: "Phase show", cmd: "liaison project-phase show" },
  { label: "Phase advance", cmd: "liaison project-phase advance" },
] as const;

function taskPhaseCmd(phase: string | null | undefined): string {
  const p = (phase ?? "plan").toLowerCase();
  if (p === "review") return "liaison approve";
  if (p === "complete" || p === "close") return "liaison close-task";
  return "liaison start build";
}

export function PhaseControlsPanel({ compact = false }: { compact?: boolean }) {
  const { state, selectedProject, selectedTaskId, refresh } = useCommandCenter();
  const [runBusy, setRunBusy] = useState<string | null>(null);
  const [runOutput, setRunOutput] = useState<string | null>(null);

  const runWorkflowCmd = useCallback(
    async (cmd: string, key: string) => {
      if (!selectedProject) return;
      setRunBusy(key);
      setRunOutput(null);
      try {
        const data = await runLiaisonFromBrowser({
          cmd,
          project: selectedProject,
          task: selectedTaskId,
        });
        if (data == null) return;
        setRunOutput(data.output ?? (data.ok ? "OK" : "Failed"));
        if (data.ok) refresh(true);
      } catch (err) {
        setRunOutput(err instanceof Error ? err.message : String(err));
      } finally {
        setRunBusy(null);
      }
    },
    [refresh, selectedProject, selectedTaskId]
  );

  const runReporterAdvance = useCallback(async () => {
    if (!selectedProject) return;
    setRunBusy("advance");
    setRunOutput(null);
    try {
      const data = await advanceReporterStepFromBrowser({
        project: selectedProject,
        task: selectedTaskId,
        currentStep: state?.reporter_step_state?.current_step_id,
      });
      if (data == null) return;
      setRunOutput(data.output ?? (data.ok ? "Advanced" : "Advance blocked"));
      if (data.ok) refresh(true);
    } catch (err) {
      setRunOutput(err instanceof Error ? err.message : String(err));
    } finally {
      setRunBusy(null);
    }
  }, [refresh, selectedProject, selectedTaskId, state?.reporter_step_state?.current_step_id]);

  if (!state) return null;

  const focus = state.focus;
  const taskPhase = state.active_task_phase;
  const explainer =
    "Project phase = maturity (registry lifecycle). Task phase = slice lifecycle (plan → build → review → close). See docs/execution-bridge.md.";

  if (!selectedProject || !focus) {
    return (
      <Panel
        eyebrow="Phases"
        title="Project & task phase"
        purpose={explainer}
        className={compact ? "" : "mb-4"}
      >
        <p className="text-sm text-liaison-on-surface-variant">
          Focus a project to see maturity phase and active task phase with copy commands.
        </p>
      </Panel>
    );
  }

  const projectPhase = focus.project_phase ?? focus.phase;
  const lifecycle = focus.lifecycle;
  const workflowCommands = (
    state.suggested_workflow_commands?.length
      ? state.suggested_workflow_commands
      : state.next_workflow_step?.suggested_liaison_commands ?? []
  ).slice(0, 6);
  const intakeGateOpen = workflowIntakeGateOpen(state);
  const nextRunnable = firstRunnableWorkflowCommand(state);
  const showAdvance = reporterAutoAdvanceOptIn(state);
  const canAdvance = reporterStepAdvanceEnabled(state);

  return (
    <Panel
      eyebrow="Phases"
      title={`${selectedProject} · phases`}
      purpose={explainer}
      className={compact ? "" : "mb-4"}
    >
      <div className={`grid gap-3 ${compact ? "" : "md:grid-cols-2"}`}>
        <div className="rounded-lg border border-liaison-outline-variant/50 p-3 text-sm">
          <p className="text-[10px] uppercase text-liaison-on-surface-variant mb-1">
            Project phase (maturity)
          </p>
          <p className="font-medium mono">
            {lifecycle}/{projectPhase}
          </p>
          {focus.phase && focus.phase !== projectPhase ? (
            <p className="text-xs text-liaison-on-surface-variant mt-1">{focus.phase}</p>
          ) : null}
          <div className="flex flex-wrap gap-2 mt-2">
            {PROJECT_CMDS.map(({ label, cmd }) => (
              <CopyButton key={cmd} text={cmd} label={label} />
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-liaison-outline-variant/50 p-3 text-sm">
          <p className="text-[10px] uppercase text-liaison-on-surface-variant mb-1">
            Task phase (slice)
          </p>
          <p className="font-medium mono">{taskPhase ?? "—"}</p>
          <p className="text-xs text-liaison-on-surface-variant mt-1">
            Bound to {state.active_task_id ?? "first open kanban task"}.
          </p>
          <div className="flex flex-wrap gap-2 mt-2">
            <CopyButton text={taskPhaseCmd(taskPhase)} label="Next step" />
            <CopyButton text="liaison approve" label="Approve" />
            <CopyButton text="liaison close-task" label="Close task" />
          </div>
        </div>
      </div>
      {state.next_workflow_step ? (
        <div className="mt-3 rounded-lg border border-liaison-primary/30 bg-liaison-surface-container/30 px-3 py-2 text-sm">
          <p className="text-[10px] uppercase text-liaison-primary mb-1">Next workflow step</p>
          <p className="font-medium">{state.next_workflow_step.label}</p>
          {!intakeGateOpen ? (
            <p className="text-xs text-liaison-on-surface-variant mt-1">
              Workflow copy commands unlock after intake soft-ready or executor launch ready.
            </p>
          ) : null}
          {nextRunnable ? (
            <div className="flex flex-wrap gap-2 items-center mt-2 mb-1">
              <button
                type="button"
                disabled={runBusy !== null}
                onClick={() => void runWorkflowCmd(nextRunnable, "next")}
                className="text-xs px-2 py-1 rounded border border-liaison-primary text-liaison-primary hover:bg-liaison-surface-container disabled:opacity-50"
              >
                {runBusy === "next" ? "Running…" : "Run next workflow step"}
              </button>
              <span className="text-[10px] text-liaison-on-surface-variant mono truncate max-w-full">
                {nextRunnable}
              </span>
            </div>
          ) : null}
          {workflowCommands.map((cmd) => {
            const copyEnabled = suggestedWorkflowCommandEnabled(state, cmd);
            const runEnabled = suggestedWorkflowCommandRunnable(state, cmd);
            const gateHint = cmd.toLowerCase().includes("close-task")
              ? "Validate step must be complete before close-task"
              : !copyEnabled
                ? "Intake soft-ready or executor launch ready required"
                : "Command not on browser allowlist";
            return (
              <div key={cmd} className="flex gap-2 items-center mt-1">
                <code className="mono text-xs flex-1 truncate">{cmd}</code>
                <CopyButton
                  text={cmd}
                  label="Copy"
                  disabled={!copyEnabled}
                  title={copyEnabled ? undefined : gateHint}
                />
                <button
                  type="button"
                  disabled={!runEnabled || runBusy !== null}
                  title={runEnabled ? undefined : gateHint}
                  onClick={() => void runWorkflowCmd(cmd, cmd)}
                  className="text-[10px] px-1.5 py-0.5 rounded border border-liaison-outline-variant hover:bg-liaison-surface-container disabled:opacity-50 shrink-0"
                >
                  {runBusy === cmd ? "…" : "Run"}
                </button>
              </div>
            );
          })}
          {showAdvance ? (
            <div className="flex flex-wrap gap-2 items-center mt-3 pt-2 border-t border-liaison-outline-variant/40">
              <button
                type="button"
                disabled={!canAdvance || runBusy !== null}
                title={
                  canAdvance
                    ? undefined
                    : "Complete current reporter step (and approve outbox) before advance"
                }
                onClick={() => void runReporterAdvance()}
                className="text-xs px-2 py-1 rounded border border-liaison-teal text-liaison-teal hover:bg-liaison-surface-container disabled:opacity-50"
              >
                {runBusy === "advance" ? "Advancing…" : "Advance reporter step"}
              </button>
              <span className="text-[10px] text-liaison-on-surface-variant">
                Opt-in via project_plans.yaml · never uses --force
              </span>
            </div>
          ) : null}
          {runOutput ? (
            <pre className="mt-2 text-xs mono whitespace-pre-wrap max-h-32 overflow-auto rounded border border-liaison-outline-variant/40 p-2 bg-liaison-surface">
              {runOutput}
            </pre>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}
