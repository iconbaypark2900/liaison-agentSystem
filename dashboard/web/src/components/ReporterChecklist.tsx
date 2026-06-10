"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import type { KanbanTask, ReporterStepStatus } from "@/lib/command-center-types";
import { executorLaunchReady } from "@/lib/command-center-helpers";
import {
  buildReporterChecklistSteps,
  countOpenKanbanTasks,
  reporterStepGlyph,
} from "@/lib/operator-templates";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

function findTask(
  openTasks: KanbanTask[],
  taskId: string | null,
  activeTaskId?: string | null
): KanbanTask | undefined {
  const id = taskId ?? activeTaskId;
  if (!id) return openTasks[0];
  return openTasks.find((t) => t.task_id === id) ?? openTasks[0];
}

export function ReporterChecklist() {
  const { state, selectedProject, selectedTaskId, setSelectedTaskId } = useCommandCenter();
  if (!state || !selectedProject) return null;
  const buildReady = executorLaunchReady(state);

  const openTasks = countOpenKanbanTasks(state.kanban);
  const pendingHandoffs = state.handoffs.filter((h) => h.status === "pending_approval").length;
  const focus = state.focus;
  const activeId = selectedTaskId ?? state.active_task_id ?? null;
  const primaryTask = findTask(openTasks, selectedTaskId, state.active_task_id);
  const disk = primaryTask?.reporter_steps;
  const stepState = state.reporter_step_state;
  const currentStepId = stepState?.current_step_id;
  const steps = buildReporterChecklistSteps({
    task: primaryTask,
    defaultProfile: focus?.default_profile,
    agentName: focus?.recommended_agents[0],
  });

  return (
    <Panel
      eyebrow={buildReady ? "Playbook" : "Playbook (after intake)"}
      title={`Reporter checklist · ${selectedProject}`}
      className={`mt-4 ${buildReady ? "" : "opacity-90"}`}
    >
      {pendingHandoffs > 0 ? (
        <p className="text-sm text-liaison-warning mb-3">
          {pendingHandoffs} pending handoff{pendingHandoffs === 1 ? "" : "s"} awaiting approval
        </p>
      ) : null}
      {openTasks.length === 0 ? (
        <p className="text-sm text-liaison-on-surface-variant">No open tasks for this project.</p>
      ) : (
        <ul className="space-y-2 mb-4">
          {openTasks.slice(0, 6).map((task) => {
            const active = task.task_id === activeId;
            return (
              <li key={task.task_id}>
                <button
                  type="button"
                  onClick={() => setSelectedTaskId(task.task_id)}
                  className={`w-full text-left text-sm rounded-lg px-2 py-1.5 border ${
                    active
                      ? "border-liaison-primary bg-liaison-surface-container"
                      : "border-transparent hover:bg-liaison-surface-container"
                  }`}
                >
                  <span className="mono text-xs font-medium">{task.task_id}</span>
                  <span className="text-liaison-on-surface-variant ml-2 text-xs">
                    {task.current_phase ?? "?"} · gate {task.gate_status ?? "—"}
                  </span>
                  {task.description ? (
                    <p className="text-xs text-liaison-on-surface-variant mt-1 truncate">
                      {task.description}
                    </p>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {primaryTask ? (
        <>
          <p className="panel-eyebrow mb-2">
            Workflow · <span className="mono">{primaryTask.task_id}</span>
          </p>
          {currentStepId ? (
            <p className="text-xs text-liaison-primary mb-2">
              Current step: <span className="mono font-medium">{currentStepId}</span>
              {stepState?.allowed_next?.length ? (
                <span className="text-liaison-on-surface-variant">
                  {" "}
                  · next: {stepState.allowed_next.join(", ")}
                </span>
              ) : null}
            </p>
          ) : null}
          <ol className="space-y-2">
            {steps.map((step) => {
              const key = step.id as keyof ReporterStepStatus;
              const done = disk?.[key];
              const pending = key === "approve" && disk && !disk.approve && disk.attach;
              const isCurrent = currentStepId === step.id;
              return (
                <li
                  key={step.id}
                  className={`text-sm flex flex-wrap items-start gap-2 rounded-lg px-1 py-0.5 ${
                    isCurrent ? "bg-liaison-primary/10 ring-1 ring-liaison-primary/30" : ""
                  }`}
                >
                  <span
                    className={`w-5 shrink-0 font-bold ${
                      done ? "text-liaison-teal" : pending ? "text-liaison-warning" : ""
                    }`}
                    aria-hidden
                  >
                    {disk ? reporterStepGlyph(Boolean(done), pending) : "○"}
                  </span>
                  <span className="font-medium w-14 shrink-0">{step.label}</span>
                  <span className="text-xs text-liaison-on-surface-variant flex-1">{step.hint}</span>
                  {step.cmd ? <CopyButton text={step.cmd} label="Copy" /> : null}
                </li>
              );
            })}
          </ol>
        </>
      ) : null}
    </Panel>
  );
}
