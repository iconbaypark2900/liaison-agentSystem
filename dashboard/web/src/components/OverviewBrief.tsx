"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import type { PanelBriefSection } from "@/lib/command-center-types";
import { Panel } from "./Panel";

function BriefCard({ section }: { section: PanelBriefSection }) {
  return (
    <div className="rounded-lg border border-liaison-outline-variant/50 p-3 text-sm">
      <p className="text-xs uppercase tracking-wide text-liaison-on-surface-variant mb-1">
        {section.title}
      </p>
      <p className="leading-relaxed text-sm">{section.body}</p>
      {(section.bullets?.length ?? 0) > 0 ? (
        <ul className="mt-2 list-disc list-inside space-y-0.5 text-xs text-liaison-on-surface-variant">
          {section.bullets!.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function OverviewBrief() {
  const { state } = useCommandCenter();
  const brief = state?.overview_brief;
  if (!brief) return null;

  const steps = brief.playbook ?? [];

  return (
    <Panel
      eyebrow="Situation"
      title="Command center snapshot"
      purpose="Project, work, hub, patterns, and ops at a glance — before diving into tabs."
      className="mb-4"
    >
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
        <BriefCard section={brief.project} />
        <BriefCard section={brief.work} />
        <BriefCard section={brief.hub} />
        <BriefCard section={brief.patterns} />
        <BriefCard section={brief.ops} />
      </div>
      {steps.length > 0 ? (
        <div>
          <p className="text-xs uppercase tracking-wide text-liaison-on-surface-variant mb-2">
            Playbook
          </p>
          <ol className="list-decimal list-inside space-y-1 text-sm">
            {steps.map((step) => (
              <li key={step.id}>
                <span className="font-medium">{step.label}</span>
                <span className="text-liaison-on-surface-variant ml-1">— {step.detail}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </Panel>
  );
}
