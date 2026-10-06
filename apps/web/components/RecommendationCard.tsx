import Image from "next/image";
import { safeExternalUrl } from "../lib/url";
import { artistDisplayName, copyFor, factorLabel, recommendationExplanation } from "../lib/i18n";
import type { FeedbackValue, InterfaceLanguage, RecommendationItem } from "../types/music";

type Props = {
  item: RecommendationItem;
  index: number;
  rating?: FeedbackValue;
  pending: boolean;
  onFeedback: (value: FeedbackValue) => void;
  language?: InterfaceLanguage;
};

export default function RecommendationCard({
  item,
  index,
  rating,
  pending,
  onFeedback,
  language = "en",
}: Props) {
  const copy = copyFor(language);
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
            alt={language === "zh" ? `${item.title} 的封面` : `Cover artwork for ${item.title}`}
            width={144}
            height={144}
            unoptimized
          />
        ) : (
          <span aria-label={language === "zh" ? `${item.title} 暂无封面` : `No artwork for ${item.title}`} role="img">
            ♪
          </span>
        )}
      </div>
      <div className="track-body">
        <div className="track-heading">
          <div>
            <h3>{item.title}</h3>
            <p>
              {artistDisplayName(item.track.artist)}
              {item.track.album ? (
                <span className="album"> · {item.track.album.name}</span>
              ) : null}
            </p>
          </div>
          <span className="match">{copy.score} {item.score.toFixed(2)}</span>
        </div>
        <p className="explanation">{recommendationExplanation(item, language)}</p>
        <div className="track-footer">
          <div className="providers" aria-label={copy.sources}>
            {providers.map((provider) => (
              <span key={provider}>{provider}</span>
            ))}
          </div>
          <div className="track-actions">
            <button
              type="button"
              className={rating === "like" ? "feedback selected" : "feedback"}
              aria-label={`${copy.like} ${item.title}`}
              aria-pressed={rating === "like"}
              disabled={pending}
              onClick={() => onFeedback("like")}
            >
              ♡ <span>{copy.like}</span>
            </button>
            <button
              type="button"
              className={
                rating === "dislike" ? "feedback selected" : "feedback"
              }
              aria-label={`${copy.dislike} ${item.title}`}
              aria-pressed={rating === "dislike"}
              disabled={pending}
              onClick={() => onFeedback("dislike")}
            >
              − <span>{copy.dislike}</span>
            </button>
            {link ? (
              <a
                className="open-link"
                href={link}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={language === "zh" ? `在 ${item.track.source.provider} 打开歌曲 ${item.title}` : `Open track ${item.title} in ${item.track.source.provider}`}
              >
                {item.track.source.provider === "musicbrainz" ? copy.verificationSource : copy.openTrack}
              </a>
            ) : null}
          </div>
        </div>
        <details className="score-details">
          <summary>{copy.whyMatch}</summary>
          <dl>
            {Object.entries(item.score_breakdown).map(([name, value]) => (
              <div key={name}>
                <dt>{factorLabel(name, language)}</dt>
                <dd>{value.toFixed(2)}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>
    </article>
  );
}
