import type { DiscoveryResponse, InterfaceLanguage, RecommendationItem } from "../types/music";

export const LANGUAGE_STORAGE_KEY = "sonora.interface-language";

export function readLanguage(): InterfaceLanguage {
  try {
    return localStorage.getItem(LANGUAGE_STORAGE_KEY) === "zh" ? "zh" : "en";
  } catch {
    return "en";
  }
}

export function saveLanguage(language: InterfaceLanguage) {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // The current page can still switch language when browser storage is blocked.
  }
}

const en = {
  home: "Sonora home",
  assistant: "Music assistant ↗",
  heroDescription: "Begin with a song, artist, or feeling. We’ll find music that resonates—and learn what you love along the way.",
  searchAside: "Your next listen starts here.",
  seedLabel: "Song or mood",
  seedPlaceholder: "e.g. 我好想你, Dreams by Fleetwood Mac, late-night jazz…",
  resultsLabel: "Results",
  trackUnit: "tracks",
  findMusic: "Find music",
  finding: "Finding…",
  connecting: "Connecting your listening profile…",
  loading: "Finding your next listen…",
  deviceUnavailable: "Your device profile could not be connected. Try again later.",
  partialSources: "Some sources are unavailable. Showing the music we could find.",
  recommendationsError: "Couldn’t load recommendations. Check the service and try again.",
  feedbackError: "Couldn’t save feedback. Please try again.",
  profileError: "Your profile is unavailable right now.",
  tryAgain: "Try again",
  tasteChanged: "Your taste has changed.",
  refresh: "Refresh recommendations ↗",
  emptyTitle: "Ready to discover",
  emptyDescription: "Start with a song you love—or a mood you can’t quite name.",
  noTracks: "No tracks found",
  noTracksDescription: "Try another song or mood to start a different search.",
  basedOn: "Based on",
  modelSeed: "Model-assisted identification, matched in catalog.",
  verifiedSeed: "Verified original-artist recording.",
  confirmArtist: "Which artist did you mean?",
  confirmDescription: "Several recordings share this title. Confirm the artist to discover related songs.",
  guidanceTitle: "Listening direction",
  modelUnavailable: "Model guidance is unavailable; recommendations are still ready.",
  guidanceLanguage: "Search again for guidance in this language.",
  like: "Like",
  dislike: "Dislike",
  score: "Score",
  sources: "Music sources",
  openTrack: "Open track ↗",
  whyMatch: "Why this match?",
  profileIntro: "Your likes shape the next set of recommendations.",
  profileLoading: "Loading your profile…",
  artists: "Artists",
  genres: "Genres & tags",
  language: "Language",
  noSignals: "No signals yet",
  recentFeedback: "Recent feedback",
  profileEmpty: "Your listening story starts with a like.",
  footer: "Thoughtful music discovery, one track at a time.",
};

type Copy = Record<keyof typeof en, string>;
const zh: Copy = {
  home: "Sonora 首页",
  assistant: "音乐助手 ↗",
  heroDescription: "从一首歌、一位歌手或一种心情出发，寻找与你共鸣的音乐，也逐渐了解你的喜好。",
  searchAside: "下一首好歌，从这里开始。",
  seedLabel: "歌曲或心情",
  seedPlaceholder: "例如：我好想你、Dreams by Fleetwood Mac、深夜爵士…",
  resultsLabel: "推荐数量",
  trackUnit: "首",
  findMusic: "发现音乐",
  finding: "寻找中…",
  connecting: "正在连接你的音乐偏好…",
  loading: "正在寻找下一首好歌…",
  deviceUnavailable: "暂时无法连接设备偏好，请稍后重试。",
  partialSources: "部分音乐来源暂不可用，已展示可用曲目。",
  recommendationsError: "暂时无法获取推荐，请检查服务后重试。",
  feedbackError: "暂时无法保存反馈，请重试。",
  profileError: "暂时无法加载你的偏好。",
  tryAgain: "重试",
  tasteChanged: "已更新你的音乐偏好。",
  refresh: "刷新推荐 ↗",
  emptyTitle: "准备发现新音乐",
  emptyDescription: "从一首喜欢的歌，或一种难以描述的心情开始。",
  noTracks: "暂未找到歌曲",
  noTracksDescription: "换一首歌或一种心情，再试一次。",
  basedOn: "起点歌曲",
  modelSeed: "模型辅助识别，已匹配曲库",
  verifiedSeed: "已核实原唱歌手版本",
  confirmArtist: "你想听哪位歌手的版本？",
  confirmDescription: "找到多个同名录音，请确认歌手后继续发现相关歌曲。",
  guidanceTitle: "聆听方向",
  modelUnavailable: "助手解读暂不可用，歌曲推荐仍可正常查看。",
  guidanceLanguage: "重新搜索可获取当前语言的助手解读。",
  like: "喜欢",
  dislike: "不喜欢",
  score: "匹配分",
  sources: "音乐来源",
  openTrack: "打开歌曲 ↗",
  whyMatch: "为什么推荐？",
  profileIntro: "你的喜好会影响下一次推荐。",
  profileLoading: "正在加载你的偏好…",
  artists: "歌手",
  genres: "曲风与标签",
  language: "歌曲语言",
  noSignals: "暂无偏好记录",
  recentFeedback: "最近反馈",
  profileEmpty: "喜欢一首歌，开启你的聆听记录。",
  footer: "从每一首歌，发现更贴近你的音乐。",
};

