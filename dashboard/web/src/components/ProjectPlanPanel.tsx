"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

export function ProjectPlanPanel() {
  const { state, selectedProject } = useCommandCenter();
  const plan = state?.project_plan;
  if (!selectedProject || !plan) return null;

  const eng = plan.engineering_gate;
  const research = plan.research_gate;
  const writeCmd =
    plan.liaison_cmd_write ?? `liaison plan-project --project ${selectedProject} --write`;

  return (
    <Panel
      eyebrow="Operating plan"
      title={`Portfolio plan · ${selectedProject}`}
      purpose={
        plan.has_on_disk_plan
          ? "Registry defaults merged with on-disk PROJECT_OPERATING_PLAN.md."
          : "Registry defaults from project_plans.yaml — write to repo memory to persist."
      }
      className="mt-4 mb-4"
    >
      <div className="flex flex-wrap gap-2 text-sm mb-3">
        <span className="font-medium">Workflow: {plan.workflow}</span>
        <span className="text-liaison-on-surface-variant">·</span>
        <span>Pattern: {plan.pattern ?? "—"}</span>
        <span className="text-liaison-on-surface-variant">·</span>
        <span>Profile: {plan.validation_profile}</span>
        {plan.tier ? (
          <>
            <span className="text-liaison-on-surface-variant">·</span>
            <span className="text-xs uppercase text-liaison-on-surface-variant">
              Tier {plan.tier}
            </span>
          </>
        ) : null}
      </div>

      {research?.summary ? (
        <div className="mb-3 text-sm">
          <p className="panel-eyebrow mb-1">Research gate</p>
          <p className="text-liaison-on-surface-variant">{research.summary}</p>
        </div>
      ) : null}

      {eng?.summary ? (
        <div className="mb-3 text-sm">
          <p className="panel-eyebrow mb-1">Engineering gate</p>
          <p
            className={
              eng.blocked
                ? "text-liaison-warning"
                : "text-liaison-on-surface-variant"
            }
          >
            {eng.summary}
          </p>
          {eng.intake_note ? (
            <p className="text-xs mt-1 text-liaison-on-surface-variant">{eng.intake_note}</p>
          ) : null}
        </div>
      ) : null}

      {plan.backlog && plan.backlog.length > 0 ? (
        <div className="mb-3">
          <p className="panel-eyebrow mb-1 text-sm">Backlog</p>
          <ul className="text-xs space-y-1 text-liaison-on-surface-variant">
            {plan.backlog.slice(0, 6).map((line) => (
              <li key={line}>• {line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex gap-2 flex-wrap">
        <CopyButton text={writeCmd} label="Copy write plan" />
      </div>
    </Panel>
  );
}
