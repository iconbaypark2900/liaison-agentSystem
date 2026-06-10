import { NextRequest, NextResponse } from "next/server";

import { runSparkFlowJson } from "@/lib/liaison-exec";

export async function POST(request: NextRequest) {
  const spawn = request.nextUrl.searchParams.get("spawn") === "1";
  try {
    const args = spawn ? ["venture-queue", "next", "--spawn"] : ["venture-queue", "next"];
    const data = await runSparkFlowJson(args);
    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
