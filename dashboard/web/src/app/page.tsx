"use client";

import { CommandCenterFooter } from "@/components/CommandCenterFooter";
import { CommandCenterTabs } from "@/components/CommandCenterTabs";
import { GateStrip } from "@/components/GateStrip";
import { useCommandCenter } from "@/context/CommandCenterContext";

export default function CommandCenterPage() {
  const { error, isInitialLoading, isRefreshing } = useCommandCenter();

  if (error) {
    return (
      <div className="panel text-liaison-error">
        <p className="font-semibold">Failed to load command center</p>
        <p className="text-sm mt-2">{error.message}</p>
        <p className="text-xs mt-2 text-liaison-on-surface-variant">
          Set LIAISON_ROOT in dashboard/web/.env.local and ensure liaison command-center --json works.
        </p>
      </div>
    );
  }

  return (
    <>
      <GateStrip />
      {isRefreshing && !isInitialLoading ? (
        <p className="text-[10px] uppercase tracking-wide text-liaison-on-surface-variant mb-2">
          Updating…
        </p>
      ) : null}
      <CommandCenterTabs />
      <CommandCenterFooter />
    </>
  );
}
