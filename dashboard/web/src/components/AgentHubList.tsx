"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import type { AgentRow } from "@/lib/command-center-types";
import { hubAgentGroupId, groupAgentRows } from "@/lib/hub-agent-groups";
import { useCommandCenter } from "@/context/CommandCenterContext";
import { agentFromQuery, mergeQueryParams } from "@/lib/url-query-helpers";
import {
  buildAttachTemplate,
  buildObserveSessionComplete,
  buildOpenInTerminalScript,
  buildReporterBundle,
} from "@/lib/operator-templates";
import { AgentResumeSections } from "./AgentResumeSections";
import { CopyButton } from "./CopyButton";

async function spawnTerminal(
  launch: string,
  title: string,
  agentName: string,
  project?: string | null,
  taskId?: string | null,
  patternId?: string | null
): Promise<{ note: string | null; completeHint?: string }> {
  try {
    const res = await fetch("/api/terminal/spawn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        launch,
        title,
        agentName,
        project: project ?? undefined,
        taskId: taskId ?? undefined,
        patternId: patternId ?? undefined,
      }),
    });
    const data = (await res.json()) as {
      mode?: string;
      spawned?: boolean;
      message?: string;
      completeHint?: string;
    };
    if (data.spawned) {
      return {
        note: data.completeHint
          ? "Spawned — copy complete-session when pane A finishes"
          : "Spawned terminal window with launch line",
        completeHint: data.completeHint,
      };
    }
    return { note: data.message ?? "Copy fallback — terminal bridge unavailable" };
  } catch {
    return { note: "Copy fallback — terminal spawn failed" };
  }
}

