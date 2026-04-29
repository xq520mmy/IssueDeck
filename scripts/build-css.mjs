import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptsDir = dirname(fileURLToPath(import.meta.url));
const rootDir = join(scriptsDir, "..");
const tailwindCli = join(rootDir, "node_modules", "tailwindcss", "lib", "cli.js");

const result = spawnSync(
  process.execPath,
  [
    tailwindCli,
    "-c",
    "tailwind.config.cjs",
    "-i",
    "./src/issuedeck/features/dashboard/static/css/input.css",
    "-o",
    "./src/issuedeck/features/dashboard/static/css/dashboard.css",
    "--minify",
  ],
  {
    cwd: rootDir,
    env: {
      ...process.env,
      BROWSERSLIST_IGNORE_OLD_DATA: "1",
    },
    stdio: "inherit",
  },
);

process.exit(result.status ?? 1);
