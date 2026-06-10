"use client";

import Link from "next/link";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";
import { StatusPill } from "./StatusPill";

export function ProjectDetailPanel({ compact = false }: { compact?: boolean }) {
  const { state, selectedProject, setSelectedProject } = useCommandCenter();
  const detail = state?.project_detail;

  if (!selectedProject) {
    return (
      <Panel
        eyebrow="Portfolio"
        title="Project detail"
        purpose="Select a project to see goals, agents, skills, and production path."
        className={compact ? "" : "mb-4"}
      >
        <p className="text-sm text-liaison-on-surface-variant">
          Use the matrix or{" "}
          <Link href="/projects" className="text-liaison-primary">
            Projects
          </Link>{" "}
          page for the full registry.
        </p>
        <ul className="mt-3 space-y-1 text-xs">
          {(state?.project_portfolio ?? []).slice(0, 8).map((row) => (
            <li key={row.key}>
              <button
                type="button"
                onClick={() => setSelectedProject(row.key)}
                className="text-left hover:text-liaison-primary w-full"
              >
                <span className="font-medium">{row.label}</span>
                <span className="text-liaison-on-surface-variant ml-2">
                  {row.agent_chain}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>
    );
  }

  if (!detail) {
    return (
      <Panel title={`Project · ${selectedProject}`}>
        <p className="text-sm text-liaison-on-surface-variant">Loading project detail…</p>
      </Panel>
    );
  }

  return (
    <Panel
      eyebrow="Portfolio"
      title={detail.label}
      purpose="What this project is for, which agents and skills to use, and how to reach production readiness."
      className={compact ? "" : "mb-4"}
    >
      <p className="text-sm leading-relaxed mb-4">{detail.intent}</p>

      <div className="grid sm:grid-cols-2 gap-3 text-sm mb-4">
        <div>
          <p className="text-[10px] uppercase text-liaison-on-surface-variant">Workflow</p>
          <p>{detail.workflow ?? "—"}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase text-liaison-on-surface-variant">Pattern</p>
          <p>{detail.pattern ?? "—"}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase text-liaison-on-surface-variant">Agents</p>
          <p className="mono text-xs">{detail.agent_chain}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase text-liaison-on-surface-variant">Validation</p>
          <p>{detail.validation_profile ?? "none"}</p>
        </div>
      </div>

      {detail.specialists.length > 0 ? (
        <p className="text-xs mb-4">
          <span className="text-liaison-on-surface-variant">Specialists: </span>
          {detail.specialists.join(", ")}
        </p>
      ) : null}

      <div className="mb-4">
        <p className="text-[10px] uppercase tracking-wide text-liaison-on-surface-variant mb-2">
          Production readiness
        </p>
        <ul className="space-y-1">
          {detail.production_checklist.map((item) => (
            <li key={item.id} className="flex items-center gap-2 text-sm">
              <StatusPill status={item.done ? "pass" : "warn"}>
                {item.done ? "✓" : "○"}
              </StatusPill>
              <span>{item.label}</span>
              {item.detail ? (
                <span className="text-xs text-liaison-on-surface-variant">({item.detail})</span>
              ) : null}
            </li>
          ))}
        </ul>
      </div>

      {detail.research_summary ? (
        <div className="mb-4 rounded-lg border border-liaison-outline-variant/50 p-3">
          <p className="text-[10px] uppercase text-liaison-on-surface-variant mb-1">
            Research before build
          </p>
          <p className="text-sm leading-relaxed">{detail.research_summary}</p>
          <ul className="mt-2 space-y-1">
            {detail.research_commands.map((cmd) => (
              <li key={cmd} className="flex gap-2 items-center text-xs">
                <code className="mono flex-1 truncate">{cmd}</code>
                {!cmd.startsWith("#") ? <CopyButton text={cmd} /> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {detail.skills.length > 0 ? (
        <div className="mb-4">
          <p className="text-[10px] uppercase text-liaison-on-surface-variant mb-1">
            Skills to utilize
          </p>
          <ul className="list-disc list-inside text-sm space-y-0.5">
            {detail.skills.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {detail.backlog.length > 0 && !compact ? (
        <div className="mb-4">
          <p className="text-[10px] uppercase text-liaison-on-surface-variant mb-1">Backlog</p>
          <ul className="list-disc list-inside text-xs text-liaison-on-surface-variant">
            {detail.backlog.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 pt-2 border-t border-liaison-outline-variant/30">
        <CopyButton text={detail.liaison_cmds.intake} label="Intake" />
        <CopyButton text={detail.liaison_cmds.plan} label="Plan" />
        <CopyButton text={detail.liaison_cmds.assess} label="Assess" />
        <Link
          href="/hub"
          className="text-xs px-2 py-1 rounded-md border border-liaison-outline-variant text-liaison-primary no-underline"
        >
          Hub workflows
        </Link>
      </div>
    </Panel>
  );
}
