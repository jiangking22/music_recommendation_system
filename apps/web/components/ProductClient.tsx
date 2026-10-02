"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createApiClient, type ApiClient } from "../lib/api";
import { getDeviceId } from "../lib/device";
import type {
  FeedbackValue,
  PreferenceProfile,
  RecommendationResponse,
  RecommendationItem,
} from "../types/music";
import ProfilePanel from "./ProfilePanel";
import RecommendationCard from "./RecommendationCard";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ProductClient() {
  const api = useRef<ApiClient | null>(null);
  const [ready, setReady] = useState(false);
  const [seed, setSeed] = useState("");
  const [limit, setLimit] = useState(5);
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [profile, setProfile] = useState<PreferenceProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [ratings, setRatings] = useState<Record<string, FeedbackValue>>({});
  const [pending, setPending] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [preferencesChanged, setPreferencesChanged] = useState(false);

  useEffect(() => {
    const client = createApiClient(API_BASE, getDeviceId());
    api.current = client;
    let active = true;
    client
      .bootstrap()
      .catch(() => {
        if (active)
          setNotice(
            "Your device profile could not be connected. Try again later.",
          );
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
        if (active) setProfileError("Your profile is unavailable right now.");
      })
      .finally(() => {
        if (active) setProfileLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function findMusic(event?: React.FormEvent) {
    event?.preventDefault();
    if (!api.current || !seed.trim() || loading) return;
    setLoading(true);
    setError(null);
    setNotice(null);
    setFeedbackError(null);
    try {
      const response = await api.current.recommend(seed.trim(), limit);
      setResult(response);
      setPreferencesChanged(false);
      if (Object.values(response.sources).some((source) => source.error))
        setNotice(
          "Some sources are unavailable. Showing the music we could find.",
        );
    } catch {
      setError(
        "Couldn’t load recommendations. Check the service and try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function sendFeedback(item: RecommendationItem, value: FeedbackValue) {
    if (!api.current || pending) return;
    const previous = ratings[item.id];
    setRatings((current) => ({ ...current, [item.id]: value }));
    setPending(item.id);
    setFeedbackError(null);
    try {
      await api.current.feedback(item.track, value);
      setPreferencesChanged(true);
      try {
        const nextProfile = await api.current.profile();
        setProfile(nextProfile);
        setProfileError(null);
      } catch {
        setProfileError("Your profile is unavailable right now.");
      }
    } catch {
      setRatings((current) => {
        const next = { ...current };
        if (previous) next[item.id] = previous;
        else delete next[item.id];
        return next;
      });
      setFeedbackError("Couldn’t save feedback. Please try again.");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="site-shell">
      <header className="site-header">
        <Link href="/" className="brand" aria-label="Sonora home">
          <span className="brand-icon">◉</span> sonora
          <span className="brand-dot">.</span>
        </Link>
        <Link href="/agent" className="agent-nav">Music assistant ↗</Link>
      </header>
      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <span className="eyebrow">FIND YOUR NEXT FAVORITE</span>
            <h1 id="hero-title">
              Listen into
              <br />
              <em>something new.</em>
            </h1>
            <p>
              Begin with a song, artist, or feeling. We’ll find music that
              resonates—and learn what you love along the way.
            </p>
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
                  <span className="eyebrow">01 / DISCOVER</span>
                  <h2 id="search-title">What’s on your mind?</h2>
                </div>
                <span className="section-aside">
                  Your next listen starts here.
                </span>
              </div>
              <form onSubmit={findMusic}>
                <div className="form-row">
                  <div className="input-wrap">
                    <label htmlFor="seed">Song or mood</label>
                    <input
                      id="seed"
                      value={seed}
                      onChange={(event) => setSeed(event.target.value)}
                      placeholder="e.g. Dreams by Fleetwood Mac, late-night jazz…"
                      maxLength={120}
                      required
                    />
                  </div>
                  <div className="limit-wrap">
                    <label htmlFor="limit">Results</label>
                    <select
                      id="limit"
                      value={limit}
                      onChange={(event) => setLimit(Number(event.target.value))}
                    >
                      <option value={3}>3 tracks</option>
                      <option value={5}>5 tracks</option>
                      <option value={10}>10 tracks</option>
                    </select>
                  </div>
                  <button
                    className="primary-button"
                    type="submit"
                    disabled={!ready || loading}
                  >
                    {loading ? "Finding…" : "Find music"}
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
                  <span className="eyebrow">02 / YOUR MIX</span>
                  <h2 id="results-title">Made for this moment</h2>
                </div>
                {result && !loading ? (
                  <span className="result-count">
                    {result.items.length} tracks found
                  </span>
                ) : null}
              </div>
              <div className="status-region" aria-live="polite">
                {!ready ? <p>Connecting your listening profile…</p> : null}
                {loading ? (
                  <p className="loading-state">Finding your next listen…</p>
                ) : null}
                {notice ? <p className="notice">{notice}</p> : null}
                {error ? (
                  <div role="alert" className="error-state">
                    <p>{error}</p>
                    <button type="button" onClick={() => findMusic()}>
                      Try again
                    </button>
                  </div>
                ) : null}
                {feedbackError ? (
                  <p role="alert" className="feedback-error">
                    {feedbackError}
                  </p>
                ) : null}
                {preferencesChanged ? (
                  <p className="personalization-note">
                    Your taste has changed.{" "}
                    <button type="button" onClick={() => findMusic()}>
                      Refresh recommendations ↗
                    </button>
                  </p>
                ) : null}
              </div>
              {!loading && !result && !error ? (
                <div className="empty-state">
                  <div aria-hidden="true" className="empty-art">
                    ♫
                  </div>
                  <h3>Ready to discover</h3>
                  <p>
                    Start with a song you love—or a mood you can’t quite name.
                  </p>
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
                      />
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">
                    <h3>No tracks found</h3>
                    <p>Try another song or mood to start a different search.</p>
                  </div>
                )
              ) : null}
            </section>
          </div>
          <ProfilePanel
            profile={profile}
            loading={profileLoading}
            error={profileError}
          />
        </div>
      </main>
      <footer className="site-footer">
        <span>sonora. / Find your frequency.</span>
        <span>Thoughtful music discovery, one track at a time.</span>
      </footer>
    </div>
  );
}
