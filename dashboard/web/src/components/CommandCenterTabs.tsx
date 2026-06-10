"use client";

import { useState } from "react";

import { OpsWorkspace } from "./OpsWorkspace";
import { OverviewActions } from "./OverviewActions";
import { OverviewBrief } from "./OverviewBrief";
import { ReporterChecklist } from "./ReporterChecklist";
import { WorkstreamBrief } from "./WorkstreamBrief";
import { IntakePanel } from "./IntakePanel";
import { ProjectPlanPanel } from "./ProjectPlanPanel";
import { ProjectDetailPanel } from "./ProjectDetailPanel";
import { BuildCorpusPanel } from "./BuildCorpusPanel";
import { KanbanBoard } from "./KanbanBoard";
import { ControlColumn } from "./ControlColumn";
import { ProjectMatrixTable } from "./ProjectMatrixTable";
import { HubWorkflowPanel } from "./HubWorkflowPanel";
import { ExecutionBridgePanel } from "./ExecutionBridgePanel";
import { PhaseControlsPanel } from "./PhaseControlsPanel";
import { PlaybookProgressBar } from "./PlaybookProgressBar";
import { useCommandCenter } from "@/context/CommandCenterContext";
import { Panel } from "./Panel";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "workstream", label: "Workstream" },
  { id: "ops", label: "Ops" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function CommandCenterTabs() {
  const [tab, setTab] = useState<TabId>("overview");
  const { state, selectedProject, setSelectedProject } = useCommandCenter();

  if (!state) return null;

  return (
    <div className="mb-6">
      <div className="flex flex-wrap gap-1 border-b border-liaison-outline-variant/50 mb-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 -mb-px ${
              tab === t.id
                ? "border-liaison-primary text-liaison-primary bg-liaison-surface-container/50"
                : "border-transparent text-liaison-on-surface-variant hover:text-liaison-on-surface"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <PlaybookProgressBar />

      {tab === "overview" ? <OverviewTab /> : null}
      {tab === "workstream" ? (
        <WorkstreamTab
          selectedProject={selectedProject}
          onSelectProject={setSelectedProject}
        />
      ) : null}
      {tab === "ops" ? <OpsTab /> : null}
    </div>
  );
}

function OverviewTab() {
  return (
    <div className="grid lg:grid-cols-12 gap-4">
      <div className="lg:col-span-8 space-y-4 max-h-[min(70vh,720px)] overflow-y-auto pr-1">
        <PhaseControlsPanel />
        <OverviewBrief />
        <OverviewActions />
        <div className="grid md:grid-cols-2 gap-4">
          <IntakePanel />
          <ProjectPlanPanel />
        </div>
      </div>
      <div className="lg:col-span-4 space-y-4">
        <ExecutionBridgePanel compact />
        <ControlColumn />
        <ProjectDetailPanel compact />
      </div>
    </div>
  );
}

function WorkstreamTab({
  selectedProject,
  onSelectProject,
}: {
  selectedProject: string | null;
  onSelectProject: (key: string | null) => void;
}) {
  const { state } = useCommandCenter();
  if (!state) return null;

  return (
    <div className="grid lg:grid-cols-12 gap-4">
      <div className="lg:col-span-4 space-y-4 max-h-[min(75vh,780px)] overflow-y-auto">
        <Panel eyebrow="Focus" title="Project matrix" purpose="Select to scope kanban and detail.">
          <ProjectMatrixTable
            rows={state.project_matrix}
            selected={selectedProject}
            onSelect={onSelectProject}
            portfolioDetail={state.projects_portfolio_detail}
            compact
          />
        </Panel>
        <ReporterChecklist />
      </div>
      <div className="lg:col-span-8 space-y-4 max-h-[min(75vh,780px)] overflow-y-auto pr-1">
        <PhaseControlsPanel compact />
        <ProjectDetailPanel />
        <WorkstreamBrief />
        <BuildCorpusPanel />
        <HubWorkflowPanel />
        <Panel eyebrow="Kanban" title="Tasks" purpose={selectedProject ? `Scoped to ${selectedProject}` : "All projects"}>
          <KanbanBoard kanban={state.kanban} />
        </Panel>
      </div>
    </div>
  );
}

function OpsTab() {
  return <OpsWorkspace />;
}
