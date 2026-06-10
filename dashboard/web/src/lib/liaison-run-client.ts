/** Browser-side confirm + POST for allowlisted liaison commands. */

export function liaisonCmdNeedsConfirm(cmd: string): boolean {
  const trimmed = cmd.trim();
  return /^liaison\s+(validate|approve-artifact|close-task|start-pattern)\b/.test(trimmed);
}

export function confirmLiaisonRun(opts: {
  cmd: string;
  project?: string | null;
  task?: string | null;
}): boolean {
  if (typeof window === "undefined") return true;
  if (!liaisonCmdNeedsConfirm(opts.cmd)) return true;
  const lines = [
    "Run this liaison command?",
    "",
    opts.cmd,
    "",
    "Scope:",
    opts.project ? `  project: ${opts.project}` : "  project: (none)",
    opts.task ? `  task: ${opts.task}` : "  task: (none)",
  ];
  return window.confirm(lines.join("\n"));
}

export async function postLiaisonRun(body: {
  cmd: string;
  project?: string | null;
  task?: string | null;
}): Promise<{ ok?: boolean; output?: string; cmd?: string }> {
  const res = await fetch("/api/liaison/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await res.json()) as { ok?: boolean; output?: string; cmd?: string };
}

export async function runLiaisonFromBrowser(opts: {
  cmd: string;
  project?: string | null;
  task?: string | null;
}): Promise<{ ok?: boolean; output?: string; cmd?: string } | null> {
  if (!confirmLiaisonRun(opts)) return null;
  return postLiaisonRun(opts);
}

export function confirmReporterStepAdvance(opts: {
  project?: string | null;
  task?: string | null;
  currentStep?: string | null;
}): boolean {
  if (typeof window === "undefined") return true;
  const lines = [
    "Advance reporter checklist step?",
    "",
    "This writes reporter_step_state.json on disk (no --force).",
    "",
    "Scope:",
    opts.project ? `  project: ${opts.project}` : "  project: (none)",
    opts.task ? `  task: ${opts.task}` : "  task: (active task)",
    opts.currentStep ? `  current step: ${opts.currentStep}` : "",
  ].filter(Boolean);
  return window.confirm(lines.join("\n"));
}

export async function postReporterStepAdvance(body: {
  project: string;
  task?: string | null;
}): Promise<{ ok?: boolean; output?: string; cmd?: string }> {
  const res = await fetch("/api/liaison/reporter-step/advance", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await res.json()) as { ok?: boolean; output?: string; cmd?: string };
}

export async function advanceReporterStepFromBrowser(opts: {
  project: string;
  task?: string | null;
  currentStep?: string | null;
}): Promise<{ ok?: boolean; output?: string; cmd?: string } | null> {
  if (!confirmReporterStepAdvance(opts)) return null;
  return postReporterStepAdvance({ project: opts.project, task: opts.task });
}
