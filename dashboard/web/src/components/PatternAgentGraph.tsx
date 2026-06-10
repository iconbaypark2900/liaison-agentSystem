"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import type { ProjectAgentPattern } from "@/lib/command-center-types";
import { buildHubHref } from "@/lib/url-query-helpers";

export function PatternAgentGraph({
  patterns,
  selectedPatternId,
  projectKey,
  taskId,
}: {
  patterns: ProjectAgentPattern[];
  selectedPatternId?: string | null;
  projectKey?: string | null;
  taskId?: string | null;
}) {
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();

  if (!patterns.length) {
    return (
      <p className="text-xs text-liaison-on-surface-variant">
        No project agent patterns — focus a Tier A project with a plan pattern.
      </p>
    );
  }

  const pattern =
    patterns.find((p) => p.id === selectedPatternId) ?? patterns[0];

  return (
    <div className="space-y-2">
      <p className="text-[10px] uppercase tracking-wide text-liaison-on-surface-variant">
        Pattern graph · {pattern.label}
      </p>
      <div
        className="flex flex-wrap items-center gap-1.5 p-3 rounded-lg border border-liaison-outline-variant/60 bg-liaison-surface-container/40"
        role="list"
        aria-label={`Agent chain for ${pattern.id}`}
      >
        {pattern.agents.map((agent, index) => (
          <span key={`${pattern.id}-${agent}-${index}`} className="inline-flex items-center gap-1.5">
            {index > 0 ? (
              <span className="text-liaison-on-surface-variant text-sm" aria-hidden>
                →
              </span>
            ) : null}
            <Link
              href={buildHubHref(
                {
                  project: projectKey ?? null,
                  task: taskId ?? null,
                  pattern: pattern.id,
                  agent,
                },
                queryString
              )}
              className="text-xs px-2 py-1 rounded-md border border-liaison-primary/40 bg-liaison-canvas hover:bg-liaison-surface-container mono"
            >
              {agent}
            </Link>
          </span>
        ))}
      </div>
      {patterns.length > 1 ? (
        <p className="text-[10px] text-liaison-on-surface-variant">
          Showing <span className="mono">{pattern.id}</span>
          {selectedPatternId && selectedPatternId !== pattern.id
            ? ` (selected ${selectedPatternId} unavailable)`
            : null}
          {" · "}
          {patterns.length} patterns for this project
        </p>
      ) : null}
    </div>
  );
}
