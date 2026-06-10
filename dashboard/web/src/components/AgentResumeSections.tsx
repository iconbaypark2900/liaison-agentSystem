"use client";

import type { ReactNode } from "react";

import type { RolodexResume } from "@/lib/command-center-types";

function ResumeSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-liaison-on-surface-variant mb-1">
        {title}
      </p>
      {children}
    </div>
  );
}

export function AgentResumeSections({ resume }: { resume: RolodexResume }) {
  const caps = resume.capabilities ?? [];
  return (
    <div className="space-y-3">
      {resume.headline &&
      resume.summary &&
      resume.headline !== resume.summary.slice(0, resume.headline.length) ? (
        <ResumeSection title="Headline">
          <p className="text-sm leading-relaxed font-medium">{resume.headline}</p>
        </ResumeSection>
      ) : null}
      {resume.summary ? (
        <ResumeSection title="Profile">
          <p className="text-sm leading-relaxed">{resume.summary}</p>
        </ResumeSection>
      ) : null}
      {caps.length > 0 ? (
        <ResumeSection title="Capabilities">
          <ul className="list-disc list-inside space-y-1 text-sm leading-relaxed">
            {caps.map((cap) => (
              <li key={cap}>{cap}</li>
            ))}
          </ul>
        </ResumeSection>
      ) : null}
      {resume.best_for ? (
        <ResumeSection title="Best for">
          <p className="text-sm leading-relaxed">{resume.best_for}</p>
        </ResumeSection>
      ) : null}
      {resume.when_to_use ? (
        <ResumeSection title="When to use">
          <p className="text-sm leading-relaxed">{resume.when_to_use}</p>
        </ResumeSection>
      ) : null}
      {resume.outputs ? (
        <ResumeSection title="Outputs">
          <p className="text-sm leading-relaxed">{resume.outputs}</p>
        </ResumeSection>
      ) : null}
      {resume.limits ? (
        <ResumeSection title="Limits">
          <p className="text-sm leading-relaxed">{resume.limits}</p>
        </ResumeSection>
      ) : null}
    </div>
  );
}
