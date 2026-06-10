import { describe, expect, it } from "vitest";

import type { AgentRow, ProjectAgentPattern } from "@/lib/command-center-types";
import {
  buildAttachTemplate,
  buildHandoffPlayBlock,
  buildInitTemplate,
  buildOpenInTerminalScript,
  buildPatternPlayBlock,
  buildReporterBundle,
  buildReporterChecklistSteps,
  buildStartPatternCmd,
  buildValidateHint,
  handoffChainEdges,
  handoffChainsForAgent,
  reporterStepGlyph,
  suggestPatternTaskId,
} from "@/lib/operator-templates";

const sampleAgent: AgentRow = {
  name: "hermes",
  display: "hermes",
  status: "Active",
  registry_status: "active",
  tasks: 2,
  launch: "hermes",
  role: "engineer",
};

const samplePattern: ProjectAgentPattern = {
  id: "hermes-led-slice",
  label: "Hermes-led with specialist reports",
  agents: ["hermes", "qca"],
  when: "Default product engineering",
  steps: ["Hermes implements", "liaison attach qca"],
};

describe("buildAttachTemplate", () => {
  it("includes agent name and paste placeholder", () => {
    expect(buildAttachTemplate("qca")).toContain("liaison attach qca");
    expect(buildAttachTemplate("qca")).toContain("<paste agent output>");
  });
});

describe("buildReporterBundle", () => {
  it("includes cd hint, init, attach, validate", () => {
    const bundle = buildReporterBundle({
      projectPath: "/spark/my-repo",
      agent: sampleAgent,
      taskId: "t1",
      description: "Fix bug",
      defaultProfile: "python",
    });
    expect(bundle).toContain("cd /spark/my-repo");
    expect(bundle).toContain('liaison init t1 "Fix bug"');
    expect(bundle).toContain("liaison attach hermes");
    expect(bundle).toContain("liaison validate --profile python");
  });
});

describe("buildOpenInTerminalScript", () => {
  it("combines launch and liaison next steps", () => {
    const script = buildOpenInTerminalScript(sampleAgent);
    expect(script).toContain("hermes");
    expect(script).toContain("liaison attach hermes");
    expect(script).toContain("liaison validate");
  });
});

describe("buildStartPatternCmd", () => {
  it("formats start-pattern with task id and description", () => {
    const cmd = buildStartPatternCmd(samplePattern, "my-task", "My desc");
    expect(cmd).toBe(
      'liaison start-pattern hermes-led-slice --task-id my-task --description "My desc"'
    );
  });

  it("suggests task id when omitted", () => {
    const cmd = buildStartPatternCmd(samplePattern);
    expect(cmd).toContain("liaison start-pattern hermes-led-slice --task-id hermes-led-slice-");
  });
});

describe("suggestPatternTaskId", () => {
  it("prefixes pattern id", () => {
    expect(suggestPatternTaskId(samplePattern)).toMatch(/^hermes-led-slice-/);
  });
});

describe("buildValidateHint", () => {
  it("omits profile when none", () => {
    expect(buildValidateHint("none")).toBe("liaison validate");
  });
});

describe("buildReporterChecklistSteps", () => {
  it("returns six workflow steps with commands", () => {
    const steps = buildReporterChecklistSteps({ defaultProfile: "backend" });
    expect(steps.map((s) => s.id)).toEqual([
      "init",
      "snapshot",
      "attach",
      "approve",
      "validate",
      "close",
    ]);
    expect(steps.find((s) => s.id === "validate")?.cmd).toContain("backend");
  });
});

describe("buildInitTemplate", () => {
  it("quotes description", () => {
    expect(buildInitTemplate("abc", "Do thing")).toBe('liaison init abc "Do thing"');
  });
});

describe("buildPatternPlayBlock", () => {
  it("includes start-pattern, snapshot, and steps", () => {
    const block = buildPatternPlayBlock(samplePattern, "tid-1", "/repo");
    expect(block).toContain("cd /repo");
    expect(block).toContain("liaison start-pattern hermes-led-slice --task-id tid-1");
    expect(block).toContain("liaison snapshot --show");
    expect(block).toContain("Hermes implements");
  });
});

describe("reporterStepGlyph", () => {
  it("maps done and pending", () => {
    expect(reporterStepGlyph(true)).toBe("✓");
    expect(reporterStepGlyph(false)).toBe("○");
    expect(reporterStepGlyph(false, true)).toBe("!");
  });
});

describe("buildReporterBundle snapshot", () => {
  it("includes snapshot line when taskId bound", () => {
    const bundle = buildReporterBundle({
      projectPath: "/r",
      agent: sampleAgent,
      taskId: "t99",
    });
    expect(bundle).toContain("liaison snapshot --show");
    expect(bundle).toContain("task_id: t99");
  });
});

const sampleChain = {
  name: "ML Intern → QCA → Hermes",
  agents: ["ml_intern", "qca", "hermes"],
  when: "Benchmark → review → integrate",
};

describe("handoff play blocks", () => {
  it("handoffChainEdges returns adjacent pairs", () => {
    expect(handoffChainEdges(sampleChain)).toEqual([
      { from: "ml_intern", to: "qca" },
      { from: "qca", to: "hermes" },
    ]);
  });

  it("handoffChainsForAgent filters chains", () => {
    const chains = [sampleChain, { name: "QCA only", agents: ["qca", "hermes"], when: "x" }];
    expect(handoffChainsForAgent(chains, "qca")).toHaveLength(2);
    expect(handoffChainsForAgent(chains, "unsloth_studio")).toHaveLength(0);
  });

  it("buildHandoffPlayBlock includes attach for both agents", () => {
    const block = buildHandoffPlayBlock({
      chain: sampleChain,
      fromAgent: "ml_intern",
      toAgent: "qca",
      projectPath: "/spark/sigma",
      taskId: "t-handoff",
      defaultProfile: "sigma",
    });
    expect(block).toContain("ml_intern → qca");
    expect(block).toContain("liaison attach ml_intern");
    expect(block).toContain("liaison attach qca");
    expect(block).toContain("liaison validate --profile sigma");
  });
});
