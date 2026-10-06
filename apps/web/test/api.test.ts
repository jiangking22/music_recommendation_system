import { testSession, withCsrf } from "./auth-helpers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient } from "../lib/api";

afterEach(() => vi.unstubAllGlobals());
beforeEach(testSession);

describe("API client", () => {
  it("carries the verified storefront only for explicit confirmation", async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(new Response(
      JSON.stringify({ items: [], sources: {} }), { status: 200 })));
    const api = createApiClient("http://localhost:8000", withCsrf(fetcher));
    await api.discover("晴天", 5, "zh", "周杰伦", "TW");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      seed: "晴天", limit: 5, language: "zh", seed_artist: "周杰伦", seed_storefront: "TW",
    });
    await api.discover("jazz", 5, "en");
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ seed: "jazz", limit: 5, language: "en" });
  });
  it("sends bounded rejection summaries and combines cancellation with the identification deadline", async () => {
    const deadline = vi.spyOn(AbortSignal, "timeout");
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "unknown",
      suggestion: null, matched_track: null, sources: {} }), { status: 200 }));
    const api = createApiClient("http://localhost:8000", withCsrf(fetcher));
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
  it("sends session headers and parses a recommendation", async () => {
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
      withCsrf(fetcher),
    );
    expect((await api.recommend("jazz", 5)).items).toEqual([]);
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/v1/recommendations",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
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
      withCsrf(fetcher),
    );
    await expect(api.profile()).rejects.toMatchObject({
      code: "validation_error",
      status: 422,
    } satisfies Partial<ApiError>);
  });

  it("sends the discovery locale and artist confirmation with a bounded deadline", async () => {
    const deadline = vi.spyOn(AbortSignal, "timeout");
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], sources: {} }), { status: 200 }));
    const api = createApiClient("http://localhost:8000", withCsrf(fetcher));
    await api.discover("我好想你", 5, "zh", "苏打绿");
    expect(fetcher).toHaveBeenCalledWith("http://localhost:8000/v1/recommendations/discover", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ seed: "我好想你", limit: 5, language: "zh", seed_artist: "苏打绿" }),
      credentials: "same-origin",
    }));
    expect(deadline).toHaveBeenCalledWith(60000);
    deadline.mockRestore();
  });
});
