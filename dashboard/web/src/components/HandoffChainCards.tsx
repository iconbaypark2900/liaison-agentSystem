"use client";

import type { HandoffChain } from "@/lib/command-center-types";
import {
  buildHandoffPlayBlock,
  handoffChainEdges,
  handoffChainsForAgent,
} from "@/lib/operator-templates";
import { CopyButton } from "./CopyButton";

export function HandoffChainCards({
  chains,
  highlightAgent,
  projectPath,
  taskId,
  defaultProfile,
}: {
  chains: HandoffChain[];
  highlightAgent?: string | null;
  projectPath?: string;
  taskId?: string | null;
  defaultProfile?: string;
}) {
  const visible = highlightAgent ? handoffChainsForAgent(chains, highlightAgent) : chains;

  if (!visible.length) {
    return (
      <p className="text-sm text-liaison-on-surface-variant">
        {highlightAgent
          ? `No registry handoff chains include ${highlightAgent}.`
          : "No handoff chains in registry."}
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {visible.map((c) => (
        <li
          key={c.name}
          className="rounded-lg border border-liaison-outline-variant p-3 bg-liaison-surface text-sm"
        >
          <p className="font-medium">{c.name}</p>
          <p className="mono text-xs text-liaison-teal mt-1">{c.agents.join(" → ")}</p>
          <p className="text-xs text-liaison-on-surface-variant mt-1">{c.when}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            {handoffChainEdges(c).map(({ from, to }) => (
              <CopyButton
                key={`${c.name}-${from}-${to}`}
                text={buildHandoffPlayBlock({
                  chain: c,
                  fromAgent: from,
                  toAgent: to,
                  projectPath,
                  taskId: taskId ?? undefined,
                  defaultProfile,
                })}
                label={`${from} → ${to}`}
              />
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}
