"use client";

import { CommandCenterFooter } from "@/components/CommandCenterFooter";
import { GateStrip } from "@/components/GateStrip";
import { OpsWorkspace } from "@/components/OpsWorkspace";
import { PanelSkeleton } from "@/components/PanelSkeleton";
import { useCommandCenter } from "@/context/CommandCenterContext";

export default function OpsPage() {
  const { isInitialLoading, isRefreshing } = useCommandCenter();

  if (isInitialLoading) {
    return (
      <>
        <GateStrip />
        <PanelSkeleton lines={10} />
      </>
    );
  }

  return (
    <>
      <GateStrip />
      {isRefreshing ? (
        <p className="text-[10px] uppercase text-liaison-on-surface-variant mb-2">Updating…</p>
      ) : null}
      <p className="text-xs text-liaison-on-surface-variant mb-3">
        Same Ops workspace as the home Command Center Ops tab — scroll-contained columns, signoff playbook
        first.
      </p>
      <OpsWorkspace showMetrics />
      <CommandCenterFooter />
    </>
  );
}
