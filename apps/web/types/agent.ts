import type { ProviderResult, RecommendationItem } from "./music";

export type ToolName = "get_user_profile" | "recommend_tracks" | "search_music_knowledge" | "explain_recommendation";
export type AgentStatus = { stage: string; label: string; tool?: ToolName; status?: string };
export type NativeSearchState = { status: "unavailable"; reason: "unsupported" | "unverified" | "local_mode" };
export type ModelCapabilities = { provider: string; supports_deep_thinking: boolean; native_search: NativeSearchState;
  music_catalog_search?: "available" | "unavailable"; web_search?: "available" | "not_configured" };
export type AgentSearchReport = {
  requested: number; returned: number; reused: boolean; expanded: boolean; external_requests: number;
  web_search: "not_configured" | "not_needed" | "used" | "error";
  end_reason: "enough" | "insufficient_matches" | "insufficient_evidence" | "upstream_failure" | "deadline" | "budget_exhausted" | "ambiguous";
  attempts: { platform: string; status: string; result_count: number }[];
};
export type AgentResponse = {
  conversation_id: string;
  answer: string;
  recommended_tracks: RecommendationItem[];
  used_tools: { name: ToolName; status: "ok" | "error" }[];
  explanation: string;
  citations: { document_id: string; title: string; chunk_id: string; text: string; score: number }[];
  sources: Record<string, ProviderResult>;
  provider: string;
  fallback_reason?: "llm_unavailable" | null;
  thinking_mode?: "basic" | "standard" | "deep";
  thinking_unavailable_reason?: "unsupported" | "llm_unavailable" | null;
  native_search?: NativeSearchState;
  search_report?: AgentSearchReport | null;
  web_references?: { title: string; url: string; track_ids: string[] }[];
};
