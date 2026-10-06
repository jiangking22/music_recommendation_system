import { beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AgentClient from "../components/AgentClient";

const api = vi.hoisted(() => ({ stream: vi.fn() }));
vi.mock("../lib/agent", () => ({ streamAgentChat: api.stream }));
vi.mock("../lib/device", () => ({ getDeviceId: () => "device_1234567890" }));
const result = { conversation_id: "one", answer: "为你找到学习音乐。", recommended_tracks: [],
  used_tools: [{ name: "recommend_tracks", status: "ok" }], explanation: "", citations: [],
  sources: {}, provider: "local" };

beforeEach(() => { vi.clearAllMocks(); api.stream.mockResolvedValue(result); });

it("shows history, statuses and sends follow-up in the same conversation", async () => {
  api.stream.mockImplementationOnce(async (_url, _device, _message, _conversation, onStatus) => {
    onStatus({ stage: "preferences", label: "查询偏好", tool: "get_user_profile" });
    return result;
  });
  render(<AgentClient />);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "推荐适合学习的歌" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText(result.answer)).toBeInTheDocument();
  expect(screen.getByText("本地助手")).toBeInTheDocument();
  expect(screen.getByText(/查询偏好/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "再来几首" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() => expect(api.stream).toHaveBeenLastCalledWith(
    expect.any(String), "device_1234567890", "再来几首", "one", expect.any(Function), expect.any(AbortSignal)));
});

it("shows recoverable request errors", async () => {
  api.stream.mockRejectedValueOnce(new Error("Music assistant timed out."));
  render(<AgentClient />);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "推荐音乐" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Music assistant timed out.");
  expect(screen.getByRole("button", { name: "发送" })).toBeEnabled();
});

it("uses the catalog artist display name in recommended tracks", async () => {
  const track = { title: "红豆", artist: { name: "Faye Wong", display_name: "王菲", provider_artist_id: null },
    album: null, duration_ms: null, artwork_url: null, language: null, genres: [], tags: [], popularity: null,
    canonical_key: "红豆::faye wong", source: { provider: "itunes", provider_track_id: "one", external_url: null } };
  api.stream.mockResolvedValueOnce({ ...result, recommended_tracks: [{
    id: track.canonical_key, title: track.title, artist: track.artist.name, track,
    explanation: "Shares musical attributes.", score: 1, score_breakdown: {}, provenance: [track.source],
  }] });
  render(<AgentClient />);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "推荐音乐" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText("王菲")).toBeInTheDocument();
  expect(screen.queryByText("Faye Wong")).not.toBeInTheDocument();
});
