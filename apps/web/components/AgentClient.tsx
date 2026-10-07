"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { getAgentCapabilities, streamAgentChat } from "../lib/agent";
import { ApiError } from "../lib/api";
import { AccountMenu } from "./AuthGate";
import { artistDisplayName } from "../lib/i18n";
import { safeExternalUrl } from "../lib/url";
import type { AgentResponse, AgentStatus, ModelCapabilities, ToolName } from "../types/agent";

const LABELS: Record<ToolName, string> = { get_user_profile: "音乐偏好", recommend_tracks: "查找推荐",
  search_music_knowledge: "音乐知识", explain_recommendation: "推荐理由" };
const API_BASE = "/api";
const ERRORS: Record<string, string> = {
  agent_timeout: "请求超时，请重试。",
  agent_busy: "音乐助手正忙，请稍后重试。",
  llm_unavailable: "音乐服务暂不可用，请稍后重试。",
  database_unavailable: "暂时无法读取对话，请稍后重试。",
  conversation_conflict: "对话已更新，请重试这条消息。",
  invalid_model_output: "暂时无法理解这次请求，请换个说法或重试。",
  incomplete_stream: "回复中断，请重试。",
  model_output_truncated: "回答超出长度限制，请缩小问题范围后重试。",
};

export default function AgentClient() {
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<{ role: string; text: string }[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [result, setResult] = useState<AgentResponse | null>(null);
  const [statuses, setStatuses] = useState<AgentStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deepThinking, setDeepThinking] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [capabilities, setCapabilities] = useState<ModelCapabilities | null>(null);
  const [capabilityError, setCapabilityError] = useState(false);
  const conversation = useRef<string | undefined>(undefined);
  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const inFlight = useRef(false);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    const check = new AbortController();
    void getAgentCapabilities(API_BASE, check.signal).then((value) => {
      if (!check.signal.aborted) setCapabilities(value);
    }).catch(() => { if (!check.signal.aborted) setCapabilityError(true); });
    return () => check.abort();
  }, []);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const text = message.trim();
    if (!text || inFlight.current) return;
    inFlight.current = true;
    controller.current = new AbortController();
    const signal = controller.current.signal;
    setLoading(true); setError(null); setStatuses([]); setResult(null);
    setStopped(false);
    setPending(text);
    try {
      const next = await streamAgentChat(API_BASE, text, conversation.current,
        (status) => { if (!signal.aborted) setStatuses((items) => [...items, status].slice(-8)); }, signal, undefined, deepThinking);
      if (signal.aborted) return;
      conversation.current = next.conversation_id;
      setResult(next); setMessage("");
      setPending(null);
      setHistory((items) => [...items, { role: "你", text }, { role: "Sonora", text: next.answer }].slice(-12));
      input.current?.focus();
    } catch (failure) {
      if (!signal.aborted) setError(failure instanceof ApiError
        ? ERRORS[failure.code] ?? "暂时无法回答，请重试。" : "连接中断，请检查网络后重试。");
    } finally {
      if (controller.current?.signal === signal) {
        inFlight.current = false;
        setLoading(false);
      }
    }
  }

  function stop() {
    controller.current?.abort();
    controller.current = null;
    inFlight.current = false;
    setLoading(false); setPending(null); setStatuses([]); setStopped(true);
    input.current?.focus();
  }

  return <div className="site-shell agent-shell">
    <header className="site-header">
      <Link href="/" className="brand" aria-label="Sonora home"><span className="brand-icon">◉</span> sonora<span className="brand-dot">.</span></Link>
      <div className="header-actions"><Link href="/" className="agent-nav">探索音乐 ↗</Link><AccountMenu language="zh" /></div>
    </header>
    <main className="agent-main">
      <div className="agent-intro"><span className="eyebrow">SONORA / MUSIC ASSISTANT</span>
        <h1>把此刻，交给音乐。</h1><p>聊聊想听的歌，或一起了解你喜欢的音乐人。</p></div>
      <div className="agent-columns">
        <section className="agent-conversation" aria-labelledby="conversation-title">
          <h2 id="conversation-title">音乐助手</h2>
          {!history.length && !pending ? <div className="agent-welcome"><span aria-hidden="true">♫</span>
            <p>从一个心情、一位歌手开始。</p><div className="agent-suggestions">
              {["推荐适合学习的歌", "介绍周杰伦", "介绍爵士乐"].map((text) => <button type="button" key={text}
                onClick={() => { setMessage(text); input.current?.focus(); }}>{text} ↗</button>)}</div></div> : null}
          <div className="agent-history" role="log" aria-label="对话历史" aria-live="polite">
            {history.map((entry, i) => <article key={i} className={entry.role === "你" ? "agent-user" : "agent-reply"}>
              <span>{entry.role}</span><p>{entry.text}</p></article>)}
            {pending ? <article className="agent-user"><span>你</span><p>{pending}</p>
              {error ? <small>发送未完成，可重试</small> : null}</article> : null}</div>
          <form onSubmit={send} className="agent-form"><label htmlFor="agent-message">想听什么？</label>
            <div><input id="agent-message" ref={input} value={message} maxLength={2000} required
              onChange={(event) => setMessage(event.target.value)} placeholder="推荐适合学习的歌…" />
              <button type="submit" className="primary-button" disabled={loading}>{loading ? "处理中…" : "发送"}</button></div>
            <div className="agent-controls"><label className="agent-thinking"><input type="checkbox" checked={deepThinking}
              disabled={loading || capabilities?.supports_deep_thinking === false}
              onChange={(event) => setDeepThinking(event.target.checked)} />深度思考</label>
              {loading ? <button type="button" className="agent-stop" onClick={stop}>停止</button> : null}
              {deepThinking ? <small>深入理解与分析，最多等待约两分钟。</small> : null}</div></form>
          {stopped ? <p role="status" className="notice">已停止，可修改问题或重新发送。</p> : null}
          {error ? <p role="alert" className="error-state">{error}</p> : null}
          {result?.fallback_reason ? <p role="status" className="notice">
            智能服务暂不可用，已使用基础模式。推荐仍按音乐匹配与已有偏好排序。
          </p> : null}
          {result?.thinking_unavailable_reason === "unsupported" ? <p className="notice">
            当前模型接口暂不支持深度思考，已使用{result.provider === "local" ? "基础" : "普通"}模式。
          </p> : null}
        </section>
        <aside className="agent-progress" aria-labelledby="progress-title"><h2 id="progress-title">这次聆听</h2>
          <div aria-live="polite" aria-busy={loading}>
            {!statuses.length ? <p>等待你的第一句话。</p> : <ol>{statuses.map((status, i) => <li key={i}>
              {status.label}{status.tool ? ` · ${LABELS[status.tool] ?? status.tool}` : ""}</li>)}</ol>}
          </div>
          {result ? <><span className="agent-mode">{result.fallback_reason ? "基础模式"
            : result.provider === "local" ? "本地助手" : result.thinking_mode === "deep" ? "深度思考" : "音乐助手"}</span>
            <ul className="agent-tools">{result.used_tools.map((tool) => <li key={tool.name}>
              {LABELS[tool.name]} · {tool.status === "ok" ? "完成" : "未完成"}</li>)}</ul></> : null}
          <p className="agent-footnote">音乐偏好随账号同步，对话仅限当前登录会话。</p>
          {capabilities || result?.native_search ? <p className="agent-footnote">当前模型接口暂不支持联网检索</p>
            : capabilityError ? <p className="agent-footnote">暂时无法确认联网能力，可继续对话。</p> : null}
        </aside>
      </div>
      {result?.recommended_tracks.length ? <section className="agent-mix" aria-labelledby="mix-title">
        <div className="section-heading"><h2 id="mix-title">为此刻挑选</h2><span className="result-count">{result.recommended_tracks.length} 首</span></div>
        <div className="agent-track-list">{result.recommended_tracks.map((item, i) => {
          const artwork = safeExternalUrl(item.track.artwork_url);
          const link = safeExternalUrl(item.track.source.external_url);
          return <article className="agent-track" key={item.id}><span className="agent-track-number">{i + 1}</span>
            <div className="agent-artwork">{artwork ? <Image src={artwork} width={80} height={80} alt={`${item.title} 封面`} unoptimized /> : <span aria-hidden="true">♪</span>}</div>
            <div><h3>{item.title}</h3><p>{artistDisplayName(item.track.artist)}</p><p className="agent-track-reason">{item.explanation}</p>
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