export function AgentHubList({
  agents,
  compact = false,
  projectPath,
  defaultProfile,
  selectedTaskId,
  activeTaskId,
  readyToBuild = true,
  executorLaunchReady,
}: {
  agents: AgentRow[];
  compact?: boolean;
  projectPath?: string;
  defaultProfile?: string;
  selectedTaskId?: string | null;
  activeTaskId?: string | null;
  readyToBuild?: boolean;
  executorLaunchReady?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const urlAgent = agentFromQuery(queryString);

  const { selectedProject, selectedPatternId } = useCommandCenter();
  const [selected, setSelected] = useState<string | null>(
    urlAgent && agents.some((a) => a.name === urlAgent) ? urlAgent : (agents[0]?.name ?? null)
  );
  const [terminalNote, setTerminalNote] = useState<string | null>(null);
  const [completeHint, setCompleteHint] = useState<string | null>(null);

  useEffect(() => {
    if (urlAgent && agents.some((a) => a.name === urlAgent)) {
      setSelected(urlAgent);
    }
  }, [urlAgent, agents]);

  function selectAgent(name: string) {
    setSelected(name);
    const q = mergeQueryParams(queryString, { agent: name });
    router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
  }

  const agent = agents.find((a) => a.name === selected);
  const taskId = selectedTaskId ?? activeTaskId;

  async function openInTerminal() {
    if (!agent) return;
    const script = buildOpenInTerminalScript(agent);
    const result = await spawnTerminal(
      agent.launch,
      agent.name,
      agent.name,
      selectedProject,
      taskId,
      selectedPatternId
    );
    if (result.note && !result.completeHint) {
      await navigator.clipboard.writeText(script);
      setTerminalNote(result.note);
      setCompleteHint(null);
      setTimeout(() => setTerminalNote(null), 4000);
      return;
    }
    setTerminalNote(result.note ?? "Spawned terminal window with launch line");
    setCompleteHint(result.completeHint ?? null);
    setTimeout(() => {
      setTerminalNote(null);
      setCompleteHint(null);
    }, 8000);
  }

  const attachCmd = agent ? buildAttachTemplate(agent.name) : "";
  const bundle =
    agent && taskId
      ? buildReporterBundle({
          projectPath,
          agent,
          taskId,
          defaultProfile,
        })
      : "";

  const { grouped, other } = groupAgentRows(agents);
  const isLiaisonLane = agent
    ? agent.name === "liaison" || agent.name === "data_flywheel"
    : false;
  const isExceptional = agent ? hubAgentGroupId(agent.name) === "exceptional_phase" : false;
  const isExecutor = agent ? hubAgentGroupId(agent.name) === "executors" : false;
  const canLaunch = executorLaunchReady ?? readyToBuild;
  const executorGated = isExecutor && !canLaunch;

  function renderAgentButton(a: AgentRow) {
    return (
      <li key={a.name}>
        <button
          type="button"
          onClick={() => selectAgent(a.name)}
          className={`w-full text-left px-2 py-1.5 rounded-lg text-sm ${
            selected === a.name
              ? "bg-liaison-surface-container text-liaison-primary"
              : "hover:bg-liaison-surface-container"
          }`}
        >
          <span className="font-medium">{a.display}</span>
          {a.recommended ? (
            <span className="text-xs text-liaison-teal ml-1">★</span>
          ) : null}
          <span className="text-xs text-liaison-on-surface-variant ml-2">
            {a.tasks} tasks · {a.status}
          </span>
        </button>
      </li>
    );
  }

  return (
    <div className={compact ? "space-y-2" : "grid md:grid-cols-2 gap-4"}>
      <div className="space-y-3 max-h-[min(28rem,70vh)] overflow-auto pr-1">
        {grouped.map(({ group, agents: groupAgents }) => (
          <section key={group.id}>
            <h3 className="text-[10px] uppercase font-bold tracking-widest text-liaison-on-surface-variant px-1">
              {group.label}
            </h3>
            <p className="text-[10px] text-liaison-on-surface-variant px-1 mb-1 leading-snug">
              {group.description}
            </p>
            <ul className="space-y-1">{groupAgents.map(renderAgentButton)}</ul>
          </section>
        ))}
        {other.length > 0 ? (
          <section>
            <h3 className="text-[10px] uppercase font-bold tracking-widest text-liaison-on-surface-variant px-1">
              Other
            </h3>
            <ul className="space-y-1">{other.map(renderAgentButton)}</ul>
          </section>
        ) : null}
      </div>
      {agent ? (
        <div className="panel text-sm space-y-3">
          {isExceptional && agent.launch_note ? (
            <div className="rounded-lg border border-liaison-warning/50 bg-liaison-warning/10 px-3 py-2 text-xs text-liaison-warning">
              <p className="font-semibold mb-1">Exceptional phase CLI</p>
              <p>{agent.launch_note}</p>
            </div>
          ) : null}
          <div>
            <p className="font-headline font-semibold">{agent.display}</p>
            <p className="text-xs text-liaison-on-surface-variant">
              registry {agent.registry_status} · {agent.tasks} open tasks
            </p>
          </div>
          {agent.resume &&
          (agent.resume.summary || (agent.resume.capabilities?.length ?? 0) > 0) ? (
            <AgentResumeSections resume={agent.resume} />
          ) : (
            <div>
              <p className="text-[10px] uppercase text-liaison-on-surface-variant">Role</p>
              <p>{agent.role ?? agent.status}</p>
            </div>
          )}
          <div>
            <p className="text-[10px] uppercase text-liaison-on-surface-variant">Launch</p>
            <p className="mono text-xs break-all">{agent.launch}</p>
          </div>
          {agent.hub_docs && agent.hub_docs !== "—" ? (
            <div>
              <p className="text-[10px] uppercase text-liaison-on-surface-variant">Hub docs</p>
              <p className="mono text-xs break-all">{agent.hub_docs}</p>
            </div>
          ) : null}
          {agent.handoff_guide && agent.handoff_guide !== "—" ? (
            <div>
              <p className="text-[10px] uppercase text-liaison-on-surface-variant">Handoff guide</p>
              <p className="mono text-xs break-all">{agent.handoff_guide}</p>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2 pt-1">
            <CopyButton
              text={agent.launch}
              label={isLiaisonLane ? "Copy liaison cmd" : "Copy launch"}
            />
            <CopyButton text={attachCmd} label="Copy attach" />
            {bundle ? <CopyButton text={bundle} label="Copy reporter bundle" /> : null}
            {!isLiaisonLane ? (
              <button
                type="button"
                onClick={() => void openInTerminal()}
                disabled={executorGated}
                className="text-xs px-2 py-1 rounded-md border border-liaison-outline-variant hover:bg-liaison-surface-container text-liaison-primary disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Open in terminal
              </button>
            ) : null}
          </div>
          {completeHint ? (
            <div className="flex gap-2 items-center">
              <code className="mono text-[10px] flex-1 truncate">{completeHint}</code>
              <CopyButton text={completeHint} label="Copy session done" />
            </div>
          ) : selectedProject && taskId && !isLiaisonLane ? (
            <CopyButton
              text={buildObserveSessionComplete({
                agent: agent.name,
                projectKey: selectedProject,
                taskId,
                exitCode: 0,
              })}
              label="Copy session done"
            />
          ) : null}
          {executorGated ? (
            <p className="text-xs text-liaison-warning">
              Intake not ready for executors — resolve blockers or use soft-ready path when profile/tier
              allows.
            </p>
          ) : null}
          {!taskId ? (
            <p className="text-xs text-liaison-warning">Select a task in the playbook to bind reporter bundle.</p>
          ) : null}
          {terminalNote ? (
            <p className="text-xs text-liaison-on-surface-variant">{terminalNote}</p>
          ) : null}
          <p className="text-xs text-liaison-on-surface-variant">
            {isLiaisonLane
              ? "Liaison lane — governance and flywheel workflows; not a separate runtime agent."
              : "Run executors in a terminal pane — browser copies launch lines only."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
