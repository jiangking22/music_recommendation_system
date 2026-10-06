import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProductClient from "../components/ProductClient";
import type { DiscoveryResponse, PreferenceProfile } from "../types/music";

const api = vi.hoisted(() => ({
  recommend: vi.fn(),
  discover: vi.fn(),
  identifyOriginal: vi.fn(),
  resolveRecording: vi.fn(),
  feedback: vi.fn(),
  profile: vi.fn(),
}));
vi.mock("../lib/api", () => ({ createApiClient: () => api }));

const emptyProfile: PreferenceProfile = {
  artists: [],
  genres: [],
  tags: [],
  languages: [],
  recent_feedback: [],
};
const track = {
  title: "Night Signal",
  artist: { name: "Mira Vale", provider_artist_id: null },
  album: { name: "Blue Hours", provider_album_id: null },
  duration_ms: null,
  artwork_url: null,
  source: {
    provider: "local",
    provider_track_id: "one",
    external_url: "https://example.com/song",
  },
  language: "en",
  genres: ["Jazz"],
  tags: ["Night"],
  popularity: null,
  canonical_key: "night signal::mira vale",
};
const result: DiscoveryResponse = {
  request_id: "one",
  seed_track: null,
  seed_candidates: [],
  seed_status: "unresolved",
  guidance: "Explore the available catalog.",
  guidance_provider: "local",
  guidance_status: "ready",
  items: [
    {
      id: "night signal::mira vale",
      title: track.title,
      artist: track.artist.name,
      explanation: "Matches your night listening.",
      track,
      score: 0.82,
      score_breakdown: { seed_relevance: 0.4 },
      provenance: [track.source],
    },
  ],
  sources: { local: { provider: "local", tracks: [track], error: null } },
};

beforeEach(() => {
  vi.resetAllMocks();
  api.profile.mockResolvedValue(emptyProfile);
  api.discover.mockResolvedValue(result);
  api.feedback.mockResolvedValue({
    track_key: result.items[0].id,
    value: "like",
  });
});

