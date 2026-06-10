"use client";

import { BuildCorpusPanel } from "@/components/BuildCorpusPanel";
import { CommandCenterFooter } from "@/components/CommandCenterFooter";
import { GateStrip } from "@/components/GateStrip";
import { KanbanBoard } from "@/components/KanbanBoard";
import { ProjectDetailPanel } from "@/components/ProjectDetailPanel";
import { ProjectMatrixTable } from "@/components/ProjectMatrixTable";
import { HubWorkflowPanel } from "@/components/HubWorkflowPanel";
import { Panel } from "@/components/Panel";
import { useCommandCenter } from "@/context/CommandCenterContext";
import { KpiCard } from "@/components/KpiCard";

export default function ProjectsPage() {
  const { state, selectedProject, setSelectedProject, isInitialLoading, isRefreshing } =
    useCommandCenter();

  if (isInitialLoading) {
    return (
      <>
        <GateStrip />
        <div className="h-64 rounded-lg bg-liaison-surface-container animate-pulse" />
      </>
    );
  }
  if (!state) return null;

  const refreshCls = isRefreshing ? "opacity-75 transition-opacity" : "";

  return (
    <>
      <GateStrip />
      <div className={`grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 ${refreshCls}`}>
        <KpiCard
          label="Registered"
          value={state.project_portfolio?.length ?? state.projects_registry?.length ?? state.project_matrix.length}
        />
        <KpiCard label="Open tasks" value={state.summary.open_tasks} />
        <KpiCard label="Filtered open" value={state.summary.filtered_open} />
        <KpiCard
          label="Blockers"
          value={state.summary.blockers}
          tone={state.summary.blockers ? "bad" : "good"}
        />
      </div>

      <div className={`grid lg:grid-cols-12 gap-4 ${refreshCls}`}>
        <div className="lg:col-span-4 max-h-[min(80vh,820px)] overflow-y-auto space-y-4">
          <Panel eyebrow="Matrix" title="All projects" purpose="Ranked registry — select for detail.">
            <ProjectMatrixTable
              rows={state.project_matrix}
              selected={selectedProject}
              onSelect={setSelectedProject}
              portfolioDetail={state.projects_portfolio_detail}
              compact
            />
          </Panel>
          <Panel eyebrow="Kanban" title="Tasks" purpose={selectedProject ? selectedProject : "All"}>
            <KanbanBoard kanban={state.kanban} />
          </Panel>
        </div>
        <div className="lg:col-span-8 max-h-[min(80vh,820px)] overflow-y-auto space-y-4 pr-1">
          <ProjectDetailPanel />
          <BuildCorpusPanel />
          <HubWorkflowPanel />
        </div>
      </div>
      <CommandCenterFooter />
    </>
  );
}
