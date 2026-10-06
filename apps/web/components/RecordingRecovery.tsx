"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ApiClient } from "../lib/api";
import { artistDisplayName, copyFor } from "../lib/i18n";
import { safeExternalUrl } from "../lib/url";
import type { InterfaceLanguage, RecordingResolveResponse, Track } from "../types/music";
import SearchReport, { platformName } from "./SearchReport";

export default function RecordingRecovery({ query, artist, language, resolve, onSelect }: {
  query: string; artist?: string; language: InterfaceLanguage;
  resolve: ApiClient["resolveRecording"];
  onSelect: (track: Track, resolutionId: string) => void;
}) {
  const copy = copyFor(language), id = useId();
  const [platform, setPlatform] = useState("qq"), [link, setLink] = useState("");
  const [singer, setSinger] = useState(artist ?? "");
  const [result, setResult] = useState<RecordingResolveResponse | null>(null);
  const [history, setHistory] = useState<RecordingResolveResponse["search_report"][]>([]);
  const [busy, setBusy] = useState(false), [failed, setFailed] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function search(event: React.FormEvent) {
    event.preventDefault();
    if (controller.current) return;
    const current = new AbortController(); controller.current = current;
    if (result) setHistory(previous => [...previous, result.search_report].slice(-3));
    setBusy(true); setFailed(false); setResult(null);
    try {
      const response = await resolve(query, language, singer.trim() || undefined,
        link.trim() ? undefined : platform, link.trim() || undefined, current.signal);
      if (!current.signal.aborted) setResult(response);
    } catch {
      if (!current.signal.aborted) setFailed(true);
    } finally {
      if (!current.signal.aborted) setBusy(false);
      if (controller.current === current) controller.current = null;
    }
  }
  const choices = result?.matched_track && result.resolution_id
    ? [{ track: result.matched_track, resolution_id: result.resolution_id }] : result?.candidates ?? [];
  return <div className="recording-recovery">
    <h4>{copy.sourceRecovery}</h4>
    <form onSubmit={search} className="recovery-form">
      <label htmlFor={`${id}-platform`}>{copy.sourcePlatform}</label>
      <select id={`${id}-platform`} value={platform} onChange={e => setPlatform(e.target.value)} disabled={busy}>
        {["qq", "netease", "itunes", "musicbrainz", "kugou", "kuwo"].map(name => <option key={name} value={name}>
          {platformName(name)}{["kugou", "kuwo"].includes(name) ? language === "zh" ? "（暂不可用）" : " (unavailable)" : ""}
        </option>)}
      </select>
      <label htmlFor={`${id}-artist`}>{copy.sourceArtist}</label>
      <input id={`${id}-artist`} value={singer} onChange={e => setSinger(e.target.value)} maxLength={200} disabled={busy} />
      <label htmlFor={`${id}-link`}>{copy.sourceLink}</label>
      <input id={`${id}-link`} type="url" value={link} onChange={e => setLink(e.target.value)} maxLength={2048}
        placeholder="https://…" disabled={busy} />
      <button type="submit" className="text-button" disabled={busy}>{busy ? copy.sourceSearching : copy.sourceSearch}</button>
    </form>
    <div aria-live="polite" aria-busy={busy}>
      {failed ? <p role="alert">{copy.recommendationsError}</p> : null}
      {result?.status === "unsupported_platform" ? <p>{copy.sourceUnsupported}</p> : null}
      {result?.status === "unavailable" ? <p>{copy.sourceUnavailable}</p> : null}
      {result?.status === "not_found" ? <p>{copy.searchNotFound}</p> : null}
      {result?.status === "incomplete" ? <p>{copy.searchIncomplete}</p> : null}
      {choices.map(({ track, resolution_id }) => {
        const url = safeExternalUrl(track.source.external_url);
        return <div className="resolved-choice" key={resolution_id}>
          <p><strong>{track.title} · {artistDisplayName(track.artist)}</strong></p>
          <p>{platformName(track.source.provider)} · {copy.catalogMatched}</p>
          {track.source.provider === "musicbrainz" ? <p>{copy.metadataOnly}</p> : null}
          {url ? <a href={url} target="_blank" rel="noopener noreferrer">{copy.verificationSource}</a> : null}
          <button type="button" className="text-button" onClick={() => onSelect(track, resolution_id)}>{copy.confirmAndRecommend}</button>
        </div>;
      })}
      {choices.length ? <p>{copy.memoryNotice}</p> : null}
      {history.map((report, index) => <SearchReport key={index} report={report} language={language} />)}
      <SearchReport report={result?.search_report} language={language} />
    </div>
  </div>;
}
