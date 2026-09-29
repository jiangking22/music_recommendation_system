import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient } from "../lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
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
});
