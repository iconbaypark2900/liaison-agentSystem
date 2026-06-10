import { describe, expect, it } from "vitest";

import {
  confirmLiaisonRun,
  confirmReporterStepAdvance,
  liaisonCmdNeedsConfirm,
} from "@/lib/liaison-run-client";

describe("liaison-run-client", () => {
  it("flags allowlisted write commands", () => {
    expect(liaisonCmdNeedsConfirm("liaison validate --profile python")).toBe(true);
    expect(liaisonCmdNeedsConfirm("liaison approve-artifact foo.md")).toBe(true);
    expect(liaisonCmdNeedsConfirm("liaison close-task --task-id t1")).toBe(true);
    expect(liaisonCmdNeedsConfirm("liaison start-pattern hermes-led")).toBe(true);
    expect(liaisonCmdNeedsConfirm("liaison status")).toBe(false);
  });

  it("skips confirm when window is unavailable", () => {
    expect(confirmLiaisonRun({ cmd: "liaison status" })).toBe(true);
    expect(confirmReporterStepAdvance({ project: "sigma", currentStep: "validate" })).toBe(true);
  });
});
