import { spawn } from "child_process";
import { NextRequest, NextResponse } from "next/server";

import { resolveLiaisonBin, resolveLiaisonRoot } from "@/lib/liaison-root";

export async function GET(request: NextRequest) {
  const refresh = request.nextUrl.searchParams.get("refresh") === "1";
  const project = request.nextUrl.searchParams.get("project")?.trim() || "";
  const task = request.nextUrl.searchParams.get("task")?.trim() || "";
  const pattern = request.nextUrl.searchParams.get("pattern")?.trim() || "";

  const root = resolveLiaisonRoot();
  const bin = resolveLiaisonBin(root);
  const args = ["command-center", "--json"];
  if (refresh) args.push("--refresh");
  if (project) args.push("--project", project);
  if (task) args.push("--task", task);
  if (pattern) args.push("--pattern", pattern);

  try {
    const stdout = await runCommand(bin, args, root);
    const state = JSON.parse(stdout);
    return NextResponse.json(state);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: message, hint: "Set LIAISON_ROOT in dashboard/web/.env.local" },
      { status: 500 }
    );
  }
}

function runCommand(bin: string, args: string[], cwd: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(bin, args, { cwd, env: process.env });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `liaison exited ${code}`));
        return;
      }
      resolve(stdout);
    });
  });
}
