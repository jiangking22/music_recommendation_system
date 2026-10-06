import { ApiError } from "./api";
import type { AgentResponse, AgentStatus } from "../types/agent";

function validateResult(value: unknown): AgentResponse {
  const result = value as AgentResponse;
  if (!result || typeof result.answer !== "string" || typeof result.conversation_id !== "string"
    || typeof result.explanation !== "string" || typeof result.provider !== "string"
    || !Array.isArray(result.recommended_tracks) || !Array.isArray(result.used_tools)
    || !Array.isArray(result.citations) || !result.sources
    || (result.fallback_reason != null && result.fallback_reason !== "llm_unavailable")
    || result.recommended_tracks.some((item) => !item || typeof item.id !== "string"
      || typeof item.title !== "string" || typeof item.artist !== "string"
      || typeof item.explanation !== "string" || typeof item.score !== "number"
      || !item.track?.source || !Array.isArray(item.provenance))
    || result.used_tools.some((tool) => !tool || typeof tool.name !== "string" || typeof tool.status !== "string")
    || result.citations.some((citation) => !citation || typeof citation.title !== "string"
      || typeof citation.text !== "string" || typeof citation.chunk_id !== "string")) {
    throw new ApiError("invalid_response", "Music assistant returned invalid results.", 502);
  }
  return result;
}

export async function streamAgentChat(
  baseUrl: string, deviceId: string, message: string, conversationId: string | undefined,
  onStatus: (status: AgentStatus) => void, signal?: AbortSignal, fetcher: typeof fetch = fetch,
): Promise<AgentResponse> {
  const response = await fetcher(`${baseUrl.replace(/\/$/, "")}/v1/agent/chat/stream`, {
    method: "POST", headers: { "Content-Type": "application/json", "X-Device-Id": deviceId },
    body: JSON.stringify({ message, device_id: deviceId, conversation_id: conversationId }),
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(65000)]) : AbortSignal.timeout(65000),
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(body.error?.code ?? "http_error", body.error?.message ?? "Music assistant unavailable.", response.status);
  }
  if (!response.body || !response.headers.get("Content-Type")?.startsWith("text/event-stream"))
    throw new ApiError("invalid_response", "Music assistant did not return a stream.", 502);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 1024 * 1024) throw new ApiError("invalid_response", "Response exceeds limit.", 502);
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replaceAll("\r\n", "\n");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const lines = frame.split("\n");
        const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
        const json = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
        if (!json) continue;
        let data;
        try { data = JSON.parse(json); }
        catch { throw new ApiError("invalid_response", "Music assistant returned invalid data.", 502); }
        if (event === "error") throw new ApiError(data.error?.code ?? "agent_error", data.error?.message ?? "Music assistant unavailable.", 502);
        if (event === "status" && typeof data.label === "string") onStatus(data);
        if (event === "done") return validateResult(data);
      }
    }
    throw new ApiError("incomplete_stream", "The reply was interrupted. Please try again.", 502);
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
