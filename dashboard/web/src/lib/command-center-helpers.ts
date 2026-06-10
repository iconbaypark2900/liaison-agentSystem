import type { CommandCenterState, ProjectMatrixRow } from "./command-center-types";

export function sortProjectMatrix(rows: ProjectMatrixRow[]): ProjectMatrixRow[] {
  return [...rows].sort((a, b) => b.score - a.score);
}

export type ProjectMatrixSortKey = "score" | "label";

export function filterProjectMatrix(
  rows: ProjectMatrixRow[],
  query: string
): ProjectMatrixRow[] {
  const q = query.trim().toLowerCase();
  if (!q) return rows;
  return rows.filter(
    (row) =>
      row.option.toLowerCase().includes(q) ||
      (row.impact ?? "").toLowerCase().includes(q) ||
      `${row.lifecycle}/${row.phase}`.toLowerCase().includes(q)
  );
}

export function sortProjectMatrixBy(
  rows: ProjectMatrixRow[],
  key: ProjectMatrixSortKey
): ProjectMatrixRow[] {
  if (key === "label") {
    return [...rows].sort((a, b) => a.option.localeCompare(b.option));
  }
  return sortProjectMatrix(rows);
}

export function formatGatePhase(state: CommandCenterState): string {
  if (state.focus) {
    return `${state.focus.lifecycle}/${state.focus.phase}`;
  }
  const top = sortProjectMatrix(state.project_matrix)[0];
  return top ? `${top.lifecycle}/${top.phase}` : "—";
}

export function formatValidationStatus(state: CommandCenterState): "pass" | "warn" | "fail" | "unknown" {
  if (state.summary.blockers > 0 || state.engineering_metrics.gate_failures > 0) {
    return "fail";
  }
  if (state.focus?.validation === "required") {
    return "warn";
  }
  return "pass";
}

export function formatDebriefAge(state: CommandCenterState): string {
  const age = state.engineering_metrics.last_debrief_age;
  if (age) return age;
  if (state.debriefs.length > 0) return state.debriefs[0].age;
  return "—";
}

export function isDebriefStale(state: CommandCenterState): boolean {
  if (state.summary.debrief_stale != null) return state.summary.debrief_stale;
  if (state.engineering_metrics.debrief_stale != null) {
    return Boolean(state.engineering_metrics.debrief_stale);
  }
  if (state.ops_signoff?.debrief_stale != null) return state.ops_signoff.debrief_stale;
  return false;
}

/** Whether hub executors may launch (soft gate for profile / tier-A projects). */
export function executorLaunchReady(state: CommandCenterState): boolean {
  if (state.summary.executor_launch_ready != null) {
    return state.summary.executor_launch_ready;
  }
  return state.summary.ready_to_build ?? true;
}

/** Intake soft gate OR executor launch ready (Track E1.1). */
export function workflowIntakeGateOpen(state: CommandCenterState): boolean {
  if (state.summary.executor_launch_ready) return true;
  return Boolean(state.summary.ready_to_build_soft);
}

function validateStepComplete(state: CommandCenterState): boolean {
  const completed = state.reporter_step_state?.completed_steps ?? [];
  if (completed.includes("validate")) return true;
  const taskId = state.active_task_id;
  if (!taskId) return false;
  for (const bucket of Object.values(state.kanban)) {
    for (const task of bucket) {
      if (task.task_id === taskId) {
        return task.reporter_steps?.validate === true;
      }
    }
  }
  return false;
}

/** Allowlisted liaison subcommands runnable from workflow panel (Track E1.2). */
export function isBrowserWorkflowRunAllowlisted(cmd: string): boolean {
  return /^liaison\s+(validate|approve-artifact|close-task|start-pattern)\b/.test(cmd.trim());
}

/** Gate copy-only suggested workflow commands (not auto-exec). */
export function suggestedWorkflowCommandEnabled(
  state: CommandCenterState,
  cmd: string
): boolean {
  if (!workflowIntakeGateOpen(state)) return false;
  if (cmd.toLowerCase().includes("close-task")) {
    return validateStepComplete(state);
  }
  return true;
}

/** Gate browser Run buttons on suggested workflow rows (E1.2). */
export function suggestedWorkflowCommandRunnable(
  state: CommandCenterState,
  cmd: string
): boolean {
  return (
    suggestedWorkflowCommandEnabled(state, cmd) && isBrowserWorkflowRunAllowlisted(cmd)
  );
}

export function reporterAutoAdvanceOptIn(state: CommandCenterState): boolean {
  return state.project_plan?.reporter_auto_advance === true;
}

/** Explicit advance button — never bypass approve/outbox gates (E1.3). */
export function reporterStepAdvanceEnabled(state: CommandCenterState): boolean {
  if (!reporterAutoAdvanceOptIn(state)) return false;
  if (!workflowIntakeGateOpen(state)) return false;
  const stepState = state.reporter_step_state;
  if (!stepState?.current_step_id) return false;
  if (!stepState.allowed_next?.length) return false;
  if (stepState.current_step_id === "approve") {
    const pendingHandoffs = (state.handoffs ?? []).filter(
      (h) => h.status === "pending_approval"
    ).length;
    if (pendingHandoffs > 0) return false;
  }
  return true;
}

export function firstRunnableWorkflowCommand(state: CommandCenterState): string | null {
  const commands = (
    state.suggested_workflow_commands?.length
      ? state.suggested_workflow_commands
      : state.next_workflow_step?.suggested_liaison_commands ?? []
  ).slice(0, 6);
  return commands.find((cmd) => suggestedWorkflowCommandRunnable(state, cmd)) ?? null;
}

export function buildCommandCenterUrl(
  base: string,
  opts: {
    refresh?: boolean;
    project?: string | null;
    task?: string | null;
    pattern?: string | null;
  }
): string {
  const params = new URLSearchParams();
  if (opts.refresh) params.set("refresh", "1");
  if (opts.project) params.set("project", opts.project);
  if (opts.task) params.set("task", opts.task);
  if (opts.pattern) params.set("pattern", opts.pattern);
  const q = params.toString();
  return q ? `${base}?${q}` : base;
}
