"use client";

import { Fragment, useMemo, useState } from "react";

import type { ProjectPortfolioDetail } from "@/lib/command-center-types";
import type { ProjectMatrixRow } from "@/lib/command-center-types";
import {
  filterProjectMatrix,
  sortProjectMatrixBy,
  type ProjectMatrixSortKey,
} from "@/lib/command-center-helpers";

function PortfolioDetailStrip({ detail }: { detail: ProjectPortfolioDetail }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-liaison-on-surface-variant py-2 px-1">
      <span className={detail.intake_ready ? "text-liaison-teal" : "text-liaison-error"}>
        Intake {detail.intake_ready ? "ready" : "blocked"}
        {detail.intake_blockers ? ` (${detail.intake_blockers})` : ""}
      </span>
      <span className={detail.ready_to_build ? "text-liaison-teal" : "text-liaison-warning"}>
        Build {detail.ready_to_build ? "ready" : "pending"}
      </span>
      <span>
        Plan {detail.has_plan ? (detail.plan_workflow ?? "yes") : "missing"}
      </span>
      <span>
        Corpus {detail.corpus_trace_count} trace
        {detail.corpus_trace_count === 1 ? "" : "s"}
        {detail.build_steps_recorded > 0 ? ` · ${detail.build_steps_recorded} steps` : ""}
      </span>
    </div>
  );
}

export function ProjectMatrixTable({
  rows,
  selected,
  onSelect,
  portfolioDetail,
  compact = false,
}: {
  rows: ProjectMatrixRow[];
  selected: string | null;
  onSelect: (option: string | null) => void;
  portfolioDetail?: ProjectPortfolioDetail[];
  compact?: boolean;
}) {
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<ProjectMatrixSortKey>("score");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const detailByKey = useMemo(() => {
    const map = new Map<string, ProjectPortfolioDetail>();
    for (const d of portfolioDetail ?? []) {
      map.set(d.project_key, d);
    }
    return map;
  }, [portfolioDetail]);

  const visible = useMemo(
    () => sortProjectMatrixBy(filterProjectMatrix(rows, filter), sortKey),
    [rows, filter, sortKey]
  );

  const toggleExpand = (key: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-2">
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter project / phase…"
          className="flex-1 min-w-[8rem] rounded border border-liaison-outline-variant px-2 py-1 text-xs bg-liaison-surface"
          aria-label="Filter projects"
        />
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as ProjectMatrixSortKey)}
          className="rounded border border-liaison-outline-variant px-2 py-1 text-xs bg-liaison-surface"
          aria-label="Sort projects"
        >
          <option value="score">Sort: score</option>
          <option value="label">Sort: name</option>
        </select>
      </div>
      <div className={`overflow-auto ${compact ? "max-h-[min(60vh,520px)]" : "max-h-96"}`}>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-[10px] uppercase text-liaison-on-surface-variant border-b border-liaison-outline-variant">
              <th className="py-2 pr-1 w-6" aria-label="Expand" />
              <th className="py-2 pr-2">Project</th>
              {!compact && <th className="py-2 pr-2">Phase</th>}
              <th className="py-2 pr-2">Score</th>
              <th className="py-2">Impact</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td colSpan={compact ? 4 : 5} className="py-4 text-xs text-liaison-on-surface-variant">
                  No projects match filter.
                </td>
              </tr>
            ) : (
              visible.map((row) => {
                const detail = detailByKey.get(row.option);
                const isExpanded = expanded.has(row.option);
                const colSpan = compact ? 4 : 5;
                return (
                  <Fragment key={row.option}>
                    <tr
                      onClick={() => onSelect(selected === row.option ? null : row.option)}
                      className={`cursor-pointer border-b border-liaison-outline-variant/50 hover:bg-liaison-surface-container ${
                        selected === row.option ? "bg-liaison-surface-container" : ""
                      }`}
                    >
                      <td className="py-2 pr-1">
                        {detail ? (
                          <button
                            type="button"
                            onClick={(e) => toggleExpand(row.option, e)}
                            className="text-xs text-liaison-on-surface-variant hover:text-liaison-on-surface w-5"
                            aria-expanded={isExpanded}
                            aria-label={`${isExpanded ? "Collapse" : "Expand"} ${row.option} preview`}
                          >
                            {isExpanded ? "▾" : "▸"}
                          </button>
                        ) : (
                          <span className="w-5 inline-block" />
                        )}
                      </td>
                      <td className="py-2 pr-2 font-medium">{row.option}</td>
                      {!compact && (
                        <td className="py-2 pr-2 mono text-xs">
                          {row.lifecycle}/{row.phase}
                        </td>
                      )}
                      <td className="py-2 pr-2 tabular-nums">{row.score}</td>
                      <td className="py-2 text-xs">{row.impact}</td>
                    </tr>
                    {isExpanded && detail ? (
                      <tr className="border-b border-liaison-outline-variant/30">
                        <td colSpan={colSpan} className="pb-1 bg-liaison-surface-container/40">
                          <PortfolioDetailStrip detail={detail} />
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
