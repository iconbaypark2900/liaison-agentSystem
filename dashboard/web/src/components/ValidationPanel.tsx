"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { KpiCard } from "./KpiCard";
import { Panel } from "./Panel";
import { StatusPill } from "./StatusPill";

type RunSummary = {
  run_id: string;
  task_id: string;
  project: string;
  status: string;
  validation_passed: boolean;
  security_passed: boolean;
};

type ValidationPanelData = {
  profiles_defined: string[];
  profile_count: number;
  profile_usage: Record<string, number>;
  profile_check_scripts: Record<string, string>;
  recent_runs: RunSummary[];
};

export function ValidationPanel() {
  const { state } = useCommandCenter();
  const data = (state?.panels?.validation as ValidationPanelData | undefined) ?? null;
  if (!data) {
    return (
      <Panel eyebrow="Phase 11" title="Validation">
        <p className="text-sm text-liaison-on-surface-variant">No validation data available.</p>
      </Panel>
    );
  }

  const recentPassed = data.recent_runs.filter((r) => r.validation_passed).length;

  return (
    <Panel
      eyebrow="Phase 11"
      title="Validation"
      purpose="Validation profile coverage and recent run results"
    >
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <KpiCard label="Profiles" value={data.profile_count} />
        <KpiCard label="In Use" value={Object.keys(data.profile_usage).length} />
        <KpiCard label="Recent Runs" value={data.recent_runs.length} />
        <KpiCard
          label="Passed"
          value={recentPassed}
          tone={recentPassed === data.recent_runs.length && data.recent_runs.length > 0 ? "good" : "default"}
        />
      </div>
      <div className="mb-4 text-xs">
        <p className="panel-eyebrow mb-2">Profile Usage</p>
        {Object.keys(data.profile_usage).length === 0 ? (
          <p className="text-liaison-on-surface-variant">No profiles in use yet.</p>
        ) : (
          <ul className="space-y-1">
            {Object.entries(data.profile_usage).map(([name, count]) => (
              <li
                key={name}
                className="flex justify-between items-center rounded border border-liaison-outline-variant px-2 py-1"
              >
                <span className="truncate mr-2">{name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-liaison-on-surface-variant">
                    {data.profile_check_scripts[name] ?? ""}
                  </span>
                  <span className="tabular-nums">{count}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <p className="panel-eyebrow mb-2">Recent Validation Runs</p>
        <ul className="space-y-1 text-xs">
          {data.recent_runs.slice(0, 10).map((r) => {
            const status = r.validation_passed ? "pass" : "fail";
            return (
              <li
                key={r.run_id}
                className="flex items-center gap-2 rounded border border-liaison-outline-variant px-2 py-1"
              >
                <StatusPill status={status}>{r.status}</StatusPill>
                <span className="truncate flex-1">{r.task_id}</span>
                <span className="text-liaison-on-surface-variant">{r.project}</span>
              </li>
            );
          })}
          {data.recent_runs.length === 0 ? (
            <li className="text-liaison-on-surface-variant">No runs yet.</li>
          ) : null}
        </ul>
      </div>
    </Panel>
  );
}
