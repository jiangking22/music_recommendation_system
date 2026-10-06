import { describe, expect, it, vi } from "vitest";
import { GET, POST } from "../app/api/v1/[...path]/route";

const params = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("fixed API proxy", () => {
  it("cancels a stalled incoming body when the browser disconnects", async () => {
    const controller = new AbortController();
    const cancelled = vi.fn();
    const request = new Request("http://localhost:3000/api/v1/feedback", { method: "POST",
      body: new ReadableStream({ cancel: cancelled }), signal: controller.signal, duplex: "half" } as RequestInit);
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    const pending = POST(request, params(["feedback"]));
    await Promise.resolve();
    controller.abort();
    const result = await pending;
    expect(result.status).toBe(408);
    expect(cancelled).toHaveBeenCalled();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("forwards cookie/origin/CSRF and preserves multiple cookies and SSE chunks", async () => {
    const upstream = new Response("event: done\ndata: {}\n\n", { headers: { "Content-Type": "text/event-stream" } });
    upstream.headers.append("Set-Cookie", "sonora_session=placeholder; HttpOnly; Path=/");
    upstream.headers.append("Set-Cookie", "sonora_csrf=placeholder; HttpOnly; Path=/");
    const fetcher = vi.fn().mockResolvedValue(upstream); vi.stubGlobal("fetch", fetcher);
    const request = new Request("http://localhost:3000/api/v1/agent/chat/stream", { method: "POST", body: "{}",
      headers: { Origin: "http://localhost:3000", Cookie: "sonora_session=placeholder", "X-CSRF-Token": "placeholder",
        "X-Forwarded-For": "attacker-supplied" } });
    const result = await POST(request, params(["agent", "chat", "stream"]));
    expect(fetcher.mock.calls[0][0]).toBe("http://127.0.0.1:8000/v1/agent/chat/stream");
    const headers = fetcher.mock.calls[0][1].headers;
    expect(headers.get("origin")).toBe("http://localhost:3000");
    expect(headers.get("cookie")).toContain("sonora_session=");
    expect(headers.has("x-forwarded-for")).toBe(false);
    expect(result.headers.getSetCookie()).toHaveLength(2);
    expect(result.headers.get("cache-control")).toBe("no-store");
    expect(await result.text()).toContain("event: done");
  });

  it("rejects oversized bodies and unsafe paths without upstream calls", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    const huge = new Request("http://localhost:3000/api/v1/feedback", { method: "POST", body: "x".repeat(65537) });
    expect((await POST(huge, params(["feedback"]))).status).toBe(413);
    expect((await GET(new Request("http://localhost:3000/api/v1/x"), params(["..", "health"]))).status).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("returns safe errors without following redirects and propagates cancellation", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 302, headers: { Location: "https://evil.example" } }));
    vi.stubGlobal("fetch", fetcher);
    const result = await GET(new Request("http://localhost:3000/api/v1/profile", { signal: controller.signal }), params(["profile"]));
    expect(result.status).toBe(502);
    expect(fetcher.mock.calls[0][1].redirect).toBe("manual");
    controller.abort();
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
  });
});
