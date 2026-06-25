"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { KpiCard } from "./KpiCard";
import { Panel } from "./Panel";
import { StatusPill } from "./StatusPill";

type ApprovalRow = {
  task_id: string;
  from_agent: string;
  to_agent: string;
  status: string;
  summary: string;
  phase: string;
  repo: string;
};

type ApprovalsPanelData = {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  rows: ApprovalRow[];
};

export function ApprovalsPanel() {
  const { state } = useCommandCenter();
  const data = (state?.panels?.approvals as ApprovalsPanelData | undefined) ?? null;
  if (!data) {
    return (
      <Panel eyebrow="Phase 11" title="Approvals">
        <p className="text-sm text-liaison-on-surface-variant">No approval data available.</p>
      </Panel>
    );
  }

  return (
    <Panel
      eyebrow="Phase 11"
      title="Approvals"
      purpose="Pending handoffs and execution requests awaiting human review"
    >
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <KpiCard label="Total" value={data.total} />
        <KpiCard label="Pending" value={data.pending} tone="warn" />
        <KpiCard label="Approved" value={data.approved} tone="good" />
        <KpiCard label="Rejected" value={data.rejected} tone="bad" />
      </div>
      <div>
        <p className="panel-eyebrow mb-2">Recent Approval Items</p>
        <ul className="space-y-1 text-xs">
          {data.rows.slice(0, 15).map((r, i) => {
            const status =
              r.status === "approved"
                ? "pass"
                : r.status === "rejected"
                  ? "fail"
                  : "warn";
            return (
              <li
                key={`${r.task_id}-${i}`}
                className="rounded border border-liaison-outline-variant px-2 py-1"
              >
                <div className="flex items-center gap-2">
                  <StatusPill status={status}>{r.status.replace("_", " ")}</StatusPill>
                  <span className="truncate flex-1">
                    {r.from_agent || "?"} → {r.to_agent || "?"}
                  </span>
                  <span className="text-liaison-on-surface-variant">{r.task_id}</span>
                </div>
                {r.summary ? (
                  <p className="text-liaison-on-surface-variant mt-1 truncate">{r.summary}</p>
                ) : null}
              </li>
            );
          })}
          {data.rows.length === 0 ? (
            <li className="text-liaison-on-surface-variant">No approval items.</li>
          ) : null}
        </ul>
      </div>
    </Panel>
  );
}
