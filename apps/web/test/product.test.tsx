import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProductClient from "../components/ProductClient";
import type { DiscoveryResponse, PreferenceProfile } from "../types/music";

const api = vi.hoisted(() => ({
  bootstrap: vi.fn(),
  recommend: vi.fn(),
  discover: vi.fn(),
  feedback: vi.fn(),
  profile: vi.fn(),
}));
vi.mock("../lib/device", () => ({ getDeviceId: () => "device_1234567890" }));
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
  api.bootstrap.mockResolvedValue({ deviceId: "device_1234567890" });
  api.profile.mockResolvedValue(emptyProfile);
  api.discover.mockResolvedValue(result);
  api.feedback.mockResolvedValue({
    track_key: result.items[0].id,
    value: "like",
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
    expect(screen.getByText(/finding your next listen/i)).toBeInTheDocument();
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
    expect(screen.getByText("正在寻找下一首好歌…")).toBeInTheDocument();
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
    api.profile.mockRejectedValueOnce(new Error("offline"));
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
