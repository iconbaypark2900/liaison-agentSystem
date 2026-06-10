import { describe, expect, it } from "vitest";

import type { ProjectIntake, ProjectIntakeCheck } from "@/lib/command-center-types";

function intakeReadyFromChecks(checks: ProjectIntakeCheck[]): boolean {
  return checks.filter((c) => c.severity === "critical").every((c) => c.pass);
}

describe("intake readiness", () => {
  it("requires all critical checks to pass", () => {
    const checks: ProjectIntakeCheck[] = [
      {
        id: "project_brief",
        severity: "critical",
        pass: true,
        label: "Brief",
        detail: "ok",
      },
      {
        id: "task_hygiene",
        severity: "critical",
        pass: false,
        label: "Tasks",
        detail: "missing",
      },
    ];
    expect(intakeReadyFromChecks(checks)).toBe(false);
  });

  it("allows warn failures when only critical considered", () => {
    const checks: ProjectIntakeCheck[] = [
      {
        id: "project_brief",
        severity: "critical",
        pass: true,
        label: "Brief",
        detail: "ok",
      },
      {
        id: "current_state",
        severity: "warn",
        pass: false,
        label: "State",
        detail: "stale",
      },
    ];
    expect(intakeReadyFromChecks(checks)).toBe(true);
  });
});

describe("project intake fixture shape", () => {
  it("matches command-center JSON contract", () => {
    const intake: ProjectIntake = {
      project: "demo",
      path: "/tmp/demo",
      generated_at: "2026-05-31T00:00:00",
      intake_ready: false,
      ready_to_build: false,
      recommended_lane: "research",
      checks: [],
      blockers: [
        {
          id: "project_brief",
          severity: "critical",
          label: "Project brief filled",
          detail: "missing",
          liaison_cmd: "liaison memory-init",
        },
      ],
    };
    expect(intake.blockers[0].liaison_cmd).toContain("memory-init");
    expect(intake.recommended_lane).toBe("research");
  });
});
