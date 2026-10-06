import type {
  FeedbackValue,
  DiscoveryResponse,
  InterfaceLanguage,
  OriginalIdentificationResponse,
  SongIdentity,
  PreferenceProfile,
  RecommendationResponse,
  Track,
  VerifiedStorefront,
  RecordingResolveResponse,
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
  let discoveryController: AbortController | null = null;
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
    cancelDiscovery: () => discoveryController?.abort(),
    bootstrap: () => request<{ deviceId: string }>("/v1/device"),
    recommend: (seed: string, limit: number) =>
      request<RecommendationResponse>("/v1/recommendations", "POST", {
        seed,
        limit,
      }),
    discover: (seed: string, limit: number, language: InterfaceLanguage, seedArtist?: string, seedStorefront?: VerifiedStorefront,
      resolutionId?: string, signal?: AbortSignal) => {
      discoveryController?.abort();
      discoveryController = new AbortController();
      return request<DiscoveryResponse>("/v1/recommendations/discover", "POST", {
        seed,
        limit,
        language,
        ...(seedArtist ? { seed_artist: seedArtist } : {}),
        ...(seedStorefront ? { seed_storefront: seedStorefront } : {}),
        ...(resolutionId ? { resolution_id: resolutionId } : {}),
      }, 60000, signal ? AbortSignal.any([signal, discoveryController.signal]) : discoveryController.signal);
    },
    resolveRecording: (seed: string, language: InterfaceLanguage, artist?: string, platform?: string,
      songUrl?: string, signal?: AbortSignal) => request<RecordingResolveResponse>("/v1/recordings/resolve", "POST", {
        seed, language, ...(artist ? { artist } : {}), ...(platform ? { platform } : {}),
        ...(songUrl ? { song_url: songUrl } : {}),
      }, 35000, signal),
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
