"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { isDebriefStale } from "@/lib/command-center-helpers";
import { runLiaisonFromBrowser } from "@/lib/liaison-run-client";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";
import { StatusPill } from "./StatusPill";

export function OpsSignoffPanel() {
  const { state, selectedProject, selectedTaskId, refresh } = useCommandCenter();
  const [runOutput, setRunOutput] = useState<string | null>(null);
  const [runBusy, setRunBusy] = useState(false);

  const signoff = state?.ops_signoff;
  const validationProfile =
    state?.project_plan?.validation_profile ||
    state?.focus?.default_profile ||
    "";
  const canRunValidate =
    Boolean(selectedProject) &&
    validationProfile &&
    validationProfile !== "none";

  const runLiaison = useCallback(
    async (cmd: string) => {
      setRunBusy(true);
      setRunOutput(null);
      try {
        const data = await runLiaisonFromBrowser({
          cmd,
          project: selectedProject,
          task: selectedTaskId,
        });
        if (data == null) return;
        setRunOutput(data.output ?? (data.ok ? "OK" : "Failed"));
        if (data.ok) refresh(true);
      } catch (err) {
        setRunOutput(err instanceof Error ? err.message : String(err));
      } finally {
        setRunBusy(false);
      }
    },
    [refresh, selectedProject, selectedTaskId]
  );

  if (!signoff) return null;

  const nextAction = state?.workflow_next_action;

  return (
    <Panel
      eyebrow="Signoff"
      title="Ops checklist"
      purpose="Final gate before close — handoffs, validation, debrief freshness."
      className="mb-6"
    >
      {signoff.summary ? (
        <p className="text-sm leading-relaxed mb-4">{signoff.summary}</p>
      ) : null}

      {nextAction ? (
        <div className="mb-4 rounded-lg border border-liaison-primary/40 bg-liaison-surface-container px-3 py-2 text-sm">
          <p className="font-medium text-liaison-primary mb-1">Workflow next action</p>
          <p className="text-xs text-liaison-on-surface-variant mb-2">{nextAction.hint}</p>
          <div className="flex flex-wrap gap-2 items-center">
            <code className="mono text-xs flex-1 truncate">{nextAction.liaison_cmd}</code>
            <CopyButton text={nextAction.liaison_cmd} label="Copy" />
            <button
              type="button"
              disabled={runBusy || !selectedProject}
              onClick={() => void runLiaison(nextAction.liaison_cmd)}
              className="text-xs px-2 py-1 rounded border border-liaison-outline-variant hover:bg-liaison-surface disabled:opacity-50"
            >
              Run close-task
            </button>
          </div>
        </div>
      ) : null}

      {(signoff.playbook?.length ?? 0) > 0 ? (
        <div className="mb-4">
          <p className="text-xs uppercase tracking-wide text-liaison-on-surface-variant mb-2">
            Signoff playbook
          </p>
          <ol className="list-decimal list-inside space-y-1 text-sm text-liaison-on-surface-variant">
            {signoff.playbook!.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 mb-4">
        <StatusPill status={signoff.pending_handoff_count ? "fail" : "pass"}>
          Handoffs {signoff.pending_handoff_count}
        </StatusPill>
        <StatusPill status={signoff.gate_failures ? "fail" : "pass"}>
          Gate failures {signoff.gate_failures}
        </StatusPill>
        <StatusPill status={signoff.flywheel_open ? "warn" : "pass"}>
          Flywheel {signoff.flywheel_open}
        </StatusPill>
        <StatusPill status={signoff.debrief_stale || isDebriefStale(state) ? "fail" : "pass"}>
          Debrief {signoff.debrief_age}
          {signoff.debrief_stale ? ` · stale (>${signoff.debrief_stale_days ?? 7}d)` : ""}
        </StatusPill>
        <StatusPill status={signoff.ready_for_signoff ? "pass" : "warn"}>
          {signoff.ready_for_signoff ? "Ready for signoff" : "Action required"}
        </StatusPill>
      </div>

      {canRunValidate ? (
        <div className="mb-4 flex flex-wrap gap-2 items-center text-sm">
          <span className="text-xs text-liaison-on-surface-variant">
            Profile <span className="mono">{validationProfile}</span>
          </span>
          <button
            type="button"
            disabled={runBusy}
            onClick={() =>
              void runLiaison(`liaison validate --profile ${validationProfile}`)
            }
            className="text-xs px-2 py-1 rounded border border-liaison-primary text-liaison-primary hover:bg-liaison-surface-container disabled:opacity-50"
          >
            {runBusy ? "Running…" : "Run validate"}
          </button>
        </div>
      ) : null}

      {runOutput ? (
        <pre className="mb-4 text-xs mono whitespace-pre-wrap max-h-32 overflow-auto rounded border border-liaison-outline-variant/40 p-2 bg-liaison-surface-container">
          {runOutput}
        </pre>
      ) : null}

      <ul className="space-y-2 mb-6">
        {signoff.checklist.map((step) => (
          <li
            key={step.id}
            className="flex flex-wrap items-start gap-2 rounded-lg border border-liaison-outline-variant/40 px-3 py-2 text-sm"
          >
            <span className={step.done ? "text-liaison-teal" : "text-liaison-warning"}>
              {step.done ? "✓" : "○"}
            </span>
            <div className="flex-1 min-w-[10rem]">
              <p className="font-medium">{step.label}</p>
              {step.how_to ? (
                <p className="text-xs leading-relaxed text-liaison-on-surface-variant mt-1">
                  {step.how_to}
                </p>
              ) : step.detail ? (
                <p className="text-xs text-liaison-on-surface-variant">{step.detail}</p>
              ) : null}
            </div>
            {step.liaison_cmd ? <CopyButton text={step.liaison_cmd} label="Copy" /> : null}
          </li>
        ))}
      </ul>

      {signoff.pending_handoffs.length > 0 ? (
        <div className="mb-6">
          <p className="text-xs uppercase tracking-wide text-liaison-on-surface-variant mb-2">
            {signoff.global_scope && !selectedProject
              ? "Pending handoffs · all projects"
              : "Pending handoffs"}
          </p>
          <ul className="space-y-2 text-sm">
            {signoff.pending_handoffs.slice(0, 8).map((h) => (
              <li
                key={`${h.task_id}-${h.artifact}`}
                className="border-b border-liaison-outline-variant/40 pb-2"
              >
                {h.project_key && !selectedProject ? (
                  <Link
                    href={`/?project=${encodeURIComponent(h.project_key)}`}
                    className="text-liaison-primary hover:underline text-xs font-medium"
                  >
                    {h.project_key}
                  </Link>
                ) : (
                  <span className="text-liaison-on-surface-variant text-xs">{h.repo}</span>
                )}
                <span className="mono text-xs ml-2">{h.task_id}</span>
                <p className="text-xs truncate">{h.artifact}</p>
                {h.artifact ? (
                  <div className="mt-1 flex flex-wrap gap-2 items-center">
                    <code className="mono text-xs flex-1 truncate">
                      liaison approve-artifact {h.artifact}
                    </code>
                    <CopyButton text={`liaison approve-artifact ${h.artifact}`} />
                    {selectedProject ? (
                      <button
                        type="button"
                        disabled={runBusy}
                        onClick={() =>
                          void runLiaison(`liaison approve-artifact ${h.artifact}`)
                        }
                        className="text-[10px] px-1.5 py-0.5 rounded border border-liaison-outline-variant hover:bg-liaison-surface-container disabled:opacity-50"
                      >
                        Approve
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div>
        <p className="text-xs uppercase tracking-wide text-liaison-on-surface-variant mb-2">
          Copy hints
        </p>
        <ul className="space-y-2">
          {signoff.copy_hints.map((hint) => (
            <li key={hint.label} className="flex gap-2 items-center text-sm">
              <span className="font-medium shrink-0">{hint.label}</span>
              <code className="mono text-xs flex-1 truncate">{hint.liaison_cmd}</code>
              <CopyButton text={hint.liaison_cmd} />
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}
