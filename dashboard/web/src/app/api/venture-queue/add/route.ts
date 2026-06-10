import { NextRequest, NextResponse } from "next/server";

import { runSparkFlowJson } from "@/lib/liaison-exec";

export async function POST(request: NextRequest) {
  let body: {
    project?: string;
    taskId?: string;
    agent?: string;
    pattern?: string;
    priority?: number;
  };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const project = body.project?.trim();
  const taskId = body.taskId?.trim();
  if (!project || !taskId) {
    return NextResponse.json({ error: "project and taskId are required" }, { status: 400 });
  }

  const args = [
    "venture-queue",
    "add",
    "--project",
    project,
    "--task-id",
    taskId,
    "--agent",
    body.agent?.trim() || "hermes",
  ];
  if (body.pattern?.trim()) args.push("--pattern", body.pattern.trim());
  if (typeof body.priority === "number") args.push("--priority", String(body.priority));

  try {
    const item = await runSparkFlowJson(args);
    return NextResponse.json(item);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
