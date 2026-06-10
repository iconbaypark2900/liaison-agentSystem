"use client";

import { useState } from "react";

import { useCommandCenter } from "@/context/CommandCenterContext";
import type { ProjectRegistryEntry } from "@/lib/command-center-types";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

function RegistryRowCards({
  entry,
  focused,
}: {
  entry: ProjectRegistryEntry;
  focused: boolean;
}) {
  const intake = focused ? "See intake panel above when focused." : entry.liaison_cmd_intake;
  const plan = focused ? "See plan panel above when focused." : entry.liaison_cmd_plan;

  return (
    <div className="grid md:grid-cols-3 gap-3 mt-3 text-sm">
      <div className="rounded-lg border border-liaison-outline-variant/50 p-3">
        <p className="text-xs uppercase text-liaison-on-surface-variant mb-1">Intake</p>
        <p className="text-xs">
          Brief {entry.has_brief ? "✓" : "○"} · Phase {entry.has_phase ? "✓" : "○"}
        </p>
        <div className="mt-2 flex gap-2 items-center">
          <code className="mono text-xs flex-1 truncate">{intake}</code>
          {!focused ? <CopyButton text={entry.liaison_cmd_intake} /> : null}
        </div>
      </div>
      <div className="rounded-lg border border-liaison-outline-variant/50 p-3">
        <p className="text-xs uppercase text-liaison-on-surface-variant mb-1">Operating plan</p>
        <p className="text-xs">
          {entry.has_on_disk_plan
            ? "On disk"
            : entry.has_registry_plan
              ? `Tier ${entry.plan_tier ?? "?"}`
              : "Missing"}
        </p>
        <div className="mt-2 flex gap-2 items-center">
          <code className="mono text-xs flex-1 truncate">{plan}</code>
          {!focused ? <CopyButton text={entry.liaison_cmd_plan} /> : null}
        </div>
      </div>
      <div className="rounded-lg border border-liaison-outline-variant/50 p-3">
        <p className="text-xs uppercase text-liaison-on-surface-variant mb-1">Build corpus</p>
        <p className="text-xs text-liaison-on-surface-variant">
          {focused
            ? "Traces and recipes when project focused on /."
            : "Focus project on Command Center for corpus summary."}
        </p>
        <div className="mt-2 flex gap-2 items-center">
          <code className="mono text-xs flex-1 truncate">{entry.liaison_cmd_focus}</code>
          <CopyButton text={entry.liaison_cmd_focus} label="Focus" />
        </div>
      </div>
    </div>
  );
}

export function WorkstreamProjectReport() {
  const { state, selectedProject } = useCommandCenter();
  const [expandedKey, setExpandedKey] = useState<string | null>(selectedProject);

  const registry = state?.projects_registry ?? [];
  if (!registry.length) return null;

  const focusedCorpus = state?.build_corpus_summary;
  const focusedIntake = state?.project_intake;
  const focusedPlan = state?.project_plan;

  return (
    <Panel
      eyebrow="Portfolio"
      title="Registered projects"
      purpose="Expand a row for intake, plan, and corpus copy targets."
      className="mb-6"
    >
      <ul className="space-y-2">
        {registry.map((entry) => {
          const expanded = expandedKey === entry.key;
          const focused = selectedProject === entry.key;
          return (
            <li
              key={entry.key}
              className="rounded-lg border border-liaison-outline-variant/50 overflow-hidden"
            >
              <button
                type="button"
                onClick={() => setExpandedKey(expanded ? null : entry.key)}
                className="w-full flex flex-wrap items-center gap-2 px-3 py-2 text-left hover:bg-liaison-surface-container/50"
              >
                <span className="font-medium">{entry.label}</span>
                <span className="text-xs text-liaison-on-surface-variant">
                  {entry.lifecycle}/{entry.phase} · score {entry.score}
                </span>
                {focused ? (
                  <span className="text-xs text-liaison-teal ml-auto">focused</span>
                ) : (
                  <span className="text-xs text-liaison-on-surface-variant ml-auto">
                    {expanded ? "▾" : "▸"}
                  </span>
                )}
              </button>
              {expanded || focused ? (
                <div className="px-3 pb-3 border-t border-liaison-outline-variant/30">
                  {focused && focusedIntake ? (
                    <p className="text-xs mt-2">
                      Intake: {focusedIntake.intake_ready ? "ready" : "blocked"} · Build:{" "}
                      {focusedIntake.ready_to_build ? "ready" : "pending"}
                    </p>
                  ) : null}
                  {focused && focusedPlan ? (
                    <p className="text-xs">
                      Plan: {focusedPlan.workflow} ·{" "}
                      {focusedPlan.has_on_disk_plan ? "on disk" : "registry"}
                    </p>
                  ) : null}
                  {focused && focusedCorpus ? (
                    <p className="text-xs mb-2">
                      Corpus: {focusedCorpus.build_steps_recorded ?? 0} steps ·{" "}
                      {focusedCorpus.exported_recipes ?? 0} recipes
                    </p>
                  ) : null}
                  <RegistryRowCards entry={entry} focused={focused} />
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
