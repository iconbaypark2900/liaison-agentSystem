import { describe, expect, it } from "vitest";

import {
  filterProjectMatrix,
  firstRunnableWorkflowCommand,
  formatGatePhase,
  formatValidationStatus,
  isBrowserWorkflowRunAllowlisted,
  reporterAutoAdvanceOptIn,
  reporterStepAdvanceEnabled,
  sortProjectMatrix,
  sortProjectMatrixBy,
  suggestedWorkflowCommandEnabled,
  suggestedWorkflowCommandRunnable,
  workflowIntakeGateOpen,
} from "@/lib/command-center-helpers";
import type { CommandCenterState, ProjectMatrixRow } from "@/lib/command-center-types";

const sampleMatrix: ProjectMatrixRow[] = [
  {
    option: "b",
    label: "B",
    score: 40,
    confidence: 50,
    impact: "Med",
    effort: "Med",
    contributors: "x",
    phase: "alpha",
    lifecycle: "classified",
  },
  {
    option: "a",
    label: "A",
    score: 90,
    confidence: 80,
    impact: "High",
    effort: "Low",
    contributors: "y",
    phase: "beta",
    lifecycle: "classified",
  },
];

describe("sortProjectMatrix", () => {
  it("sorts by score descending", () => {
    const sorted = sortProjectMatrix(sampleMatrix);
    expect(sorted[0].option).toBe("a");
  });
});

describe("filterProjectMatrix", () => {
  it("filters by project key substring", () => {
    const filtered = filterProjectMatrix(sampleMatrix, "high");
    expect(filtered).toHaveLength(1);
    expect(filtered[0].option).toBe("a");
  });
});

describe("sortProjectMatrixBy", () => {
  it("sorts by label ascending", () => {
    const sorted = sortProjectMatrixBy(sampleMatrix, "label");
    expect(sorted[0].option).toBe("a");
  });
});

describe("formatGatePhase", () => {
  it("uses focus when present", () => {
    const state = {
      focus: {
        project: "x",
        lifecycle: "classified",
        phase: "beta",
      },
      project_matrix: sampleMatrix,
    } as unknown as CommandCenterState;
    expect(formatGatePhase(state)).toBe("classified/beta");
  });
});

describe("formatValidationStatus", () => {
  it("returns fail when blockers", () => {
    const state = {
      summary: { blockers: 2 },
      engineering_metrics: { gate_failures: 0 },
    } as unknown as CommandCenterState;
    expect(formatValidationStatus(state)).toBe("fail");
  });
});

describe("suggestedWorkflowCommandEnabled", () => {
  const base = {
    summary: { ready_to_build_soft: false, executor_launch_ready: false },
    kanban: { todo: [], in_progress: [], review: [], done: [] },
    reporter_step_state: { current_step_id: "validate", completed_steps: [], allowed_next: [] },
  } as unknown as CommandCenterState;

  it("blocks when intake gate closed", () => {
    expect(workflowIntakeGateOpen(base)).toBe(false);
    expect(suggestedWorkflowCommandEnabled(base, "liaison snapshot --show")).toBe(false);
  });

  it("allows non-close when soft ready", () => {
    const state = {
      ...base,
      summary: { ready_to_build_soft: true, executor_launch_ready: false },
    } as unknown as CommandCenterState;
    expect(suggestedWorkflowCommandEnabled(state, "liaison snapshot --show")).toBe(true);
  });

  it("blocks close-task until validate complete", () => {
    const state = {
      ...base,
      summary: { ready_to_build_soft: true, executor_launch_ready: false },
    } as unknown as CommandCenterState;
    expect(suggestedWorkflowCommandEnabled(state, "liaison close-task")).toBe(false);
    const ready = {
      ...state,
      reporter_step_state: {
        current_step_id: "close",
        completed_steps: ["validate"],
        allowed_next: [],
      },
    } as unknown as CommandCenterState;
    expect(suggestedWorkflowCommandEnabled(ready, "liaison close-task")).toBe(true);
  });
});

describe("isBrowserWorkflowRunAllowlisted", () => {
  it("allows validate, approve-artifact, close-task, start-pattern", () => {
    expect(isBrowserWorkflowRunAllowlisted("liaison validate --profile python")).toBe(true);
    expect(isBrowserWorkflowRunAllowlisted("liaison approve-artifact report.md")).toBe(true);
    expect(isBrowserWorkflowRunAllowlisted("liaison close-task")).toBe(true);
    expect(isBrowserWorkflowRunAllowlisted("liaison start-pattern hermes-led-slice")).toBe(true);
    expect(isBrowserWorkflowRunAllowlisted("liaison snapshot --show")).toBe(false);
    expect(isBrowserWorkflowRunAllowlisted("liaison attach hermes --text hi")).toBe(false);
  });
});

describe("suggestedWorkflowCommandRunnable", () => {
  const ready = {
    summary: { ready_to_build_soft: true, executor_launch_ready: false },
    kanban: { todo: [], in_progress: [], review: [], done: [] },
    reporter_step_state: {
      current_step_id: "validate",
      completed_steps: ["validate"],
      allowed_next: ["close"],
    },
    suggested_workflow_commands: [
      "liaison validate --profile python",
      "liaison snapshot --show",
      "liaison close-task",
    ],
  } as unknown as CommandCenterState;

  it("requires allowlist and gates", () => {
    expect(suggestedWorkflowCommandRunnable(ready, "liaison validate --profile python")).toBe(
      true
    );
    expect(suggestedWorkflowCommandRunnable(ready, "liaison snapshot --show")).toBe(false);
    expect(suggestedWorkflowCommandRunnable(ready, "liaison close-task")).toBe(true);
  });

  it("picks first runnable workflow command", () => {
    expect(firstRunnableWorkflowCommand(ready)).toBe("liaison validate --profile python");
  });
});

describe("reporterStepAdvanceEnabled", () => {
  const base = {
    summary: { ready_to_build_soft: true, executor_launch_ready: false },
    project_plan: { reporter_auto_advance: true },
    reporter_step_state: {
      current_step_id: "snapshot",
      completed_steps: ["init"],
      allowed_next: ["attach"],
    },
    handoffs: [],
  } as unknown as CommandCenterState;

  it("requires opt-in and allowed_next", () => {
    expect(reporterAutoAdvanceOptIn(base)).toBe(true);
    expect(reporterStepAdvanceEnabled(base)).toBe(true);
    expect(
      reporterStepAdvanceEnabled({
        ...base,
        project_plan: { reporter_auto_advance: false },
      } as CommandCenterState)
    ).toBe(false);
  });

  it("blocks approve step with pending handoffs", () => {
    const blocked = {
      ...base,
      reporter_step_state: {
        current_step_id: "approve",
        completed_steps: ["attach"],
        allowed_next: ["validate"],
      },
      handoffs: [{ status: "pending_approval" }],
    } as unknown as CommandCenterState;
    expect(reporterStepAdvanceEnabled(blocked)).toBe(false);
  });
});
