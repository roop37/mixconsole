import { type ChildProcess, execFileSync, spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

export const PORT = 8799;
export const STATE_FILE = path.join(tmpdir(), "mixconsole-e2e-state.json");
const repo = path.resolve(import.meta.dirname, "../../..");

async function healthy(): Promise<boolean> {
  try {
    return (await fetch(`http://127.0.0.1:${PORT}/api/v1/health`)).ok;
  } catch {
    return false;
  }
}

/** Builds synthetic audio, starts `mixconsole serve --ui` on a throwaway data dir, stops it after. */
export default async function setup(): Promise<() => Promise<void>> {
  const work = mkdtempSync(path.join(tmpdir(), "mixconsole-e2e-"));
  const env = {
    ...process.env,
    MIXCONSOLE_CACHE_DIR: path.join(work, "cache"),
    MIXCONSOLE_STEMS: "off",
    MIXCONSOLE_WORKERS: "2",
  };
  const audio = path.join(work, "audio");
  execFileSync("uv", ["run", "python", path.join(repo, "apps/console/e2e/make_audio.py"), audio], {
    cwd: repo,
    env,
    stdio: "inherit",
  });
  execFileSync(
    "uv",
    ["run", "mixconsole", "listen", "build", "--synthetic", "-o", path.join(work, "kit")],
    {
      cwd: repo,
      env,
      stdio: "inherit",
    },
  );
  const data = path.join(work, "data");
  const server: ChildProcess = spawn(
    "uv",
    ["run", "mixconsole", "serve", "--ui", "--port", String(PORT), "--data-dir", data],
    { cwd: repo, env, stdio: "inherit" },
  );
  for (let i = 0; i < 120 && !(await healthy()); i++) await new Promise((r) => setTimeout(r, 500));
  if (!(await healthy())) throw new Error("mixconsole serve did not start");
  const token = readFileSync(path.join(data, "server.token"), "utf8").trim();
  writeFileSync(STATE_FILE, JSON.stringify({ token, audio, kit: path.join(work, "kit"), work }));
  return async () => {
    server.kill("SIGTERM");
    await new Promise((r) => setTimeout(r, 500));
    rmSync(work, { recursive: true, force: true });
    rmSync(STATE_FILE, { force: true });
  };
}
