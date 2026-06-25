"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { Panel } from "./Panel";

type Bundle = {
  name: string;
  kind: string;
  path: string;
};

type ContextBundlesData = {
  count: number;
  bundles: Bundle[];
};

export function ContextBundlesPanel() {
  const { state } = useCommandCenter();
  const data = (state?.panels?.context_bundles as ContextBundlesData | undefined) ?? null;
  if (!data) {
    return (
      <Panel eyebrow="Phase 11" title="Context Bundles">
        <p className="text-sm text-liaison-on-surface-variant">No bundle data available.</p>
      </Panel>
    );
  }

  return (
    <Panel
      eyebrow="Phase 11"
      title="Context Bundles"
      purpose="Available context bundle artifacts"
    >
      <p className="text-xs text-liaison-on-surface-variant mb-2">
        Total: {data.count}
      </p>
      {data.bundles.length === 0 ? (
        <p className="text-sm text-liaison-on-surface-variant">
          No context bundles found. Run <code>liaison bundle</code> to create one.
        </p>
      ) : (
        <ul className="space-y-1 text-xs">
          {data.bundles.map((b) => (
            <li
              key={b.name}
              className="flex items-center gap-2 rounded border border-liaison-outline-variant px-2 py-1"
            >
              <span className="font-mono truncate flex-1">{b.name}</span>
              <span className="text-liaison-on-surface-variant">{b.kind}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
