/** URL query helpers for command center operator session (project / task / pattern / agent). */

export function projectFromQuery(queryString: string): string | null {
  const v = new URLSearchParams(queryString).get("project")?.trim();
  return v || null;
}

export function taskFromQuery(queryString: string): string | null {
  const v = new URLSearchParams(queryString).get("task")?.trim();
  return v || null;
}

export function patternFromQuery(queryString: string): string | null {
  const v = new URLSearchParams(queryString).get("pattern")?.trim();
  return v || null;
}

export function agentFromQuery(queryString: string): string | null {
  const v = new URLSearchParams(queryString).get("agent")?.trim();
  return v || null;
}

export type QuerySessionUpdates = {
  project?: string | null;
  task?: string | null;
  pattern?: string | null;
  agent?: string | null;
};

export function mergeQueryParams(queryString: string, updates: QuerySessionUpdates): string {
  const params = new URLSearchParams(queryString);
  if ("project" in updates) {
    if (updates.project) params.set("project", updates.project);
    else params.delete("project");
  }
  if ("task" in updates) {
    if (updates.task) params.set("task", updates.task);
    else params.delete("task");
  }
  if ("pattern" in updates) {
    if (updates.pattern) params.set("pattern", updates.pattern);
    else params.delete("pattern");
  }
  if ("agent" in updates) {
    if (updates.agent) params.set("agent", updates.agent);
    else params.delete("agent");
  }
  return params.toString();
}

/** Hub deep link preserving project / task / pattern / agent. */
export function buildHubHref(
  base: {
    project?: string | null;
    task?: string | null;
    pattern?: string | null;
    agent?: string | null;
  },
  queryString = ""
): string {
  const q = mergeQueryParams(queryString, {
    project: base.project ?? null,
    task: base.task ?? null,
    pattern: base.pattern ?? null,
    agent: base.agent ?? null,
  });
  return q ? `/hub?${q}` : "/hub";
}
