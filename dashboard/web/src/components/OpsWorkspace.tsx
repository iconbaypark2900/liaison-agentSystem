"use client";

import Link from "next/link";
import { useState } from "react";

import { OpsSignoffPanel } from "./OpsSignoffPanel";
import { Panel } from "./Panel";
import { ReporterChecklist } from "./ReporterChecklist";
import { CopyButton } from "./CopyButton";
import { useCommandCenter } from "@/context/CommandCenterContext";

/** Ops signoff + inbox preview — shared by Overview tabs and /ops route. */
export function OpsWorkspace({ showMetrics = false }: { showMetrics?: boolean }) {
  const { state, selectedProject } = useCommandCenter();
  if (!state) return null;

  const handoffs = selectedProject
    ? state.handoffs
    : (state.ops_signoff?.pending_handoffs?.length
        ? state.ops_signoff.pending_handoffs
        : state.handoffs);

  const flywheelOpen = state.summary.flywheel_open ?? state.ops_signoff?.flywheel_open ?? 0;
  const flywheelPhases =
    (state.ops_signoff?.flywheel_phases?.length
      ? state.ops_signoff.flywheel_phases
      : state.workflow_phases) ?? [];
  const flywheelCopy =
    state.ops_signoff?.flywheel_copy_cmds ??
    (flywheelOpen > 0 ? ["liaison init --workflow data-flywheel"] : []);

  return (
    <div className="grid lg:grid-cols-12 gap-4 max-h-[min(75vh,780px)]">
      <div className="lg:col-span-7 overflow-y-auto pr-1 space-y-4">
        <OpsSignoffPanel />
        {flywheelOpen > 0 ? (
          <Panel
            eyebrow="Flywheel"
            title={`Data flywheel · ${flywheelOpen} open task(s)`}
            purpose="Workflow steps from data-flywheel.yaml — copy init and phase commands in pane B."
          >
            {flywheelCopy.length > 0 ? (
              <ul className="space-y-2 mb-4 text-sm">
                {flywheelCopy.map((cmd) => (
                  <li key={cmd} className="flex gap-2 items-center">
                    <code className="mono text-xs flex-1 truncate">{cmd}</code>
                    <CopyButton text={cmd} />
                  </li>
                ))}
              </ul>
            ) : null}
            {flywheelPhases.length > 0 ? (
              <ol className="list-decimal list-inside space-y-2 text-sm">
                {flywheelPhases.map((phase) => (
                  <li key={phase.id} className="border-b border-liaison-outline-variant/30 pb-2">
                    <span className="font-medium">{phase.label}</span>
                    {phase.objective ? (
                      <p className="text-xs text-liaison-on-surface-variant mt-0.5">
                        {phase.objective}
                      </p>
                    ) : null}
                    {(phase.suggested_liaison_commands ?? []).slice(0, 2).map((cmd) => (
                      <div key={cmd} className="flex gap-2 items-center mt-1">
                        <code className="mono text-[10px] flex-1 truncate">{cmd}</code>
                        <CopyButton text={cmd} />
                      </div>
                    ))}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-xs text-liaison-on-surface-variant">
                No workflow phases loaded — run{" "}
                <code className="mono">liaison init --workflow data-flywheel</code> in project repo.
              </p>
            )}
          </Panel>
        ) : null}
        {showMetrics ? (
          <Panel eyebrow="Metrics" title="Engineering metrics">
            <ul className="space-y-2 max-h-56 overflow-auto text-sm">
              {state.metrics_rows.map((row) => (
                <li key={row.id}>
                  <p className="font-medium">{row.label}</p>
                  <p className="text-xs text-liaison-on-surface-variant">{row.detail}</p>
                </li>
              ))}
            </ul>
          </Panel>
        ) : null}
      </div>
      <div className="lg:col-span-5 space-y-4 overflow-y-auto">
        <ReporterChecklist />
        <Panel
          eyebrow="Inbox"
          title={selectedProject ? "Handoffs preview" : "All projects · handoffs"}
          purpose={
            selectedProject
              ? "Pending approvals for focused project."
              : "Top pending handoffs across repos — click project to focus."
          }
        >
          <ul className="space-y-2 text-sm max-h-48 overflow-auto">
            {handoffs.slice(0, 12).map((h) => (
              <li
                key={`${h.task_id}-${h.artifact}`}
                className="text-xs border-b border-liaison-outline-variant/30 pb-1"
              >
                {h.project_key && !selectedProject ? (
                  <Link
                    href={`/?project=${encodeURIComponent(h.project_key)}`}
                    className="text-liaison-primary hover:underline font-medium"
                  >
                    {h.project_key}
                  </Link>
                ) : (
                  <span className="font-medium">{h.repo}</span>
                )}
                <span className="mono ml-2">{h.task_id}</span> · {h.status} · {h.artifact}
              </li>
            ))}
          </ul>
        </Panel>
        <Panel eyebrow="Memory" title="Debriefs preview">
          <ul className="space-y-1 text-xs max-h-40 overflow-auto">
            {state.debriefs.slice(0, 8).map((d) => (
              <li key={d.path ?? d.file} className="truncate">
                <span className="font-medium">{d.repo}</span> · {d.age}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
