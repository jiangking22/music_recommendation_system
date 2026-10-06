import { invalidateSession, setSession } from "../lib/auth";

export function testSession() {
  invalidateSession(false);
  setSession({ user: { user_id: "account_test", username: "Listener" }, session_id: "session_test" });
}

// The request/stream tests exercise business payloads; real auth behavior has its own suite.
export function withCsrf(fetcher: typeof fetch): typeof fetch {
  return (url, options) => String(url).endsWith("/auth/csrf")
    ? Promise.resolve(new Response(JSON.stringify({ csrf_token: "csrf_test" }))) : fetcher(url, options);
}
