import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AuthForm from "../components/AuthForm";
import { AuthGate } from "../components/AuthGate";
import { authFetch, invalidateSession, safeReturnPath, setSession } from "../lib/auth";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation, usePathname: () => "/agent" }));
const session = { user: { user_id: "one", username: "Listener" }, session_id: "login_one" };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });

beforeEach(() => { vi.clearAllMocks(); invalidateSession(false); });

describe("account lifecycle", () => {
  it("allows long Unicode passwords within the 128-character limit", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.endsWith("/csrf") ? json({ csrf_token: "csrf-test" }) : json(session, 201))));
    render(<AuthForm mode="register" />);
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "UnicodeListener" } });
    const password = "🎵".repeat(100);
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: password } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/"));
  });

  it("clears a visible profile at the server's session expiry without another user action", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(json({ ...session, expires_at: new Date(Date.now() + 60000).toISOString() }))
      .mockImplementation(() => new Promise(() => {})));
    try {
      await act(async () => { render(<AuthGate><p>Private profile</p></AuthGate>); });
      expect(screen.getByText("Private profile")).toBeInTheDocument();
      await act(async () => { await vi.advanceTimersByTimeAsync(60001); });
      expect(screen.queryByText("Private profile")).not.toBeInTheDocument();
    } finally { vi.useRealTimers(); }
  });

  it("binds logout and password changes to the visible login session", async () => {
    setSession(session);
    const fetcher = vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.endsWith("/csrf") ? json({ csrf_token: "csrf-test" }) : json({ ok: true })));
    for (const operation of ["logout", "change-password"]) {
      await authFetch(`/api/v1/auth/${operation}`, { method: "POST", body: "{}" }, fetcher);
      const call = fetcher.mock.calls.find(([url]) => String(url).endsWith(operation))!;
      expect(new Headers(call[1].headers).get("X-Session-Id")).toBe("login_one");
    }
  });

  it("shares one CSRF bootstrap across concurrent first writes", async () => {
    setSession(session);
    const fetcher = vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.endsWith("/csrf") ? json({ csrf_token: "csrf-test" }) : json({ ok: true })));
    await Promise.all([authFetch("/api/v1/feedback", { method: "POST" }, fetcher),
      authFetch("/api/v1/recommendations", { method: "POST" }, fetcher)]);
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith("/csrf"))).toHaveLength(1);
  });

  it("only accepts local return paths", () => {
    for (const value of ["https://evil.example", "//evil.example", "/\\evil", "/login", "/api/v1/profile", "/%5cevil", "/\n/evil"])
      expect(safeReturnPath(value)).toBe("/");
    expect(safeReturnPath("/agent?mode=music")).toBe("/agent?mode=music");
  });

  it("carries session context, cookies and CSRF without device ownership", async () => {
    setSession(session);
    const fetcher = vi.fn().mockResolvedValueOnce(json({ csrf_token: "csrf-test" }))
      .mockResolvedValueOnce(json({ items: [] }));
    await authFetch("/api/v1/recommendations", { method: "POST", body: "{}" }, fetcher);
    expect(fetcher.mock.calls[1][1]).toMatchObject({ credentials: "same-origin", cache: "no-store" });
    const headers = new Headers(fetcher.mock.calls[1][1].headers);
    expect(headers.get("X-Session-Id")).toBe("login_one");
    expect(headers.get("X-CSRF-Token")).toBe("csrf-test");
    expect(headers.has("X-Device-Id")).toBe(false);
  });

  it("aborts in-flight requests and discards late successful responses after logout", async () => {
    setSession(session);
    let finish!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementation(() => new Promise<Response>((resolve) => { finish = resolve; }));
    const pending = authFetch("/api/v1/profile", {}, fetcher);
    invalidateSession(false);
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
    finish(json({ private: "old account" }));
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  it("hides business content until identity validation and redirects anonymous users", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ error: { code: "authentication_required" } }, 401)));
    render(<AuthGate><p>Private profile</p></AuthGate>);
    expect(screen.queryByText("Private profile")).not.toBeInTheDocument();
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/login?next=%2Fagent"));
  });

  it("clears private content immediately when another tab changes the session", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(json(session))
      .mockImplementation(() => new Promise(() => {}));
    vi.stubGlobal("fetch", fetcher);
    render(<AuthGate><p>Private profile</p></AuthGate>);
    expect(await screen.findByText("Private profile")).toBeInTheDocument();
    act(() => { invalidateSession(false); });
    expect(screen.queryByText("Private profile")).not.toBeInTheDocument();
  });

  it("registers with confirmation and supports password visibility", async () => {
    const fetcher = vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.endsWith("/csrf") ? json({ csrf_token: "csrf-test" }) : json(session, 201)));
    vi.stubGlobal("fetch", fetcher);
    render(<AuthForm mode="register" />);
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "Listener" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "long password with spaces" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "different password" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords do not match");
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "long password with spaces" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/"));
    const posted = fetcher.mock.calls.find(([url]) => String(url).endsWith("/register"));
    expect(JSON.parse(posted![1].body)).toMatchObject({ username: "Listener", password: "long password with spaces" });
  });
});
