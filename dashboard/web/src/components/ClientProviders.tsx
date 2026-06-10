"use client";

import type { ReactNode } from "react";

import { CommandCenterProvider } from "@/context/CommandCenterContext";
import { ThemeProvider } from "@/context/ThemeContext";
import AppLayout from "@/components/shell/AppLayout";

export function ClientProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <CommandCenterProvider>
        <AppLayout>{children}</AppLayout>
      </CommandCenterProvider>
    </ThemeProvider>
  );
}
