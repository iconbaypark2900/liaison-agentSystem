import fs from "fs";
import path from "path";

import { resolveLiaisonRoot } from "./liaison-root";

export type LiaisonBrowserAuditEntry = {
  ts: string;
  cmd: string;
  project?: string;
  task?: string;
  ok?: boolean;
};

export function appendBrowserLiaisonAudit(entry: LiaisonBrowserAuditEntry): void {
  const root = resolveLiaisonRoot();
  const logPath = path.join(root, "memory", "browser_liaison_audit.jsonl");
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  fs.appendFileSync(logPath, `${JSON.stringify(entry)}\n`, "utf8");
}
