import Image from "next/image";
import { safeExternalUrl } from "../lib/url";
import type { FeedbackValue, RecommendationItem } from "../types/music";

type Props = {
  item: RecommendationItem;
  index: number;
  rating?: FeedbackValue;
  pending: boolean;
  onFeedback: (value: FeedbackValue) => void;
};

export default function RecommendationCard({
  item,
  index,
  rating,
  pending,
  onFeedback,
}: Props) {
  const link =
    safeExternalUrl(item.track.source.external_url) ??
    item.provenance
      .map((source) => safeExternalUrl(source.external_url))
      .find(Boolean);
  const artwork = safeExternalUrl(item.track.artwork_url);
  const providers = [
    ...new Set(item.provenance.map((source) => source.provider)),
  ];
  return (
    <article className="track-card">
      <span className="track-index">{String(index + 1).padStart(2, "0")}</span>
      <div className="artwork">
        {artwork ? (
          <Image
            src={artwork}
            alt={`Cover artwork for ${item.title}`}
            width={144}
            height={144}
            unoptimized
          />
        ) : (
          <span aria-label={`No artwork for ${item.title}`} role="img">
            ♪
          </span>
        )}
      </div>
      <div className="track-body">
        <div className="track-heading">
          <div>
            <h3>{item.title}</h3>
            <p>
              {item.artist}
              {item.track.album ? (
                <span className="album"> · {item.track.album.name}</span>
              ) : null}
            </p>
          </div>
          <span className="match">Score {item.score.toFixed(2)}</span>
        </div>
        <p className="explanation">{item.explanation}</p>
        <div className="track-footer">
          <div className="providers" aria-label="Music sources">
            {providers.map((provider) => (
              <span key={provider}>{provider}</span>
            ))}
          </div>
          <div className="track-actions">
            <button
              type="button"
              className={rating === "like" ? "feedback selected" : "feedback"}
              aria-label={`Like ${item.title}`}
              aria-pressed={rating === "like"}
              disabled={pending}
              onClick={() => onFeedback("like")}
            >
              ♡ <span>Like</span>
            </button>
            <button
              type="button"
              className={
                rating === "dislike" ? "feedback selected" : "feedback"
              }
              aria-label={`Dislike ${item.title}`}
              aria-pressed={rating === "dislike"}
              disabled={pending}
              onClick={() => onFeedback("dislike")}
            >
              − <span>Dislike</span>
            </button>
            {link ? (
              <a
                className="open-link"
                href={link}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open track ${item.title} in ${item.track.source.provider}`}
              >
                Open track ↗
              </a>
            ) : null}
          </div>
        </div>
        <details className="score-details">
          <summary>Why this match?</summary>
          <dl>
            {Object.entries(item.score_breakdown).map(([name, value]) => (
              <div key={name}>
                <dt>{name.replaceAll("_", " ")}</dt>
                <dd>{value.toFixed(2)}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>
    </article>
  );
}
