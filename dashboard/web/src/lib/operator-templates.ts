import type { AgentRow, HandoffChain, KanbanTask, ProjectAgentPattern } from "./command-center-types";

export function buildAttachTemplate(agentName: string): string {
  return `liaison attach ${agentName} --title "Report" --text "<paste agent output>"`;
}

export function buildInitTemplate(taskId: string, description: string): string {
  return `liaison init ${taskId} "${description}"`;
}

export function buildValidateHint(profile?: string): string {
  if (profile && profile !== "none") {
    return `liaison validate --profile ${profile}`;
  }
  return "liaison validate";
}

export function buildReporterBundle(opts: {
  projectPath?: string;
  agent: AgentRow;
  taskId: string;
  description?: string;
  defaultProfile?: string;
  includeSnapshot?: boolean;
}): string {
  const { projectPath, agent, taskId, description, defaultProfile, includeSnapshot = true } = opts;
  const cdHint = projectPath ? `cd ${projectPath}` : "# cd <project-repo>";
  const desc = description ?? "Describe the slice";
  const lines = [
    "# Reporter bundle — run in terminal (Hermes executes; Liaison governs)",
    `# task_id: ${taskId}`,
    cdHint,
    buildInitTemplate(taskId, desc),
  ];
  if (includeSnapshot) {
    lines.push("liaison snapshot --show");
  }
  lines.push(buildAttachTemplate(agent.name), buildValidateHint(defaultProfile));
  return lines.join("\n");
}

export function buildPatternPlayBlock(
  pattern: ProjectAgentPattern,
  taskId: string,
  projectPath?: string
): string {
  const cdHint = projectPath ? `cd ${projectPath}` : "# cd <project-repo>";
  const start = buildStartPatternCmd(pattern, taskId, pattern.label);
  const stepsYaml = pattern.steps.map((s, i) => `  - ${i + 1}. ${s}`).join("\n");
  return [
    "# Full play — pattern + bound task (run in terminal)",
    cdHint,
    start,
    "liaison snapshot --show",
    "steps:",
    stepsYaml,
    "",
    buildAttachTemplate(pattern.agents[0] ?? "hermes"),
    "liaison approve-artifact <report.md>",
    "liaison validate",
  ].join("\n");
}

export function reporterStepGlyph(done: boolean, pending?: boolean): string {
  if (done) return "✓";
  if (pending) return "!";
  return "○";
}

export function buildOpenInTerminalScript(agent: AgentRow): string {
  const launch = agent.launch && agent.launch !== "—" ? agent.launch : "";
  const nextSteps = [
    "# Liaison next steps (after agent produces output):",
    buildAttachTemplate(agent.name),
    "liaison approve-artifact <report.md>",
    "liaison validate",
  ].join("\n");
  if (!launch) return nextSteps;
  return `${launch}\n\n${nextSteps}`;
}

export function suggestPatternTaskId(pattern: ProjectAgentPattern): string {
  const stamp = new Date().toISOString().slice(11, 19).replace(/:/g, "");
  return `${pattern.id}-${stamp}`;
}

export function buildStartPatternCmd(
  pattern: ProjectAgentPattern,
  taskId?: string,
  description?: string
): string {
  const tid = taskId ?? suggestPatternTaskId(pattern);
  const desc = description ?? pattern.label;
  return `liaison start-pattern ${pattern.id} --task-id ${tid} --description "${desc}"`;
}

/** Adjacent pairs in a handoff chain (for copy-play buttons). */
export function handoffChainEdges(chain: HandoffChain): { from: string; to: string }[] {
  const agents = chain.agents.filter((a) => a && a !== "—");
  const edges: { from: string; to: string }[] = [];
  for (let i = 0; i < agents.length - 1; i += 1) {
    edges.push({ from: agents[i], to: agents[i + 1] });
  }
  return edges;
}

/** Chains where agent appears (for hub detail handoff section). */
export function handoffChainsForAgent(chains: HandoffChain[], agentName: string): HandoffChain[] {
  return chains.filter((c) => c.agents.includes(agentName));
}

export function buildHandoffPlayBlock(opts: {
  chain: HandoffChain;
  fromAgent: string;
  toAgent: string;
  projectPath?: string;
  taskId?: string;
  defaultProfile?: string;
}): string {
  const { chain, fromAgent, toAgent, projectPath, taskId, defaultProfile } = opts;
  const cdHint = projectPath ? `cd ${projectPath}` : "# cd <project-repo>";
  const tid = taskId ?? "<task-id>";
  return [
    `# Handoff play — ${chain.name}`,
    `# ${fromAgent} → ${toAgent} · task ${tid}`,
    cdHint,
    "",
    `# After ${fromAgent} finishes in pane A:`,
    buildAttachTemplate(fromAgent),
    `liaison approve-artifact <${fromAgent}-report.md>`,
    "",
    `# Hand off to ${toAgent} (pane A or attach):`,
    buildAttachTemplate(toAgent),
    buildValidateHint(defaultProfile),
    "",
    `# Chain: ${chain.agents.join(" → ")}`,
    chain.when ? `# When: ${chain.when}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

export interface ReporterChecklistStep {
  id: string;
  label: string;
  hint: string;
  cmd?: string;
}

export function buildReporterChecklistSteps(opts: {
  task?: KanbanTask;
  defaultProfile?: string;
  agentName?: string;
}): ReporterChecklistStep[] {
  const { task, defaultProfile, agentName } = opts;
  const tid = task?.task_id ?? "<task-id>";
  const agent = agentName ?? "hermes";
  return [
    {
      id: "init",
      label: "Init",
      hint: "Create governed task with BRIEF",
      cmd: task ? undefined : buildInitTemplate(tid, "Describe the slice"),
    },
    {
      id: "snapshot",
      label: "Snapshot",
      hint: "Capture repo state for the task",
      cmd: "liaison snapshot --show",
    },
    {
      id: "attach",
      label: "Attach",
      hint: "Paste specialist or executor report into outbox",
      cmd: buildAttachTemplate(agent),
    },
    {
      id: "approve",
      label: "Approve",
      hint: "Review outbox artifact before integration",
      cmd: "liaison approve-artifact <report.md>",
    },
    {
      id: "validate",
      label: "Validate",
      hint: "Run validation profile gates",
      cmd: buildValidateHint(defaultProfile),
    },
    {
      id: "close",
      label: "Close",
      hint: "Close task when gates pass",
      cmd: "liaison close-task",
    },
  ];
}

export function countOpenKanbanTasks(
  kanban: { todo: KanbanTask[]; in_progress: KanbanTask[]; review: KanbanTask[] }
): KanbanTask[] {
  return [...kanban.todo, ...kanban.in_progress, ...kanban.review];
}

export function buildObserveSessionComplete(opts: {
  agent: string;
  projectKey: string;
  taskId: string;
  exitCode?: number;
}): string {
  const code = opts.exitCode ?? 0;
  return (
    `liaison observe-session complete --agent ${opts.agent} --exit-code ${code} ` +
    `--project ${opts.projectKey} --task-id ${opts.taskId}`
  );
}
