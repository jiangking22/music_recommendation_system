import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient } from "../lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("sends bounded rejection summaries and combines cancellation with the identification deadline", async () => {
    const deadline = vi.spyOn(AbortSignal, "timeout");
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "unknown",
      suggestion: null, matched_track: null, sources: {} }), { status: 200 }));
    const api = createApiClient("http://localhost:8000", "device_1234567890", fetcher);
    const controller = new AbortController();
    const rejected = [{ title: "Shared Title", artist: "First" }];
    await api.identifyOriginal("Shared Title", "zh", rejected, controller.signal);
    expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/v1/recommendations/identify-original",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ seed: "Shared Title",
        language: "zh", rejected_candidates: rejected }) }));
    expect(deadline).toHaveBeenCalledWith(60000);
    const signal = fetcher.mock.calls[0][1].signal;
    expect(signal.aborted).toBe(false);
    controller.abort();
    expect(signal.aborted).toBe(true);
    deadline.mockRestore();
  });
  it("sends device headers and parses a recommendation", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ request_id: "one", items: [], sources: {} }),
          { status: 200 },
        ),
      );
    const api = createApiClient(
      "http://localhost:8000",
      "device_1234567890",
      fetcher,
    );
    expect((await api.recommend("jazz", 5)).items).toEqual([]);
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/v1/recommendations",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-Device-Id": "device_1234567890",
        }),
        body: JSON.stringify({ seed: "jazz", limit: 5 }),
      }),
    );
  });

  it("returns structured API errors", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { code: "validation_error", message: "Invalid request." },
          }),
          { status: 422 },
        ),
      );
    const api = createApiClient(
      "http://localhost:8000",
      "device_1234567890",
      fetcher,
    );
    await expect(api.profile()).rejects.toMatchObject({
      code: "validation_error",
      status: 422,
    } satisfies Partial<ApiError>);
  });

  it("sends the discovery locale and artist confirmation with a bounded deadline", async () => {
    const deadline = vi.spyOn(AbortSignal, "timeout");
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], sources: {} }), { status: 200 }));
    const api = createApiClient("http://localhost:8000", "device_1234567890", fetcher);
    await api.discover("我好想你", 5, "zh", "苏打绿");
    expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/v1/recommendations/discover", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ seed: "我好想你", limit: 5, language: "zh", seed_artist: "苏打绿" }),
      headers: expect.objectContaining({ "X-Device-Id": "device_1234567890" }),
    }));
    expect(deadline).toHaveBeenCalledWith(60000);
    deadline.mockRestore();
  });
});
