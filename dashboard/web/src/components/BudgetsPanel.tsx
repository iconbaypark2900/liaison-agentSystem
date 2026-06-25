"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { KpiCard } from "./KpiCard";
import { Panel } from "./Panel";
import { StatusPill } from "./StatusPill";

type BudgetLimit = {
  name: string;
  source: string;
  per_run: number | string | null;
  per_day: number | string | null;
  currency: string;
};

type RecentRun = {
  run_id: string;
  task_id: string;
  shell_commands_executed: boolean;
  models_called: boolean;
  executors_called: boolean;
};

type BudgetsPanelData = {
  limits_count: number;
  limits: BudgetLimit[];
  recent_runs: RecentRun[];
};

export function BudgetsPanel() {
  const { state } = useCommandCenter();
  const data = (state?.panels?.budgets as BudgetsPanelData | undefined) ?? null;
  if (!data) {
    return (
      <Panel eyebrow="Phase 11" title="Budgets">
        <p className="text-sm text-liaison-on-surface-variant">No budget data available.</p>
      </Panel>
    );
  }

  const recentWithSpend = data.recent_runs.filter(
    (r) => r.shell_commands_executed || r.models_called || r.executors_called,
  ).length;

  return (
    <Panel
      eyebrow="Phase 11"
      title="Budgets"
      purpose="Configured limits and recent spend"
    >
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <KpiCard label="Limits" value={data.limits_count} />
        <KpiCard label="Recent Runs" value={data.recent_runs.length} />
        <KpiCard
          label="With Spend"
          value={recentWithSpend}
          tone={recentWithSpend > 0 ? "good" : "default"}
        />
      </div>
      <div className="mb-4 text-xs">
        <p className="panel-eyebrow mb-2">Configured Limits</p>
        {data.limits.length === 0 ? (
          <p className="text-liaison-on-surface-variant">No limits configured.</p>
        ) : (
          <ul className="space-y-1">
            {data.limits.map((l) => (
              <li
                key={`${l.source}-${l.name}`}
                className="flex items-center gap-2 rounded border border-liaison-outline-variant px-2 py-1"
              >
                <span className="font-mono truncate flex-1">{l.name}</span>
                <span className="text-liaison-on-surface-variant">
                  {l.per_run ?? "—"} / run
                </span>
                <span className="text-liaison-on-surface-variant">
                  {l.per_day ?? "—"} / day
                </span>
                <span className="text-liaison-on-surface-variant uppercase">
                  {l.currency}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <p className="panel-eyebrow mb-2">Recent Run Spend</p>
        <ul className="space-y-1 text-xs">
          {data.recent_runs.slice(0, 10).map((r) => {
            const tone = r.models_called
              ? "fail"
              : r.executors_called
                ? "warn"
                : "pass";
            return (
              <li
                key={r.run_id}
                className="flex items-center gap-2 rounded border border-liaison-outline-variant px-2 py-1"
              >
                <StatusPill status={tone}>
                  {r.models_called
                    ? "models"
                    : r.executors_called
                      ? "exec"
                      : r.shell_commands_executed
                        ? "shell"
                        : "none"}
                </StatusPill>
                <span className="truncate flex-1">{r.task_id || r.run_id}</span>
                <span className="text-liaison-on-surface-variant">{r.run_id}</span>
              </li>
            );
          })}
          {data.recent_runs.length === 0 ? (
            <li className="text-liaison-on-surface-variant">No recent runs.</li>
          ) : null}
        </ul>
      </div>
    </Panel>
  );
}
