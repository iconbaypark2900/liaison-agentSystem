import { NextRequest, NextResponse } from "next/server";

import { appendBrowserLiaisonAudit } from "@/lib/liaison-audit";
import { runReporterStepAdvanceBrowser } from "@/lib/liaison-exec";

export async function POST(request: NextRequest) {
  let body: { project?: string; task?: string };
  try {
    body = (await request.json()) as { project?: string; task?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const project =
    body.project?.trim() || request.nextUrl.searchParams.get("project")?.trim() || "";
  const task = body.task?.trim() || request.nextUrl.searchParams.get("task")?.trim() || "";

  if (!project) {
    return NextResponse.json({ error: "project is required" }, { status: 400 });
  }

  const cmd = "liaison reporter-step advance";
  appendBrowserLiaisonAudit({
    ts: new Date().toISOString(),
    cmd,
    project,
    task: task || undefined,
  });

  try {
    const result = await runReporterStepAdvanceBrowser(project, task || null);
    appendBrowserLiaisonAudit({
      ts: new Date().toISOString(),
      cmd,
      project,
      task: task || undefined,
      ok: result.ok,
    });
    return NextResponse.json(result, { status: result.ok ? 200 : 403 });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    appendBrowserLiaisonAudit({
      ts: new Date().toISOString(),
      cmd,
      project,
      task: task || undefined,
      ok: false,
    });
    return NextResponse.json(
      { ok: false, output: message, cmd, error: message },
      { status: 500 }
    );
  }
}
