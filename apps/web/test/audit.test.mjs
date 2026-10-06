import { describe, expect, it } from "vitest";
import { assessAudit } from "../scripts/audit-check.mjs";

const advisory = { url: "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm" };
const devLock = { packages: { "node_modules/braces": { dev: true } } };
const finding = { severity: "high", nodes: ["node_modules/braces"], via: [advisory] };

describe("dependency audit policy", () => {
  it("allows only the documented unpatched development braces advisory", () => {
    expect(assessAudit({ vulnerabilities: { braces: finding } }, devLock))
      .toEqual({ blocked: [], exceptions: ["braces"] });
  });
  it("blocks the same package when included in production", () => {
    expect(assessAudit({ vulnerabilities: { braces: finding } }, { packages: { "node_modules/braces": {} } }).blocked)
      .toEqual(["braces"]);
  });
  it("blocks a different advisory and other high-severity dependencies", () => {
    expect(assessAudit({ vulnerabilities: { braces: { ...finding, via: [{ url: "https://example.com/unknown" }] },
      next: { severity: "critical" } } }, devLock).blocked).toEqual(["braces", "next"]);
  });
  it("fails closed for malformed reports and unresolved dependency chains", () => {
    expect(() => assessAudit({ error: { code: "network_failure" } }, devLock)).toThrow();
    expect(assessAudit({ vulnerabilities: { braces: { ...finding, via: ["missing"] } } }, devLock).blocked).toEqual(["braces"]);
  });
});
