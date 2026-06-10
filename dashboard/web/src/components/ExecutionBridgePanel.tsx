"use client";

import { useCallback, useState } from "react";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { buildObserveSessionComplete } from "@/lib/operator-templates";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

function outcomeGlyph(outcome: string | null | undefined): string {
  if (outcome === "success") return "✓";
  if (outcome === "failure") return "✗";
  return "○";
}

type VentureNextResponse = {
  item?: { id: string; project_key: string; task_id: string; agent: string } | null;
  message?: string;
  spawned?: boolean;
  hints?: {
    launch?: string;
    register_cmd?: string;
    complete_cmd?: string;
    spawn_cmd?: string;
    copy_block?: string;
    spawn_result?: {
      spawned?: boolean;
      mode?: string;
      message?: string;
      pane_pid?: number;
    };
  };
};

export function ExecutionBridgePanel({ compact = false }: { compact?: boolean }) {
  const { state, selectedProject, selectedTaskId, refresh } = useCommandCenter();
  const [projectKey, setProjectKey] = useState(selectedProject ?? "");
  const [taskId, setTaskId] = useState(selectedTaskId ?? "");
  const [agent, setAgent] = useState("hermes");
  const [busy, setBusy] = useState<string | null>(null);
  const [nextHints, setNextHints] = useState<VentureNextResponse["hints"] | null>(null);
  const [queueMessage, setQueueMessage] = useState<string | null>(null);

  const postQueue = useCallback(
    async (path: string, body?: Record<string, unknown>) => {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = (await res.json()) as Record<string, unknown>;
      if (!res.ok) {
        throw new Error(String(data.error ?? res.statusText));
      }
      return data;
    },
    []
  );

  const handleAdd = async () => {
    if (!projectKey.trim() || !taskId.trim()) return;
    setBusy("add");
    try {
      await postQueue("/api/venture-queue/add", {
        project: projectKey.trim(),
        taskId: taskId.trim(),
        agent: agent.trim() || "hermes",
      });
      refresh(true);
    } catch (err) {
      setQueueMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const handleNext = async (spawn = false) => {
    setBusy(spawn ? "next-spawn" : "next");
    setQueueMessage(null);
    try {
      const path = spawn ? "/api/venture-queue/next?spawn=1" : "/api/venture-queue/next";
      const data = (await postQueue(path)) as VentureNextResponse;
      setNextHints(data.hints ?? null);
      const spawnMsg = data.hints?.spawn_result?.spawned
        ? `Spawned (${data.hints.spawn_result.mode})`
        : data.hints?.spawn_result?.message;
      setQueueMessage(
        spawnMsg ||
          data.message ||
          (data.item ? "Next item ready" : "No item")
      );
      if (spawn && data.hints?.spawn_result?.spawned) {
        refresh(true);
      }
    } catch (err) {
      setQueueMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const spawnAllowed = state?.terminal_bridge?.spawn_allowed ?? false;

  const handleMark = async (action: "running" | "done", itemId: string) => {
    setBusy(itemId);
    try {
      await postQueue(`/api/venture-queue/mark-${action}`, { itemId });
      refresh(true);
    } catch (err) {
      setQueueMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  if (!state) return null;

  const usage = state.workstation_usage;
  const pending = (state.venture_queue ?? []).filter((i) => i.status === "pending");
  const running = (state.terminal_sessions ?? []).filter(
    (s) => s.status !== "ended" && s.alive !== false
  );

  const completeCmd =
    selectedProject && selectedTaskId
      ? buildObserveSessionComplete({
          agent: running[0]?.agent_name ?? "hermes",
          projectKey: selectedProject,
          taskId: selectedTaskId,
          exitCode: 0,
        })
      : null;

  const hintsText = nextHints
    ? nextHints.copy_block ||
      [nextHints.spawn_cmd, nextHints.launch, nextHints.register_cmd, nextHints.complete_cmd]
        .filter(Boolean)
        .join("\n")
    : "";

  return (
    <Panel
      eyebrow="Bridge"
      title="Execution bridge"
      purpose="Venture-bound terminal sessions and workstation capacity — record outcomes without Cursor."
      className={compact ? "" : "mb-4"}
    >
      {usage ? (
        <p className="text-xs text-liaison-on-surface-variant mb-3">
          Ventures {usage.running_ventures}/{usage.max_active_ventures} active ·{" "}
          {usage.ventures_free} free
          {state.venture_queue_summary
            ? ` · Queue pending ${state.venture_queue_summary.pending_count}`
            : ""}
          {state.summary.executor_session_stale
            ? ` · Stale sessions ${state.summary.executor_session_stale_count ?? 1}`
            : ""}
        </p>
      ) : null}

      {usage?.engine_slots?.length ? (
        <ul className="flex flex-wrap gap-2 mb-3 text-xs">
          {usage.engine_slots.map((slot) => (
            <li
              key={slot.engine}
              className="px-2 py-0.5 rounded bg-liaison-surface-container mono"
            >
              {slot.engine} {slot.used}/{slot.max}
            </li>
          ))}
        </ul>
      ) : null}

      {running.length > 0 ? (
        <div className="mb-3">
          <p className="text-[10px] uppercase text-liaison-on-surface-variant mb-1">Live sessions</p>
          <ul className="space-y-1 text-xs">
            {running.map((s) => (
              <li key={s.id} className="mono">
                {s.agent_name}
                {s.project_key ? ` · ${s.project_key}` : ""}
                {s.task_id ? ` · ${s.task_id}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-liaison-on-surface-variant mb-3">No live executor sessions.</p>
      )}

      <div className="mb-3 border-t border-liaison-outline-variant/50 pt-3">
        <p className="text-[10px] uppercase text-liaison-on-surface-variant mb-2">Venture queue</p>
        <div className="grid grid-cols-3 gap-2 mb-2 text-xs">
          <input
            className="rounded border border-liaison-outline-variant px-2 py-1 bg-liaison-surface"
            placeholder="project"
            value={projectKey}
            onChange={(e) => setProjectKey(e.target.value)}
          />
          <input
            className="rounded border border-liaison-outline-variant px-2 py-1 bg-liaison-surface"
            placeholder="task-id"
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
          />
          <input
            className="rounded border border-liaison-outline-variant px-2 py-1 bg-liaison-surface"
            placeholder="agent"
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-2 mb-2">
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void handleAdd()}
            className="text-xs px-2 py-1 rounded border border-liaison-outline-variant hover:bg-liaison-surface-container disabled:opacity-50"
          >
            {busy === "add" ? "Adding…" : "Add to queue"}
          </button>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void handleNext(false)}
            className="text-xs px-2 py-1 rounded border border-liaison-outline-variant hover:bg-liaison-surface-container disabled:opacity-50"
          >
            {busy === "next" ? "Loading…" : "Next hints"}
          </button>
          {spawnAllowed ? (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void handleNext(true)}
              className="text-xs px-2 py-1 rounded border border-liaison-primary text-liaison-primary hover:bg-liaison-surface-container disabled:opacity-50"
            >
              {busy === "next-spawn" ? "Spawning…" : "Next + spawn"}
            </button>
          ) : null}
          {hintsText ? <CopyButton text={hintsText} label="Copy play block" /> : null}
        </div>
        {queueMessage ? (
          <p className="text-xs text-liaison-on-surface-variant mb-2">{queueMessage}</p>
        ) : null}
        {pending.length > 0 ? (
          <ul className="space-y-1 text-xs max-h-32 overflow-auto">
            {pending.map((q) => (
              <li key={q.id} className="flex flex-wrap items-center gap-2">
                <span>
                  <span className="font-medium">{q.project_key}</span> · {q.task_id} · {q.agent}
                </span>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void handleMark("running", q.id)}
                  className="text-[10px] px-1.5 py-0.5 rounded border border-liaison-outline-variant hover:bg-liaison-surface-container disabled:opacity-50"
                >
                  Mark running
                </button>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void handleMark("done", q.id)}
                  className="text-[10px] px-1.5 py-0.5 rounded border border-liaison-outline-variant hover:bg-liaison-surface-container disabled:opacity-50"
                >
                  Mark done
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-liaison-on-surface-variant">No pending queue items.</p>
        )}
      </div>

      {completeCmd ? (
        <div className="flex gap-2 items-center mt-2">
          <code className="mono text-[10px] flex-1 truncate">{completeCmd}</code>
          <CopyButton text={completeCmd} label="Copy complete" />
        </div>
      ) : (
        <p className="text-xs text-liaison-on-surface-variant">
          Focus a project and task to copy observe-session complete.
        </p>
      )}
    </Panel>
  );
}

export { outcomeGlyph };
