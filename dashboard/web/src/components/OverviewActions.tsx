"use client";

import Link from "next/link";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

export function OverviewActions() {
  const { state, selectedProject, isRefreshing, refresh } = useCommandCenter();
  if (!state?.overview_actions?.length) return null;

  const hubHref = selectedProject ? `/hub?project=${encodeURIComponent(selectedProject)}` : "/hub";
  const projectsHref = selectedProject
    ? `/projects?project=${encodeURIComponent(selectedProject)}`
    : "/projects";

  return (
    <Panel
      eyebrow="Playbook"
      title="Overview actions"
      purpose="Drive intake → plan → hub without leaving the command center."
      className="mb-4"
    >
      <ul className="space-y-2">
        {state.overview_actions.map((action) => {
          const isRefresh = action.kind === "refresh";
          return (
            <li
              key={action.id}
              className="flex flex-wrap items-start gap-2 rounded-lg border border-liaison-outline-variant/50 px-3 py-2 text-sm"
            >
              <div className="flex-1 min-w-[12rem]">
                <p className="font-medium">{action.label}</p>
                <p className="text-xs text-liaison-on-surface-variant mt-0.5">{action.detail}</p>
                {action.how_to ? (
                  <p className="text-xs leading-relaxed mt-2 text-liaison-on-surface-variant/90">
                    {action.how_to}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2 items-center">
                {isRefresh ? (
                  <button
                    type="button"
                    onClick={() => refresh(true)}
                    disabled={isRefreshing}
                    className="text-xs px-2 py-1 rounded-md border border-liaison-outline-variant hover:bg-liaison-surface-container text-liaison-primary disabled:opacity-50"
                  >
                    {isRefreshing ? "Syncing…" : "Sync liaison"}
                  </button>
                ) : null}
                {action.id === "action:hub" ? (
                  <Link
                    href={hubHref}
                    className="text-xs px-2 py-1 rounded-md border border-liaison-outline-variant hover:bg-liaison-surface-container text-liaison-primary no-underline"
                  >
                    Open hub
                  </Link>
                ) : null}
                {action.id === "action:pick-project" ? (
                  <Link
                    href={projectsHref}
                    className="text-xs px-2 py-1 rounded-md border border-liaison-outline-variant hover:bg-liaison-surface-container text-liaison-primary no-underline"
                  >
                    Projects
                  </Link>
                ) : null}
                {action.liaison_cmd && !isRefresh ? (
                  <CopyButton text={action.liaison_cmd} label="Copy cmd" />
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
