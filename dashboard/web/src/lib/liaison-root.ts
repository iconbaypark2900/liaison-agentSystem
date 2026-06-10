import fs from "fs";
import path from "path";

/** Resolve LIAISON_ROOT for API routes (server-only). */
export function resolveLiaisonRoot(): string {
  const fromEnv = process.env.LIAISON_ROOT?.trim();
  if (fromEnv) return path.resolve(fromEnv);
  return path.resolve(process.cwd(), "../..");
}

export function resolveLiaisonBin(root: string): string {
  const liaison = path.join(root, "bin", "liaison");
  const sparkFlow = path.join(root, "bin", "spark-flow");
  if (fs.existsSync(liaison)) return liaison;
  return sparkFlow;
}
