import EmbeddedPostgres from "embedded-postgres";
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const dataRoot = path.resolve(here, "data");
const dataDir = path.resolve(dataRoot, `run-${Date.now()}`);
if (!dataDir.startsWith(dataRoot + path.sep)) throw new Error("Invalid test data directory");
const password = randomBytes(24).toString("hex");
const port = Number(process.env.TEST_POSTGRES_PORT || 55432);
let startupLog = "";
const pg = new EmbeddedPostgres({
  databaseDir: dataDir, user: "postgres", password, port,
  authMethod: "scram-sha-256", persistent: true, createPostgresUser: false,
  postgresFlags: ["-h", "127.0.0.1"],
  onLog: (line) => { startupLog = (startupLog + line).slice(-4000); },
  onError: () => {},
});
let testExitCode = 1;
let started = false;
try {
  await pg.initialise();
  await pg.start();
  started = true;
  console.log("Isolated PostgreSQL started on loopback; running backend tests.");
  const python = process.env.TEST_PYTHON || path.join(root, "backend", ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  const code = await new Promise((resolve, reject) => {
    const child = spawn(python, ["-m", "pytest", "backend/tests", "-q", "--basetemp", path.join(dataDir, "pytest"), ...process.argv.slice(2)], {
      cwd: root, stdio: "inherit", windowsHide: true,
      env: { ...process.env, TEST_DATABASE_URL: `postgresql://postgres:${password}@127.0.0.1:${port}/postgres` },
    });
    child.once("error", reject);
    child.once("exit", resolve);
  });
  testExitCode = code ?? 1;
} catch (error) {
  console.error("Database test runner failed:", String(error).replaceAll(password, "[redacted]"));
  if (!started) console.error(startupLog.replaceAll(password, "[redacted]"));
} finally {
  if (started) {
    await pg.stop();
    console.log("Test PostgreSQL stopped. Local cluster files remain in ignored tools/postgres/data.");
  }
}
// embedded-postgres installs process handlers; explicitly preserve pytest's result
// after graceful cluster shutdown instead of allowing a dependency to replace it.
process.exit(testExitCode);
