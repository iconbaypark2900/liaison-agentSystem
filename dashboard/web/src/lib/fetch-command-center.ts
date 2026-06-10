import type { CommandCenterState } from "./command-center-types";
import { buildCommandCenterUrl } from "./command-center-helpers";

export async function fetchCommandCenter(opts?: {
  refresh?: boolean;
  project?: string | null;
  task?: string | null;
  pattern?: string | null;
}): Promise<CommandCenterState> {
  const url = buildCommandCenterUrl("/api/command-center", {
    refresh: opts?.refresh,
    project: opts?.project ?? undefined,
    task: opts?.task ?? undefined,
    pattern: opts?.pattern ?? undefined,
  });
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error((err as { error?: string }).error ?? "Failed to load command center");
  }
  return res.json() as Promise<CommandCenterState>;
}
