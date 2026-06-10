import { spawn } from "child_process";

import { resolveLiaisonBin, resolveLiaisonRoot } from "./liaison-root";

export type LiaisonRunResult = {
  ok: boolean;
  output: string;
  cmd: string;
};

export async function runAllowlistedLiaison(
  cmd: string,
  project?: string | null
): Promise<LiaisonRunResult> {
  const root = resolveLiaisonRoot();
  const bin = resolveLiaisonBin(root);
  const args = ["run-allowlisted", "--cmd", cmd];
  if (project) args.push("--project", project);

  const stdout = await runCommand(bin, args, root);
  return JSON.parse(stdout) as LiaisonRunResult;
}

export async function runSparkFlowJson(args: string[]): Promise<unknown> {
  const root = resolveLiaisonRoot();
  const bin = resolveLiaisonBin(root);
  const stdout = await runCommand(bin, args, root);
  return JSON.parse(stdout) as unknown;
}

export async function runReporterStepAdvanceBrowser(
  project: string,
  taskId?: string | null
): Promise<LiaisonRunResult> {
  const root = resolveLiaisonRoot();
  const bin = resolveLiaisonBin(root);
  const args = ["reporter-step-advance-browser", "--project", project];
  if (taskId) args.push("--task-id", taskId);
  const stdout = await runCommand(bin, args, root);
  return JSON.parse(stdout) as LiaisonRunResult;
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
