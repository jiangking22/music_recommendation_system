import { ApiError } from "./errors";

export type AuthSession = { user: { user_id: string; username: string }; session_id: string; expires_at?: string | null };
let identity: AuthSession | null = null;
let lifetime = new AbortController();
let csrfToken: string | null = null;
let csrfPending: Promise<string> | null = null;
let channel: BroadcastChannel | null = null;
const listeners = new Set<() => void>();
export function sessionSignal() { return lifetime.signal; }

export function safeReturnPath(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/";
  try {
    const decoded = decodeURIComponent(value);
    if (/[\\\s]/.test(decoded) || decoded.startsWith("//")) return "/";
    const url = new URL(value, "https://sonora.invalid");
    if (url.origin !== "https://sonora.invalid" || /^(\/api(?:\/|$)|\/login(?:\/|$)|\/register(?:\/|$))/.test(url.pathname)) return "/";
    return url.pathname + url.search + url.hash;
  } catch { return "/"; }
}

export function setSession(session: AuthSession) {
  if (identity?.session_id !== session.session_id) {
    lifetime.abort(); lifetime = new AbortController(); csrfToken = null; csrfPending = null;
  }
  identity = session;
}

export function invalidateSession(broadcast = true) {
  identity = null; csrfToken = null; csrfPending = null;
  lifetime.abort(); lifetime = new AbortController();
  listeners.forEach((listener) => listener());
  if (broadcast) {
    channel?.postMessage("changed");
    // Non-secret event marker is a fallback for browsers without BroadcastChannel.
    try { localStorage.setItem("sonora.auth-event", `${Date.now()}:${Math.random()}`); } catch { /* storage optional */ }
  }
}

export function subscribeSession(listener: () => void) {
  if (typeof window !== "undefined" && !channel && typeof BroadcastChannel !== "undefined") {
    channel = new BroadcastChannel("sonora.auth");
    channel.onmessage = () => invalidateSession(false);
  }
  listeners.add(listener);
  const storage = (event: StorageEvent) => { if (event.key === "sonora.auth-event") invalidateSession(false); };
  window.addEventListener("storage", storage);
  return () => { listeners.delete(listener); window.removeEventListener("storage", storage); };
}

export async function authFetch(url: string, options: RequestInit = {}, fetcher: typeof fetch = fetch,
  timeoutMs = 70000): Promise<Response> {
  const authenticated = !url.includes("/v1/auth/");
  if (authenticated && !identity) throw new ApiError("authentication_required", "Please sign in.", 401);
  const current = identity;
  const epoch = lifetime.signal;
  const signal = AbortSignal.any([epoch, AbortSignal.timeout(timeoutMs), ...(options.signal ? [options.signal] : [])]);
  const headers = new Headers(options.headers);
  if (current && (authenticated || /\/auth\/(logout|change-password)$/.test(url))) headers.set("X-Session-Id", current.session_id);
  if (options.method && !["GET", "HEAD", "OPTIONS"].includes(options.method)) {
    if (!csrfToken) {
      if (!csrfPending) {
        const pending = (async () => {
          // Bootstrap belongs to the session, rather than whichever write starts first.
          const result = await fetcher("/api/v1/auth/csrf", { credentials: "same-origin", cache: "no-store",
            signal: AbortSignal.any([epoch, AbortSignal.timeout(12000)]) });
          if (!result.ok) throw new ApiError("auth_unavailable", "Account service unavailable.", result.status);
          const csrf = await result.json();
          if (typeof csrf.csrf_token !== "string") throw new ApiError("invalid_response", "Invalid account response.", 502);
          if (epoch.aborted) throw new DOMException("Session changed.", "AbortError");
          csrfToken = csrf.csrf_token;
          return csrf.csrf_token as string;
        })();
        csrfPending = pending;
        void pending.finally(() => { if (csrfPending === pending) csrfPending = null; }).catch(() => {});
      }
      await csrfPending;
    }
    if (signal.aborted) throw new DOMException("Request cancelled.", "AbortError");
    headers.set("X-CSRF-Token", csrfToken!);
  }
  const response = await fetcher(url, { ...options, headers, signal, credentials: "same-origin", cache: "no-store" });
  if (epoch.aborted) { await response.body?.cancel(); throw new DOMException("Session changed.", "AbortError"); }
  if (authenticated && response.status === 401) invalidateSession();
  if (response.status === 403) csrfToken = null;
  return response;
}

export async function authRequest<T>(operation: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await authFetch(`/api/v1/auth/${operation}`, { method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(12000)]) : AbortSignal.timeout(12000) });
  } catch (error) {
    if (error instanceof ApiError || (error instanceof Error && error.name === "AbortError")) throw error;
    throw new ApiError("network_error", "Account service unavailable. Please retry.", 0);
  }
  const value = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(value?.error?.code ?? "auth_unavailable", value?.error?.message ?? "Account service unavailable.", response.status);
  if (!value) throw new ApiError("invalid_response", "Invalid account response.", 502);
  return value as T;
}
