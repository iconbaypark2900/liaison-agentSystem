"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import type { ProjectIntakeCheck } from "@/lib/command-center-types";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

function checkGlyph(c: ProjectIntakeCheck): string {
  if (c.pass) return "✓";
  return c.severity === "critical" ? "✗" : "!";
}

export function IntakePanel() {
  const { state, selectedProject, isRefreshing, refresh } = useCommandCenter();
  const intake = state?.project_intake;
  if (!selectedProject || !intake) return null;

  const cmd = `liaison project-intake --project ${selectedProject} --show`;

  return (
    <Panel
      eyebrow="Intake"
      title={`Project readiness · ${selectedProject}`}
      purpose={
        intake.ready_to_build
          ? "Ready to scaffold tasks and run executors in terminal."
          : "Resolve gaps before Hermes/build executors — research and classify first."
      }
      className="mt-4 mb-4"
    >
      <div className="flex flex-wrap items-center gap-2 mb-4 text-sm">
        <span
          className={
            intake.intake_ready
              ? "text-liaison-teal font-medium"
              : "text-liaison-error font-medium"
          }
        >
          Intake {intake.intake_ready ? "ready" : "blocked"}
        </span>
        <span className="text-liaison-on-surface-variant">·</span>
        <span
          className={
            intake.ready_to_build
              ? "text-liaison-teal font-medium"
              : "text-liaison-warning font-medium"
          }
        >
          Build {intake.ready_to_build ? "ready" : "not ready"}
        </span>
        <span className="text-liaison-on-surface-variant text-xs">
          Lane: {intake.recommended_lane}
        </span>
        <button
          type="button"
          onClick={() => refresh(true)}
          disabled={isRefreshing}
          className="ml-auto text-xs px-2 py-1 rounded-md border border-liaison-outline-variant hover:bg-liaison-surface-container disabled:opacity-50"
        >
          {isRefreshing ? "Re-running…" : "Re-run intake"}
        </button>
      </div>

      {intake.blockers.length > 0 ? (
        <ul className="space-y-2 mb-4 text-sm">
          {intake.blockers.slice(0, 6).map((b) => (
            <li
              key={b.id}
              className="rounded-lg border border-liaison-outline-variant/50 px-3 py-2"
            >
              <span className="font-medium">
                [{b.severity}] {b.label}
              </span>
              <p className="text-xs text-liaison-on-surface-variant mt-1">{b.detail}</p>
              {b.liaison_cmd ? (
                <div className="mt-1 flex gap-2 items-center">
                  <code className="mono text-xs flex-1 truncate">{b.liaison_cmd}</code>
                  <CopyButton text={b.liaison_cmd} label="Copy fix" />
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <p className="panel-eyebrow mb-2">Checks</p>
      <ul className="space-y-1 text-xs">
        {intake.checks.map((c) => (
          <li key={c.id} className="flex gap-2 items-start">
            <span
              className={`w-4 shrink-0 font-bold ${
                c.pass ? "text-liaison-teal" : c.severity === "critical" ? "text-liaison-error" : "text-liaison-warning"
              }`}
            >
              {checkGlyph(c)}
            </span>
            <span className="font-medium w-36 shrink-0">{c.label}</span>
            <span className="text-liaison-on-surface-variant flex-1">{c.detail}</span>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex gap-2">
        <CopyButton text={cmd} label="Copy CLI report" />
      </div>
    </Panel>
  );
}
