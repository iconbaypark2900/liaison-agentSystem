"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { Panel } from "./Panel";

type LogRow = {
  run_id: string;
  log: string;
  size: number;
  tail: string;
};

type LogsPanelData = {
  count: number;
  rows: LogRow[];
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function LogsPanel() {
  const { state } = useCommandCenter();
  const data = (state?.panels?.logs as LogsPanelData | undefined) ?? null;
  if (!data) {
    return (
      <Panel eyebrow="Phase 11" title="Logs">
        <p className="text-sm text-liaison-on-surface-variant">No log data available.</p>
      </Panel>
    );
  }

  return (
    <Panel
      eyebrow="Phase 11"
      title="Logs"
      purpose="Recent run logs and JSONL artifacts"
    >
      <p className="text-xs text-liaison-on-surface-variant mb-2">
        Log files: {data.count}
      </p>
      {data.rows.length === 0 ? (
        <p className="text-sm text-liaison-on-surface-variant">
          No run logs yet. Worker runs will populate this panel.
        </p>
      ) : (
        <ul className="space-y-2 text-xs">
          {data.rows.slice(0, 20).map((r, i) => (
            <li
              key={`${r.run_id}-${r.log}-${i}`}
              className="rounded border border-liaison-outline-variant px-2 py-1"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono">{r.log}</span>
                <span className="text-liaison-on-surface-variant">{r.run_id}</span>
                <span className="text-liaison-on-surface-variant ml-auto">
                  {formatSize(r.size)}
                </span>
              </div>
              {r.tail ? (
                <pre className="bg-liaison-surface-container rounded p-2 text-[10px] overflow-auto max-h-32">
                  {r.tail}
                </pre>
              ) : (
                <p className="text-liaison-on-surface-variant italic">empty</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
