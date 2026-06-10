"use client";

import { useState } from "react";

import { useSearchParams } from "next/navigation";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { agentFromQuery } from "@/lib/url-query-helpers";
import { executorLaunchReady } from "@/lib/command-center-helpers";
import { AgentHubList } from "./AgentHubList";
import { HandoffChainCards } from "./HandoffChainCards";
import { PatternAgentGraph } from "./PatternAgentGraph";
import { Panel } from "./Panel";
import { PanelSkeleton } from "./PanelSkeleton";
import { PatternPicker } from "./PatternPicker";

export function HubColumn() {
  const {
    state,
    isInitialLoading,
    isRefreshing,
    selectedTaskId,
    selectedProject,
    selectedPatternId,
  } = useCommandCenter();
  const hubAgent = agentFromQuery(useSearchParams().toString());
  const [deckExpanded, setDeckExpanded] = useState(false);

  if (isInitialLoading) {
    return <Panel title="Hub"><PanelSkeleton lines={5} /></Panel>;
  }
  if (!state) return null;

  const patterns = state.project_agent_patterns ?? [];
  const refreshCls = isRefreshing ? "opacity-75 transition-opacity" : "";

  return (
    <div className={`space-y-4 ${refreshCls}`}>
      <Panel eyebrow="Hub" title="Local agent hub" purpose="Launch lines and handoff chains (L3).">
        <AgentHubList
          agents={state.agent_rows}
          compact={!deckExpanded}
          projectPath={state.focus?.path}
          defaultProfile={state.focus?.default_profile}
          selectedTaskId={selectedTaskId}
          activeTaskId={state.active_task_id}
          readyToBuild={state.summary.ready_to_build ?? true}
          executorLaunchReady={executorLaunchReady(state)}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setDeckExpanded((e) => !e)}
            className="text-xs px-2 py-1 rounded-md border border-liaison-outline-variant hover:bg-liaison-surface-container text-liaison-primary"
          >
            {deckExpanded ? "Collapse operator deck" : "Expand operator deck"}
          </button>
        </div>
        {deckExpanded && patterns.length > 0 ? (
          <div className="mt-4 pt-4 border-t border-liaison-outline-variant">
            <p className="panel-eyebrow mb-2">Patterns</p>
            <PatternPicker patterns={patterns} projectPath={state.focus?.path} />
            <div className="mt-3">
              <PatternAgentGraph
                patterns={patterns}
                selectedPatternId={selectedPatternId}
                projectKey={selectedProject}
                taskId={selectedTaskId}
              />
            </div>
          </div>
        ) : null}
      </Panel>
      <Panel eyebrow="Patterns" title="Handoff chains">
        <HandoffChainCards
          chains={state.handoff_chains}
          highlightAgent={hubAgent}
          projectPath={state.focus?.path}
          taskId={selectedTaskId}
          defaultProfile={state.focus?.default_profile}
        />
      </Panel>
    </div>
  );
}
