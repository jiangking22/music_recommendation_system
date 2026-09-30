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
