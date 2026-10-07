import { beforeEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AgentClient from "../components/AgentClient";
import { ApiError } from "../lib/api";

const api = vi.hoisted(() => ({ stream: vi.fn() }));
vi.mock("../lib/agent", () => ({ streamAgentChat: api.stream }));
const result = { conversation_id: "one", answer: "为你找到学习音乐。", recommended_tracks: [],
  used_tools: [{ name: "recommend_tracks", status: "ok" }], explanation: "", citations: [],
  sources: {}, provider: "local" };

beforeEach(() => { vi.clearAllMocks(); api.stream.mockResolvedValue(result); });

it("shows history, statuses and sends follow-up in the same conversation", async () => {
  api.stream.mockImplementationOnce(async (_url, _message, _conversation, onStatus) => {
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
    expect.any(String), "再来几首", "one", expect.any(Function), expect.any(AbortSignal), undefined, false));
});

it("shows recoverable request errors", async () => {
  api.stream.mockRejectedValueOnce(new ApiError("agent_timeout", "Music assistant timed out.", 504));
  render(<AgentClient />);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "推荐音乐" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("请求超时，请重试");
  expect(screen.getByRole("button", { name: "发送" })).toBeEnabled();
});

it("retries a failed message without duplicating it in the conversation", async () => {
  api.stream.mockRejectedValueOnce(new ApiError("llm_unavailable", "Language provider unavailable.", 503));
  render(<AgentClient />);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "缓慢的歌" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("音乐服务暂不可用");
  expect(screen.getAllByText("缓慢的歌")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText(result.answer)).toBeInTheDocument();
  expect(screen.getAllByText("缓慢的歌")).toHaveLength(1);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  // A later intentional repeat is a new turn, not suppressed as a duplicate.
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "缓慢的歌" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() => expect(screen.getAllByText(result.answer)).toHaveLength(2));
  expect(screen.getAllByText("缓慢的歌")).toHaveLength(2);
});

it("labels automatic basic mode separately from configured local mode", async () => {
  api.stream.mockResolvedValueOnce({ ...result, fallback_reason: "llm_unavailable" });
  render(<AgentClient />);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "emo的歌" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText("基础模式")).toBeInTheDocument();
  expect(screen.getByText(/智能服务暂不可用，已使用基础模式/)).toBeInTheDocument();
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

it("opts into deep thinking, keeps selection and ignores a stopped reply", async () => {
  let finish: (value: typeof result) => void = () => {};
  api.stream.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  render(<AgentClient />);
  const toggle = screen.getByRole("checkbox", { name: "深度思考" });
  expect(toggle).not.toBeChecked();
  fireEvent.click(toggle);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "缓慢的歌" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  const call = api.stream.mock.calls[0];
  expect(call[6]).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "停止" }));
  expect(call[4].aborted).toBe(true);
  expect(screen.getByRole("button", { name: "发送" })).toBeEnabled();
  expect(toggle).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText(result.answer)).toBeInTheDocument();
  finish({ ...result, answer: "late response" });
  await waitFor(() => expect(screen.queryByText("late response")).not.toBeInTheDocument());
  expect(screen.getAllByText("缓慢的歌")).toHaveLength(1);
});
