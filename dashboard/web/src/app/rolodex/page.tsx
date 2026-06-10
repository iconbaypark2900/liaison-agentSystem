"use client";

import { CommandCenterFooter } from "@/components/CommandCenterFooter";
import { GateStrip } from "@/components/GateStrip";
import { RolodexPanel } from "@/components/RolodexPanel";

export default function RolodexPage() {
  return (
    <>
      <GateStrip />
      <RolodexPanel />
      <CommandCenterFooter />
    </>
  );
}
