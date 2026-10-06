"use client";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { authRequest, invalidateSession, setSession, subscribeSession, type AuthSession } from "../lib/auth";
import { ApiError } from "../lib/errors";
import { authCopy } from "../lib/auth-copy";
import { readLanguage } from "../lib/i18n";

const Context = createContext<AuthSession | null>(null);
export function useAccount() { return useContext(Context); }

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [session, update] = useState<AuthSession | null>(null);
  const [checking, setChecking] = useState(true);
  const [failed, setFailed] = useState(false);
  const [attempt, retry] = useState(0);
  const [language, setLanguage] = useState<"en" | "zh">("en");
  const pathname = usePathname();
  const router = useRouter();
  const current = useRef<AuthSession | null>(null);
  useEffect(() => {
    let active = true;
    let validation: AbortController | null = null;
    let expiry: ReturnType<typeof setTimeout> | undefined;
    // Browser language is unavailable during the server's initial render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLanguage(readLanguage());
    async function check() {
      validation?.abort();
      clearTimeout(expiry);
      const controller = new AbortController(); validation = controller;
      setChecking(true); setFailed(false);
      try {
        const value = await authRequest<AuthSession>("me", undefined, controller.signal);
        if (!active || controller.signal.aborted) return;
        if (!value.user?.user_id || !value.user.username || !value.session_id) throw new Error("Invalid account");
        setSession(value); current.current = value; update(value); setChecking(false);
        const expires = value.expires_at ? Date.parse(value.expires_at) : NaN;
        if (Number.isFinite(expires)) {
          const expire = () => {
            const remaining = expires - Date.now();
            if (remaining <= 0) invalidateSession();
            // 30-day sessions exceed the browser's maximum timer delay.
            else expiry = setTimeout(expire, Math.min(remaining, 86400000));
          };
          expiry = setTimeout(expire, Math.max(0, Math.min(expires - Date.now(), 86400000)));
        }
      } catch (error) {
        if (!active || controller.signal.aborted || (error instanceof Error && error.name === "AbortError")) return;
        current.current = null; update(null); setChecking(false);
        if (error instanceof ApiError && error.status === 401) {
          const next = pathname + window.location.search;
          router.replace(`/login?next=${encodeURIComponent(next)}`);
        } else setFailed(true);
      }
    }
    const changed = () => { current.current = null; update(null); void check(); };
    const unsubscribe = subscribeSession(changed);
    const focus = () => { void check(); };
    const visibility = () => { if (document.visibilityState === "visible") void check(); };
    window.addEventListener("focus", focus);
    document.addEventListener("visibilitychange", visibility);
    void check();
    return () => { active = false; validation?.abort(); clearTimeout(expiry); unsubscribe(); window.removeEventListener("focus", focus);
      document.removeEventListener("visibilitychange", visibility); };
  }, [pathname, router, attempt]);
  const copy = authCopy[language];
  return <>
    {checking ? <main className="auth-status" role="status">{copy.checking}</main> : null}
    {failed ? <main className="auth-status" role="alert"><p>{copy.unavailable}</p>
      <button className="primary-button" onClick={() => retry((n) => n + 1)}>{copy.retry}</button></main> : null}
    {session ? <Context.Provider value={session}><div key={session.session_id} hidden={checking || failed}>{children}</div></Context.Provider> : null}
  </>;
}

export function AccountMenu({ language = "en" }: { language?: "en" | "zh" }) {
  const session = useAccount();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  if (!session) return null;
  const copy = authCopy[language];
  async function logout() {
    if (pending) return;
    setPending(true); setError(false);
    try {
      await authRequest("logout", {});
      invalidateSession(); router.replace("/login"); router.refresh();
    } catch { setPending(false); setError(true); }
  }
  return <details className="account-menu"><summary>{session.user.username}</summary>
    <div className="account-dropdown"><a href="/account/password">{copy.change}</a>
      <button type="button" disabled={pending} onClick={logout}>{pending ? copy.busy : copy.logout}</button>
      {error ? <p role="alert">{copy.unavailable}</p> : null}</div></details>;
}
