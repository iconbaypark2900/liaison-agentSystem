"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { Panel } from "./Panel";

export function WorkstreamBrief() {
  const { state, selectedProject } = useCommandCenter();
  const brief = state?.workstream_brief;
  if (!brief) return null;

  return (
    <Panel
      eyebrow="Workstream"
      title={brief.title}
      purpose="How to run the reporter path on the focused project and kanban task."
      className="mb-4"
    >
      <p className="text-sm leading-relaxed mb-3">{brief.body}</p>
      {brief.reporter_how_to ? (
        <div className="rounded-lg border border-liaison-primary/30 bg-liaison-surface-container/40 px-3 py-2 mb-4">
          <p className="text-xs uppercase tracking-wide text-liaison-primary mb-1">
            How to use (reporter path)
          </p>
          <p className="text-sm leading-relaxed">{brief.reporter_how_to}</p>
        </div>
      ) : null}
      {(brief.sections?.length ?? 0) > 0 ? (
        <div className="grid md:grid-cols-3 gap-3">
          {brief.sections!.map((section) => (
            <div
              key={section.title}
              className="rounded-lg border border-liaison-outline-variant/50 p-3 text-sm"
            >
              <p className="text-xs uppercase text-liaison-on-surface-variant mb-1">
                {section.title}
              </p>
              <p className="leading-relaxed">{section.body}</p>
              {(section.bullets?.length ?? 0) > 0 ? (
                <ul className="mt-2 space-y-1">
                  {section.bullets!.map((b) =>
                    b ? (
                      <li key={b} className="flex gap-2 items-start text-xs">
                        <code className="mono flex-1 truncate">{b}</code>
                      </li>
                    ) : null
                  )}
                </ul>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {!selectedProject ? (
        <p className="text-xs text-liaison-on-surface-variant mt-2">
          Open <strong>/projects</strong> or use the project matrix to focus a repo.
        </p>
      ) : null}
    </Panel>
  );
}
