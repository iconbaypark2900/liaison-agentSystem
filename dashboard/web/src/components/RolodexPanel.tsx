"use client";

import { useMemo, useState, type ReactNode } from "react";

import { useCommandCenter } from "@/context/CommandCenterContext";
import type { RolodexEntry } from "@/lib/command-center-types";
import { AgentResumeSections } from "./AgentResumeSections";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

const CATEGORIES = [
  { key: "skills", label: "Skills", hint: "Capabilities and playbooks" },
  { key: "subagents", label: "Subagents", hint: "Hub agents, workers, and handoff chains" },
  { key: "projects", label: "Projects", hint: "Registered repos and multi-agent patterns" },
  { key: "commands", label: "Commands", hint: "Liaison CLI verbs and workflows" },
  { key: "tools", label: "Tools", hint: "MCP tools, routes, and integrations" },
] as const;

type CategoryKey = (typeof CATEGORIES)[number]["key"];

function ResumeSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-liaison-on-surface-variant mb-1">
        {title}
      </p>
      {children}
    </div>
  );
}

function RolodexDetail({ entry }: { entry: RolodexEntry | null }) {
  if (!entry) {
    return (
      <p className="text-sm text-liaison-on-surface-variant">
        Select an entry to see workflow steps, actions, and reference paths.
      </p>
    );
  }

  const resume = entry.resume;
  const what = entry.what ?? entry.summary;
  const whenToUse = entry.when_to_use;
  const nextSteps =
    entry.next_steps ??
    (entry.actions ?? [])
      .filter((a) => a.liaison_cmd && !a.liaison_cmd.startsWith("#"))
      .map((a) => ({ label: a.label, liaison_cmd: a.liaison_cmd }));

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="font-semibold text-base">{entry.title}</h3>
        {entry.subtitle ? (
          <p className="text-liaison-on-surface-variant text-xs mt-1">{entry.subtitle}</p>
        ) : null}
      </div>

      {resume && (resume.summary || (resume.capabilities?.length ?? 0) > 0) ? (
        <AgentResumeSections resume={resume} />
      ) : (
        <>
          {what ? (
            <ResumeSection title="What">
              <p className="text-sm leading-relaxed">{what}</p>
            </ResumeSection>
          ) : null}
          {whenToUse ? (
            <ResumeSection title="When to use">
              <p className="text-sm leading-relaxed">{whenToUse}</p>
            </ResumeSection>
          ) : null}
        </>
      )}

      {nextSteps.length > 0 ? (
        <div>
          <p className="text-xs uppercase tracking-wide text-liaison-on-surface-variant mb-2">
            Next steps
          </p>
          <ol className="list-decimal list-inside space-y-2">
            {nextSteps.map((step) => (
              <li key={`${step.label}-${step.liaison_cmd ?? "note"}`} className="text-sm">
                <span className="font-medium">{step.label}</span>
                {step.liaison_cmd ? (
                  <div className="flex gap-2 items-center mt-1 ml-4">
                    <code className="mono text-xs flex-1 truncate text-liaison-on-surface-variant">
                      {step.liaison_cmd}
                    </code>
                    <CopyButton text={step.liaison_cmd} />
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {entry.path || entry.launch ? (
        <div className="pt-2 border-t border-liaison-outline-variant/30">
          <p className="text-xs uppercase tracking-wide text-liaison-on-surface-variant mb-1">
            Technical reference
          </p>
          {entry.path ? (
            <p className="text-xs text-liaison-on-surface-variant truncate" title={entry.path}>
              {entry.path}
            </p>
          ) : null}
          {entry.launch ? (
            <div className="flex gap-2 items-center mt-1">
              <code className="mono text-xs flex-1 truncate text-liaison-on-surface-variant">
                {entry.launch}
              </code>
              <CopyButton text={entry.launch} label="Copy command" />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function RolodexPanel({ compact = false }: { compact?: boolean }) {
  const { state } = useCommandCenter();
  const [category, setCategory] = useState<CategoryKey>("skills");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const entries = useMemo(() => {
    const catalog = state?.rolodex;
    if (!catalog) return [];
    return catalog[category] ?? [];
  }, [state?.rolodex, category]);

  const selected = useMemo(
    () => entries.find((e) => e.id === selectedId) ?? entries[0] ?? null,
    [entries, selectedId]
  );

  if (!state?.rolodex) return null;

  const intros = state?.rolodex_category_intros;
  const categoryIntro = intros?.[category];

  return (
    <Panel
      eyebrow="Rolodex"
      title={compact ? "Spec-driven reference" : "Skills · subagents · projects · commands · tools"}
      purpose="Rich detail with copy targets — same JSON as Textual rolodex tab."
      className={compact ? "" : "mb-6"}
    >
      <div className="flex flex-wrap gap-1 mb-4">
        {CATEGORIES.map((cat) => {
          const count = state.rolodex?.[cat.key]?.length ?? 0;
          const active = category === cat.key;
          return (
            <button
              key={cat.key}
              type="button"
              onClick={() => {
                setCategory(cat.key);
                setSelectedId(null);
              }}
              className={`text-xs px-2 py-1 rounded-md border text-left ${
                active
                  ? "border-liaison-primary bg-liaison-surface-container text-liaison-primary"
                  : "border-liaison-outline-variant text-liaison-on-surface-variant hover:bg-liaison-surface-container"
              }`}
              title={cat.hint}
            >
              <span className="block">
                {cat.label} ({count})
              </span>
              {active ? (
                <span className="block text-[10px] opacity-80 font-normal">{cat.hint}</span>
              ) : null}
            </button>
          );
        })}
      </div>

      {categoryIntro ? (
        <p className="text-sm leading-relaxed text-liaison-on-surface-variant mb-4 border-b border-liaison-outline-variant/30 pb-3">
          {categoryIntro.body}
        </p>
      ) : null}

      <div className={`grid gap-4 ${compact ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1 md:grid-cols-5"}`}>
        <ul
          className={`space-y-1 overflow-auto max-h-80 ${
            compact ? "lg:col-span-1" : "md:col-span-2"
          }`}
        >
          {entries.map((entry) => {
            const active = (selected?.id ?? entries[0]?.id) === entry.id;
            return (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(entry.id)}
                  className={`w-full text-left rounded-lg px-2 py-2 text-sm border ${
                    active
                      ? "border-liaison-primary bg-liaison-surface-container"
                      : "border-transparent hover:bg-liaison-surface-container/60"
                  }`}
                >
                  <span className="font-medium">{entry.title}</span>
                  {entry.recommended ? (
                    <span className="text-liaison-teal ml-1 text-xs">★</span>
                  ) : null}
                  {entry.subtitle ? (
                    <p className="text-xs text-liaison-on-surface-variant truncate">
                      {entry.subtitle}
                    </p>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
        <div className={compact ? "lg:col-span-1" : "md:col-span-3"}>
          <RolodexDetail entry={selected} />
        </div>
      </div>
    </Panel>
  );
}
