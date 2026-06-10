"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { useCommandCenter } from "@/context/CommandCenterContext";
import { useTheme } from "@/context/ThemeContext";

const NAV = [
  { href: "/", label: "Command Center", icon: "dashboard" },
  { href: "/projects", label: "Projects", icon: "folder" },
  { href: "/hub", label: "Hub", icon: "hub" },
  { href: "/rolodex", label: "Rolodex", icon: "menu_book" },
  { href: "/ops", label: "Ops", icon: "inbox" },
  { href: "/settings", label: "Settings", icon: "settings" },
];

const SIDEBAR_KEY = "liaison-sidebar-collapsed";

function NavLink({
  href,
  label,
  icon,
  active,
  collapsed,
}: {
  href: string;
  label: string;
  icon: string;
  active: boolean;
  collapsed: boolean;
}) {
  const base =
    "flex items-center rounded-lg text-sm font-medium transition-all no-underline";
  const pad = collapsed ? "justify-center px-2 py-3" : "gap-3 px-4 py-3 border-l-4";
  const activeCls = active
    ? "bg-liaison-surface-container text-liaison-primary border-liaison-primary-container"
    : "text-liaison-on-surface-variant hover:bg-liaison-surface-container border-transparent";

  return (
    <Link href={href} title={collapsed ? label : undefined} className={`${base} ${pad} ${activeCls}`}>
      <span className="material-symbols-outlined text-xl shrink-0">{icon}</span>
      {!collapsed ? <span>{label}</span> : null}
    </Link>
  );
}

export default function AppLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { cycle, preference } = useTheme();
  const { state } = useCommandCenter();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(SIDEBAR_KEY) === "1") setCollapsed(true);
    } catch {
      /* ignore */
    }
  }, []);

  const toggle = () => {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  const projectCount = state?.project_matrix.length ?? "—";

  return (
    <div className="min-h-screen flex">
      <aside
        className={`hidden md:flex flex-col fixed left-0 top-0 h-screen bg-liaison-surface-low border-r border-liaison-outline-variant z-50 transition-[width] duration-200 ${
          collapsed ? "w-16" : "w-64"
        }`}
      >
        <div className="flex flex-col flex-1 min-h-0 py-6">
          <div className={`mb-6 shrink-0 flex ${collapsed ? "flex-col items-center px-2" : "px-6 justify-between"}`}>
            <Link href="/" className="no-underline text-inherit">
              {collapsed ? (
                <span className="font-headline text-liaison-primary text-lg font-bold">LC</span>
              ) : (
                <>
                  <h1 className="font-headline text-liaison-primary text-lg font-bold">
                    Liaison
                  </h1>
                  <p className="text-[10px] uppercase tracking-widest text-liaison-on-surface-variant mt-1">
                    Command Center
                  </p>
                </>
              )}
            </Link>
            <button
              type="button"
              onClick={toggle}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="rounded-lg p-1.5 text-liaison-on-surface-variant hover:bg-liaison-surface-container"
            >
              <span className="material-symbols-outlined">
                {collapsed ? "chevron_right" : "chevron_left"}
              </span>
            </button>
          </div>
          <nav className={`flex-1 overflow-y-auto space-y-1 ${collapsed ? "px-1.5" : "px-3"}`}>
            {NAV.map((item) => (
              <NavLink
                key={item.href}
                {...item}
                active={pathname === item.href}
                collapsed={collapsed}
              />
            ))}
          </nav>
          {!collapsed ? (
            <div className="px-6 mt-4 text-xs text-liaison-on-surface-variant">
              <p>Session</p>
              <p className="mt-1">{projectCount} projects</p>
              <p>{state?.env ?? "—"}</p>
            </div>
          ) : null}
        </div>
      </aside>

      <div
        className={`flex-1 flex flex-col min-h-screen transition-[margin] duration-200 ${
          collapsed ? "md:ml-16" : "md:ml-64"
        }`}
      >
        <header className="sticky top-0 z-40 border-b border-liaison-outline-variant bg-liaison-surface-low/95 backdrop-blur px-4 md:px-8 py-4 flex items-center justify-between gap-4">
          <div>
            <h2 className="font-headline text-xl font-semibold">
              Phoenix Liaison Command Center
            </h2>
            <p className="text-sm text-liaison-on-surface-variant">
              Agent orchestration and project decisions
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={cycle}
              className="rounded-lg p-2 border border-liaison-outline-variant text-liaison-on-surface-variant hover:bg-liaison-surface-container"
              title={`Theme: ${preference}`}
            >
              <span className="material-symbols-outlined">contrast</span>
            </button>
            <span className="mono text-xs text-liaison-on-surface-variant hidden sm:inline">
              {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        </header>
        <main className="flex-1 px-4 md:px-8 py-6">{children}</main>
      </div>
    </div>
  );
}
