"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { KanbanBoard } from "./KanbanBoard";
import { Panel } from "./Panel";
import { PanelSkeleton } from "./PanelSkeleton";
import { ProjectMatrixTable } from "./ProjectMatrixTable";

export function ProjectsColumn() {
  const { state, selectedProject, setSelectedProject, isInitialLoading, isRefreshing } =
    useCommandCenter();

  if (isInitialLoading) {
    return (
      <Panel title="Projects">
        <PanelSkeleton />
      </Panel>
    );
  }
  if (!state) return null;

  const focus = state.focus;
  const refreshCls = isRefreshing ? "opacity-75 transition-opacity" : "";

  return (
    <Panel
      eyebrow="Projects"
      title="18-project registry"
      purpose="Select a project to scope kanban and handoffs. Hermes executes; Liaison governs."
      className={refreshCls}
    >
      <ProjectMatrixTable
        rows={state.project_matrix}
        selected={selectedProject}
        onSelect={setSelectedProject}
        portfolioDetail={state.projects_portfolio_detail}
        compact
      />
      {focus ? (
        <div className="mt-4 p-3 rounded-lg border border-liaison-teal/30 bg-liaison-surface text-sm">
          <p className="font-headline font-semibold">{focus.project}</p>
          <p className="mono text-xs mt-1">
            {focus.lifecycle}/{focus.phase} · validate {focus.validation}
          </p>
          <p className="text-xs mt-2">
            Agents: {focus.recommended_agents.join(", ") || "—"}
          </p>
        </div>
      ) : (
        <p className="text-xs text-liaison-on-surface-variant mt-3">
          Select a project to focus the board.
        </p>
      )}
      <div className="mt-4">
        <p className="panel-eyebrow mb-2">Kanban mini</p>
        <KanbanBoard kanban={state.kanban} />
      </div>
    </Panel>
  );
}
