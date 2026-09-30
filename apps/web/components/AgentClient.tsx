"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { streamAgentChat } from "../lib/agent";
import { getDeviceId } from "../lib/device";
import { safeExternalUrl } from "../lib/url";
import type { AgentResponse, AgentStatus, ToolName } from "../types/agent";

const LABELS: Record<ToolName, string> = { get_user_profile: "音乐偏好", recommend_tracks: "查找推荐",
  search_music_knowledge: "音乐知识", explain_recommendation: "推荐理由" };
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function AgentClient() {
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<{ role: string; text: string }[]>([]);
  const [result, setResult] = useState<AgentResponse | null>(null);
  const [statuses, setStatuses] = useState<AgentStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const conversation = useRef<string | undefined>(undefined);
  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const text = message.trim();
    if (!text || loading) return;
    controller.current = new AbortController();
    const signal = controller.current.signal;
    setLoading(true); setError(null); setStatuses([]); setResult(null);
    setHistory((items) => [...items, { role: "你", text }].slice(-12));
    try {
      const next = await streamAgentChat(API_BASE, getDeviceId(), text, conversation.current,
        (status) => { if (!signal.aborted) setStatuses((items) => [...items, status].slice(-8)); }, signal);
      if (signal.aborted) return;
      conversation.current = next.conversation_id;
      setResult(next); setMessage("");
      setHistory((items) => [...items, { role: "Sonora", text: next.answer }].slice(-12));
      input.current?.focus();
    } catch (failure) {
      if (!signal.aborted) setError(failure instanceof Error ? failure.message : "暂时无法回答，请重试。");
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }

  return <div className="site-shell agent-shell">
    <header className="site-header">
      <Link href="/" className="brand" aria-label="Sonora home"><span className="brand-icon">◉</span> sonora<span className="brand-dot">.</span></Link>
      <Link href="/" className="agent-nav">探索音乐 ↗</Link>
    </header>
    <main className="agent-main">
      <div className="agent-intro"><span className="eyebrow">SONORA / MUSIC ASSISTANT</span>
        <h1>把此刻，交给音乐。</h1><p>聊聊想听的歌，或一起了解你喜欢的音乐人。</p></div>
      <div className="agent-columns">
        <section className="agent-conversation" aria-labelledby="conversation-title">
          <h2 id="conversation-title">音乐助手</h2>
          {!history.length ? <div className="agent-welcome"><span aria-hidden="true">♫</span>
            <p>从一个心情、一位歌手开始。</p><div className="agent-suggestions">
              {["推荐适合学习的歌", "介绍周杰伦", "介绍爵士乐"].map((text) => <button type="button" key={text}
                onClick={() => { setMessage(text); input.current?.focus(); }}>{text} ↗</button>)}</div></div> : null}
          <div className="agent-history" role="log" aria-label="对话历史" aria-live="polite">
            {history.map((entry, i) => <article key={i} className={entry.role === "你" ? "agent-user" : "agent-reply"}>
              <span>{entry.role}</span><p>{entry.text}</p></article>)}</div>
          <form onSubmit={send} className="agent-form"><label htmlFor="agent-message">想听什么？</label>
            <div><input id="agent-message" ref={input} value={message} maxLength={2000} required
              onChange={(event) => setMessage(event.target.value)} placeholder="推荐适合学习的歌…" />
              <button type="submit" className="primary-button" disabled={loading}>{loading ? "处理中…" : "发送"}</button></div></form>
          {error ? <p role="alert" className="error-state">{error}</p> : null}
        </section>
        <aside className="agent-progress" aria-labelledby="progress-title"><h2 id="progress-title">这次聆听</h2>
          <div aria-live="polite" aria-busy={loading}>
            {!statuses.length ? <p>等待你的第一句话。</p> : <ol>{statuses.map((status, i) => <li key={i}>
              {status.label}{status.tool ? ` · ${LABELS[status.tool] ?? status.tool}` : ""}</li>)}</ol>}
          </div>
          {result ? <><span className="agent-mode">{result.provider === "local" ? "本地助手" : "音乐助手"}</span>
            <ul className="agent-tools">{result.used_tools.map((tool) => <li key={tool.name}>
              {LABELS[tool.name]} · {tool.status === "ok" ? "完成" : "未完成"}</li>)}</ul></> : null}
          <p className="agent-footnote">你的音乐偏好与当前设备关联。</p>
        </aside>
      </div>
      {result?.recommended_tracks.length ? <section className="agent-mix" aria-labelledby="mix-title">
        <div className="section-heading"><h2 id="mix-title">为此刻挑选</h2><span className="result-count">{result.recommended_tracks.length} 首</span></div>
        <div className="agent-track-list">{result.recommended_tracks.map((item, i) => {
          const artwork = safeExternalUrl(item.track.artwork_url);
          const link = safeExternalUrl(item.track.source.external_url);
          return <article className="agent-track" key={item.id}><span className="agent-track-number">{i + 1}</span>
            <div className="agent-artwork">{artwork ? <Image src={artwork} width={80} height={80} alt={`${item.title} 封面`} unoptimized /> : <span aria-hidden="true">♪</span>}</div>
            <div><h3>{item.title}</h3><p>{item.artist}</p><p className="agent-track-reason">{item.explanation}</p>
              <div className="providers">{[...new Set(item.provenance.map((source) => source.provider))].map((name) => <span key={name}>{name}</span>)}</div></div>
            {link ? <a className="open-link" href={link} target="_blank" rel="noopener noreferrer">播放 ↗</a> : null}</article>;
        })}</div>
        {Object.values(result.sources).some((source) => source.error) ? <p className="notice">部分音乐来源暂不可用，已展示可用曲目。</p> : null}
        {result.explanation ? <details className="agent-explanation"><summary>推荐理由</summary><p>{result.explanation}</p></details> : null}
      </section> : null}
      {result?.citations.length ? <section className="agent-citations"><h2>参考资料</h2>
        {result.citations.map((citation) => <p key={citation.chunk_id}><strong>{citation.title}</strong> · {citation.text}</p>)}</section> : null}
    </main>
  </div>;
}
