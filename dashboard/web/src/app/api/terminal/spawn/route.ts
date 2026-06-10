import { spawn, spawnSync } from "child_process";
import { NextRequest, NextResponse } from "next/server";

import { resolveLiaisonBin, resolveLiaisonRoot } from "@/lib/liaison-root";

type BridgeMode = "copy" | "tmux" | "wezterm";

function resolveBridgeMode(): BridgeMode {
  const raw = process.env.TERMINAL_BRIDGE?.trim().toLowerCase();
  if (raw === "copy" || raw === "tmux" || raw === "wezterm") return raw;
  if (commandExists("tmux")) return "tmux";
  return "copy";
}

function wrapLaunchWithComplete(
  launch: string,
  root: string,
  agentName: string,
  project: string,
  taskId: string
): string {
  const bin = resolveLiaisonBin(root);
  const complete = `${bin} observe-session complete --agent ${agentName} --exit-code $EXIT_CODE --project ${project} --task-id ${taskId}`;
  return `${launch}; EXIT_CODE=$?; ${complete}; exit $EXIT_CODE`;
}

function commandExists(name: string): boolean {
  const probe = spawnSync("sh", ["-c", `command -v ${name}`], { encoding: "utf8" });
  return probe.status === 0;
}

function registerTerminalSession(
  root: string,
  agentName: string,
  launch: string,
  title: string,
  pid?: number,
  project?: string,
  taskId?: string,
  patternId?: string
): void {
  const bin = resolveLiaisonBin(root);
  const args = [
    "terminal-session",
    "register",
    "--agent-name",
    agentName,
    "--launch",
    launch,
    "--title",
    title,
  ];
  if (pid) args.push("--pid", String(pid));
  if (project) args.push("--project", project);
  if (taskId) args.push("--task-id", taskId);
  if (patternId) args.push("--pattern", patternId);
  spawnSync(bin, args, { cwd: root, env: process.env, encoding: "utf8" });
}

function captureTmuxPanePid(title: string): number | undefined {
  const listed = spawnSync(
    "tmux",
    ["list-panes", "-a", "-F", "#{window_name}\t#{pane_pid}", "-t", title],
    { encoding: "utf8", env: process.env }
  );
  if (listed.status === 0 && listed.stdout.trim()) {
    for (const line of listed.stdout.trim().split("\n")) {
      const [name, pidStr] = line.split("\t");
      if (name === title) {
        const pid = parseInt(pidStr, 10);
        if (Number.isFinite(pid)) return pid;
      }
    }
  }
  const fallback = spawnSync(
    "tmux",
    ["list-panes", "-F", "#{pane_pid}", "-t", title],
    { encoding: "utf8", env: process.env }
  );
  if (fallback.status === 0 && fallback.stdout.trim()) {
    const pid = parseInt(fallback.stdout.trim().split("\n")[0], 10);
    if (Number.isFinite(pid)) return pid;
  }
  return undefined;
}

function spawnTmuxWindow(
  title: string,
  effectiveLaunch: string
): { ok: boolean; pid?: number; error?: string } {
  const created = spawnSync(
    "tmux",
    ["new-window", "-P", "-F", "#{pane_pid}", "-n", title, "bash", "-lc", effectiveLaunch],
    { encoding: "utf8", env: process.env }
  );
  if (created.status !== 0) {
    return { ok: false, error: created.stderr?.trim() || "tmux new-window failed" };
  }
  const pid = parseInt(created.stdout.trim(), 10);
  if (Number.isFinite(pid)) {
    return { ok: true, pid };
  }
  return { ok: true, pid: captureTmuxPanePid(title) };
}

export async function POST(request: NextRequest) {
  let body: {
    launch?: string;
    title?: string;
    agentName?: string;
    project?: string;
    taskId?: string;
    patternId?: string;
  };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const launch = body.launch?.trim();
  if (!launch) {
    return NextResponse.json({ error: "launch is required" }, { status: 400 });
  }

  const agentName = body.agentName?.trim() || body.title?.trim() || "agent";
  const mode = resolveBridgeMode();
  if (mode === "copy") {
    return NextResponse.json({
      mode: "copy",
      copied: false,
      message: "TERMINAL_BRIDGE=copy — use Open in terminal / Copy launch in UI",
      launch,
    });
  }

  const binary = mode;
  if (!commandExists(binary)) {
    return NextResponse.json({
      mode: "copy",
      copied: false,
      message: `${binary} not found — falling back to copy`,
      launch,
    });
  }

  const title = body.title?.trim() || agentName;
  const project = body.project?.trim();
  const taskId = body.taskId?.trim();
  const root = resolveLiaisonRoot();
  const effectiveLaunch =
    project && taskId ? wrapLaunchWithComplete(launch, root, agentName, project, taskId) : launch;

  try {
    let panePid: number | undefined;
    if (mode === "tmux") {
      const result = spawnTmuxWindow(title, effectiveLaunch);
      if (!result.ok) {
        throw new Error(result.error ?? "tmux spawn failed");
      }
      panePid = result.pid;
    } else {
      await new Promise<void>((resolve, reject) => {
        const child = spawn(binary, ["start", "--", "bash", "-lc", effectiveLaunch], {
          detached: true,
          stdio: "ignore",
          env: process.env,
        });
        child.on("error", reject);
        child.on("spawn", () => {
          child.unref();
          resolve();
        });
      });
    }
    registerTerminalSession(
      root,
      agentName,
      effectiveLaunch,
      title,
      panePid,
      project,
      taskId,
      body.patternId?.trim()
    );
    const completeHint =
      project && taskId
        ? `liaison observe-session complete --agent ${agentName} --exit-code 0 --project ${project} --task-id ${taskId}`
        : undefined;
    return NextResponse.json({
      mode,
      spawned: true,
      launch: effectiveLaunch,
      agentName,
      panePid,
      completeHint,
      wrapped: Boolean(project && taskId),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({
      mode: "copy",
      spawned: false,
      message: `${mode} spawn failed: ${message}`,
      launch,
    });
  }
}
