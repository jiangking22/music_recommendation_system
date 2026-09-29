import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ProductClient from "../components/ProductClient";
import type { RecommendationResponse, PreferenceProfile } from "../types/music";

const api = vi.hoisted(() => ({
  bootstrap: vi.fn(),
  recommend: vi.fn(),
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
const result: RecommendationResponse = {
  request_id: "one",
  items: [
    {
      id: "night signal::mira vale",
      title: track.title,
      artist: track.artist.name,
      explanation: "Matches your night listening.",
      track,
      score: 0.82,
      score_breakdown: { seed: 0.4 },
      provenance: [track.source],
    },
  ],
  sources: { local: { provider: "local", tracks: [track], error: null } },
};

beforeEach(() => {
  vi.clearAllMocks();
  api.bootstrap.mockResolvedValue({ deviceId: "device_1234567890" });
  api.profile.mockResolvedValue(emptyProfile);
  api.recommend.mockResolvedValue(result);
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
    let finish!: (value: RecommendationResponse) => void;
    api.recommend.mockImplementationOnce(
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
    api.recommend.mockRejectedValueOnce(new Error("offline"));
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
    await waitFor(() => expect(api.recommend).toHaveBeenCalledTimes(2));
  });
});
