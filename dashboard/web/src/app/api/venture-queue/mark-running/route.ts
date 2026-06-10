import { NextRequest, NextResponse } from "next/server";

import { runSparkFlowJson } from "@/lib/liaison-exec";

export async function POST(request: NextRequest) {
  let body: { itemId?: string };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const itemId = body.itemId?.trim();
  if (!itemId) {
    return NextResponse.json({ error: "itemId is required" }, { status: 400 });
  }

  try {
    const item = await runSparkFlowJson(["venture-queue", "mark-running", itemId]);
    return NextResponse.json(item);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
