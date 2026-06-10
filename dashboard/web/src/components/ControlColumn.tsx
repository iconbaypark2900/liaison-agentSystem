"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { CopyButton } from "./CopyButton";
import { KpiCard } from "./KpiCard";
import { Panel } from "./Panel";
import { PanelSkeleton } from "./PanelSkeleton";

export function ControlColumn() {
  const { state, refresh, isInitialLoading, isRefreshing } = useCommandCenter();

  if (isInitialLoading) {
    return (
      <Panel title="Control">
        <PanelSkeleton />
      </Panel>
    );
  }
  if (!state) return null;

  const quick = state.metrics_rows.slice(0, 12);
  const refreshCls = isRefreshing ? "opacity-75 transition-opacity" : "";

  return (
    <Panel
      eyebrow="Control"
      title="Operator cockpit"
      purpose="Read-only liaison commands — copy and run in terminal."
      className={refreshCls}
    >
      <div className="grid grid-cols-2 gap-2 mb-4">
        <KpiCard label="Open tasks" value={state.summary.open_tasks} />
        <KpiCard
          label="Blockers"
          value={state.summary.blockers}
          tone={state.summary.blockers > 0 ? "bad" : "good"}
        />
      </div>
      <button
        type="button"
        onClick={() => refresh(true)}
        disabled={isRefreshing}
        className="w-full mb-3 py-2 rounded-lg bg-liaison-primary text-liaison-canvas text-sm font-medium disabled:opacity-50"
      >
        {isRefreshing ? "Syncing liaison…" : "Sync liaison"}
      </button>
      <ul className="space-y-2 max-h-80 overflow-auto">
        {quick.map((row) => (
          <li key={row.id} className="text-xs border-b border-liaison-outline-variant/40 pb-2">
            <p className="font-medium">{row.label}</p>
            <p className="text-liaison-on-surface-variant truncate">{row.detail}</p>
            {row.liaison_cmd ? (
              <div className="mt-1 flex gap-2 items-center">
                <code className="mono flex-1 truncate">{row.liaison_cmd}</code>
                <CopyButton text={row.liaison_cmd} label="!" />
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
