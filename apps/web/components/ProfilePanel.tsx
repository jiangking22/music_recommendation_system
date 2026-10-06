import { artistDisplayName, copyFor } from "../lib/i18n";
import type { InterfaceLanguage, PreferenceProfile } from "../types/music";

export default function ProfilePanel({
  profile,
  loading,
  error,
  language = "en",
}: {
  profile: PreferenceProfile | null;
  loading: boolean;
  error: string | null;
  language?: InterfaceLanguage;
}) {
  const copy = copyFor(language);
  const sections = [
    [copy.artists, profile?.artists],
    [copy.genres, [...(profile?.genres ?? []), ...(profile?.tags ?? [])]],
    [copy.language, profile?.languages],
  ] as const;
  return (
    <aside className="profile-panel" aria-labelledby="profile-title">
      <div className="profile-top">
        <span className="eyebrow" lang="en">YOUR LISTENING DNA</span>
        <div className="profile-mark">◎</div>
      </div>
      <h2 id="profile-title" lang="en">Preference profile</h2>
      <p className="profile-intro">
        {copy.profileIntro}
      </p>
      {loading ? (
        <p role="status">{copy.profileLoading}</p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : (
        <>
          {sections.map(([label, values]) => (
            <section className="profile-section" key={label}>
              <h3>{label}</h3>
              {values && values.length > 0 ? (
                <div className="chips">
                  {values.slice(0, 5).map((value) => (
                    <span className="chip" key={value.name}>
                      {label === copy.artists ? artistDisplayName(value) : value.name}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="profile-muted">{copy.noSignals}</p>
              )}
            </section>
          ))}
          <section className="profile-section">
            <h3>{copy.recentFeedback}</h3>
            {profile?.recent_feedback.length ? (
              <ul className="recent-feedback">
                {profile.recent_feedback.map((item) => (
                  <li key={item.track_key}>
                    <span>
                      {item.value === "like" ? "♡" : "−"}{" "}
                      {item.track_key.split("::")[0]}
                    </span>
                    <strong>{item.value === "like" ? copy.like : copy.dislike}</strong>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="profile-muted">
                {copy.profileEmpty}
              </p>
            )}
          </section>
        </>
      )}
    </aside>
  );
}
