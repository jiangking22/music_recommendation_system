import { describe, expect, it } from "vitest";
import { safeExternalUrl } from "../lib/url";

describe("provider links", () => {
  it("accepts only absolute HTTP links", () => {
    expect(safeExternalUrl("https://music.example/song")).toBe(
      "https://music.example/song",
    );
    expect(safeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(safeExternalUrl("/relative/path")).toBeNull();
  });
});
