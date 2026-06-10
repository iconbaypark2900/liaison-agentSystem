import { NextRequest, NextResponse } from "next/server";

import { appendBrowserLiaisonAudit } from "@/lib/liaison-audit";
import { runAllowlistedLiaison } from "@/lib/liaison-exec";

export async function POST(request: NextRequest) {
  let body: { cmd?: string; project?: string; task?: string };
  try {
    body = (await request.json()) as { cmd?: string; project?: string; task?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const cmd = body.cmd?.trim();
  if (!cmd) {
    return NextResponse.json({ error: "cmd is required" }, { status: 400 });
  }

  const project = body.project?.trim() || request.nextUrl.searchParams.get("project")?.trim() || "";
  const task = body.task?.trim() || request.nextUrl.searchParams.get("task")?.trim() || "";

  appendBrowserLiaisonAudit({
    ts: new Date().toISOString(),
    cmd,
    project: project || undefined,
    task: task || undefined,
  });

  try {
    const result = await runAllowlistedLiaison(cmd, project || null);
    appendBrowserLiaisonAudit({
      ts: new Date().toISOString(),
      cmd,
      project: project || undefined,
      task: task || undefined,
      ok: result.ok,
    });
    return NextResponse.json(result, { status: result.ok ? 200 : 403 });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    appendBrowserLiaisonAudit({
      ts: new Date().toISOString(),
      cmd,
      project: project || undefined,
      task: task || undefined,
      ok: false,
    });
    return NextResponse.json(
      { ok: false, output: message, cmd, error: message },
      { status: 500 }
    );
  }
}
