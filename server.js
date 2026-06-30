const { spawn } = require("node:child_process");
const path = require("node:path");

const cwd = __dirname;
const server = path.join(cwd, "server.py");

const child = spawn("python", [server], {
  cwd,
  stdio: "inherit",
  shell: false,
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
