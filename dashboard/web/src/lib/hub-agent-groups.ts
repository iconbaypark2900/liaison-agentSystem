import type { AgentRow } from "./command-center-types";

export type HubAgentGroupId = "executors" | "liaison_lanes" | "exceptional_phase";

export interface HubAgentGroup {
  id: HubAgentGroupId;
  label: string;
  description: string;
  agentNames: readonly string[];
}

export const AGENT_DISPLAY_NAMES: Record<string, string> = {
  data_flywheel: "Data flywheel (workflow)",
};

export const HUB_AGENT_GROUPS: HubAgentGroup[] = [
  {
    id: "executors",
    label: "Executors",
    description: "Domain work — code, research, calibration, training (run in terminal)",
    agentNames: ["hermes", "qca", "ml_intern", "unsloth_studio"],
  },
  {
    id: "liaison_lanes",
    label: "Liaison lanes",
    description: "Governance and flywheel workflows inside Liaison (not separate daemons)",
    agentNames: ["liaison", "data_flywheel"],
  },
  {
    id: "exceptional_phase",
    label: "Exceptional phase CLIs",
    description: "Phase-bound Spark Flow agents — prefer reporter + Hermes by default",
    agentNames: ["codex", "opencode", "claude"],
  },
];

const NAME_TO_GROUP = new Map<string, HubAgentGroupId>(
  HUB_AGENT_GROUPS.flatMap((g) => g.agentNames.map((n) => [n, g.id] as const))
);

export function hubAgentGroupId(name: string): HubAgentGroupId | "other" {
  return NAME_TO_GROUP.get(name) ?? "other";
}

export function groupAgentRows(agents: AgentRow[]): {
  grouped: { group: HubAgentGroup; agents: AgentRow[] }[];
  other: AgentRow[];
} {
  const byId = new Map<HubAgentGroupId, AgentRow[]>(
    HUB_AGENT_GROUPS.map((g) => [g.id, []])
  );
  const other: AgentRow[] = [];

  for (const agent of agents) {
    const gid = hubAgentGroupId(agent.name);
    if (gid === "other") {
      other.push(agent);
      continue;
    }
    byId.get(gid)!.push(agent);
  }

  const grouped = HUB_AGENT_GROUPS.map((group) => ({
    group,
    agents: byId.get(group.id) ?? [],
  })).filter((entry) => entry.agents.length > 0);

  return { grouped, other };
}
