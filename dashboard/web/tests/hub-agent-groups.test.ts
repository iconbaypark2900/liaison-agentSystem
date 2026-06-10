import { describe, expect, it } from "vitest";

import { groupAgentRows, hubAgentGroupId } from "@/lib/hub-agent-groups";
import type { AgentRow } from "@/lib/command-center-types";

function row(name: string): AgentRow {
  return {
    name,
    display: name,
    status: "Idle",
    registry_status: "active",
    tasks: 0,
    launch: "—",
  };
}

describe("hubAgentGroupId", () => {
  it("classifies executors", () => {
    expect(hubAgentGroupId("hermes")).toBe("executors");
    expect(hubAgentGroupId("unsloth_studio")).toBe("executors");
  });

  it("classifies liaison lanes", () => {
    expect(hubAgentGroupId("liaison")).toBe("liaison_lanes");
    expect(hubAgentGroupId("data_flywheel")).toBe("liaison_lanes");
  });

  it("classifies exceptional phase CLIs", () => {
    expect(hubAgentGroupId("codex")).toBe("exceptional_phase");
  });
});

describe("groupAgentRows", () => {
  it("orders groups and preserves agents", () => {
    const agents = [
      row("claude"),
      row("hermes"),
      row("data_flywheel"),
      row("liaison"),
    ];
    const { grouped, other } = groupAgentRows(agents);
    expect(other).toHaveLength(0);
    expect(grouped.map((g) => g.group.id)).toEqual([
      "executors",
      "liaison_lanes",
      "exceptional_phase",
    ]);
    expect(grouped.find((g) => g.group.id === "executors")!.agents[0].name).toBe(
      "hermes"
    );
  });
});
