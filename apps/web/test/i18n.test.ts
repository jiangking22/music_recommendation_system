import { describe, expect, it } from "vitest";
import { factorLabel, recommendationExplanation } from "../lib/i18n";
import type { RecommendationItem } from "../types/music";

describe("canonical recommendation explanations", () => {
  it("translates measured seed factors and negative feedback without claiming an original recording", () => {
    const item = {
      explanation: "related musical attributes; less aligned with past feedback",
      score_breakdown: { seed_artist: 1, seed_genre: 0.5, seed_tag: 0.5, seed_language: 0.2, genre_affinity: -0.3, disliked_track: -8 },
    } satisfies Pick<RecommendationItem, "explanation" | "score_breakdown">;
    expect(recommendationExplanation(item, "zh")).toBe("来自起点歌曲的歌手；与起点歌曲曲风相近；与起点歌曲标签相近；与起点歌曲语言相同；曾标记为不喜欢；与以往反馈较不一致");
    expect(recommendationExplanation(item, "en")).toBe(item.explanation);
    expect(factorLabel("seed_genre", "zh")).toBe("起点曲风");
    expect(factorLabel("source_confidence", "zh")).toBe("来源可信度");
  });
});
