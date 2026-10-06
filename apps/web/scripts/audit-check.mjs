import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

const advisory = "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm";
const developmentChain = new Set(["braces", "micromatch", "fast-glob", "@next/eslint-plugin-next", "eslint-config-next"]);

export function assessAudit(report, lock) {
  if (report.error || !report.vulnerabilities || typeof report.vulnerabilities !== "object" || Array.isArray(report.vulnerabilities))
    throw new Error("Invalid audit report");
  function knownDevelopmentFinding(name, visited = new Set()) {
    const finding = report.vulnerabilities[name];
    if (!developmentChain.has(name) || visited.has(name) || finding?.severity !== "high" ||
      !Array.isArray(finding.nodes) || !finding.nodes.length ||
      !finding.nodes.every((path) => lock.packages?.[path]?.dev === true) ||
      !Array.isArray(finding.via) || !finding.via.length) return false;
    const next = new Set([...visited, name]);
    return finding.via.every((cause) => typeof cause === "string"
      ? knownDevelopmentFinding(cause, next) : cause?.url === advisory);
  }
  const blocked = [], exceptions = [];
  for (const [name, finding] of Object.entries(report.vulnerabilities)) {
    if (!["info", "low", "moderate", "high", "critical"].includes(finding?.severity)) throw new Error("Invalid severity");
    if (["high", "critical"].includes(finding.severity)) {
      (knownDevelopmentFinding(name) ? exceptions : blocked).push(name);
    }
  }
  return { blocked, exceptions };
}

function main() {
  const root = fileURLToPath(new URL("../", import.meta.url));
  if (!process.env.npm_execpath) throw new Error("Run through npm run audit");
  const result = spawnSync(process.execPath, [process.env.npm_execpath, "audit", "--json"], {
    cwd: root, encoding: "utf8", timeout: 60000, maxBuffer: 2 * 1024 * 1024,
  });
  if (result.error || ![0, 1].includes(result.status)) throw new Error("Dependency audit unavailable");
  const report = JSON.parse(result.stdout);
  const lock = JSON.parse(readFileSync(new URL("../package-lock.json", import.meta.url), "utf8"));
  const assessment = assessAudit(report, lock);
  if (assessment.exceptions.length) console.warn(`Documented development-only exception: ${assessment.exceptions.join(", ")} (${advisory})`);
  if (assessment.blocked.length) throw new Error(`Unapproved high/critical findings: ${assessment.blocked.join(", ")}`);
  console.log("Dependency audit policy passed.");
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