describe("original candidate rejection", () => {
  const candidate = { ...track, title: "Shared Title" };
  const newTrack = { ...candidate, artist: { name: "Another Artist", provider_artist_id: null },
    canonical_key: "shared title::another artist" };
  const identification = { request_id: "identify", status: "matched", suggestion: {
    title: "Shared Title", artist: "Another Artist" }, matched_track: newTrack, sources: {} };

  async function showChoices() {
    api.discover.mockResolvedValueOnce({ ...result, items: [], seed_status: "ambiguous",
      seed_candidates: [candidate] });
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "Shared Title" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await screen.findByText("Which artist did you mean?");
  }

  it("identifies from the original query and waits for confirmation before recommending", async () => {
    api.identifyOriginal.mockResolvedValue(identification);
    await showChoices();
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "Edited Input" } });
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    expect(await screen.findByText("Shared Title · Another Artist")).toBeInTheDocument();
    expect(api.identifyOriginal).toHaveBeenCalledWith("Shared Title", "en", [
      { title: "Shared Title", artist: "Mira Vale" }], expect.any(AbortSignal));
    expect(api.discover).toHaveBeenCalledTimes(1);
    api.discover.mockResolvedValueOnce({ ...result, seed_status: "matched", seed_track: newTrack });
    fireEvent.click(screen.getByRole("button", { name: "Confirm and recommend" }));
    await screen.findByText("Night Signal");
    expect(api.discover).toHaveBeenLastCalledWith("Shared Title", 5, "en", "Another Artist");
    expect(screen.getByText("Model suggestion, confirmed by you.")).toBeInTheDocument();
  });

  it("shows unmatched suggestions without a confirmation or playback button", async () => {
    api.identifyOriginal.mockResolvedValue({ ...identification, status: "unverified", matched_track: null });
    await showChoices();
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    expect(await screen.findByText("Model suggestion; not verified in the music catalog.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm and recommend" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /open track/i })).not.toBeInTheDocument();
    expect(api.discover).toHaveBeenCalledTimes(1);
  });

  it("allows rejection of a matched fallback-model artist and manual correction", async () => {
    api.identifyOriginal.mockResolvedValue(identification);
    await showChoices();
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    await screen.findByText("Shared Title · Another Artist");
    fireEvent.click(screen.getByRole("button", { name: "Different artist — I'll provide it" }));
    expect(screen.getByLabelText("Correct artist")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Verify artist" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Confirm and recommend" })).not.toBeInTheDocument();
    expect(api.discover).toHaveBeenCalledTimes(1);
    expect(api.identifyOriginal).toHaveBeenCalledTimes(1);
  });

  it("offers online evidence and uses the verified storefront for confirmation and refresh", async () => {
    const verified = { ...newTrack, source: { ...newTrack.source,
      external_url: "https://music.apple.com/tw/song/123" } };
    api.identifyOriginal.mockResolvedValue({ ...identification, matched_track: verified, verified_storefront: "TW" });
    await showChoices();
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    expect(await screen.findByText("Verified online against an official music catalog.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View verification source ↗" })).toHaveAttribute(
      "href", "https://music.apple.com/tw/song/123");
    api.discover.mockResolvedValue({ ...result, seed_status: "matched", seed_track: verified, seed_storefront: "TW" });
    fireEvent.click(screen.getByRole("button", { name: "Confirm and recommend" }));
    await screen.findByText("Night Signal");
    expect(api.discover).toHaveBeenLastCalledWith("Shared Title", 5, "en", "Another Artist", "TW");
    fireEvent.click(screen.getByRole("button", { name: /^like night signal$/i }));
    fireEvent.click(await screen.findByRole("button", { name: /refresh recommendations/i }));
    await waitFor(() => expect(api.discover).toHaveBeenCalledTimes(3));
    expect(api.discover).toHaveBeenLastCalledWith("Shared Title", 5, "en", "Another Artist", "TW");
    await waitFor(() => expect(screen.getByRole("button", { name: /find music/i })).toBeEnabled());
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "New Title" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await waitFor(() => expect(api.discover).toHaveBeenLastCalledWith("New Title", 5, "en", undefined));
  });

  it("offers the real QQ recording evidence and confirms through the existing multi-source discovery", async () => {
    const qqTrack = { ...newTrack, source: { provider: "qq", provider_track_id: "102210521",
      external_url: "https://y.qq.com/n/ryqq/songDetail/004AGa4s1SF7je" } };
    api.identifyOriginal.mockResolvedValue({ ...identification, matched_track: qqTrack, verified_storefront: null });
    await showChoices();
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    expect(await screen.findByRole("link", { name: "View verification source ↗" })).toHaveAttribute(
      "href", qqTrack.source.external_url);
    expect(api.discover).toHaveBeenCalledTimes(1);
    api.discover.mockResolvedValue({ ...result, seed_status: "matched", seed_track: qqTrack });
    fireEvent.click(screen.getByRole("button", { name: "Confirm and recommend" }));
    await screen.findByText("Night Signal");
    expect(api.discover).toHaveBeenLastCalledWith("Shared Title", 5, "en", "Another Artist");
  });

  it("keeps choices after a failure and allows a translated manual retry", async () => {
    api.identifyOriginal.mockRejectedValueOnce(Object.assign(new Error("safe"), {
      code: "identification_not_configured" })).mockResolvedValueOnce({ ...identification,
      status: "unknown", suggestion: null, matched_track: null });
    await showChoices();
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No model API is configured on the server.");
    expect(screen.getByRole("button", { name: "Shared Title · Mira Vale" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
    expect(screen.getByRole("alert")).toHaveTextContent("服务端尚未配置大模型 API。");
    fireEvent.click(screen.getByRole("button", { name: "重试识别" }));
    expect(await screen.findByText("暂未找到其他可靠候选，请修改歌名或补充歌手。" )).toBeInTheDocument();
    expect(api.identifyOriginal).toHaveBeenCalledTimes(2);
    expect(api.discover).toHaveBeenCalledTimes(1);
  });

  it("blocks duplicate clicks and aborts identification when a new search starts", async () => {
    let finish!: (value: typeof identification) => void;
    api.identifyOriginal.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    await showChoices();
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    expect(screen.getByText("Calling the model and verifying the recording online…")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    expect(api.identifyOriginal).toHaveBeenCalledTimes(1);
    const signal = api.identifyOriginal.mock.calls[0][3];
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "New Search" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await screen.findByText("Night Signal");
    expect(signal.aborted).toBe(true);
    await act(async () => finish(identification));
    expect(screen.queryByText("Shared Title · Another Artist")).not.toBeInTheDocument();
  });

  it.each([
    ["identification_unavailable", "The model API is unavailable. Please try again."],
    ["identification_timeout", "Identification timed out. Please try again."],
    ["identification_invalid_output", "The model returned invalid identification data. Please try again."],
    ["identification_busy", "The music service is busy. Please try again later."],
  ])("shows the specific %s error without losing artist choices", async (code, message) => {
    api.identifyOriginal.mockRejectedValueOnce(Object.assign(new Error("safe"), { code }));
    await showChoices();
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("button", { name: "Shared Title · Mira Vale" })).toBeEnabled();
    expect(api.identifyOriginal).toHaveBeenCalledTimes(1);
  });

  it("preserves confirmed model origin through a failed recommendation retry and language change", async () => {
    api.identifyOriginal.mockResolvedValue(identification);
    await showChoices();
    fireEvent.click(screen.getByRole("button", { name: "None of the above" }));
    await screen.findByRole("button", { name: "Confirm and recommend" });
    api.discover.mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ...result, seed_status: "matched", seed_track: newTrack });
    fireEvent.click(screen.getByRole("button", { name: "Confirm and recommend" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Model suggestion, confirmed by you.")).toBeInTheDocument();
    expect(api.discover).toHaveBeenLastCalledWith("Shared Title", 5, "en", "Another Artist");
    fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
    expect(screen.getByText("模型建议，经用户确认")).toBeInTheDocument();
    expect(api.identifyOriginal).toHaveBeenCalledTimes(1);
  });
});

describe("all model artists require confirmation", () => {
  const suggested = { ...track, title: "Shared Title" };
  const corrected = { ...suggested, artist: { name: "Correct Artist", provider_artist_id: null },
    canonical_key: "shared title::correct artist" };
  async function showSuggestion() {
    api.discover.mockResolvedValueOnce({ ...result, items: [], seed_track: suggested, seed_status: "matched",
      seed_resolution_source: "model", requires_confirmation: true, resolution_id: "model-proof" });
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "Shared Title" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await screen.findByRole("button", { name: "Confirm and recommend" });
  }
  it("holds the initial suggestion until confirmation and retains its proof", async () => {
    await showSuggestion();
    expect(api.discover).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("No tracks found")).not.toBeInTheDocument();
    expect(screen.getByText("Awaiting artist confirmation")).toBeInTheDocument();
    api.discover.mockResolvedValueOnce({ ...result, seed_track: suggested, seed_status: "matched" });
    fireEvent.click(screen.getByRole("button", { name: "Confirm and recommend" }));
    await screen.findByText("Night Signal");
    expect(api.discover).toHaveBeenLastCalledWith("Shared Title", 5, "en", "Mira Vale", undefined, "model-proof");
    expect(screen.getByText("Model suggestion, confirmed by you.")).toBeInTheDocument();
  });
  it("verifies a supplied artist across sources and only recommends after selecting that recording", async () => {
    await showSuggestion();
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "Edited Input" } });
    fireEvent.click(screen.getByRole("button", { name: "Different artist — I'll provide it" }));
    expect(screen.queryByRole("button", { name: "Confirm and recommend" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Correct artist"), { target: { value: "Correct Artist" } });
    api.resolveRecording.mockResolvedValueOnce({ request_id: "manual", status: "matched",
      matched_track: corrected, resolution_id: "correct-proof", candidates: [], sources: {},
      search_report: { attempts: [], end_reason: "matched", external_requests: 1, incomplete: false } });
    fireEvent.click(screen.getByRole("button", { name: "Verify artist" }));
    await screen.findByText("Shared Title · Correct Artist");
    expect(api.resolveRecording).toHaveBeenLastCalledWith("Shared Title", "en", "Correct Artist", undefined, undefined, expect.any(AbortSignal));
    expect(api.discover).toHaveBeenCalledTimes(1);
    api.discover.mockResolvedValueOnce({ ...result, seed_status: "matched", seed_track: corrected });
    fireEvent.click(screen.getByRole("button", { name: "Confirm and recommend" }));
    await screen.findByText("Night Signal");
    expect(api.discover).toHaveBeenLastCalledWith("Shared Title", 5, "en", "Correct Artist", undefined, "correct-proof");
    expect(screen.queryByText("Model suggestion, confirmed by you.")).not.toBeInTheDocument();
  });
  it("cancels manual correction on a new search and ignores its late recording", async () => {
    await showSuggestion();
    fireEvent.click(screen.getByRole("button", { name: "Different artist — I'll provide it" }));
    fireEvent.change(screen.getByLabelText("Correct artist"), { target: { value: "Correct Artist" } });
    let release!: (value: unknown) => void;
    api.resolveRecording.mockReturnValueOnce(new Promise(resolve => { release = resolve; }));
    fireEvent.click(screen.getByRole("button", { name: "Verify artist" }));
    const signal = api.resolveRecording.mock.calls[0][5] as AbortSignal;
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "New Query" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await screen.findByText("Night Signal");
    expect(signal.aborted).toBe(true);
    await act(async () => release({ request_id: "late", status: "matched", matched_track: corrected,
      resolution_id: "late-proof", candidates: [], sources: {} }));
    expect(screen.queryByText("Shared Title · Correct Artist")).not.toBeInTheDocument();
    expect(api.discover).toHaveBeenLastCalledWith("New Query", 5, "en", undefined);
  });
});

describe("recommendation home", () => {
  it("renders empty state then recommendation details", async () => {
    render(<ProductClient />);
    expect(screen.getByText(/Start with a song/i)).toBeInTheDocument();
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), {
      target: { value: "jazz" },
    });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    expect(await screen.findByText("Night Signal")).toBeInTheDocument();
    expect(screen.getByText("Mira Vale")).toBeInTheDocument();
    expect(screen.getByText(/Blue Hours/)).toBeInTheDocument();
    expect(
      screen.getByText("Matches your night listening."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open track/i })).toHaveAttribute(
      "href",
      "https://example.com/song",
    );
  });

  it("shows loading, full error, and partial provider failure", async () => {
    let finish!: (value: DiscoveryResponse) => void;
    api.discover.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), {
      target: { value: "jazz" },
    });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    expect(screen.getByText(/automatically expanding the search/i)).toBeInTheDocument();
    finish({
      ...result,
      sources: {
        itunes: {
          provider: "itunes",
          tracks: [],
          error: { code: "timeout", message: "Timed out" },
        },
      },
    });
    expect(await screen.findByText("Night Signal")).toBeInTheDocument();
    expect(
      screen.getByText(/some sources are unavailable/i),
    ).toBeInTheDocument();
    api.discover.mockRejectedValueOnce(new Error("offline"));
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /couldn.t load recommendations/i,
    );
  });

  it("updates feedback, restores failed changes, and refreshes profile", async () => {
    api.profile.mockResolvedValueOnce(emptyProfile).mockResolvedValue({
      ...emptyProfile,
      artists: [{ name: "mira vale", weight: 1 }],
      recent_feedback: [
        { track_key: result.items[0].id, artist: "mira vale", value: "like" },
      ],
    });
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), {
      target: { value: "jazz" },
    });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await screen.findByText("Night Signal");
    fireEvent.click(
      screen.getByRole("button", { name: /^like night signal$/i }),
    );
    expect(
      screen.getByRole("button", { name: /^like night signal$/i }),
    ).toHaveAttribute("aria-pressed", "true");
    await waitFor(() =>
      expect(api.feedback).toHaveBeenCalledWith(track, "like"),
    );
    expect((await screen.findAllByText("mira vale")).length).toBeGreaterThan(0);
    api.feedback.mockRejectedValueOnce(new Error("offline"));
    fireEvent.click(
      screen.getByRole("button", { name: /dislike night signal/i }),
    );
    expect(
      await screen.findByText(/couldn.t save feedback/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^like night signal$/i }),
    ).toHaveAttribute("aria-pressed", "true");
    api.feedback.mockResolvedValueOnce({
      track_key: result.items[0].id,
      value: "dislike",
    });
    fireEvent.click(
      screen.getByRole("button", { name: /^dislike night signal$/i }),
    );
    await waitFor(() =>
      expect(api.feedback).toHaveBeenLastCalledWith(track, "dislike"),
    );
    expect(
      screen.getByRole("button", { name: /^dislike night signal$/i }),
    ).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(
      screen.getByRole("button", { name: /refresh recommendations/i }),
    );
    await waitFor(() => expect(api.discover).toHaveBeenCalledTimes(2));
  });

  it("translates populated UI and explanations while preserving music and theme headings", async () => {
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "jazz" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await screen.findByText("Night Signal");
    fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
    expect(screen.getByLabelText("歌曲或心情")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "喜欢 Night Signal" })).toBeInTheDocument();
    expect(screen.getByText("符合输入线索")).toBeInTheDocument();
    expect(screen.getByText("Night Signal")).toBeInTheDocument();
    expect(screen.getByText("Mira Vale")).toBeInTheDocument();
    expect(screen.getByText(/Blue Hours/)).toBeInTheDocument();
    expect(screen.getByText("local")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Listen into\s*something new\./);
    expect(screen.getByRole("heading", { name: "Made for this moment" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Preference profile" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("zh-CN");
    expect(api.discover).toHaveBeenCalledTimes(1);
  });

  it("restores and persists the interface language and sends it with discovery", async () => {
    localStorage.setItem("sonora.interface-language", "zh");
    const view = render(<ProductClient />);
    await screen.findByText("准备发现新音乐");
    fireEvent.change(screen.getByLabelText("歌曲或心情"), { target: { value: "我好想你" } });
    fireEvent.click(screen.getByRole("button", { name: /发现音乐/ }));
    await screen.findByText("Night Signal");
    expect(api.discover).toHaveBeenCalledWith("我好想你", 5, "zh", undefined);
    fireEvent.click(screen.getByRole("button", { name: "Switch to English" }));
    expect(localStorage.getItem("sonora.interface-language")).toBe("en");
    view.unmount();
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    expect(document.documentElement.lang).toBe("en");
  });

  it("translates a pending request and its error using the current locale", async () => {
    let fail!: (reason: Error) => void;
    api.discover.mockImplementationOnce(() => new Promise((_, reject) => { fail = reject; }));
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "jazz" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
    expect(screen.getByText("正在检索音乐曲库，并自动扩大检索范围…")).toBeInTheDocument();
    fail(new Error("offline"));
    expect(await screen.findByRole("alert")).toHaveTextContent("暂时无法获取推荐，请检查服务后重试。");
    fireEvent.click(screen.getByRole("button", { name: "Switch to English" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/couldn.t load recommendations/i);
  });

  it("shows a resolved seed separately and asks for artist confirmation on ambiguous matches", async () => {
    const seedTrack = { ...track, title: "我好想你", artist: { name: "苏打绿", provider_artist_id: null }, canonical_key: "我好想你::苏打绿" };
    const cover = { ...seedTrack, artist: { name: "Cover Artist", provider_artist_id: null }, canonical_key: "我好想你::cover artist" };
    api.discover.mockResolvedValueOnce({ ...result, items: [], seed_status: "ambiguous", seed_candidates: [seedTrack, cover] })
      .mockResolvedValueOnce({ ...result, seed_status: "matched", seed_track: seedTrack });
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "我好想你" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    expect(await screen.findByText("Which artist did you mean?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "我好想你 · 苏打绿" }));
    await screen.findByText("Based on");
    expect(screen.getByText("我好想你 · 苏打绿")).toBeInTheDocument();
    expect(api.discover).toHaveBeenLastCalledWith("我好想你", 5, "en", "苏打绿");
    expect(screen.getByText("Night Signal")).toBeInTheDocument();
    expect(screen.queryByText(/original recording/i)).not.toBeInTheDocument();
  });

  it("keeps an artist selection when refreshing feedback and clears it for a new seed", async () => {
    const candidate = { ...track, title: "Shared title" };
    api.discover.mockResolvedValueOnce({ ...result, items: [], seed_status: "ambiguous", seed_candidates: [candidate] });
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "Shared title" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Shared title · Mira Vale" }));
    await screen.findByText("Night Signal");
    fireEvent.click(screen.getByRole("button", { name: /^like night signal$/i }));
    fireEvent.click(await screen.findByRole("button", { name: /refresh recommendations/i }));
    await waitFor(() => expect(api.discover).toHaveBeenLastCalledWith("Shared title", 5, "en", "Mira Vale"));
    await waitFor(() => expect(screen.getByRole("button", { name: /find music/i })).toBeEnabled());
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "Another title" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await waitFor(() => expect(api.discover).toHaveBeenLastCalledWith("Another title", 5, "en", undefined));
  });

  it("displays artist names while preserving candidate selection and feedback identity", async () => {
    const seedTrack = { ...track, title: "匆匆那年", artist: { name: "Faye Wong", display_name: "王菲", provider_artist_id: null }, canonical_key: "匆匆那年::faye wong" };
    const relatedTrack = { ...seedTrack, title: "红豆", canonical_key: "红豆::faye wong" };
    const item = { ...result.items[0], id: relatedTrack.canonical_key, title: relatedTrack.title, artist: "Faye Wong", track: relatedTrack };
    api.profile.mockResolvedValue({ ...emptyProfile, artists: [
      { name: "faye wong", display_name: "王菲", weight: 1 },
      { name: "Fleetwood Mac", weight: 0.5 },
    ] });
    api.discover.mockResolvedValueOnce({ ...result, items: [], seed_status: "ambiguous", seed_candidates: [seedTrack] })
      .mockResolvedValueOnce({ ...result, items: [item], seed_status: "matched", seed_track: seedTrack, seed_resolution_source: "user" });
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "匆匆那年" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    expect(await screen.findByRole("button", { name: "匆匆那年 · 王菲" })).toBeInTheDocument();
    expect(screen.getByText("王菲")).toBeInTheDocument();
    expect(screen.getByText("Fleetwood Mac")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
    fireEvent.click(screen.getByRole("button", { name: "匆匆那年 · 王菲" }));
    await screen.findByText("起点歌曲");
    expect(api.discover).toHaveBeenLastCalledWith("匆匆那年", 5, "zh", "Faye Wong");
    expect(screen.getByText("匆匆那年 · 王菲")).toBeInTheDocument();
    expect(screen.getAllByText("王菲")).toHaveLength(2);
    expect(screen.getByText(/以 匆匆那年 · 王菲 为起点/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "喜欢 红豆" }));
    await waitFor(() => expect(api.feedback).toHaveBeenCalledWith(relatedTrack, "like"));
    expect(api.feedback.mock.calls[0][0].artist.name).toBe("Faye Wong");
    expect(api.feedback.mock.calls[0][0].canonical_key).toBe("红豆::faye wong");
    fireEvent.click(screen.getByRole("button", { name: "Switch to English" }));
    expect(screen.getByText("匆匆那年 · 王菲")).toBeInTheDocument();
    expect(screen.getAllByText("王菲")).toHaveLength(2);
    expect(screen.getByText("Fleetwood Mac")).toBeInTheDocument();
  });

  it("keeps the model identification marker when switching guidance language", async () => {
    const seedTrack = { ...track, title: "匆匆那年", artist: { name: "Faye Wong", display_name: "王菲", provider_artist_id: null } };
    api.discover.mockResolvedValueOnce({ ...result, seed_track: seedTrack, seed_status: "matched",
      seed_resolution_source: "model", guidance: "MODEL GUIDANCE IN ENGLISH", guidance_provider: "openai_compatible" });
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "匆匆那年" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    expect(await screen.findByText("Model-assisted identification, matched in catalog.")).toBeInTheDocument();
    expect(screen.queryByText(/original.artist/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
    expect(screen.getByText("模型辅助识别，已匹配曲库")).toBeInTheDocument();
    expect(screen.queryByText("MODEL GUIDANCE IN ENGLISH")).not.toBeInTheDocument();
    expect(screen.getByText(/以 匆匆那年 · 王菲 为起点/)).toBeInTheDocument();
    expect(screen.queryByText(/原唱/)).not.toBeInTheDocument();
    expect(api.discover).toHaveBeenCalledTimes(1);
  });

  it("labels an original artist only when the seed came from a verified hint", async () => {
    api.discover.mockResolvedValueOnce({ ...result, seed_track: track, seed_status: "matched", seed_resolution_source: "verified_hint" });
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "Night Signal" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    expect(await screen.findByText("Verified original-artist recording.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
    expect(screen.getByText("已核实原唱歌手版本")).toBeInTheDocument();
  });

  it("retains local guidance on model failure and hides model prose after a language switch", async () => {
    api.discover.mockResolvedValueOnce({ ...result, guidance_status: "unavailable" })
      .mockResolvedValueOnce({ ...result, guidance: "MODEL GUIDANCE IN ENGLISH", guidance_provider: "openai_compatible" });
    render(<ProductClient />);
    await screen.findByText("Ready to discover");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "jazz" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    expect(await screen.findByText("Model guidance is unavailable; recommendations are still ready.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await screen.findByText("MODEL GUIDANCE IN ENGLISH");
    fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
    expect(screen.queryByText("MODEL GUIDANCE IN ENGLISH")).not.toBeInTheDocument();
    expect(screen.getByText("重新搜索可获取当前语言的助手解读。")).toBeInTheDocument();
    expect(screen.getByText("Night Signal")).toBeInTheDocument();
  });

  it("translates profile and feedback failures while preserving saved rating rollback", async () => {
    api.profile.mockRejectedValue(new Error("offline"));
    api.feedback.mockRejectedValueOnce(new Error("offline"));
    render(<ProductClient />);
    await screen.findByText("Your profile is unavailable right now.");
    fireEvent.change(screen.getByLabelText(/song or mood/i), { target: { value: "jazz" } });
    fireEvent.click(screen.getByRole("button", { name: /find music/i }));
    await screen.findByText("Night Signal");
    fireEvent.click(screen.getByRole("button", { name: /^like night signal$/i }));
    await screen.findByText(/couldn.t save feedback/i);
    fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
    expect(screen.getByText("暂时无法加载你的偏好。")).toBeInTheDocument();
    expect(screen.getByText("暂时无法保存反馈，请重试。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "喜欢 Night Signal" })).toHaveAttribute("aria-pressed", "false");
  });

  it("lets the current page switch language when browser storage is blocked", async () => {
    const read = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Storage blocked"); });
    const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Storage blocked"); });
    try {
      render(<ProductClient />);
      await screen.findByText("Ready to discover");
      fireEvent.click(screen.getByRole("button", { name: "切换为中文" }));
      expect(screen.getByLabelText("歌曲或心情")).toBeInTheDocument();
      expect(document.documentElement.lang).toBe("zh-CN");
    } finally {
      read.mockRestore();
      write.mockRestore();
    }
  });
});
