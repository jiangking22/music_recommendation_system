"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authRequest, invalidateSession, safeReturnPath, setSession, type AuthSession } from "../lib/auth";
import { authCopy } from "../lib/auth-copy";
import { ApiError } from "../lib/errors";
import { readLanguage, saveLanguage } from "../lib/i18n";

export default function AuthForm({ mode }: { mode: "login" | "register" | "password" }) {
  const router = useRouter();
  const [language, setLanguage] = useState<"en" | "zh">("en");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [next, setNext] = useState("/");
  const copy = authCopy[language];
  useEffect(() => {
    // Restore browser-only preferences after the matching server/client first render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLanguage(readLanguage());
    setNext(safeReturnPath(new URLSearchParams(window.location.search).get("next")));
  }, []);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (pending) return;
    setError("");
    if (mode !== "password" && !/^[A-Za-z0-9_]{3,32}$/.test(username)) { setError(copy.invalidUsername); return; }
    if (password.length < 15 || password.length > 128) { setError(copy.invalidPassword); return; }
    if (mode !== "login" && password !== confirmation) { setError(copy.mismatch); return; }
    setPending(true);
    try {
      if (mode === "password") {
        await authRequest("change-password", { old_password: oldPassword, new_password: password });
        invalidateSession(); router.replace("/login");
      } else {
        const value = await authRequest<AuthSession>(mode, { username, password, remember });
        invalidateSession(); setSession(value); router.replace(next);
      }
      setPassword(""); setConfirmation(""); setOldPassword(""); router.refresh();
    } catch (failure) {
      const code = failure instanceof ApiError ? failure.code : "";
      setError(code === "invalid_credentials" ? copy.invalid_credentials : code === "username_taken" ? copy.username_taken
        : code === "auth_rate_limited" ? copy.auth_rate_limited : code === "csrf_invalid" ? copy.csrf_invalid : copy.unavailable);
      setPending(false);
    }
  }
  const title = mode === "login" ? copy.loginTitle : mode === "register" ? copy.registerTitle : copy.changeTitle;
  return <div className="site-shell auth-shell" lang={language === "zh" ? "zh-CN" : "en"}>
    <header className="site-header"><Link href="/" className="brand"><span className="brand-icon">◉</span> sonora<span className="brand-dot">.</span></Link>
      <button className="language-toggle" type="button" onClick={() => {
        const value = language === "en" ? "zh" : "en"; setLanguage(value); saveLanguage(value); setError("");
      }}>{language === "en" ? "中文" : "English"}</button></header>
    <main className="auth-layout"><section className="auth-intro"><span className="eyebrow">SONORA / YOUR ACCOUNT</span>
      <h1>{title}</h1><p>{mode === "password" ? copy.changeHelp : copy.intro}</p>
      <div className="auth-vinyl" aria-hidden="true"><span>SONORA<br />SESSIONS</span></div></section>
      <section className="auth-panel" aria-labelledby="auth-form-title"><h2 id="auth-form-title">{mode === "login" ? copy.login : mode === "register" ? copy.register : copy.change}</h2>
        <form onSubmit={submit} aria-busy={pending}>
          {mode !== "password" ? <div className="auth-field"><label htmlFor="username">{copy.username}</label>
            <input id="username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} minLength={3} maxLength={32}
              value={username} onChange={(e) => setUsername(e.target.value)} required disabled={pending} aria-describedby={mode === "register" ? "username-help" : undefined} />
            {mode === "register" ? <small id="username-help">{copy.usernameHelp}</small> : null}</div> :
            <div className="auth-field"><label htmlFor="old-password">{copy.oldPassword}</label><input id="old-password" type={show ? "text" : "password"}
              autoComplete="current-password" minLength={15} maxLength={128} value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} required disabled={pending} /></div>}
          <div className="auth-field"><label htmlFor="password">{mode === "password" ? copy.newPassword : copy.password}</label>
            <input id="password" name="password" type={show ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={15} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} required disabled={pending} aria-describedby="password-help" />
            <small id="password-help">{copy.passwordHelp}</small></div>
          {mode !== "login" ? <div className="auth-field"><label htmlFor="confirm-password">{copy.confirm}</label>
            <input id="confirm-password" type={show ? "text" : "password"} autoComplete="new-password" minLength={15} maxLength={128}
              value={confirmation} onChange={(e) => setConfirmation(e.target.value)} required disabled={pending} /></div> : null}
          <button className="auth-show" type="button" aria-pressed={show} onClick={() => setShow(!show)}>{show ? copy.hide : copy.show}</button>
          {mode === "login" ? <label className="auth-remember"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} disabled={pending} />{copy.remember}</label> : null}
          {error ? <p className="auth-error" role="alert">{error}</p> : null}
          <button className="primary-button auth-submit" disabled={pending} type="submit">{pending ? copy.busy : mode === "login" ? copy.login : mode === "register" ? copy.register : copy.save}<span aria-hidden="true">↗</span></button>
        </form>
        {mode === "password" ? <Link href="/" className="auth-switch">{copy.back}</Link> : <>
          <p className="auth-switch">{mode === "login" ? copy.newAccount : copy.existing} <Link href={`${mode === "login" ? "/register" : "/login"}?next=${encodeURIComponent(next)}`}>{mode === "login" ? copy.register : copy.login}</Link></p>
          <details className="auth-recovery"><summary>{copy.forgotten}</summary><p>{copy.recovery}</p></details></>}
      </section></main></div>;
}
