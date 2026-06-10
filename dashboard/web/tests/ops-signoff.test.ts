import { describe, expect, it } from "vitest";

import type { OpsSignoff } from "@/lib/command-center-types";

const sampleSignoff: OpsSignoff = {
  pending_handoffs: [],
  pending_handoff_count: 0,
  gate_failures: 0,
  flywheel_open: 0,
  debrief_age: "2.1h ago",
  debrief_count: 3,
  ready_for_signoff: true,
  checklist: [
    {
      id: "signoff:handoffs",
      label: "Clear 0 pending handoff(s)",
      done: true,
      liaison_cmd: "liaison look",
    },
  ],
  copy_hints: [{ label: "Approve artifact", liaison_cmd: "liaison approve-artifact foo.md" }],
};

describe("ops_signoff shape", () => {
  it("includes checklist and copy hints for OpsSignoffPanel", () => {
    expect(sampleSignoff.checklist.length).toBeGreaterThan(0);
    expect(sampleSignoff.copy_hints[0].liaison_cmd).toMatch(/^liaison /);
    expect(typeof sampleSignoff.ready_for_signoff).toBe("boolean");
  });
});
