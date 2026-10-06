import type {
  FeedbackValue,
  DiscoveryResponse,
  InterfaceLanguage,
  OriginalIdentificationResponse,
  SongIdentity,
  PreferenceProfile,
  RecommendationResponse,
  Track,
} from "../types/music";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function createApiClient(
  baseUrl: string,
  deviceId: string,
  fetcher: typeof fetch = fetch,
) {
  const root = baseUrl.replace(/\/$/, "");
  async function request<T>(
    path: string,
    method = "GET",
    body?: unknown,
    timeoutMs = 12000,
    signal?: AbortSignal,
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetcher(`${root}${path}`, {
        method,
        headers: {
          "Content-Type": "application/json",
          "X-Device-Id": deviceId,
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs),
        cache: "no-store",
      });
    } catch (error) {
      throw new ApiError(
        "network_error",
        error instanceof Error && error.name === "TimeoutError"
          ? "Request timed out."
          : "Could not reach the music service.",
        0,
      );
    }
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new ApiError(
        "invalid_response",
        "Music service returned invalid JSON.",
        response.status,
      );
    }
    if (!response.ok) {
      const envelope = payload as {
        error?: { code?: string; message?: string };
      };
      throw new ApiError(
        envelope?.error?.code ?? "http_error",
        envelope?.error?.message ?? "Music service request failed.",
        response.status,
      );
    }
    return payload as T;
  }
  return {
    bootstrap: () => request<{ deviceId: string }>("/v1/device"),
    recommend: (seed: string, limit: number) =>
      request<RecommendationResponse>("/v1/recommendations", "POST", {
        seed,
        limit,
      }),
    discover: (seed: string, limit: number, language: InterfaceLanguage, seedArtist?: string) =>
      request<DiscoveryResponse>("/v1/recommendations/discover", "POST", {
        seed,
        limit,
        language,
        ...(seedArtist ? { seed_artist: seedArtist } : {}),
      }, 60000),
    identifyOriginal: (seed: string, language: InterfaceLanguage, rejectedCandidates: SongIdentity[], signal?: AbortSignal) =>
      request<OriginalIdentificationResponse>("/v1/recommendations/identify-original", "POST", {
        seed, language, rejected_candidates: rejectedCandidates,
      }, 60000, signal),
    feedback: (track: Track, value: FeedbackValue) =>
      request<{ track_key: string; value: FeedbackValue }>(
        "/v1/feedback",
        "POST",
        { track, value },
      ),
    profile: () => request<PreferenceProfile>("/v1/profile"),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
