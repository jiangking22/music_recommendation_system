"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createApiClient, type ApiClient } from "../lib/api";
import { getDeviceId } from "../lib/device";
import { artistDisplayName, copyFor, localGuidance, readLanguage, saveLanguage } from "../lib/i18n";
import type {
  FeedbackValue,
  PreferenceProfile,
  DiscoveryResponse,
  InterfaceLanguage,
  RecommendationItem,
  VerifiedStorefront,
} from "../types/music";
import ProfilePanel from "./ProfilePanel";
import RecommendationCard from "./RecommendationCard";
import ArtistConfirmation from "./ArtistConfirmation";
import RecordingRecovery from "./RecordingRecovery";
import SearchReport from "./SearchReport";
import { safeExternalUrl } from "../lib/url";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ProductClient() {
  const api = useRef<ApiClient | null>(null);
  const [ready, setReady] = useState(false);
  const [seed, setSeed] = useState("");
  const [limit, setLimit] = useState(5);
  const [language, setLanguage] = useState<InterfaceLanguage>("en");
  const [result, setResult] = useState<DiscoveryResponse | null>(null);
  const [resultLanguage, setResultLanguage] = useState<InterfaceLanguage>("en");
  const [resultSeed, setResultSeed] = useState("");
  const [selectedArtist, setSelectedArtist] = useState<string | undefined>();
  const [selectedStorefront, setSelectedStorefront] = useState<VerifiedStorefront | null>(null);
  const [selectedResolution, setSelectedResolution] = useState<string | undefined>();
  const [resolutionError, setResolutionError] = useState(false);
  const [confirmedModelArtist, setConfirmedModelArtist] = useState<string | null>(null);
  const discoveryRequest = useRef(0);
  const discoveryPending = useRef(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [notice, setNotice] = useState<"deviceUnavailable" | "partialSources" | null>(null);
  const [profile, setProfile] = useState<PreferenceProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState(false);
  const [ratings, setRatings] = useState<Record<string, FeedbackValue>>({});
  const [pending, setPending] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState(false);
  const [preferencesChanged, setPreferencesChanged] = useState(false);
  const copy = copyFor(language);

  useEffect(() => {
    // Browser preference is restored after hydration so the server and first client render agree.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLanguage(readLanguage());
  }, []);

  useEffect(() => {
    const previous = document.documentElement.lang;
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    return () => { document.documentElement.lang = previous; };
  }, [language]);

  function switchLanguage() {
    const next = language === "en" ? "zh" : "en";
    setLanguage(next);
    saveLanguage(next);
  }

  useEffect(() => {
    const client = createApiClient(API_BASE, getDeviceId());
    api.current = client;
    let active = true;
    client
      .bootstrap()
      .catch(() => {
        if (active)
          setNotice("deviceUnavailable");
      })
      .finally(() => {
        if (active) setReady(true);
      });
    client
      .profile()
      .then((value) => {
        if (!active) return;
        setProfile(value);
        setRatings(
          Object.fromEntries(
            value.recent_feedback.map((entry) => [
              entry.track_key,
              entry.value,
            ]),
          ),
        );
      })
      .catch(() => {
        if (active) setProfileError(true);
      })
      .finally(() => {
        if (active) setProfileLoading(false);
      });
    return () => {
      active = false;
      discoveryRequest.current += 1;
      client.cancelDiscovery?.();
    };
  }, []);

  async function findMusic(event?: React.FormEvent, artist = selectedArtist, query = seed, modelSuggested = false,
    storefront = selectedStorefront, resolutionId = selectedResolution) {
    event?.preventDefault();
    if (!api.current || !query.trim() || discoveryPending.current) return;
    const currentRequest = ++discoveryRequest.current;
    discoveryPending.current = true;
    if (modelSuggested && artist) setConfirmedModelArtist(artist);
    setLoading(true);
    setError(false);
    setResolutionError(false);
    setNotice(null);
    setFeedbackError(false);
    try {
      const response = resolutionId
        ? await api.current.discover(query.trim(), limit, language, artist, storefront ?? undefined, resolutionId)
        : storefront
        ? await api.current.discover(query.trim(), limit, language, artist, storefront)
        : await api.current.discover(query.trim(), limit, language, artist);
      if (currentRequest !== discoveryRequest.current) return;
      setResult(response);
      setResultLanguage(language);
      setResultSeed(query.trim());
      if (resolutionId) setSelectedResolution(response.resolution_id ?? undefined);
      setConfirmedModelArtist(response.seed_status === "matched" && artist &&
        (modelSuggested || (query.trim() === resultSeed && artist === confirmedModelArtist)) ? artist : null);
      setPreferencesChanged(false);
      if (Object.values(response.sources).some((source) => source.error))
        setNotice("partialSources");
    } catch (failure) {
      if (currentRequest === discoveryRequest.current) {
        setError(true);
        if (failure instanceof Error && "code" in failure && typeof failure.code === "string"
          && failure.code.startsWith("resolution_")) {
          setResolutionError(true); setSelectedResolution(undefined);
        }
      }
    } finally {
      if (currentRequest === discoveryRequest.current) {
        discoveryPending.current = false;
        setLoading(false);
      }
    }
  }

  async function sendFeedback(item: RecommendationItem, value: FeedbackValue) {
    if (!api.current || pending) return;
    const previous = ratings[item.id];
    setRatings((current) => ({ ...current, [item.id]: value }));
    setPending(item.id);
    setFeedbackError(false);
    try {
      await api.current.feedback(item.track, value);
      setPreferencesChanged(true);
      try {
        const nextProfile = await api.current.profile();
        setProfile(nextProfile);
        setProfileError(false);
      } catch {
        setProfileError(true);
      }
    } catch {
      setRatings((current) => {
        const next = { ...current };
        if (previous) next[item.id] = previous;
        else delete next[item.id];
        return next;
      });
      setFeedbackError(true);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="site-shell">
      <header className="site-header">
        <Link href="/" className="brand" aria-label={copy.home}>
          <span className="brand-icon">◉</span> sonora
          <span className="brand-dot">.</span>
        </Link>
        <div className="header-actions">
          <button type="button" className="language-toggle" onClick={switchLanguage}
            aria-label={language === "en" ? "切换为中文" : "Switch to English"}>
            <span lang="en" className={language === "en" ? "active-language" : undefined}>EN</span>
            <span aria-hidden="true"> / </span>
            <span lang="zh-CN" className={language === "zh" ? "active-language" : undefined}>中文</span>
          </button>
          <Link href="/agent" className="agent-nav">{copy.assistant}</Link>
        </div>
      </header>
      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <span className="eyebrow" lang="en">FIND YOUR NEXT FAVORITE</span>
            <h1 id="hero-title" lang="en">
              Listen into
              <br />
              <em>something new.</em>
            </h1>
            <p>{copy.heroDescription}</p>
          </div>
          <div className="hero-record" aria-hidden="true">
            <div className="record-inner">
              <span>
                SONORA
                <br />
                SESSIONS
              </span>
            </div>
          </div>
        </section>
        <div className="content-grid">
          <div className="main-column">
            <section className="search-panel" aria-labelledby="search-title">
              <div className="section-heading">
                <div>
                  <span className="eyebrow" lang="en">01 / DISCOVER</span>
                  <h2 id="search-title" lang="en">What’s on your mind?</h2>
                </div>
                <span className="section-aside">
                  {copy.searchAside}
                </span>
              </div>
              <form onSubmit={findMusic}>
                <div className="form-row">
                  <div className="input-wrap">
                    <label htmlFor="seed">{copy.seedLabel}</label>
                    <input
                      id="seed"
                      value={seed}
                      onChange={(event) => {
                        setSeed(event.target.value); setSelectedArtist(undefined); setSelectedStorefront(null);
                        setSelectedResolution(undefined);
                        if (discoveryPending.current) {
                          api.current?.cancelDiscovery?.(); discoveryRequest.current += 1;
                          discoveryPending.current = false; setLoading(false); setResult(null);
                        }
                      }}
                      placeholder={copy.seedPlaceholder}
                      maxLength={120}
                      required
                    />
                  </div>
                  <div className="limit-wrap">
                    <label htmlFor="limit">{copy.resultsLabel}</label>
                    <select
                      id="limit"
                      value={limit}
                      onChange={(event) => setLimit(Number(event.target.value))}
                    >
                      <option value={3}>3 {copy.trackUnit}</option>
                      <option value={5}>5 {copy.trackUnit}</option>
                      <option value={10}>10 {copy.trackUnit}</option>
                    </select>
                  </div>
                  <button
                    className="primary-button"
                    type="submit"
                    disabled={!ready || loading}
                  >
                    {loading ? copy.finding : copy.findMusic}
                    <span aria-hidden="true">↗</span>
                  </button>
                </div>
              </form>
            </section>
            <section
              className="results-section"
              aria-labelledby="results-title"
              aria-busy={loading}
            >
              <div className="section-heading">
                <div>
                  <span className="eyebrow" lang="en">02 / YOUR MIX</span>
                  <h2 id="results-title" lang="en">Made for this moment</h2>
                </div>
                {result && !loading ? (
                  <span className="result-count">
                    {result.requires_confirmation ? copy.awaitingArtistConfirmation
                      : language === "zh" ? `找到 ${result.items.length} 首歌曲` : `${result.items.length} tracks found`}
                  </span>
                ) : null}
              </div>
              <div className="status-region" aria-live="polite">
                {!ready ? <p>{copy.connecting}</p> : null}
                {loading ? (
                  <p className="loading-state">{copy.expandingSearch}</p>
                ) : null}
                {notice ? <p className="notice">{copy[notice]}</p> : null}
                {error ? (
                  <div role="alert" className="error-state">
                    <p>{resolutionError ? copy.resolutionExpired : copy.recommendationsError}</p>
                    <button type="button" onClick={() => findMusic()}>
                      {copy.tryAgain}
                    </button>
                  </div>
                ) : null}
                {feedbackError ? (
                  <p role="alert" className="feedback-error">
                    {copy.feedbackError}
                  </p>
                ) : null}
                {preferencesChanged ? (
                  <p className="personalization-note">
                    {copy.tasteChanged}{" "}
                    <button type="button" onClick={() => findMusic()}>
                      {copy.refresh}
                    </button>
                  </p>
                ) : null}
              </div>
              {!loading && !result && !error ? (
                <div className="empty-state">
                  <div aria-hidden="true" className="empty-art">
                    ♫
                  </div>
                  <h3>{copy.emptyTitle}</h3>
                  <p>{copy.emptyDescription}</p>
                </div>
              ) : null}
              {!loading && result && !error ? (
                <div className="discovery-context">
                  {result.seed_track && !result.requires_confirmation ? (
                    <p className="seed-track"><span>{copy.basedOn}</span>
                      <strong>{result.seed_track.title} · {artistDisplayName(result.seed_track.artist)}</strong>
                      {result.seed_resolution_source === "model" ? <span>{copy.modelSeed}</span> : null}
                      {result.seed_resolution_source === "verified_hint" ? <span>{copy.verifiedSeed}</span> : null}
                      {confirmedModelArtist ? <span>{copy.modelConfirmed}</span> : null}
                      {result.seed_storefront ? <span>{copy.onlineVerified}</span> : null}
                      {safeExternalUrl(result.seed_track.source.external_url) ? <a href={safeExternalUrl(result.seed_track.source.external_url)!}
                        target="_blank" rel="noopener noreferrer">{copy.verificationSource}</a> : null}
                      {result.seed_track.source.provider === "musicbrainz" ? <span>{copy.metadataOnly}</span> : null}
                    </p>
                  ) : null}
                  {result.seed_status === "ambiguous" || result.requires_confirmation ? (
                    <ArtistConfirmation key={`${result.request_id}:${resultSeed}`} query={resultSeed}
                      candidates={result.seed_candidates} language={language}
                      candidateResolutions={result.candidate_resolutions}
                      initialSuggestion={result.requires_confirmation && result.seed_track ? {
                        request_id: result.request_id, status: "matched",
                        suggestion: { title: result.seed_track.title, artist: result.seed_track.artist.name },
                        matched_track: result.seed_track, verified_storefront: result.seed_storefront,
                        resolution_id: result.resolution_id, sources: result.sources,
                      } : undefined}
                      identifyOriginal={(...args) => {
                        if (!api.current) return Promise.reject(new Error("Music service is not ready."));
                        return api.current.identifyOriginal(...args);
                      }}
                      resolveRecording={(...args) => api.current!.resolveRecording(...args)}
                      onSelect={(artist, modelSuggested, storefront, resolutionId) => {
                        setSeed(resultSeed);
                        setSelectedArtist(artist);
                        setSelectedStorefront(storefront ?? null);
                        setSelectedResolution(resolutionId);
                        void findMusic(undefined, artist, resultSeed, modelSuggested, storefront ?? null, resolutionId);
                      }} />
                  ) : (
                    <div className="discovery-guidance">
                      <h3>{copy.guidanceTitle}</h3>
                      <p>{result.guidance_provider === "openai_compatible" && result.guidance_status === "ready" && resultLanguage === language
                        ? result.guidance : localGuidance(result, language)}</p>
                      {result.guidance_status === "unavailable" ? <p className="guidance-note">{copy.modelUnavailable}</p> : null}
                      {result.guidance_provider === "openai_compatible" && resultLanguage !== language
                        ? <p className="guidance-note">{copy.guidanceLanguage}</p> : null}
                    </div>
                  )}
                  <SearchReport report={result.search_report} language={language} />
                  {result.seed_status === "unresolved" && !result.items.length ? <RecordingRecovery
                    key={`${result.request_id}:${resultSeed}:manual`} query={resultSeed} language={language}
                    resolve={(...args) => api.current!.resolveRecording(...args)} onSelect={(track, id) => {
                      setSeed(resultSeed); setSelectedArtist(track.artist.name); setSelectedStorefront(null); setSelectedResolution(id);
                      void findMusic(undefined, track.artist.name, resultSeed, false, null, id);
                    }} /> : null}
                </div>
              ) : null}
              {!loading && result && !error ? (
                result.items.length ? (
                  <div className="track-list">
                    {result.items.map((item, index) => (
                      <RecommendationCard
                        key={item.id}
                        item={item}
                        index={index}
                        rating={ratings[item.id]}
                        pending={pending !== null}
                        onFeedback={(value) => sendFeedback(item, value)}
                        language={language}
                      />
                    ))}
                  </div>
                ) : result.seed_status !== "matched" || result.requires_confirmation ? null : (
                  <div className="empty-state">
                    <h3>{copy.noTracks}</h3>
                    <p>{copy.noTracksDescription}</p>
                  </div>
                )
              ) : null}
            </section>
          </div>
          <ProfilePanel
            profile={profile}
            loading={profileLoading}
            error={profileError ? copy.profileError : null}
            language={language}
          />
        </div>
      </main>
      <footer className="site-footer">
        <span>sonora. / Find your frequency.</span>
        <span>{copy.footer}</span>
      </footer>
    </div>
  );
}
