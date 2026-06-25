"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { Panel } from "./Panel";
import { StatusPill } from "./StatusPill";

type ModelRoute = {
  name: string;
  provider: string;
  model: string;
  capabilities: string[];
};

type ExecutorRoute = {
  name: string;
  type: string;
  enabled: boolean;
  command: string;
  allow_execution: boolean;
};

type PhaseRoute = {
  name: string;
  preferred_agent: string;
  fallback_agent: string;
  validation: string;
};

type RoutingPanelData = {
  model_routes: ModelRoute[];
  executor_routes: ExecutorRoute[];
  phases: PhaseRoute[];
};

export function RoutingPanel() {
  const { state } = useCommandCenter();
  const data = (state?.panels?.routing as RoutingPanelData | undefined) ?? null;
  if (!data) {
    return (
      <Panel eyebrow="Phase 11" title="Routing">
        <p className="text-sm text-liaison-on-surface-variant">No routing data available.</p>
      </Panel>
    );
  }

  return (
    <Panel
      eyebrow="Phase 11"
      title="Routing"
      purpose="Model routes, executors, and phase routing"
    >
      <div className="space-y-4 text-xs">
        <section>
          <p className="panel-eyebrow mb-2">Model Routes ({data.model_routes.length})</p>
          {data.model_routes.length === 0 ? (
            <p className="text-liaison-on-surface-variant">No model routes configured.</p>
          ) : (
            <ul className="space-y-1">
              {data.model_routes.map((r) => (
                <li
                  key={r.name}
                  className="flex items-center gap-2 rounded border border-liaison-outline-variant px-2 py-1"
                >
                  <span className="font-mono truncate flex-1">{r.name}</span>
                  <span className="text-liaison-on-surface-variant">{r.provider}</span>
                  <span className="text-liaison-on-surface-variant">{r.model}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <p className="panel-eyebrow mb-2">Executor Routes ({data.executor_routes.length})</p>
          <ul className="space-y-1">
            {data.executor_routes.map((e) => (
              <li
                key={e.name}
                className="flex items-center gap-2 rounded border border-liaison-outline-variant px-2 py-1"
              >
                <StatusPill status={e.enabled ? "pass" : "warn"}>
                  {e.enabled ? "on" : "off"}
                </StatusPill>
                <StatusPill status={e.allow_execution ? "pass" : "unknown"}>
                  {e.allow_execution ? "exec" : "no-exec"}
                </StatusPill>
                <span className="font-mono">{e.name}</span>
                <span className="text-liaison-on-surface-variant ml-auto">{e.command}</span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <p className="panel-eyebrow mb-2">Phase Routing ({data.phases.length})</p>
          {data.phases.length === 0 ? (
            <p className="text-liaison-on-surface-variant">No phase routing defined.</p>
          ) : (
            <ul className="space-y-1">
              {data.phases.map((p) => (
                <li
                  key={p.name}
                  className="flex items-center gap-2 rounded border border-liaison-outline-variant px-2 py-1"
                >
                  <span className="font-mono">{p.name}</span>
                  <span className="truncate flex-1">
                    {p.preferred_agent}
                    {p.fallback_agent ? ` → ${p.fallback_agent}` : ""}
                  </span>
                  <StatusPill
                    status={p.validation === "required" ? "fail" : p.validation === "optional" ? "warn" : "ready"}
                  >
                    {p.validation}
                  </StatusPill>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Panel>
  );
}
