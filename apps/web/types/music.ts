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
};
export type DiscoveryResponse = RecommendationResponse & {
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