export function copyFor(language: InterfaceLanguage): Copy {
  return language === "zh" ? zh : en;
}

export function artistDisplayName(artist: { name: string; display_name?: string | null }): string {
  return artist.display_name?.trim() || artist.name;
}

const factors: Record<string, [string, string]> = {
  seed_relevance: ["seed relevance", "输入相关度"],
  seed_artist: ["seed artist", "起点歌手"],
  seed_genre: ["seed genre", "起点曲风"],
  seed_tag: ["seed tag", "起点标签"],
  seed_language: ["seed language", "起点语言"],
  artist_affinity: ["artist affinity", "歌手偏好"],
  genre_affinity: ["genre affinity", "曲风偏好"],
  tag_affinity: ["tag affinity", "标签偏好"],
  language_affinity: ["language affinity", "语言偏好"],
  popularity: ["popularity", "热度"],
  source_confidence: ["source confidence", "来源可信度"],
  disliked_track: ["disliked track", "已标记不喜欢"],
};

export function factorLabel(name: string, language: InterfaceLanguage): string {
  return factors[name]?.[language === "zh" ? 1 : 0] ?? (language === "zh" ? "其他因素" : name.replaceAll("_", " "));
}

export function recommendationExplanation(item: Pick<RecommendationItem, "explanation" | "score_breakdown">, language: InterfaceLanguage): string {
  if (language === "en") return item.explanation;
  const scores = item.score_breakdown;
  const reasons: string[] = [];
  const positives: Record<string, string> = {
    seed_relevance: "符合输入线索", seed_artist: "来自起点歌曲的歌手", seed_genre: "与起点歌曲曲风相近",
    seed_tag: "与起点歌曲标签相近", seed_language: "与起点歌曲语言相同",
    artist_affinity: "符合喜欢的歌手", genre_affinity: "符合偏好曲风", tag_affinity: "符合偏好标签", language_affinity: "符合偏好语言",
  };
  for (const [name, label] of Object.entries(positives)) {
    if (scores[name] > 0) reasons.push(label);
  }
  if (scores.disliked_track < 0) reasons.push("曾标记为不喜欢");
  if (["artist_affinity", "genre_affinity", "tag_affinity", "language_affinity"].some((name) => scores[name] < 0)) {
    reasons.push("与以往反馈较不一致");
  }
  return reasons.join("；") || "从可用曲库中发现的歌曲。";
}

export function localGuidance(result: DiscoveryResponse, language: InterfaceLanguage): string {
  if (result.seed_status === "ambiguous") return copyFor(language).confirmDescription;
  const seed = result.seed_track;
  if (!seed) {
    if (!result.items.length) return language === "zh"
      ? "暂未确认具体歌曲，也未找到相关曲目。添加歌手名或换个线索再试。"
      : "No specific recording or related tracks were found. Add the artist or try another input.";
    return language === "zh"
      ? `根据输入和已有偏好推荐 ${result.items.length} 首歌曲，顺序由推荐器确定。`
      : `Found ${result.items.length} tracks using your input and feedback, in recommender order.`;
  }
  return language === "zh"
    ? `以 ${seed.title} · ${artistDisplayName(seed.artist)} 为起点，结合曲风、标签和你的偏好探索其他歌曲；已排除起点歌曲的重复版本。`
    : `Start from ${seed.title} · ${artistDisplayName(seed.artist)} and explore other songs through genre, tags and your preferences. Repeated versions of the seed are excluded.`;
}
