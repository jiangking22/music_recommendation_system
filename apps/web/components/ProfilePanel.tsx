import type { PreferenceProfile } from "../types/music";

export default function ProfilePanel({
  profile,
  loading,
  error,
}: {
  profile: PreferenceProfile | null;
  loading: boolean;
  error: string | null;
}) {
  const sections = [
    ["Artists", profile?.artists],
    ["Genres & tags", [...(profile?.genres ?? []), ...(profile?.tags ?? [])]],
    ["Language", profile?.languages],
  ] as const;
  return (
    <aside className="profile-panel" aria-labelledby="profile-title">
      <div className="profile-top">
        <span className="eyebrow">YOUR LISTENING DNA</span>
        <div className="profile-mark">◎</div>
      </div>
      <h2 id="profile-title">Preference profile</h2>
      <p className="profile-intro">
        Your likes shape the next set of recommendations.
      </p>
      {loading ? (
        <p role="status">Loading your profile…</p>
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
                      {value.name}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="profile-muted">No signals yet</p>
              )}
            </section>
          ))}
          <section className="profile-section">
            <h3>Recent feedback</h3>
            {profile?.recent_feedback.length ? (
              <ul className="recent-feedback">
                {profile.recent_feedback.map((item) => (
                  <li key={item.track_key}>
                    <span>
                      {item.value === "like" ? "♡" : "−"}{" "}
                      {item.track_key.split("::")[0]}
                    </span>
                    <strong>{item.value}</strong>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="profile-muted">
                Your listening story starts with a like.
              </p>
            )}
          </section>
        </>
      )}
    </aside>
  );
}
