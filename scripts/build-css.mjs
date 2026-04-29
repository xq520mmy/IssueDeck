import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptsDir = dirname(fileURLToPath(import.meta.url));
const rootDir = join(scriptsDir, "..");
const outputCss = join(
  rootDir,
  "src",
  "issuedeck",
  "features",
  "dashboard",
  "static",
  "css",
  "dashboard.css",
);
const tailwindCli = join(
  rootDir,
  "node_modules",
  "@tailwindcss",
  "cli",
  "dist",
  "index.mjs",
);

const result = spawnSync(
  process.execPath,
  [
    tailwindCli,
    "-c",
    "tailwind.config.cjs",
    "-i",
    "./src/issuedeck/features/dashboard/static/css/input.css",
    "-o",
    outputCss,
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

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

const css = readFileSync(outputCss, "utf8").replace(
  /-?(?:\d+)?\.\d{6,}/g,
  (value) => {
    let normalized = Number(value).toFixed(5);
    normalized = normalized.replace(/0+$/, "").replace(/\.$/, "");
    if (value.startsWith("-.") && normalized.startsWith("-0.")) {
      return `-.${normalized.slice(3)}`;
    }
    if (value.startsWith(".") && normalized.startsWith("0.")) {
      return `.${normalized.slice(2)}`;
    }
    return normalized;
  },
);
writeFileSync(outputCss, css);
