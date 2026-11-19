// Runs an infra/aws/*.sh script with a real bash. On Windows, plain "bash" may be WSL's
// (slow or broken); prefer Git Bash when it is installed.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const [script, ...args] = process.argv.slice(2);
const here = dirname(fileURLToPath(import.meta.url));
const gitBash = [
  process.env.GIT_BASH,
  "C:\Program Files\Git\bin\bash.exe",
  "C:\Program Files (x86)\Git\bin\bash.exe",
].find((p) => p && existsSync(p));
const bash = process.platform === "win32" && gitBash ? gitBash : "bash";
const r = spawnSync(bash, [join(here, script), ...args], { stdio: "inherit" });
process.exit(r.status ?? 1);
