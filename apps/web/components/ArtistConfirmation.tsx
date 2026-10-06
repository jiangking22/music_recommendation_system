"use client";

import { useEffect, useRef, useState } from "react";
import type { ApiClient } from "../lib/api";
import { artistDisplayName, copyFor } from "../lib/i18n";
import { safeExternalUrl } from "../lib/url";
import type { InterfaceLanguage, OriginalIdentificationResponse, Track, VerifiedStorefront } from "../types/music";
import RecordingRecovery from "./RecordingRecovery";
import SearchReport, { platformName } from "./SearchReport";

type LookupState =
  | { status: "idle" | "loading" }
  | { status: "ready"; result: OriginalIdentificationResponse }
  | { status: "error"; code: string };

export default function ArtistConfirmation({ query, candidates, language, identifyOriginal, resolveRecording, candidateResolutions, initialSuggestion, onSelect }: {
  query: string;
  candidates: Track[];
  language: InterfaceLanguage;
  identifyOriginal: ApiClient["identifyOriginal"];
  resolveRecording?: ApiClient["resolveRecording"];
  candidateResolutions?: Record<string, string>;
  initialSuggestion?: OriginalIdentificationResponse;
  onSelect: (artist: string, modelSuggested: boolean, storefront?: VerifiedStorefront, resolutionId?: string) => void;
}) {
  const [lookup, setLookup] = useState<LookupState>(() => initialSuggestion
    ? { status: "ready", result: initialSuggestion } : { status: "idle" });
  const [correcting, setCorrecting] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const copy = copyFor(language);
  const busy = lookup.status === "loading";

  useEffect(() => () => { controller.current?.abort(); }, []);

  async function identify() {
    if (controller.current && !controller.current.signal.aborted) return;
    const current = new AbortController();
    controller.current = current;
    setLookup({ status: "loading" });
    try {
      const result = await identifyOriginal(query, language, candidates.slice(0, 5).map(track => ({
        title: track.title, artist: track.artist.name,
      })), current.signal);
      if (!current.signal.aborted) setLookup({ status: "ready", result });
    } catch (error) {
      if (!current.signal.aborted) setLookup({ status: "error", code:
        error instanceof Error && "code" in error && typeof error.code === "string" ? error.code : "network_error" });
    } finally {
      if (controller.current === current) controller.current = null;
    }
  }

  const errors: Record<string, string> = {
    identification_not_configured: copy.identificationNotConfigured,
    identification_unavailable: copy.identificationUnavailable,
    identification_timeout: copy.identificationTimeout,
    identification_invalid_output: copy.identificationInvalid,
    identification_busy: copy.identificationBusy,
  };
  const identified = lookup.status === "ready" ? lookup.result : null;
  const suggestedTrack = identified?.matched_track;
  const verificationUrl = safeExternalUrl(suggestedTrack?.source.external_url);

  return (
    <div className="seed-confirmation">
      <h3>{copy.confirmArtist}</h3>
      <p>{initialSuggestion ? copy.modelArtistConfirmation : copy.confirmDescription}</p>
      {!initialSuggestion && !correcting ? <div className="seed-choices">
        {candidates.slice(0, 5).map(candidate => (
          <button type="button" key={candidate.canonical_key} disabled={busy}
            onClick={() => onSelect(candidate.artist.name, false, undefined, candidateResolutions?.[candidate.canonical_key])}>
            {candidate.title} · {artistDisplayName(candidate.artist)}
          </button>
        ))}
        <button type="button" disabled={busy} onClick={() => void identify()}>{copy.noneOfAbove}</button>
      </div> : null}
      <div className="original-identification" aria-live="polite" aria-busy={busy}>
        {busy ? <p role="status">{copy.identifyingOriginal}</p> : null}
        {lookup.status === "error" ? (
          <>
            <p role="alert">{errors[lookup.code] ?? copy.identificationError}</p>
            <button type="button" className="text-button" onClick={() => void identify()}>{copy.retryIdentification}</button>
          </>
        ) : null}
        {identified?.status === "unknown" ? <p>{copy.originalUnknown}</p> : null}
        {identified?.suggestion ? (
          <>
            <h4>{copy.modelSuggestion}</h4>
            <p><strong>{identified.suggestion.title} · {suggestedTrack
              ? artistDisplayName(suggestedTrack.artist) : identified.suggestion.artist}</strong></p>
            <p>{identified.status === "matched"
              ? identified.verified_storefront ? copy.onlineVerified : copy.catalogMatched
              : copy.catalogUnverified}</p>
            {suggestedTrack ? <p>{platformName(suggestedTrack.source.provider)}
              {suggestedTrack.source.provider === "musicbrainz" ? ` · ${copy.metadataOnly}` : ""}</p> : null}
            {identified.status === "matched" && verificationUrl ? (
              <a href={verificationUrl} target="_blank" rel="noopener noreferrer">
                {copy.verificationSource}
              </a>
            ) : null}
            {Object.values(identified.sources).some(source => source.error) ? <p>{copy.partialSources}</p> : null}
            {!correcting && identified.status === "matched" && suggestedTrack ? (
              <button type="button" className="text-button"
                onClick={() => onSelect(suggestedTrack.artist.name, true,
                  identified.verified_storefront ?? undefined, identified.resolution_id ?? undefined)}>{copy.confirmAndRecommend}</button>
            ) : null}
          </>
        ) : null}
        {!busy && !correcting && resolveRecording ? <button type="button" className="text-button"
          onClick={() => setCorrecting(true)}>{copy.provideArtist}</button> : null}
        <SearchReport report={identified?.search_report} language={language} />
        {!busy && (correcting || identified?.status !== "matched") && resolveRecording ? <RecordingRecovery
          key={`${identified?.request_id ?? "initial"}:${correcting}`} query={query}
          artist={correcting ? undefined : identified?.suggestion?.artist} requireArtist={correcting} language={language}
          resolve={resolveRecording} onSelect={(track, id) => onSelect(track.artist.name,
            Boolean(!correcting && identified?.suggestion && track.artist.name === identified.suggestion.artist), undefined, id)} /> : null}
      </div>
    </div>
  );
}
