import { describe, expect, it, vi } from "vitest";
import { getDeviceId } from "../lib/device";

describe("anonymous device bootstrap", () => {
  it("creates one stable random ID and reuses it", () => {
    vi.stubGlobal("crypto", {
      randomUUID: vi.fn(() => "a2a91263-4a43-4a9d-981c-51cc7672d8fa"),
    });
    const first = getDeviceId();
    expect(first).toBe("device_a2a91263-4a43-4a9d-981c-51cc7672d8fa");
    expect(getDeviceId()).toBe(first);
    expect(crypto.randomUUID).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });
});
