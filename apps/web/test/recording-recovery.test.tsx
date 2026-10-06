import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RecordingRecovery from "../components/RecordingRecovery";
import type { RecordingResolveResponse } from "../types/music";
import { localGuidance } from "../lib/i18n";

const response: RecordingResolveResponse = {
  request_id: "proof", status: "matched", resolution_id: "verified-reference", candidates: [], sources: {},
  matched_track: { title: "Missing", artist: { name: "Singer", provider_artist_id: null },
    album: null, duration_ms: null, artwork_url: null, language: null, genres: [], tags: [], popularity: null,
    source: { provider: "qq", provider_track_id: "123", external_url: "https://y.qq.com/n/ryqq/songDetail/mid" },
    canonical_key: "missing::singer" },
  search_report: { attempts: [], end_reason: "matched", external_requests: 1, incomplete: false },
};

describe("manual recording recovery", () => {
  it("distinguishes incomplete search from an exhausted no-match result in both languages", () => {
    const empty = { request_id: "empty", items: [], sources: {}, seed_track: null, seed_candidates: [],
      seed_status: "unresolved" as const, guidance: "", guidance_provider: "local" as const, guidance_status: "ready" as const,
      search_report: { ...response.search_report, end_reason: "not_found" } };
    expect(localGuidance(empty, "zh")).toBe("未在已检索平台找到该歌曲，请检查歌名、歌手或来源链接。");
    expect(localGuidance({ ...empty, search_report: { ...empty.search_report, incomplete: true } }, "en"))
      .toMatch(/search is incomplete/i);
  });
  it("waits for explicit confirmation and passes the verified reference", async () => {
    const resolve = vi.fn().mockResolvedValue(response), select = vi.fn();
    render(<RecordingRecovery query="Missing" language="en" resolve={resolve} onSelect={select} />);
    fireEvent.change(screen.getByLabelText("Song link"), { target: { value: "https://y.qq.com/n/ryqq/songDetail/mid" } });
    fireEvent.click(screen.getByRole("button", { name: "Search this source" }));
    await screen.findByText("Missing · Singer");
    expect(select).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "View verification source ↗" })).toHaveAttribute("href", response.matched_track?.source.external_url);
    fireEvent.click(screen.getByRole("button", { name: "Confirm and recommend" }));
    expect(select).toHaveBeenCalledWith(response.matched_track, "verified-reference");
  });

  it("submits once, aborts on unmount and ignores a late response", async () => {
    let release!: (value: RecordingResolveResponse) => void;
    const resolve = vi.fn().mockReturnValue(new Promise(r => { release = r; }));
    const select = vi.fn();
    const view = render(<RecordingRecovery query="Missing" language="en" resolve={resolve} onSelect={select} />);
    fireEvent.click(screen.getByRole("button", { name: "Search this source" }));
    fireEvent.click(screen.getByRole("button", { name: "Searching…" }));
    expect(resolve).toHaveBeenCalledTimes(1);
    const signal = resolve.mock.calls[0][5] as AbortSignal;
    view.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => release(response));
    expect(select).not.toHaveBeenCalled();
  });

  it("invalidates a verified artist when the user edits it and can recover from failure", async () => {
    const resolve = vi.fn().mockRejectedValueOnce(new Error("Unavailable")).mockResolvedValueOnce(response);
    render(<RecordingRecovery query="Missing" requireArtist language="en" resolve={resolve} onSelect={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Correct artist"), { target: { value: "Singer" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify artist" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Verify artist" }));
    await screen.findByRole("button", { name: "Confirm and recommend" });
    fireEvent.change(screen.getByLabelText("Correct artist"), { target: { value: "Other" } });
    expect(screen.queryByRole("button", { name: "Confirm and recommend" })).not.toBeInTheDocument();
    expect(resolve).toHaveBeenCalledTimes(2);
  });
});
