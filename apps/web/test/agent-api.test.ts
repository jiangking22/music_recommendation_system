import { testSession, withCsrf } from "./auth-helpers";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { streamAgentChat } from "../lib/agent";
import { invalidateSession } from "../lib/auth";

function streamed(parts: string[]) {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({
    start(controller) {
      parts.forEach((part) => controller.enqueue(encoder.encode(part)));
      controller.close();
    },
  }), { headers: { "Content-Type": "text/event-stream" } });
}

beforeEach(testSession);

describe("Agent SSE client", () => {
  it("gives deep chat a longer deadline and aborts a stalled stream on logout", async () => {
    const cancel = vi.fn();
    const fetcher = vi.fn().mockResolvedValue(new Response(new ReadableStream({ cancel }), {
      headers: { "Content-Type": "text/event-stream" },
    }));
    const timeout = vi.spyOn(AbortSignal, "timeout");
    const pending = streamAgentChat("/api", "聊音乐", undefined, vi.fn(), undefined, withCsrf(fetcher), true);
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(JSON.parse(fetcher.mock.calls[0][1].body).deep_thinking).toBe(true);
    expect(timeout.mock.calls.some(([ms]) => ms === 130000)).toBe(true);
    expect(timeout.mock.calls.some(([ms]) => ms === 70000)).toBe(false);
    invalidateSession(false);
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
    expect(cancel).toHaveBeenCalled();
  });

  it("parses fragmented status frames and forwards authenticated session and conversation", async () => {
    const result = { conversation_id: "one", answer: "Found music", recommended_tracks: [],
      used_tools: [], explanation: "", citations: [], sources: {}, provider: "local" };
    const fetcher = vi.fn().mockResolvedValue(streamed([
      'event: status\ndata: {"stage":"analy',
      'zing","label":"分析需求"}\n\nevent: done\ndata: ',
      JSON.stringify(result) + "\n\n",
    ]));
    const onStatus = vi.fn();
    expect(await streamAgentChat("/api", "学习",
      "previous", onStatus, undefined, withCsrf(fetcher))).toEqual(result);
    expect(onStatus).toHaveBeenCalledWith({ stage: "analyzing", label: "分析需求" });
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      message: "学习", conversation_id: "previous", deep_thinking: false });
  });

  it("rejects stream errors, missing done, and malformed terminal results", async () => {
    for (const wire of ['event: error\ndata: {"error":{"code":"agent_timeout","message":"Timed out"}}\n\n',
      'event: status\ndata: {"stage":"analyzing","label":"分析需求"}\n\n',
      'event: done\ndata: {"answer":"bad"}\n\n']) {
      const fetcher = vi.fn().mockResolvedValue(streamed([wire]));
      await expect(streamAgentChat("/api", "学习",
        undefined, vi.fn(), undefined, withCsrf(fetcher))).rejects.toThrow();
    }
  });

  it("decodes Chinese status text even when UTF-8 bytes arrive individually", async () => {
    const result = { conversation_id: "one", answer: "音乐", recommended_tracks: [], used_tools: [],
      explanation: "", citations: [], sources: {}, provider: "local" };
    const bytes = new TextEncoder().encode('event: status\ndata: {"stage":"tool","label":"调用工具"}\n\n'
      + 'event: done\ndata: ' + JSON.stringify(result) + '\n\n');
    const response = new Response(new ReadableStream({ start(controller) {
      for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
      controller.close();
    } }), { headers: { "Content-Type": "text/event-stream" } });
    const status = vi.fn();
    const fetcher = vi.fn().mockResolvedValue(response);
    expect((await streamAgentChat("/api", "学习",
      undefined, status, undefined, withCsrf(fetcher))).answer).toBe("音乐");
    expect(status).toHaveBeenCalledWith({ stage: "tool", label: "调用工具" });
  });
});
