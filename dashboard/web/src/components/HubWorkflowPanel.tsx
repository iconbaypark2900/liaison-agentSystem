"use client";

import { useState } from "react";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { runLiaisonFromBrowser } from "@/lib/liaison-run-client";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

export function HubWorkflowPanel() {
  const { state, selectedProject, setSelectedPatternId, refresh } = useCommandCenter();
  const workflows = state?.hub_workflows ?? [];
  const [busyId, setBusyId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function scaffoldPattern(wf: (typeof workflows)[0]) {
    setBusyId(wf.id);
    setStatus(null);
    try {
      const data = await runLiaisonFromBrowser({
        cmd: wf.liaison_cmd,
        project: selectedProject,
      });
      if (data == null) return;
      setStatus(data.output ?? (data.ok ? "Pattern scaffolded" : "Scaffold failed"));
      if (data.ok) {
        setSelectedPatternId(wf.id);
        refresh(true);
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusyId(null);
    }
  }

  if (!selectedProject) {
    return (
      <Panel
        eyebrow="Hub"
        title="Agent workflows"
        purpose="Multi-agent patterns ranked for the focused project."
      >
        <p className="text-sm text-liaison-on-surface-variant">
          Focus a project to see which handoff patterns (ml_intern → qca → hermes, etc.) fit its
          operating plan.
        </p>
      </Panel>
    );
  }

  if (!workflows.length) {
    return null;
  }

  return (
    <Panel
      eyebrow="Hub"
      title={`Workflows for ${selectedProject}`}
      purpose="Ranked patterns — scaffold with start-pattern, then run agents in terminal and attach reports."
    >
      <ul className="space-y-3">
        {workflows.map((wf) => (
          <li
            key={wf.id}
            className={`rounded-lg border p-3 text-sm ${
              wf.recommended
                ? "border-liaison-teal/40 bg-liaison-teal/5"
                : "border-liaison-outline-variant/50"
            }`}
          >
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="font-medium">{wf.label}</span>
              {wf.recommended ? (
                <span className="text-[10px] uppercase text-liaison-teal">Best fit</span>
              ) : null}
              <span className="text-xs text-liaison-on-surface-variant ml-auto">
                fit {wf.fit_score}%
              </span>
            </div>
            <p className="mono text-xs text-liaison-primary mb-1">{wf.agents.join(" → ")}</p>
            <p className="text-xs text-liaison-on-surface-variant mb-2">{wf.when}</p>
            <p className="text-[10px] text-liaison-on-surface-variant mb-2">{wf.fit_reason}</p>
            {wf.steps.length > 0 ? (
              <ol className="list-decimal list-inside text-xs space-y-0.5 mb-2">
                {wf.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <CopyButton text={wf.liaison_cmd} label="Scaffold" />
              <button
                type="button"
                disabled={busyId === wf.id}
                onClick={() => void scaffoldPattern(wf)}
                className="text-xs px-2 py-1 rounded-md bg-liaison-primary text-liaison-canvas disabled:opacity-50"
              >
                {busyId === wf.id ? "Scaffolding…" : "Scaffold pattern"}
              </button>
              <button
                type="button"
                onClick={() => setSelectedPatternId(wf.id)}
                className="text-xs px-2 py-1 rounded-md border border-liaison-outline-variant hover:bg-liaison-surface-container"
              >
                Select pattern
              </button>
            </div>
          </li>
        ))}
      </ul>
      {status ? (
        <p className="text-xs text-liaison-on-surface-variant mt-3 whitespace-pre-wrap">{status}</p>
      ) : null}
    </Panel>
  );
}
