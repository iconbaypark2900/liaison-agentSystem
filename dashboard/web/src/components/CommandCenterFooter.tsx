"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";

export function CommandCenterFooter() {
  const { state } = useCommandCenter();
  if (!state) return null;

  return (
    <footer className="mt-6 py-2 px-4 border-t border-liaison-outline-variant text-[10px] text-liaison-on-surface-variant flex flex-wrap gap-4">
      <span>Platform {state.platform}</span>
      <span>
        Agents active {state.agent_rows.filter((a) => a.tasks > 0).length}/
        {state.agent_rows.length}
      </span>
      <span>Tasks {state.summary.total_tasks}</span>
      <span>SQLite {state.sqlite_loaded ? "loaded" : "—"}</span>
      <span>Source liaison command-center --json</span>
      <span className="ml-auto">Refresh every {state.refresh_sec}s</span>
    </footer>
  );
}
