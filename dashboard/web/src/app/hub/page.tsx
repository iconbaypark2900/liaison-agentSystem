"use client";

import { useSearchParams } from "next/navigation";

import { AgentHubList } from "@/components/AgentHubList";
import { CommandCenterFooter } from "@/components/CommandCenterFooter";
import { GateStrip } from "@/components/GateStrip";
import { HandoffChainCards } from "@/components/HandoffChainCards";
import { PatternAgentGraph } from "@/components/PatternAgentGraph";
import { HubWorkflowPanel } from "@/components/HubWorkflowPanel";
import { Panel } from "@/components/Panel";
import { PatternPicker } from "@/components/PatternPicker";
import { ProjectDetailPanel } from "@/components/ProjectDetailPanel";
import { useCommandCenter } from "@/context/CommandCenterContext";
import { executorLaunchReady } from "@/lib/command-center-helpers";
import { agentFromQuery } from "@/lib/url-query-helpers";

export default function HubPage() {
  const {
    state,
    isInitialLoading,
    isRefreshing,
    selectedTaskId,
    selectedProject,
    selectedPatternId,
  } = useCommandCenter();
  const searchParams = useSearchParams();
  const hubAgent = agentFromQuery(searchParams.toString());

  if (isInitialLoading || !state) {
    return (
      <>
        <GateStrip />
        <div className="h-48 rounded-lg bg-liaison-surface-container animate-pulse" />
      </>
    );
  }

  const patterns = state.project_agent_patterns ?? [];
  const refreshCls = isRefreshing ? "opacity-75 transition-opacity" : "";

  return (
    <>
      <GateStrip />
      <div className={`grid lg:grid-cols-12 gap-4 ${refreshCls}`}>
        <div className="lg:col-span-5 max-h-[min(78vh,760px)] overflow-y-auto">
          <Panel eyebrow="Agents" title="Hub operator deck">
            <AgentHubList
              agents={state.agent_rows}
              projectPath={state.focus?.path}
              defaultProfile={state.focus?.default_profile}
              selectedTaskId={selectedTaskId}
              activeTaskId={state.active_task_id}
              readyToBuild={state.summary.ready_to_build ?? true}
              executorLaunchReady={executorLaunchReady(state)}
            />
          </Panel>
        </div>
        <div className="lg:col-span-7 max-h-[min(78vh,760px)] overflow-y-auto space-y-4 pr-1">
          <ProjectDetailPanel compact />
          <HubWorkflowPanel />
          {patterns.length > 0 ? (
            <Panel eyebrow="Scaffold" title="Start pattern">
              <PatternPicker patterns={patterns} projectPath={state.focus?.path} />
              <div className="mt-4 pt-4 border-t border-liaison-outline-variant/40">
                <PatternAgentGraph
                  patterns={patterns}
                  selectedPatternId={selectedPatternId}
                  projectKey={selectedProject}
                  taskId={selectedTaskId}
                />
              </div>
            </Panel>
          ) : null}
          <Panel eyebrow="Chains" title="Handoff chains">
            <HandoffChainCards
              chains={state.handoff_chains}
              highlightAgent={hubAgent}
              projectPath={state.focus?.path}
              taskId={selectedTaskId}
              defaultProfile={state.focus?.default_profile}
            />
          </Panel>
        </div>
      </div>
      <CommandCenterFooter />
    </>
  );
}
