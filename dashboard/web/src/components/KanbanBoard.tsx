"use client";

import { Fragment, useState } from "react";

import type { KanbanBuckets, KanbanTask, ReporterStepStatus } from "@/lib/command-center-types";
import { useCommandCenter } from "@/context/CommandCenterContext";
import {
  buildReporterChecklistSteps,
  reporterStepGlyph,
} from "@/lib/operator-templates";
import { outcomeGlyph } from "./ExecutionBridgePanel";

function taskLabel(t: KanbanTask): string {
  const phase = t.current_phase ?? "?";
  const glyph = outcomeGlyph(t.last_executor_outcome);
  const agent = t.bound_agent ? ` · ${t.bound_agent}` : "";
  return `${glyph} ${t.task_id.slice(0, 12)} · ${phase}${agent}`;
}

const COLS: { key: keyof KanbanBuckets; label: string }[] = [
  { key: "todo", label: "Todo" },
  { key: "in_progress", label: "In Progress" },
  { key: "review", label: "Review" },
  { key: "done", label: "Done" },
];

function ReporterStepsMini({
  task,
  defaultProfile,
}: {
  task: KanbanTask;
  defaultProfile?: string;
}) {
  const steps = buildReporterChecklistSteps({
    task,
    defaultProfile,
    agentName: task.bound_agent ?? undefined,
  });
  const disk = task.reporter_steps;
  if (!disk) return null;

  return (
    <ol className="flex flex-wrap gap-x-2 gap-y-0.5 mt-1 pl-1">
      {steps.map((step) => {
        const key = step.id as keyof ReporterStepStatus;
        const done = disk[key];
        const pending = key === "approve" && !disk.approve && disk.attach;
        return (
          <li key={step.id} className="text-[10px] flex items-center gap-0.5">
            <span
              className={
                done ? "text-liaison-teal" : pending ? "text-liaison-warning" : "text-liaison-on-surface-variant"
              }
              aria-hidden
            >
              {reporterStepGlyph(Boolean(done), pending)}
            </span>
            <span className="text-liaison-on-surface-variant">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function TaskRow({
  task,
  selected,
  expanded,
  defaultProfile,
  onSelect,
  onToggleExpand,
}: {
  task: KanbanTask;
  selected: boolean;
  expanded: boolean;
  defaultProfile?: string;
  onSelect: () => void;
  onToggleExpand: (e: React.MouseEvent) => void;
}) {
  const hasReporter = Boolean(task.reporter_steps);

  return (
    <Fragment>
      <li
        role="button"
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect();
          }
        }}
        className={`text-xs mono p-1 rounded cursor-pointer hover:bg-liaison-surface-container ${
          selected
            ? "bg-liaison-primary/15 ring-1 ring-liaison-primary/40"
            : "bg-liaison-surface-container"
        }`}
        title={task.description ?? task.task_id}
      >
        <div className="flex items-start gap-1">
          {hasReporter ? (
            <button
              type="button"
              onClick={onToggleExpand}
              className="shrink-0 text-liaison-on-surface-variant hover:text-liaison-on-surface w-4"
              aria-expanded={expanded}
              aria-label={`${expanded ? "Collapse" : "Expand"} reporter steps`}
            >
              {expanded ? "▾" : "▸"}
            </button>
          ) : (
            <span className="w-4 shrink-0" />
          )}
          <span className="flex-1">{taskLabel(task)}</span>
        </div>
      </li>
      {expanded && hasReporter ? (
        <li className="pl-2 pb-1">
          <ReporterStepsMini task={task} defaultProfile={defaultProfile} />
        </li>
      ) : null}
    </Fragment>
  );
}

export function KanbanBoard({ kanban }: { kanban: KanbanBuckets }) {
  const { selectedTaskId, setSelectedTaskId, state } = useCommandCenter();
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const defaultProfile = state?.focus?.default_profile;

  const toggleExpand = (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 min-h-[120px]">
      {COLS.map(({ key, label }) => (
        <div key={key} className="rounded-lg border border-liaison-outline-variant p-2 bg-liaison-surface">
          <p className="text-[10px] uppercase font-bold text-liaison-on-surface-variant mb-2">
            {label}
          </p>
          <ul className="space-y-1 max-h-40 overflow-auto">
            {kanban[key].slice(0, 8).map((t) => (
              <TaskRow
                key={t.task_id}
                task={t}
                selected={selectedTaskId === t.task_id}
                expanded={expandedTasks.has(t.task_id)}
                defaultProfile={defaultProfile}
                onSelect={() =>
                  setSelectedTaskId(selectedTaskId === t.task_id ? null : t.task_id)
                }
                onToggleExpand={(e) => toggleExpand(t.task_id, e)}
              />
            ))}
            {kanban[key].length === 0 ? (
              <li className="text-xs text-liaison-on-surface-variant">—</li>
            ) : null}
          </ul>
        </div>
      ))}
    </div>
  );
}
