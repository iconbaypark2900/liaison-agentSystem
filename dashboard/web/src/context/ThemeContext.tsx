"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type ThemePreference = "dark" | "light" | "system";

const ThemeContext = createContext<{
  preference: ThemePreference;
  cycle: () => void;
}>({ preference: "dark", cycle: () => {} });

function applyTheme(pref: ThemePreference) {
  const root = document.documentElement;
  const dark =
    pref === "dark" ||
    (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  root.classList.toggle("dark", dark);
  root.classList.toggle("light", !dark);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<ThemePreference>("dark");

  useEffect(() => {
    try {
      const stored = localStorage.getItem("liaison-theme") as ThemePreference | null;
      if (stored) setPreference(stored);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    applyTheme(preference);
  }, [preference]);

  const cycle = useCallback(() => {
    setPreference((p) => {
      const next: ThemePreference =
        p === "dark" ? "light" : p === "light" ? "system" : "dark";
      try {
        localStorage.setItem("liaison-theme", next);
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ preference, cycle }}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
