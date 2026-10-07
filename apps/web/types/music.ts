export type FeedbackValue = "like" | "dislike";
export type ProviderSource = {
  provider: string;
  provider_track_id: string;
  external_url: string | null;
};
export type Track = {
  title: string;
  artist: { name: string; provider_artist_id: string | null; display_name?: string | null };
  album: { name: string; provider_album_id: string | null } | null;
  duration_ms: number | null;
  artwork_url: string | null;
  source: ProviderSource;
  language: string | null;
  genres: string[];
  tags: string[];
  popularity: number | null;
  canonical_key: string;
};
export type RecommendationItem = {
  id: string;
  title: string;
  artist: string;
  explanation: string;
  track: Track;
  score: number;
  score_breakdown: Record<string, number>;
  provenance: ProviderSource[];
  attribute_evidence?: { track_id: string; attribute: "language" | "vocals" | "feel";
    value: string | null; origin: "provider" | "model" | "web"; basis: string; source_url?: string | null }[];
};
export type ProviderResult = {
  provider: string;
  tracks: Track[];
  error: { code: string; message: string } | null;
};
export type RecommendationResponse = {
  request_id: string;
  items: RecommendationItem[];
  sources: Record<string, ProviderResult>;
};
export type SearchReport = {
  attempts: { platform: string; region: string | null; stage: string; operation: string;
    status: "hit" | "no_results" | "error" | "not_configured" | "not_executed" | "unavailable" | "auth_required";
    result_count: number; error_code: string | null }[];
  end_reason: string;
  external_requests: number;
  incomplete: boolean;
};
export type RecordingResolveResponse = {
  request_id: string;
  status: "matched" | "ambiguous" | "not_found" | "unsupported_platform" | "unavailable" | "incomplete";
  matched_track: Track | null;
  resolution_id: string | null;
  candidates: { track: Track; resolution_id: string }[];
  search_report: SearchReport;
  sources: Record<string, ProviderResult>;
};
export type InterfaceLanguage = "en" | "zh";
export type VerifiedStorefront = "TW" | "HK";
export type SongIdentity = { title: string; artist: string };
export type OriginalIdentificationResponse = {
  request_id: string;
  status: "matched" | "unverified" | "unknown";
  suggestion: SongIdentity | null;
  matched_track: Track | null;
  verified_storefront?: VerifiedStorefront | null;
  sources: Record<string, ProviderResult>;
  resolution_id?: string | null;
  search_report?: SearchReport | null;
};
export type DiscoveryResponse = RecommendationResponse & {
  requires_confirmation?: boolean;
  resolution_id?: string | null;
  search_report?: SearchReport | null;
  candidate_resolutions?: Record<string, string>;
  seed_track: Track | null;
  seed_candidates: Track[];
  seed_status: "matched" | "ambiguous" | "unresolved";
  seed_storefront?: VerifiedStorefront | null;
  seed_resolution_source?: "verified_hint" | "user" | "model" | "catalog" | "none";
  guidance: string;
  guidance_provider: "local" | "openai_compatible";
  guidance_status: "ready" | "unavailable";
};
export type ProfileAffinity = { name: string; weight: number; display_name?: string | null };
export type PreferenceProfile = {
  artists: ProfileAffinity[];
  genres: ProfileAffinity[];
  tags: ProfileAffinity[];
  languages: ProfileAffinity[];
  recent_feedback: {
    track_key: string;
    artist: string;
    artist_display_name?: string | null;
    value: FeedbackValue;
  }[];
};
