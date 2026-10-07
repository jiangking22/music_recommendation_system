import { beforeEach, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import AgentClient from "../components/AgentClient";
import { ApiError } from "../lib/api";

const api = vi.hoisted(() => ({ stream: vi.fn(), capabilities: vi.fn() }));
vi.mock("../lib/agent", () => ({ streamAgentChat: api.stream, getAgentCapabilities: api.capabilities }));
const result = { conversation_id: "one", answer: "为你找到学习音乐。", recommended_tracks: [],
  used_tools: [{ name: "recommend_tracks", status: "ok" }], explanation: "", citations: [],
  sources: {}, provider: "local" };

beforeEach(() => {
  vi.clearAllMocks(); api.stream.mockResolvedValue(result);
  api.capabilities.mockResolvedValue({ provider: "openai_compatible", supports_deep_thinking: true,
    native_search: { status: "unavailable", reason: "unsupported" } });
});

it('shows expanded-search counts, inference and separate web capability', async () => {
  api.capabilities.mockResolvedValue({ provider: 'openai_compatible', supports_deep_thinking: true,
    native_search: { status: 'unavailable', reason: 'unsupported' },
    music_catalog_search: 'available', web_search: 'not_configured' });
  api.stream.mockResolvedValue({ ...result,
    search_report: { requested: 5, returned: 1, reused: true, expanded: true,
      external_requests: 6, web_search: 'not_configured', end_reason: 'insufficient_evidence', attempts: [] },
    recommended_tracks: [{ id: 'one', title: 'Verified song', artist: 'Artist', explanation: 'Matching factors',
      score: 1, score_breakdown: {}, provenance: [{ provider: 'itunes' }],
      attribute_evidence: [1, 2].map(() => ({ track_id: 'one', attribute: 'vocals', value: 'vocal', origin: 'model', basis: 'Familiar recording' })),
      track: { artist: { name: 'Artist' }, source: {}, artwork_url: null } }] });
  render(<AgentClient />);
  fireEvent.change(screen.getByLabelText('想听什么？'), { target: { value: '带人声' } });
  fireEvent.click(screen.getByRole('button', { name: '发送' }));
  expect(await screen.findByText('找到 1 / 5 首 · 已扩大检索')).toBeInTheDocument();
  expect(screen.getByText(/带人声 · 模型推断/)).toBeInTheDocument();
  expect(screen.getByText('网页搜索未配置')).toBeInTheDocument();
});

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

it("shows native search unavailability before sending and keeps chat usable", async () => {
  render(<AgentClient />);
  expect(await screen.findByText("当前模型接口暂不支持联网检索")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "发送" })).toBeEnabled();
  expect(screen.queryByText(/联网检索完成/)).not.toBeInTheDocument();
});

function mockScrollArea(area: HTMLElement) {
  let height = 900;
  let top = 0;
  Object.defineProperties(area, {
    clientHeight: { configurable: true, get: () => 300 },
    scrollHeight: { configurable: true, get: () => height },
    scrollTop: { configurable: true, get: () => top, set: (value: number) => { top = Math.min(value, height - 300); } },
  });
  return { grow: (value: number) => { height = value; } };
}

it("follows the latest reply while near the bottom", async () => {
  let finish: (value: typeof result) => void = () => {};
  api.stream.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  render(<AgentClient />);
  const area = screen.getByRole("log", { name: "对话历史" });
  const scroll = mockScrollArea(area);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "聊聊曲风" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  expect(area.scrollTop).toBe(600);
  scroll.grow(1400);
  await act(async () => finish(result));
  expect(await screen.findByText(result.answer)).toBeInTheDocument();
  expect(area.scrollTop).toBe(1100);
});

it("preserves reading position on a new reply and offers return to latest", async () => {
  let finish: (value: typeof result) => void = () => {};
  api.stream.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  render(<AgentClient />);
  const area = screen.getByRole("log", { name: "对话历史" });
  const scroll = mockScrollArea(area);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "聊聊曲风" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  area.scrollTop = 120;
  fireEvent.scroll(area);
  scroll.grow(1600);
  await act(async () => finish(result));
  expect(await screen.findByText(result.answer)).toBeInTheDocument();
  expect(area.scrollTop).toBe(120);
  fireEvent.click(screen.getByRole("button", { name: "回到最新" }));
  expect(area.scrollTop).toBe(1300);
  expect(screen.queryByRole("button", { name: "回到最新" })).not.toBeInTheDocument();
});

it("keeps failure notices inside the keyboard-accessible scroll region", async () => {
  api.stream.mockRejectedValueOnce(new ApiError("agent_timeout", "Timed out", 504));
  render(<AgentClient />);
  fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: "音乐" } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  const error = await screen.findByRole("alert");
  const area = screen.getByRole("log", { name: "对话历史" });
  expect(area).toContainElement(error);
  expect(area).toHaveAttribute("tabindex", "0");
  expect(area).not.toContainElement(screen.getByRole("button", { name: "发送" }));
});

it("retains already displayed messages when the server context window advances", async () => {
  render(<AgentClient />);
  for (let turn = 0; turn < 8; turn++) {
    api.stream.mockResolvedValueOnce({ ...result, answer: `曲风回答 ${turn}` });
    fireEvent.change(screen.getByLabelText("想听什么？"), { target: { value: `曲风问题 ${turn}` } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText(`曲风回答 ${turn}`)).toBeInTheDocument();
  }
  expect(screen.getByText("曲风问题 0")).toBeInTheDocument();
});

it("bounds the panel when the mobile keyboard shrinks the visual viewport and restores it", async () => {
  const originalViewport = Object.getOwnPropertyDescriptor(window, "visualViewport");
  const originalWidth = Object.getOwnPropertyDescriptor(window, "innerWidth");
  const viewport = Object.assign(new EventTarget(), { height: 844 });
  Object.defineProperty(window, "visualViewport", { configurable: true, value: viewport });
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
  try {
    const view = render(<AgentClient />);
    const input = screen.getByLabelText("想听什么？");
    act(() => input.focus());
    act(() => { viewport.height = 360; viewport.dispatchEvent(new Event("resize")); });
    const panel = screen.getByRole("region", { name: "音乐助手" });
    expect(parseFloat(panel.style.maxHeight)).toBeLessThanOrEqual(360);
    expect(parseFloat(panel.style.maxHeight)).toBeGreaterThan(200);
    act(() => { input.blur(); viewport.height = 844; viewport.dispatchEvent(new Event("resize")); });
    expect(panel.style.maxHeight).toBe("");
    view.unmount();
  } finally {
    if (originalViewport) Object.defineProperty(window, "visualViewport", originalViewport);
    else Reflect.deleteProperty(window, "visualViewport");
    if (originalWidth) Object.defineProperty(window, "innerWidth", originalWidth);
  }
});
