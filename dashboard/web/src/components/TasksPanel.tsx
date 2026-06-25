"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { KpiCard } from "./KpiCard";
import { Panel } from "./Panel";
import { StatusPill } from "./StatusPill";

type TaskRow = {
  task_id: string;
  title: string;
  priority: string;
  status: string;
  type: string;
  repo: string;
};

type TasksPanelData = {
  total: number;
  open: number;
  closed: number;
  buckets: { todo: number; in_progress: number; review: number; done: number };
  by_project: Record<string, number>;
  by_priority: Record<string, number>;
  by_type: Record<string, number>;
  recent: TaskRow[];
};

export function TasksPanel() {
  const { state } = useCommandCenter();
  const data = (state?.panels?.tasks as TasksPanelData | undefined) ?? null;
  if (!data) {
    return (
      <Panel eyebrow="Phase 11" title="Tasks">
        <p className="text-sm text-liaison-on-surface-variant">No task data available.</p>
      </Panel>
    );
  }

  return (
    <Panel
      eyebrow="Phase 11"
      title="Tasks"
      purpose="Cross-project task queue overview"
    >
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <KpiCard label="Total" value={data.total} />
        <KpiCard label="Open" value={data.open} tone="default" />
        <KpiCard label="In Progress" value={data.buckets.in_progress} tone="good" />
        <KpiCard label="Review" value={data.buckets.review} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4 text-xs">
        <div className="rounded-lg border border-liaison-outline-variant p-3">
          <p className="panel-eyebrow mb-2">By Project</p>
          <ul className="space-y-1">
            {Object.entries(data.by_project).map(([proj, count]) => (
              <li key={proj} className="flex justify-between">
                <span className="truncate mr-2">{proj}</span>
                <span className="tabular-nums">{count}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-liaison-outline-variant p-3">
          <p className="panel-eyebrow mb-2">By Priority</p>
          <ul className="space-y-1">
            {Object.entries(data.by_priority).map(([prio, count]) => (
              <li key={prio} className="flex justify-between">
                <span className="truncate mr-2">{prio}</span>
                <span className="tabular-nums">{count}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div>
        <p className="panel-eyebrow mb-2">Recent Tasks</p>
        <ul className="space-y-1 text-xs">
          {data.recent.slice(0, 10).map((t) => (
            <li
              key={t.task_id}
              className="flex items-center gap-2 rounded border border-liaison-outline-variant px-2 py-1"
            >
              <StatusPill status={t.priority === "critical" ? "fail" : t.priority === "high" ? "warn" : "ready"}>
                {t.priority}
              </StatusPill>
              <span className="truncate flex-1">{t.title || t.task_id}</span>
              <span className="text-liaison-on-surface-variant">{t.type}</span>
            </li>
          ))}
          {data.recent.length === 0 ? (
            <li className="text-liaison-on-surface-variant">No recent tasks.</li>
          ) : null}
        </ul>
      </div>
    </Panel>
  );
}
