const ROOT = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
export const dynamic = "force-dynamic";

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!path.length || path.some((part) => !/^[A-Za-z0-9_-]+$/.test(part)))
    return Response.json({ error: { code: "invalid_path", message: "Invalid API path." } }, { status: 400 });
  const headers = new Headers();
  for (const key of ["cookie", "origin", "content-type", "x-csrf-token", "x-session-id", "x-request-id", "traceparent"])
    if (request.headers.has(key)) headers.set(key, request.headers.get(key)!);
  try {
    let body: Uint8Array<ArrayBuffer> | undefined;
    if (request.method === "POST" && request.body) {
      const reader = request.body.getReader(); const chunks: Uint8Array[] = []; let length = 0;
      const deadline = AbortSignal.any([request.signal, AbortSignal.timeout(10000)]);
      const cancel = () => { void reader.cancel().catch(() => {}); };
      deadline.addEventListener("abort", cancel, { once: true });
      if (deadline.aborted) cancel();
      try {
        while (true) {
          const { value, done } = await reader.read(); if (done) break;
          length += value.length;
          if (length > 65536) { await reader.cancel(); return Response.json({ error: { code: "request_too_large", message: "Request too large." } }, { status: 413 }); }
          chunks.push(value);
        }
      } finally { deadline.removeEventListener("abort", cancel); }
      if (deadline.aborted) return Response.json({ error: { code: "request_timeout", message: "Request cancelled or timed out." } },
        { status: 408, headers: { "Cache-Control": "no-store" } });
      body = new Uint8Array(length); let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
    }
    const target = `${ROOT.replace(/\/$/, "")}/v1/${path.join("/")}${new URL(request.url).search}`;
    const chat = path.join("/") === "agent/chat" || path.join("/") === "agent/chat/stream";
    const result = await fetch(target, { method: request.method, headers, body,
      cache: "no-store", redirect: "manual", signal: AbortSignal.any([request.signal, AbortSignal.timeout(chat ? 140000 : 70000)]) });
    const outgoing = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    for (const key of ["content-type", "x-request-id", "x-trace-id", "retry-after", "x-accel-buffering"])
      if (result.headers.has(key)) outgoing.set(key, result.headers.get(key)!);
    for (const value of result.headers.getSetCookie()) outgoing.append("set-cookie", value);
    if (result.status >= 300 && result.status < 400) { await result.body?.cancel(); throw new Error("Unexpected API redirect"); }
    return new Response(result.body, { status: result.status, headers: outgoing });
  } catch {
    return Response.json({ error: { code: "api_unavailable", message: "Music service unavailable. Please retry." } },
      { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}

export { proxy as GET, proxy as POST };
