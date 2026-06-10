"use client";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { CopyButton } from "./CopyButton";
import { Panel } from "./Panel";

export function BuildCorpusPanel() {
  const { state, selectedProject } = useCommandCenter();
  const corpus = state?.build_corpus_summary;
  if (!selectedProject || !corpus) return null;

  const recordCmd =
    corpus.liaison_record ??
    'liaison record-build --agent hermes --action "<step>" --outcome "<result>"';
  const exportCmd =
    corpus.liaison_export ??
    `liaison export-agent-recipe --from-project ${selectedProject} --write`;

  return (
    <Panel
      eyebrow="Build corpus"
      title={`Traces & recipes · ${selectedProject}`}
      purpose="Record build steps during slices; export an agent recipe when patterns stabilize."
    >
      <div className="flex flex-wrap gap-2 text-sm mb-3">
        <span className="font-medium">
          {corpus.build_steps_recorded ?? 0} build step
          {(corpus.build_steps_recorded ?? 0) === 1 ? "" : "s"}
        </span>
        <span className="text-liaison-on-surface-variant">·</span>
        <span>{corpus.open_tasks_with_build_trace ?? 0} open w/ trace</span>
        <span className="text-liaison-on-surface-variant">·</span>
        <span>{corpus.exported_recipes ?? 0} exported recipe(s)</span>
        {corpus.recommended_pattern ? (
          <>
            <span className="text-liaison-on-surface-variant">·</span>
            <span className="text-xs">Pattern {corpus.recommended_pattern}</span>
          </>
        ) : null}
      </div>

      <div className="grid md:grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg border border-liaison-outline-variant/50 p-3">
          <p className="text-xs uppercase text-liaison-on-surface-variant mb-1">Record build step</p>
          <p className="text-xs text-liaison-on-surface-variant mb-2">
            Append to BUILD_TRACE.md on the active task after Hermes or specialists ship code.
          </p>
          <div className="flex gap-2 items-center">
            <code className="mono text-xs flex-1 truncate">{recordCmd}</code>
            <CopyButton text={recordCmd} />
          </div>
        </div>
        <div className="rounded-lg border border-liaison-outline-variant/50 p-3">
          <p className="text-xs uppercase text-liaison-on-surface-variant mb-1">Export agent recipe</p>
          <p className="text-xs text-liaison-on-surface-variant mb-2">
            Aggregate traces, learnings, and pattern into registry/recipes/.
          </p>
          <div className="flex gap-2 items-center">
            <code className="mono text-xs flex-1 truncate">{exportCmd}</code>
            <CopyButton text={exportCmd} />
          </div>
        </div>
      </div>
    </Panel>
  );
}
