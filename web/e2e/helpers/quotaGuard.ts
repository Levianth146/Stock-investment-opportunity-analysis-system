/**
 * Đảm bảo suite mặc định không đụng quota/budget AI thật.
 * So sánh mtime + sha256 của _debate_budget.json và _quota_state.json.
 */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
);

export const QUOTA_WATCH_FILES = [
  path.join(repoRoot, "data/llm_cache/_debate_budget.json"),
  path.join(repoRoot, "data/llm_cache/_quota_state.json"),
] as const;

export type FileSnap = {
  path: string;
  exists: boolean;
  mtimeMs: number | null;
  sha256: string | null;
};

export function snapFile(filePath: string): FileSnap {
  if (!fs.existsSync(filePath)) {
    return { path: filePath, exists: false, mtimeMs: null, sha256: null };
  }
  const st = fs.statSync(filePath);
  const buf = fs.readFileSync(filePath);
  const sha256 = crypto.createHash("sha256").update(buf).digest("hex");
  return {
    path: filePath,
    exists: true,
    mtimeMs: st.mtimeMs,
    sha256,
  };
}

export function snapAll(): FileSnap[] {
  return QUOTA_WATCH_FILES.map(snapFile);
}

export function assertUnchanged(before: FileSnap[], after: FileSnap[]): void {
  for (let i = 0; i < before.length; i++) {
    const a = before[i];
    const b = after[i];
    if (a.exists !== b.exists) {
      throw new Error(
        `Quota file existence changed: ${a.path} exists ${a.exists} → ${b.exists}`,
      );
    }
    if (a.mtimeMs !== b.mtimeMs || a.sha256 !== b.sha256) {
      throw new Error(
        `Quota file changed during default e2e (cấm gọi LLM thật): ${a.path}\n` +
          `  mtime ${a.mtimeMs} → ${b.mtimeMs}\n` +
          `  sha256 ${a.sha256} → ${b.sha256}`,
      );
    }
  }
}

const SNAP_PATH = path.join(
  repoRoot,
  "data/web_preview/_quota_guard_snap.json",
);

export function writeStartSnap(): FileSnap[] {
  const snaps = snapAll();
  fs.mkdirSync(path.dirname(SNAP_PATH), { recursive: true });
  fs.writeFileSync(SNAP_PATH, JSON.stringify(snaps, null, 2), "utf8");
  return snaps;
}

export function readStartSnap(): FileSnap[] {
  if (!fs.existsSync(SNAP_PATH)) {
    throw new Error(`Thiếu snap quota guard: ${SNAP_PATH}`);
  }
  return JSON.parse(fs.readFileSync(SNAP_PATH, "utf8")) as FileSnap[];
}
