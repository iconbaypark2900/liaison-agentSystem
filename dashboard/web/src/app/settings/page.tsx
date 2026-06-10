"use client";

import { CommandCenterFooter } from "@/components/CommandCenterFooter";
import { Panel } from "@/components/Panel";
import { useCommandCenter } from "@/context/CommandCenterContext";
import { useTheme } from "@/context/ThemeContext";

export default function SettingsPage() {
  const { state, refresh } = useCommandCenter();
  const { preference, cycle } = useTheme();
  const bridge = process.env.NEXT_PUBLIC_TERMINAL_BRIDGE ?? "copy (server: TERMINAL_BRIDGE)";

  return (
    <>
      <Panel eyebrow="Settings" title="Session and configuration">
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-liaison-on-surface-variant">Environment</dt>
            <dd className="font-mono">{state?.env ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-liaison-on-surface-variant">User</dt>
            <dd>{state?.user ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-liaison-on-surface-variant">Platform cwd</dt>
            <dd className="font-mono">{state?.platform ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-liaison-on-surface-variant">Generated at</dt>
            <dd className="font-mono">{state?.generated_at ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-liaison-on-surface-variant">SQLite memory</dt>
            <dd>{state?.sqlite_loaded ? "loaded" : "not loaded"}</dd>
          </div>
          <div>
            <dt className="text-liaison-on-surface-variant">Refresh interval</dt>
            <dd>{state?.refresh_sec ?? 30}s</dd>
          </div>
          <div>
            <dt className="text-liaison-on-surface-variant">Theme</dt>
            <dd>{preference}</dd>
          </div>
          <div>
            <dt className="text-liaison-on-surface-variant">Terminal bridge</dt>
            <dd className="font-mono">{bridge}</dd>
          </div>
        </dl>
        <div className="flex gap-3 mt-6">
          <button
            type="button"
            onClick={cycle}
            className="px-4 py-2 rounded-lg border border-liaison-outline-variant"
          >
            Cycle theme
          </button>
          <button
            type="button"
            onClick={() => refresh(true)}
            className="px-4 py-2 rounded-lg bg-liaison-primary text-liaison-canvas"
          >
            Hard refresh data
          </button>
        </div>
        <p className="text-xs text-liaison-on-surface-variant mt-6">
          Set LIAISON_ROOT in dashboard/web/.env.local. Data source: liaison command-center --json.
        </p>
      </Panel>
      <Panel className="mt-6" eyebrow="Operator workflow" title="Two-pane: browser + terminal">
        <div className="text-sm space-y-3 text-liaison-on-surface-variant">
          <p>
            Use the <strong className="text-liaison-on-surface">browser</strong> for project focus,
            patterns, liaison scaffold commands, and copy-to-clipboard helpers. Run{" "}
            <strong className="text-liaison-on-surface">hermes</strong>,{" "}
            <strong className="text-liaison-on-surface">qca</strong>, and other agents in a{" "}
            <strong className="text-liaison-on-surface">terminal pane</strong> so you see live output.
          </p>
          <ol className="list-decimal list-inside space-y-1 text-xs">
            <li>Select a project on / or /projects</li>
            <li>On /hub: copy launch or Open in terminal for the agent</li>
            <li>After the agent finishes: Copy attach → liaison approve → validate → close</li>
            <li>Optional: Scaffold pattern runs liaison start-pattern via allowlisted API only</li>
          </ol>
          <p className="text-xs">
            <span className="font-mono">TERMINAL_BRIDGE</span> env on the Next server:{" "}
            <span className="font-mono">copy</span> (default),{" "}
            <span className="font-mono">tmux</span>, or <span className="font-mono">wezterm</span>.
            When set to tmux/wezterm and the binary exists, Open in terminal calls{" "}
            <span className="font-mono">POST /api/terminal/spawn</span> with the launch line only.
            Otherwise the UI copies the compound script to the clipboard.
          </p>
        </div>
      </Panel>
      <CommandCenterFooter />
    </>
  );
}
