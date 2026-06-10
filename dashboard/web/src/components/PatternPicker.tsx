"use client";

import { useEffect, useState } from "react";

import { useCommandCenter } from "@/context/CommandCenterContext";
import type { ProjectAgentPattern } from "@/lib/command-center-types";
import {
  buildOpenInTerminalScript,
  buildPatternPlayBlock,
  buildStartPatternCmd,
  suggestPatternTaskId,
} from "@/lib/operator-templates";
import { runLiaisonFromBrowser } from "@/lib/liaison-run-client";
import { CopyButton } from "./CopyButton";

export function PatternPicker({
  patterns,
  projectPath,
}: {
  patterns: ProjectAgentPattern[];
  projectPath?: string;
}) {
  const {
    state,
    selectedProject,
    selectedTaskId,
    selectedPatternId,
    setSelectedPatternId,
    refresh,
  } = useCommandCenter();
  const activeTaskId = state?.active_task_id;
  const [selectedId, setSelectedId] = useState(
    selectedPatternId ?? patterns[0]?.id ?? ""
  );
  const [taskId, setTaskId] = useState(selectedTaskId ?? "");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (selectedPatternId && patterns.some((p) => p.id === selectedPatternId)) {
      setSelectedId(selectedPatternId);
    }
  }, [selectedPatternId, patterns]);

  const pattern = patterns.find((p) => p.id === selectedId) ?? patterns[0];
  if (!pattern) {
    return (
      <p className="text-sm text-liaison-on-surface-variant">No project agent patterns in registry.</p>
    );
  }

  const suggested = taskId || selectedTaskId || activeTaskId || suggestPatternTaskId(pattern);
  const startCmd = buildStartPatternCmd(pattern, suggested);
  const fullPlay = buildPatternPlayBlock(pattern, suggested, projectPath);

  async function scaffoldPattern() {
    setBusy(true);
    setStatus(null);
    try {
      const data = await runLiaisonFromBrowser({
        cmd: startCmd,
        project: selectedProject,
        task: suggested,
      });
      if (data == null) return;
      setStatus(data.output ?? (data.ok ? "Pattern scaffolded" : "Scaffold failed"));
      if (data.ok) {
        setSelectedPatternId(pattern.id);
        refresh(true);
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function copyTerminalScript() {
    const agentRow = {
      name: pattern.agents[0] ?? "hermes",
      display: pattern.agents[0] ?? "hermes",
      status: "Idle",
      registry_status: "active",
      tasks: 0,
      launch: pattern.agents[0] === "hermes" ? "hermes" : pattern.agents[0] ?? "hermes",
      role: "",
    };
    const script = buildOpenInTerminalScript(agentRow);
    await navigator.clipboard.writeText(`${startCmd}\n\n${script}`);
    setStatus("Copied start-pattern + terminal next steps");
    setTimeout(() => setStatus(null), 3000);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {patterns.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => {
              setSelectedId(p.id);
              setSelectedPatternId(p.id);
              setTaskId("");
            }}
            className={`text-xs px-2 py-1 rounded-md border ${
              p.id === pattern.id
                ? "border-liaison-primary bg-liaison-surface-container"
                : "border-liaison-outline-variant hover:bg-liaison-surface-container"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="text-sm space-y-2">
        <p className="font-medium">{pattern.label}</p>
        <p className="text-liaison-on-surface-variant text-xs">{pattern.when}</p>
        <p className="text-xs">
          Agents: <span className="mono">{pattern.agents.join(" → ") || "—"}</span>
        </p>
        <ol className="list-decimal list-inside text-xs space-y-1 text-liaison-on-surface-variant">
          {pattern.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs">
          Task id
          <input
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            placeholder={suggestPatternTaskId(pattern)}
            className="block mt-1 px-2 py-1 rounded border border-liaison-outline-variant bg-liaison-canvas mono text-xs w-48"
          />
        </label>
        <CopyButton text={startCmd} label="Copy start-pattern" />
        <CopyButton text={fullPlay} label="Copy full play" />
        <button
          type="button"
          disabled={busy}
          onClick={() => void scaffoldPattern()}
          className="text-xs px-2 py-1 rounded-md bg-liaison-primary text-liaison-canvas disabled:opacity-50"
        >
          {busy ? "Scaffolding…" : "Scaffold pattern"}
        </button>
        <button
          type="button"
          onClick={() => void copyTerminalScript()}
          className="text-xs px-2 py-1 rounded-md border border-liaison-outline-variant"
        >
          Copy terminal script
        </button>
      </div>
      {status ? <p className="text-xs text-liaison-on-surface-variant whitespace-pre-wrap">{status}</p> : null}
    </div>
  );
}
