#!/usr/bin/env node
import { spawnSync } from "node:child_process";

const python = process.env.PYTHON ?? "python";
const proc = spawnSync(python, ["-m", "agentport.cli.main", ...process.argv.slice(2)], {
  stdio: "inherit",
  cwd: new URL("..", import.meta.url),
});

process.exit(proc.status ?? 1);
