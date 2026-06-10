"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { buildHubHref } from "@/lib/url-query-helpers";

type StepState = "done" | "current" | "todo";

function stepClass(state: StepState): string {
  if (state === "done") return "text-liaison-teal border-liaison-teal/40";
  if (state === "current") return "text-liaison-primary border-liaison-primary/50";
  return "text-liaison-on-surface-variant border-liaison-outline-variant/60";
}

export function PlaybookProgressBar() {
  const searchParams = useSearchParams();
  const { state, selectedProject, selectedPatternId, selectedTaskId } = useCommandCenter();
  if (!state || !selectedProject) return null;

  const intake = state.project_intake;
  const hasPlan = Boolean(state.project_plan ?? state.summary.has_project_plan);
  const intakeDone = Boolean(intake?.intake_ready ?? intake?.ready_to_build);
  const patternDone = Boolean(selectedPatternId);

  let intakeState: StepState = "todo";
  if (intakeDone) intakeState = "done";
  else if (intake) intakeState = "current";

  let planState: StepState = "todo";
  if (hasPlan) planState = "done";
  else if (intakeDone) planState = "current";

  let hubState: StepState = "todo";
  if (patternDone) hubState = "done";
  else if (hasPlan) hubState = "current";

  const hubHref = buildHubHref(
    {
      project: selectedProject,
      task: selectedTaskId,
      pattern: selectedPatternId,
      agent: state.project_agent_patterns?.find((p) => p.id === selectedPatternId)?.agents[0] ?? null,
    },
    searchParams.toString()
  );

  return (
    <nav
      aria-label="Playbook progress"
      className="sticky top-0 z-20 -mx-1 px-3 py-2 mb-3 rounded-lg border border-liaison-outline-variant/40 bg-liaison-canvas/95 backdrop-blur-sm"
    >
      <p className="text-[10px] uppercase tracking-wide text-liaison-on-surface-variant mb-2">
        Intake → Plan → Hub · {selectedProject}
      </p>
      <ol className="flex flex-wrap items-center gap-2 text-xs font-medium">
        <li>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border ${stepClass(intakeState)}`}>
            {intakeState === "done" ? "✓" : intakeState === "current" ? "○" : "·"} Intake
          </span>
        </li>
        <li className="text-liaison-on-surface-variant/50">→</li>
        <li>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border ${stepClass(planState)}`}>
            {planState === "done" ? "✓" : planState === "current" ? "○" : "·"} Plan
          </span>
        </li>
        <li className="text-liaison-on-surface-variant/50">→</li>
        <li>
          <Link
            href={hubHref}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border hover:bg-liaison-surface-container ${stepClass(hubState)}`}
          >
            {hubState === "done" ? "✓" : hubState === "current" ? "○" : "·"} Hub
            {selectedPatternId ? (
              <span className="mono text-[10px] font-normal opacity-80">({selectedPatternId})</span>
            ) : null}
          </Link>
        </li>
      </ol>
    </nav>
  );
}
