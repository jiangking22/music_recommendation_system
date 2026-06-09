"use strict";

const TARGET_COUNT = 10;
const SEARCH_COUNTRIES = ["CN", "US", "JP", "KR", "GB"];
const DOMESTIC_PROVIDERS = ["qq", "netease"];
const STREAMING_PROVIDERS = ["ytmusic", "spotify"];
const ALL_PROVIDERS = ["qq", "netease", "itunes", "ytmusic", "spotify"];
const PROVIDER_GROUPS = {
  default: [["qq", "netease"], ["itunes", "ytmusic", "spotify"]],
  chinese: [["qq", "netease"], ["itunes", "ytmusic", "spotify"]],
  english: [["itunes", "ytmusic", "spotify"], ["qq", "netease"]]
};
const FALLBACK_TERMS = ["pop hits", "mandopop", "new music", "top songs", "indie pop", "kpop"];
const REQUEST_TIMEOUT_MS = 7000;
const LOCAL_PROXY_ORIGINS = Array.from({ length: 50 }, (_, index) => `http://127.0.0.1:${8010 + index}`);
const MAX_CONCURRENT_SEARCHES = 3;
const FETCH_POOL_SIZE = 18;
const ONLINE_POOL_KEY = "music-recommendation-online-pool-v7";
const RUNTIME_FAMOUS_ARTISTS_KEY = "music-recommendation-runtime-famous-artists-v1";
const OTHER_ARTIST_HISTORY_KEY = "music-recommendation-other-artist-history-v1";
const TASTE_PROFILE_KEY = "music-recommendation-taste-profile-v1";
const TASTE_SETTINGS_KEY = "music-recommendation-taste-settings-v1";
const OTHER_ARTIST_HISTORY_LIMIT = 5;
const OTHER_ARTIST_RECENT_REPEAT_PENALTY = 160;
const MIN_RECOMMENDATION_POPULARITY = 70;
const MIN_OTHER_ARTIST_POPULARITY = 78;
const OTHER_ARTIST_EXPLORATION_WEIGHT = 18;
const ARTIST_MATCH_WEIGHT = 72;
const ARTIST_RECOMMENDATION_MIN = 3;
const OTHER_ARTIST_RECOMMENDATION_MIN = 5;
const ARTIST_RECOMMENDATION_TARGET = TARGET_COUNT - OTHER_ARTIST_RECOMMENDATION_MIN;
const AUTHORITATIVE_ARTIST_MIN_SCORE = 65;
const AUTHORITATIVE_ARTIST_RELAXED_MIN_SCORE = 42;
const AUTHORITATIVE_ARTIST_MIN_CANDIDATES = 4;
const AUTHORITATIVE_ARTIST_FAST_MIN_CANDIDATES = 1;
const AUTHORITATIVE_SEARCH_CONCURRENCY = 5;
const AUTHORITATIVE_EXPANDED_TERM_LIMIT = 4;
const WEB_ARTIST_SEARCH_PROVIDER = "网页搜索";
const CHINESE_PROVIDER_ITUNES_MAX = 2;
const NETEASE_FIRST_ARTISTS = ["华晨宇"];
const GENERIC_PROFILE_TAGS = new Set(["华语", "中文", "英语", "日语", "韩语", "纯音乐", "流行", "热门", "高热度", "人声", "旋律", "热门榜单"]);
const RELATED_ARTIST_GROUPS = [
  { artists: ["周杰伦"], related: ["林俊杰", "陶喆", "王力宏", "方大同", "五月天", "陈奕迅", "孙燕姿"] },
  { artists: ["林俊杰"], related: ["周杰伦", "王力宏", "陶喆", "方大同", "陈奕迅", "邓紫棋", "孙燕姿"] },
  { artists: ["陈奕迅"], related: ["张学友", "李克勤", "林俊杰", "周杰伦", "王菲", "孙燕姿", "五月天"] },
  { artists: ["邓紫棋"], related: ["张靓颖", "袁娅维", "华晨宇", "周深", "林俊杰", "张碧晨", "薛之谦"] },
  { artists: ["华晨宇"], related: ["张杰", "周深", "毛不易", "薛之谦", "邓紫棋", "张碧晨", "汪苏泷"] },
  { artists: ["五月天"], related: ["苏打绿", "告五人", "逃跑计划", "陈奕迅", "周杰伦", "林宥嘉", "田馥甄"] },
  { artists: ["王菲"], related: ["陈奕迅", "张学友", "莫文蔚", "孙燕姿", "刘若英", "田馥甄", "那英"] },
  { artists: ["孙燕姿"], related: ["梁静茹", "田馥甄", "蔡健雅", "王菲", "刘若英", "林俊杰", "张惠妹"] },
  { artists: ["薛之谦"], related: ["毛不易", "汪苏泷", "许嵩", "张杰", "周深", "林俊杰", "陈奕迅"] },
  { artists: ["毛不易"], related: ["赵雷", "李健", "周深", "薛之谦", "许巍", "陈粒", "房东的猫"] },
  { artists: ["告五人"], related: ["五月天", "苏打绿", "茄子蛋", "逃跑计划", "陈粒", "房东的猫", "赵雷"] },
  { artists: ["刘若英"], related: ["梁静茹", "孙燕姿", "王菲", "莫文蔚", "田馥甄", "蔡健雅", "陈绮贞"] },
  { artists: ["张杰"], related: ["华晨宇", "周深", "张碧晨", "薛之谦", "汪苏泷", "毛不易", "林俊杰"] },
  { artists: ["周深"], related: ["张杰", "华晨宇", "毛不易", "邓紫棋", "张碧晨", "李健", "薛之谦"] },
  { artists: ["汪苏泷"], related: ["许嵩", "薛之谦", "毛不易", "张杰", "周深", "林俊杰", "告五人"] },
  { artists: ["许嵩"], related: ["汪苏泷", "薛之谦", "周杰伦", "林俊杰", "毛不易", "赵雷", "李健"] },
  { artists: ["张碧晨"], related: ["邓紫棋", "周深", "张靓颖", "袁娅维", "华晨宇", "张杰", "杨宗纬"] },
  { artists: ["Taylor Swift"], related: ["Olivia Rodrigo", "Sabrina Carpenter", "Ariana Grande", "Dua Lipa", "Ed Sheeran", "Billie Eilish", "Harry Styles", "Lana Del Rey"] },
  { artists: ["The Weeknd"], related: ["Bruno Mars", "Post Malone", "Drake", "SZA", "Doja Cat", "Ariana Grande", "Dua Lipa", "Khalid"] },
  { artists: ["Billie Eilish"], related: ["Olivia Rodrigo", "Lana Del Rey", "Taylor Swift", "Ariana Grande", "SZA", "Dua Lipa", "Sabrina Carpenter"] },
  { artists: ["Ariana Grande"], related: ["Taylor Swift", "Dua Lipa", "Sabrina Carpenter", "Doja Cat", "SZA", "The Weeknd", "Billie Eilish"] },
  { artists: ["Dua Lipa"], related: ["Ariana Grande", "Taylor Swift", "The Weeknd", "Sabrina Carpenter", "Doja Cat", "Calvin Harris", "Lady Gaga"] },
  { artists: ["Ed Sheeran"], related: ["Taylor Swift", "Shawn Mendes", "Harry Styles", "Justin Bieber", "Bruno Mars", "Sam Smith", "Adele"] },
  { artists: ["NewJeans"], related: ["BLACKPINK", "IVE", "LE SSERAFIM", "aespa", "IU", "BTS", "SEVENTEEN"] },
  { artists: ["YOASOBI"], related: ["Ado", "King Gnu", "Official髭男dism", "Mrs. GREEN APPLE", "米津玄師", "宇多田ヒカル"] }
];
const CHINESE_SONG_ARTIST_REFERENCES = [
  { titles: ["晴天", "七里香", "夜曲", "稻香", "青花瓷", "告白气球", "不能说的秘密", "简单爱", "一路向北", "等你下课", "说好不哭", "安静", "半岛铁盒"], artists: ["周杰伦"] },
  { titles: ["江南", "修炼爱情", "可惜没如果", "小酒窝", "她说", "不为谁而作的歌", "背对背拥抱", "那些你很冒险的梦"], artists: ["林俊杰"] },
  { titles: ["十年", "富士山下", "爱情转移", "浮夸", "孤勇者", "K歌之王", "红玫瑰", "好久不见"], artists: ["陈奕迅"] },
  { titles: ["泡沫", "光年之外", "喜欢你", "倒数", "句号", "来自天堂的魔鬼", "多远都要在一起"], artists: ["邓紫棋"] },
  { titles: ["烟火里的尘埃", "好想爱这个世界啊", "国王与乞丐", "我管你", "齐天", "异类", "斗牛", "寒鸦少年", "寻", "微光", "卡西莫多的礼物", "蜉蝣", "疯人院", "新世界", "Here We Are"], artists: ["华晨宇"] },
  { titles: ["突然好想你", "倔强", "知足", "温柔", "后来的我们", "你不是真正的快乐", "派对动物"], artists: ["五月天"] },
  { titles: ["红豆", "匆匆那年", "因为爱情", "容易受伤的女人", "传奇", "我愿意"], artists: ["王菲"] },
  { titles: ["遇见", "天黑黑", "绿光", "开始懂了", "逆光", "我怀念的"], artists: ["孙燕姿"] },
  { titles: ["演员", "认真的雪", "丑八怪", "绅士", "刚刚好", "意外"], artists: ["薛之谦"] },
  { titles: ["消愁", "像我这样的人", "平凡的一天", "牧马城市", "无问"], artists: ["毛不易"] },
  { titles: ["爱人错过", "披星戴月的想你", "唯一", "带我去找夜生活", "好不容易"], artists: ["告五人"] },
  { titles: ["年轮", "一笑倾城", "有点甜", "万有引力", "后会无期"], artists: ["汪苏泷"] },
  { titles: ["后来", "很爱很爱你", "为爱痴狂", "成全", "原来你也在这里"], artists: ["刘若英"] },
  { titles: ["起风了"], artists: ["买辣椒也用券", "吴青峰"] },
  { titles: ["那些年"], artists: ["胡夏"] },
  { titles: ["小幸运"], artists: ["田馥甄"] },
  { titles: ["体面"], artists: ["于文文"] },
  { titles: ["追光者"], artists: ["岑宁儿"] },
  { titles: ["大鱼"], artists: ["周深"] },
  { titles: ["凉凉"], artists: ["杨宗纬", "张碧晨"] },
  { titles: ["成都"], artists: ["赵雷"] },
  { titles: ["南山南"], artists: ["马頔"] }
];
const ARTIST_ALIASES = {
  周杰伦: ["Jay Chou", "周董"],
  林俊杰: ["JJ Lin", "Wayne Lim"],
  陈奕迅: ["Eason Chan"],
  邓紫棋: ["G.E.M.", "GEM"],
  华晨宇: ["Hua Chenyu", "花花"],
  五月天: ["Mayday"],
  王菲: ["Faye Wong"],
  孙燕姿: ["Stefanie Sun"],
  刘若英: ["Rene Liu"],
  周深: ["Charlie Zhou Shen"],
  赵雷: ["Zhao Lei"]
};
const TAG_WEIGHTS = {
  华语: 16,
  英语: 16,
  日语: 16,
  韩语: 16,
  纯音乐: 16,
  流行: 13,
  民谣: 15,
  电子: 15,
  摇滚: 15,
  说唱: 15,
  "R&B": 15,
  轻音乐: 15,
  日韩流行: 14,
  热门榜单: 8,
  热门: 7,
  高热度: 8,
  新歌: 5,
  经典: 5,
  原唱歌手: 18,
  爱情: 7,
  情歌: 7,
  高能: 7,
  舒缓: 7,
  原声: 7,
  节奏: 6,
  人声: 5,
  学习: 5,
  运动: 5
};

const MOOD_PRESETS = {
  auto: { label: "自动", tags: [], types: [], queryTerms: [] },
  focus: { label: "专注学习", tags: ["学习", "安静", "钢琴", "轻音乐", "舒缓"], types: ["轻音乐", "民谣"], queryTerms: ["study music", "piano instrumental", "lofi focus", "轻音乐 学习"] },
  commute: { label: "通勤路上", tags: ["通勤", "旋律", "流行", "明亮"], types: ["流行", "R&B", "民谣"], queryTerms: ["commute playlist", "华语 通勤", "pop commute"] },
  night: { label: "夜晚放松", tags: ["夜晚", "松弛", "柔和", "舒缓", "R&B"], types: ["R&B", "爵士", "轻音乐"], queryTerms: ["night chill", "late night r&b", "夜晚 放松"] },
  energy: { label: "运动高能", tags: ["运动", "高能", "节奏", "派对", "舞曲"], types: ["电子", "摇滚", "说唱"], queryTerms: ["workout hits", "edm workout", "运动 高能"] },
  fresh: { label: "发现新歌", tags: ["新歌", "热门", "明亮"], types: ["流行", "电子", "日韩流行"], queryTerms: ["new music", "fresh finds", "新歌 推荐"] }
};

const LANGUAGES = [
  {
    name: "不限",
    queries: ["top songs", "new music", "pop hits", "indie pop", "r&b hits"],
    countries: ["CN", "US", "JP", "KR", "GB"],
    chartCountries: ["US", "CN", "JP", "KR", "GB"],
    popularTerms: ["Taylor Swift", "The Weeknd", "Ariana Grande", "周杰伦", "NewJeans", "YOASOBI"],
    typeHints: ["流行", "电子", "民谣", "R&B", "独立"]
  },
  {
    name: "华语",
    queries: ["华语流行", "国语流行", "粤语流行", "华语热歌", "华语民谣"],
    countries: ["CN"],
    chartCountries: ["CN"],
    popularTerms: ["周杰伦", "林俊杰", "邓紫棋", "陈奕迅", "五月天", "告五人", "薛之谦", "汪苏泷", "毛不易", "王菲"],
    typeHints: ["流行", "民谣", "R&B", "说唱"]
  },
  {
    name: "英语",
    queries: ["english pop", "billboard hits", "us pop", "uk pop", "r&b hits"],
    countries: ["US", "GB"],
    chartCountries: ["US", "GB"],
    popularTerms: ["Taylor Swift", "The Weeknd", "Billie Eilish", "Ariana Grande", "Dua Lipa", "Ed Sheeran", "Sabrina Carpenter"],
    typeHints: ["流行", "R&B", "电子", "摇滚", "独立"]
  },
  {
    name: "日语",
    queries: ["j-pop", "japanese pop", "anime songs", "j-rock", "city pop"],
    countries: ["JP"],
    chartCountries: ["JP"],
    popularTerms: ["YOASOBI", "米津玄師", "Official髭男dism", "Ado", "King Gnu", "宇多田ヒカル", "Mrs. GREEN APPLE"],
    typeHints: ["日韩流行", "流行", "摇滚", "电子"]
  },
  {
    name: "韩语",
    queries: ["k-pop", "korean pop", "korean r&b", "korean ballad", "k hip hop"],
    countries: ["KR"],
    chartCountries: ["KR"],
    popularTerms: ["BTS", "BLACKPINK", "NewJeans", "IVE", "LE SSERAFIM", "SEVENTEEN", "aespa", "IU"],
    typeHints: ["日韩流行", "流行", "R&B", "说唱", "电子"]
  },
  {
    name: "纯音乐",
    queries: ["instrumental", "piano instrumental", "ambient music", "classical music", "soundtrack"],
    countries: ["US", "GB", "JP"],
    chartCountries: ["US", "GB", "JP"],
    popularTerms: ["Ludovico Einaudi", "Yiruma", "Joe Hisaishi", "Hans Zimmer", "Max Richter", "piano instrumental"],
    typeHints: ["轻音乐", "古典", "电子"]
  }
];

const FAMOUS_ARTIST_NAMES = buildFamousArtistNameSet();

const elements = {
  seedInput: document.getElementById("seedInput"),
  recommendBtn: document.getElementById("recommendBtn"),
  personalRecommendBtn: document.getElementById("personalRecommendBtn"),
  clearBtn: document.getElementById("clearBtn"),
  resetTasteBtn: document.getElementById("resetTasteBtn"),
  tasteSummary: document.getElementById("tasteSummary"),
  moodSelect: document.getElementById("moodSelect"),
  noveltyRange: document.getElementById("noveltyRange"),
  popularityRange: document.getElementById("popularityRange"),
  languageButtons: document.getElementById("languageButtons"),
  recommendationList: document.getElementById("recommendationList"),
  resultTitle: document.getElementById("resultTitle"),
  resultCount: document.getElementById("resultCount"),
  activeQuery: document.getElementById("activeQuery"),
  networkStatus: document.getElementById("networkStatus"),
  artistModal: document.getElementById("artistModal"),
  artistModalHint: document.getElementById("artistModalHint"),
  artistCandidateList: document.getElementById("artistCandidateList"),
  artistManualInput: document.getElementById("artistManualInput"),
  artistManualBtn: document.getElementById("artistManualBtn"),
  artistCancelBtn: document.getElementById("artistCancelBtn")
};

let currentLanguage = LANGUAGES[0].name;
let requestSerial = 0;
let onlineSongPool = loadOnlinePool();
let tasteProfile = loadTasteProfile();
let tasteSettings = loadTasteSettings();
let pendingArtistModalCleanup = null;
let resolvedLocalProxyOrigin = "";
let initialMotionPlayed = false;
let reduceMotion = false;
let statusTween = null;
const searchCache = new Map();
const authoritativeCandidateCache = new Map();
const providerHealth = new Map();
const renderedSongMap = new Map();

init();

function init() {
  elements.languageButtons.innerHTML = LANGUAGES.map(
    (language) => `<button type="button" data-language="${language.name}" class="${language.name === currentLanguage ? "active" : ""}">${language.name}</button>`
  ).join("");
  elements.moodSelect.value = tasteSettings.mood || "auto";
  elements.noveltyRange.value = String(tasteSettings.novelty);
  elements.popularityRange.value = String(tasteSettings.popularity);
  updateTasteSummary();

  elements.recommendBtn.addEventListener("click", () => recommendByInput());
  elements.personalRecommendBtn.addEventListener("click", () => recommendPersonalRadio());
  elements.clearBtn.addEventListener("click", clearInput);
  elements.resetTasteBtn.addEventListener("click", resetTasteProfile);
  elements.moodSelect.addEventListener("change", () => {
    tasteSettings.mood = elements.moodSelect.value;
    saveTasteSettings();
    updateTasteSummary();
  });
  elements.noveltyRange.addEventListener("input", () => {
    tasteSettings.novelty = Number(elements.noveltyRange.value) || 0;
    saveTasteSettings();
    updateTasteSummary();
  });
  elements.popularityRange.addEventListener("input", () => {
    tasteSettings.popularity = Number(elements.popularityRange.value) || 0;
    saveTasteSettings();
    updateTasteSummary();
  });
  elements.recommendationList.addEventListener("click", handleRecommendationAction);
  elements.seedInput.addEventListener("input", () => {
    const seeds = parseSeedSongs(elements.seedInput.value);
    if (!seeds.length) {
      elements.activeQuery.textContent = "输入歌曲名后点击推荐按钮开始检索。";
      animateActiveQuery();
      return;
    }
    elements.activeQuery.textContent = `已输入：${seeds.join("、")}；点击“按类型推荐 10 首”后开始联网检索。`;
    animateActiveQuery();
  });
  elements.languageButtons.addEventListener("click", (event) => {
    const button = event.target.closest("[data-language]");
    if (!button) return;
    animateButtonPress(button);
    currentLanguage = button.dataset.language;
    elements.languageButtons.querySelectorAll("button").forEach((item) => {
      item.classList.toggle("active", item === button);
    });
    if (elements.seedInput.value.trim()) {
      elements.activeQuery.textContent = `已切换推荐语言：${currentLanguage}；点击推荐按钮后开始检索。`;
      animateActiveQuery();
      return;
    }
    recommendByLanguage(currentLanguage);
  });
  initMotion();
}

function initMotion() {
  if (!hasGsap()) return;

  document.body.classList.add("has-gsap");
  gsap.defaults({ duration: 0.45, ease: "power2.out", overwrite: "auto" });

  const mm = gsap.matchMedia();
  mm.add(
    {
      reduceMotion: "(prefers-reduced-motion: reduce)",
      isMobile: "(max-width: 680px)"
    },
    (context) => {
      reduceMotion = context.conditions.reduceMotion;
      animateInitialPage();
      animateLanguageButtons();
    }
  );
}

function hasGsap() {
  return typeof window !== "undefined" && Boolean(window.gsap);
}

function animateInitialPage() {
  if (!hasGsap() || initialMotionPlayed) return;
  initialMotionPlayed = true;

  const targets = [".app-header", ".control-panel", ".result-panel"];
  gsap.from(targets, {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 18,
    duration: reduceMotion ? 0.01 : 0.58,
    stagger: reduceMotion ? 0 : 0.08,
    ease: "power3.out",
    clearProps: "visibility,opacity,transform"
  });
}

function animateLanguageButtons() {
  if (!hasGsap()) return;
  gsap.from(elements.languageButtons.querySelectorAll("button"), {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 10,
    scale: reduceMotion ? 1 : 0.96,
    duration: reduceMotion ? 0.01 : 0.36,
    stagger: reduceMotion ? 0 : 0.035,
    ease: "power2.out",
    clearProps: "visibility,opacity,transform"
  });
}

function animateLoadingState() {
  if (!hasGsap()) return;
  const cards = elements.recommendationList.querySelectorAll(".loading-card");
  gsap.from(cards, {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 10,
    duration: reduceMotion ? 0.01 : 0.34,
    stagger: reduceMotion ? 0 : 0.055,
    ease: "power2.out",
    clearProps: "visibility,opacity,transform"
  });
  if (!reduceMotion) {
    gsap.to(cards, {
      backgroundPosition: "-120% 0",
      duration: 1.15,
      repeat: -1,
      ease: "none",
      stagger: 0.06
    });
  }
}

function animateMessageState(selector = ".empty-state, .error-state") {
  if (!hasGsap()) return;
  gsap.from(elements.recommendationList.querySelectorAll(selector), {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 8,
    duration: reduceMotion ? 0.01 : 0.3,
    ease: "power2.out",
    clearProps: "visibility,opacity,transform"
  });
}

function animateRecommendationResults() {
  if (!hasGsap()) return;
  const headings = elements.recommendationList.querySelectorAll(".recommendation-column-head");
  const cards = Array.from(elements.recommendationList.querySelectorAll(".song-card"));
  const activeCards = cards.filter((card) => card.classList.contains("is-active"));
  const supportCards = cards.filter((card) => !card.classList.contains("is-active"));

  gsap.from(headings, {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 10,
    duration: reduceMotion ? 0.01 : 0.28,
    stagger: reduceMotion ? 0 : 0.04,
    ease: "power2.out",
    clearProps: "visibility,opacity,transform"
  });
  gsap.from(activeCards, {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 20,
    scale: reduceMotion ? 1 : 0.97,
    duration: reduceMotion ? 0.01 : 0.5,
    stagger: reduceMotion ? 0 : 0.05,
    ease: "power3.out",
    clearProps: "visibility,opacity,transform"
  });
  gsap.from(supportCards, {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 14,
    scale: reduceMotion ? 1 : 0.985,
    duration: reduceMotion ? 0.01 : 0.38,
    delay: reduceMotion ? 0 : 0.06,
    stagger: reduceMotion ? 0 : 0.025,
    ease: "power2.out",
    clearProps: "visibility,opacity,transform"
  });
  animateActiveCardDetails();
}

function animateArtistModalOpen() {
  if (!hasGsap()) return;
  const modal = elements.artistModal.querySelector(".artist-modal");
  const candidates = elements.artistCandidateList.querySelectorAll(".artist-candidate, .empty-state");

  gsap.fromTo(elements.artistModal, { autoAlpha: 0 }, { autoAlpha: 1, duration: reduceMotion ? 0.01 : 0.22 });
  gsap.from(modal, {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 18,
    scale: reduceMotion ? 1 : 0.985,
    duration: reduceMotion ? 0.01 : 0.38,
    ease: "power3.out",
    clearProps: "visibility,opacity,transform"
  });
  gsap.from(candidates, {
    autoAlpha: 0,
    x: reduceMotion ? 0 : -10,
    duration: reduceMotion ? 0.01 : 0.3,
    stagger: reduceMotion ? 0 : 0.045,
    ease: "power2.out",
    clearProps: "visibility,opacity,transform"
  });
}

function animateArtistModalClose(onComplete) {
  if (!hasGsap()) {
    onComplete();
    return;
  }
  const modal = elements.artistModal.querySelector(".artist-modal");
  gsap.to(modal, {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 12,
    scale: reduceMotion ? 1 : 0.985,
    duration: reduceMotion ? 0.01 : 0.18,
    ease: "power2.in"
  });
  gsap.to(elements.artistModal, {
    autoAlpha: 0,
    duration: reduceMotion ? 0.01 : 0.2,
    ease: "power2.out",
    onComplete
  });
}

function animateActiveCardDetails() {
  if (!hasGsap()) return;
  const details = elements.recommendationList.querySelectorAll(
    ".song-card.is-active .cover, .song-card.is-active .song-title, .song-card.is-active .song-meta, .song-card.is-active .tag-row, .song-card.is-active .song-reason"
  );
  gsap.from(details, {
    autoAlpha: 0,
    y: reduceMotion ? 0 : 8,
    scale: reduceMotion ? 1 : 0.985,
    duration: reduceMotion ? 0.01 : 0.28,
    stagger: reduceMotion ? 0 : 0.025,
    ease: "power2.out",
    clearProps: "visibility,opacity,transform"
  });
}

function animateButtonPress(button) {
  if (!hasGsap() || !button) return;
  gsap.fromTo(button, { scale: reduceMotion ? 1 : 0.98 }, {
    scale: 1,
    duration: reduceMotion ? 0.01 : 0.24,
    ease: "back.out(2)",
    clearProps: "transform"
  });
}

function animateStatusBadge() {
  if (!hasGsap()) return;
  statusTween?.kill();
  statusTween = gsap.fromTo(elements.networkStatus, {
    autoAlpha: 0.72,
    y: reduceMotion ? 0 : -4,
    scale: reduceMotion ? 1 : 0.98
  }, {
    autoAlpha: 1,
    y: 0,
    scale: 1,
    duration: reduceMotion ? 0.01 : 0.28,
    ease: "power2.out",
    clearProps: "visibility,opacity,transform"
  });
}

function setStatusText(text) {
  elements.networkStatus.textContent = text;
  animateStatusBadge();
}

function animateActiveQuery() {
  if (!hasGsap()) return;
  gsap.fromTo(elements.activeQuery, {
    autoAlpha: 0.78,
    y: reduceMotion ? 0 : 4,
    backgroundColor: "rgba(237, 245, 255, 0.72)"
  }, {
    autoAlpha: 1,
    y: 0,
    backgroundColor: "rgba(248, 250, 252, 0.58)",
    duration: reduceMotion ? 0.01 : 0.3,
    ease: "power2.out",
    clearProps: "visibility,opacity,transform,backgroundColor"
  });
}

function clearInput() {
  animateButtonPress(elements.clearBtn);
  requestSerial += 1;
  cancelActiveRequests();
  closeArtistModal();
  setControlsDisabled(false);
  elements.seedInput.value = "";
  elements.resultTitle.textContent = "等待推荐";
  elements.resultCount.textContent = "0 / 10";
  elements.activeQuery.textContent = "输入歌曲后点击推荐；结果卡片可用滚轮或方向键切换，点“喜欢 / 不喜欢”会影响下一次推荐。";
  setStatusText("按类型推荐 · 10 首");
  elements.recommendationList.innerHTML = `<div class="empty-state">推荐结果会显示在这里。每张卡片都会展示歌曲信息、推荐理由和“喜欢 / 不喜欢”反馈按钮。</div>`;
  animateActiveQuery();
  animateMessageState();
}

function loadTasteProfile() {
  try {
    return normalizeTasteProfile(JSON.parse(localStorage.getItem(TASTE_PROFILE_KEY) || "{}"));
  } catch {
    return normalizeTasteProfile({});
  }
}

function normalizeTasteProfile(profile) {
  return {
    languages: normalizeWeightMap(profile.languages),
    types: normalizeWeightMap(profile.types),
    tags: normalizeWeightMap(profile.tags),
    artists: normalizeWeightMap(profile.artists),
    providers: normalizeWeightMap(profile.providers),
    blockedKeys: Array.isArray(profile.blockedKeys) ? uniqueStrings(profile.blockedKeys).slice(-160) : [],
    likedKeys: Array.isArray(profile.likedKeys) ? uniqueStrings(profile.likedKeys).slice(-160) : [],
    plays: Math.max(0, Number(profile.plays) || 0),
    likes: Math.max(0, Number(profile.likes) || 0),
    dislikes: Math.max(0, Number(profile.dislikes) || 0),
    updatedAt: Number(profile.updatedAt) || 0
  };
}

function normalizeWeightMap(map) {
  const source = map && typeof map === "object" ? map : {};
  return Object.fromEntries(
    Object.entries(source)
      .map(([key, value]) => [String(key || "").trim(), Math.max(-80, Math.min(160, Number(value) || 0))])
      .filter(([key, value]) => key && Math.abs(value) >= 0.5)
      .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
      .slice(0, 80)
  );
}

function loadTasteSettings() {
  try {
    const parsed = JSON.parse(localStorage.getItem(TASTE_SETTINGS_KEY) || "{}");
    return normalizeTasteSettings(parsed);
  } catch {
    return normalizeTasteSettings({});
  }
}

function normalizeTasteSettings(settings) {
  return {
    mood: MOOD_PRESETS[settings.mood] ? settings.mood : "auto",
    novelty: Math.max(0, Math.min(100, Number(settings.novelty) || 45)),
    popularity: Math.max(0, Math.min(100, Number(settings.popularity) || 62))
  };
}

function saveTasteProfile() {
  tasteProfile = normalizeTasteProfile(tasteProfile);
  try {
    localStorage.setItem(TASTE_PROFILE_KEY, JSON.stringify(tasteProfile));
  } catch {
    // 个性化画像写入失败时，推荐仍按当前会话继续。
  }
  updateTasteSummary();
}

function saveTasteSettings() {
  tasteSettings = normalizeTasteSettings(tasteSettings);
  try {
    localStorage.setItem(TASTE_SETTINGS_KEY, JSON.stringify(tasteSettings));
  } catch {
    // 偏好设置写入失败不影响本次推荐。
  }
}

function updateTasteSummary() {
  const profile = normalizeTasteProfile(tasteProfile);
  const topTags = topWeightedEntries(profile.tags, 4).map(([tag]) => tag);
  const topTypes = topWeightedEntries(profile.types, 3).map(([type]) => type);
  const topArtists = topWeightedEntries(profile.artists, 2).map(([artist]) => artist);
  const mood = MOOD_PRESETS[tasteSettings.mood] || MOOD_PRESETS.auto;
  const learned = profile.likes + profile.plays + profile.dislikes;
  const pieces = [];

  if (topTypes.length) pieces.push(`风格 ${topTypes.join("、")}`);
  if (topTags.length) pieces.push(`标签 ${topTags.join("、")}`);
  if (topArtists.length) pieces.push(`歌手 ${topArtists.join("、")}`);
  pieces.push(`心情 ${mood.label}`);
  pieces.push(`新鲜度 ${tasteSettings.novelty}%`);
  pieces.push(`热度 ${tasteSettings.popularity}%`);

  elements.tasteSummary.textContent = learned
    ? `已学习 ${learned} 次反馈：${pieces.join("；")}`
    : "喜欢几首歌后，系统会把语言、风格和歌手偏好记住；点“私人电台”会直接按画像推荐。";
}

function resetTasteProfile() {
  animateButtonPress(elements.resetTasteBtn);
  tasteProfile = normalizeTasteProfile({});
  localStorage.removeItem(TASTE_PROFILE_KEY);
  updateTasteSummary();
  setStatusText("已重置听歌画像");
}

function handleRecommendationAction(event) {
  const actionButton = event.target.closest("[data-song-action]");
  if (!actionButton) return;
  const card = actionButton.closest(".song-card");
  const song = card ? renderedSongMap.get(card.dataset.songKey) : null;
  if (!song) return;
  const action = actionButton.dataset.songAction;
  recordTasteFeedback(song, action);
  card.classList.toggle("is-liked", action === "like");
  card.classList.toggle("is-disliked", action === "dislike");
  animateButtonPress(actionButton);
}

function recordTasteFeedback(song, action) {
  const weights = { like: 16, dislike: -22, play: 7, open: 5 };
  const weight = weights[action] || 0;
  if (!weight) return;

  const profile = normalizeTasteProfile(tasteProfile);
  addTasteWeight(profile.languages, song.language, weight * 0.78);
  addTasteWeight(profile.types, song.type, weight);
  addTasteWeight(profile.tags, song.rawGenre, weight * 0.72);
  cleanRecommendationTags(song.tags || []).forEach((tag) => addTasteWeight(profile.tags, tag, weight * 0.62));
  addTasteWeight(profile.artists, song.artist, weight * 0.86);
  addTasteWeight(profile.providers, sourceProvider(song), weight * 0.34);

  const key = songIdentityKey(song);
  if (action === "like") {
    profile.likes += 1;
    profile.likedKeys = uniqueStrings([...profile.likedKeys, key]).slice(-160);
    profile.blockedKeys = profile.blockedKeys.filter((item) => item !== key);
    setStatusText("已记住：多推荐这类歌");
  } else if (action === "dislike") {
    profile.dislikes += 1;
    profile.blockedKeys = uniqueStrings([...profile.blockedKeys, key]).slice(-160);
    profile.likedKeys = profile.likedKeys.filter((item) => item !== key);
    setStatusText("已记住：少推荐这类歌");
  } else {
    profile.plays += 1;
    setStatusText("已学习一次试听偏好");
  }

  profile.updatedAt = Date.now();
  tasteProfile = profile;
  saveTasteProfile();
}

function addTasteWeight(map, key, amount) {
  const label = String(key || "").trim();
  if (!label) return;
  map[label] = Math.max(-80, Math.min(160, (Number(map[label]) || 0) + amount));
}

function topWeightedEntries(map, limit = 5) {
  return Object.entries(map || {})
    .filter(([, value]) => Number(value) > 0)
    .sort((a, b) => Number(b[1]) - Number(a[1]) || a[0].localeCompare(b[0], "zh-CN"))
    .slice(0, limit);
}

function topWeightedKey(map) {
  const [entry] = topWeightedEntries(map, 1);
  return entry ? entry[0] : "";
}

function tasteProfileToSeedProfile(profile, languageName) {
  const language = getLanguageConfig(languageName);
  const mood = MOOD_PRESETS[tasteSettings.mood] || MOOD_PRESETS.auto;
  const languages = topWeightedEntries(profile.languages, 2).map(([name]) => name);
  return {
    ...emptyProfile(),
    types: uniqueStrings([...topWeightedEntries(profile.types, 4).map(([name]) => name), ...mood.types]),
    rawGenres: topWeightedEntries(profile.types, 4).map(([name]) => name),
    tags: uniqueStrings([...topWeightedEntries(profile.tags, 10).map(([name]) => name), ...mood.tags]),
    artists: topWeightedEntries(profile.artists, 3).map(([name]) => name),
    languages: languages.length ? languages : (language.name === "不限" ? [] : [language.name]),
    countries: language.countries || []
  };
}

function formatPersonalRadioLabel(profile, language) {
  const tags = topWeightedEntries(profile.tags, 4).map(([name]) => name).join("、") || "你的近期偏好";
  const artists = topWeightedEntries(profile.artists, 2).map(([name]) => name).join("、");
  const mood = MOOD_PRESETS[tasteSettings.mood] || MOOD_PRESETS.auto;
  return `私人电台：${language}；${artists ? `偏好歌手 ${artists}；` : ""}标签 ${tags}；心情 ${mood.label}`;
}

function tasteSearchTerms(context) {
  const profile = normalizeTasteProfile(context.tasteProfile || tasteProfile);
  const settings = normalizeTasteSettings(context.tasteSettings || tasteSettings);
  const mood = MOOD_PRESETS[settings.mood] || MOOD_PRESETS.auto;
  const languageName = context.language === "不限" ? "" : context.language;
  const topTags = topWeightedEntries(profile.tags, 8).map(([name]) => name);
  const topTypes = topWeightedEntries(profile.types, 5).map(([name]) => name);
  const topArtists = topWeightedEntries(profile.artists, 5).map(([name]) => name);
  return uniqueStrings([
    ...topArtists,
    ...topArtists.flatMap((artist) => [`${artist} 推荐歌曲`, `${artist} 相似歌手`]),
    ...topTags,
    ...topTypes,
    ...topTags.map((tag) => `${languageName} ${tag}`),
    ...topTypes.map((type) => `${languageName} ${type}`),
    ...mood.queryTerms
  ]).slice(0, 28);
}

function recommendByInput() {
  const seeds = parseSeedSongs(elements.seedInput.value);
  if (seeds.length === 0) {
    recommendByLanguage(currentLanguage);
    return;
  }
  runRecommendation({
    mode: "seed",
    seeds,
    language: currentLanguage,
    seedProfile: emptyProfile(),
    tasteProfile,
    tasteSettings: { ...tasteSettings },
    title: "基于语言和风格推荐",
    label: `参考歌曲：${seeds.join("、")}；推荐语言：${currentLanguage}`
  });
}

function recommendByLanguage(language) {
  const title = language === "不限" ? "全部语言歌曲推荐" : `${language}歌曲推荐`;
  runRecommendation({
    mode: "language",
    seeds: [],
    language,
    seedProfile: emptyProfile(),
    tasteProfile,
    tasteSettings: { ...tasteSettings },
    title,
    label: `推荐语言：${language}`
  });
}

function recommendPersonalRadio() {
  animateButtonPress(elements.personalRecommendBtn);
  const profile = normalizeTasteProfile(tasteProfile);
  const bestLanguage = topWeightedKey(profile.languages) || currentLanguage;
  const language = bestLanguage && getLanguageConfig(bestLanguage).name === bestLanguage ? bestLanguage : currentLanguage;
  runRecommendation({
    mode: "personal",
    seeds: [],
    language,
    seedProfile: tasteProfileToSeedProfile(profile, language),
    tasteProfile: profile,
    tasteSettings: { ...tasteSettings, mood: elements.moodSelect.value },
    title: "私人电台",
    label: formatPersonalRadioLabel(profile, language)
  });
}

async function runRecommendation(context) {
  const serial = ++requestSerial;
  const activeContext = { ...context, serial };
  activeContext.platformPreference = inferPlatformPreference(activeContext);
  cancelActiveRequests();
  setLoading(activeContext);

  try {
    const songs = activeContext.mode === "seed"
      ? await fetchSeedRecommendations(activeContext)
      : await fetchLanguageRecommendations(activeContext);

    if (serial !== requestSerial) return;

    const completedSongs = await ensureTenSongs(songs, activeContext);
    if (serial !== requestSerial) return;

    const ranked = rankAndLimit(completedSongs, activeContext);
    renderRecommendations(ranked, activeContext);
    rememberRecentOtherArtistRecommendations(ranked, activeContext);
  } catch (error) {
    if (serial !== requestSerial) return;
    renderError(error);
  } finally {
    if (serial === requestSerial) {
      setControlsDisabled(false);
    }
  }
}

function setLoading(context) {
  animateButtonPress(elements.recommendBtn);
  setControlsDisabled(true);
  elements.resultTitle.textContent = context.title;
  elements.resultCount.textContent = "联网中";
  elements.activeQuery.textContent = context.label;
  animateActiveQuery();
  setStatusText("正在多源检索热门歌曲");
  elements.recommendationList.innerHTML = `
    <div class="loading-list" aria-label="正在加载">
      ${Array.from({ length: 5 }, () => `<div class="loading-card"></div>`).join("")}
    </div>
  `;
  animateLoadingState();
}

function setControlsDisabled(disabled) {
  elements.recommendBtn.disabled = disabled;
  elements.personalRecommendBtn.disabled = disabled;
  elements.languageButtons.querySelectorAll("button").forEach((button) => {
    button.disabled = disabled;
  });
}

async function fetchSeedRecommendations(context) {
  const seedTerms = context.seeds.slice(0, 6);
  const seedMatches = await fetchMany(seedTerms, 8, FETCH_POOL_SIZE, context.serial, context, true);
  const seedSongs = dedupeSongs(seedMatches, context);
  const authoritativeArtist = await resolveAuthoritativeSeedArtist(context, seedSongs);
  context.seedProfile = buildSeedProfile(seedSongs, context, authoritativeArtist);
  if (context.serial === requestSerial) {
    elements.activeQuery.textContent = formatSeedProfile(context);
  }
  const searchTerms = buildTypeSearchTerms(context);
  const [searchResults, artistSongs, chartSongs] = await Promise.all([
    fetchMany(searchTerms, 24, FETCH_POOL_SIZE, context.serial, context),
    fetchSeedArtistRecommendations(context),
    fetchSeedMatchedCharts(context)
  ]);
  let results = searchResults.concat(artistSongs, chartSongs);

  if (dedupeSongs(results, context).length < TARGET_COUNT) {
    results = results.concat(await fetchMany(getBackupTerms(context), 20, FETCH_POOL_SIZE, context.serial, context));
  }

  return getUsableSongs(results, context);
}

async function fetchSeedArtistRecommendations(context) {
  const profile = context.seedProfile || emptyProfile();
  const artist = profile.artists[0];
  if (!artist) return [];

  const providerOrder = getProviderOrder(context);
  const prefersDomestic = DOMESTIC_PROVIDERS.includes(providerOrder[0]);
  const firstProviders = providerOrder.slice(0, prefersDomestic ? 2 : 3).map(providerName).join("、");
  setStatusText(`正在优先从 ${firstProviders} 检索原唱歌手作品`);
  const terms = uniqueStrings([
    artist,
    `${artist} top songs`,
    `${artist} hits`,
    `${artist} 热门歌曲`,
    `${artist} 代表作`
  ]);

  let songs = [];
  if (prefersDomestic) {
    songs = songs.concat(await fetchDomesticArtistSongs(artist, context.serial, context));
    if (context.serial !== requestSerial) return [];
    if (songs.length >= ARTIST_RECOMMENDATION_TARGET + 2) {
      return markArtistSongs(songs, artist);
    }
  }

  songs = songs.concat(await fetchMany(terms, 18, FETCH_POOL_SIZE, context.serial, context, true));
  if (context.serial !== requestSerial) return [];

  if (!prefersDomestic && markArtistSongs(songs, artist).length < ARTIST_RECOMMENDATION_TARGET + 2) {
    songs = songs.concat(await fetchDomesticArtistSongs(artist, context.serial, context));
  }

  return markArtistSongs(songs, artist);
}

async function resolveAuthoritativeSeedArtist(context, seedSongs = []) {
  const countries = uniqueStrings([...getSearchCountries(context), ...SEARCH_COUNTRIES]);
  const unresolvedSeed = context.seeds[0] || "";

  for (const seed of context.seeds.slice(0, 3)) {
    if (context.serial !== requestSerial) return null;
    const title = extractSeedTitle(seed);
    if (!title) continue;

    const fastCandidates = buildFastAuthoritativeArtistCandidateList(title, seed, seedSongs, context).slice(0, 6);
    if (fastCandidates.length) {
      const selected = await showArtistSelectionModal(seed, fastCandidates, context.serial, {
        providerText: authoritativeProviderText(context, fastCandidates)
      });
      if (context.serial !== requestSerial) return null;
      if (selected) return selected;
    }

    setStatusText("正在检索权威原唱歌手");
    const candidates = await fetchAuthoritativeSeedCandidates(title, seed, countries, context.serial, context);
    const artistCandidates = buildAuthoritativeArtistCandidateList(title, seed, candidates, context).slice(0, 6);
    if (artistCandidates.length) {
      const selected = await showArtistSelectionModal(seed, artistCandidates, context.serial, {
        providerText: authoritativeProviderText(context, artistCandidates)
      });
      if (context.serial !== requestSerial) return null;
      if (selected) return selected;
    }
  }

  if (unresolvedSeed && context.serial === requestSerial) {
    return showArtistSelectionModal(unresolvedSeed, [], context.serial, {
      providerText: authoritativeProviderText(context),
      fallback: true
    });
  }

  return null;
}

function buildFastAuthoritativeArtistCandidateList(title, rawSeed, seedSongs, context) {
  const onlineCandidates = groupAuthoritativeArtistCandidates(title, rawSeed, seedSongs, AUTHORITATIVE_ARTIST_MIN_SCORE);
  const knownCandidates = shouldUseChineseArtistExpansion(title, rawSeed, context)
    ? buildChineseKnownArtistCandidates(title, rawSeed, onlineCandidates)
    : [];
  return mergeAuthoritativeArtistCandidates([...onlineCandidates, ...knownCandidates]);
}

function mergeAuthoritativeArtistCandidates(candidates) {
  const merged = new Map();
  candidates.filter(Boolean).forEach((candidate) => {
    const key = normalizeText(candidate.artist);
    const previous = merged.get(key);
    if (!previous || Number(candidate.authorityScore) > Number(previous.authorityScore)) {
      merged.set(key, candidate);
    }
  });

  return [...merged.values()].sort((a, b) => {
    return b.authorityScore - a.authorityScore || a.artist.localeCompare(b.artist, "zh-CN");
  });
}

function hasEnoughAuthoritativeCandidates(title, rawSeed, candidates, context) {
  return buildAuthoritativeArtistCandidateList(title, rawSeed, candidates, context).length >= AUTHORITATIVE_ARTIST_FAST_MIN_CANDIDATES;
}

function buildAuthoritativeArtistCandidateList(title, rawSeed, candidates, context) {
  const grouped = groupAuthoritativeArtistCandidates(title, rawSeed, candidates, AUTHORITATIVE_ARTIST_MIN_SCORE);
  if (!shouldUseChineseArtistExpansion(title, rawSeed, context) || grouped.length >= AUTHORITATIVE_ARTIST_MIN_CANDIDATES) {
    return grouped;
  }

  const knownCandidates = buildChineseKnownArtistCandidates(title, rawSeed, grouped);
  const relaxedOnlineCandidates = groupAuthoritativeArtistCandidates(title, rawSeed, candidates, AUTHORITATIVE_ARTIST_RELAXED_MIN_SCORE)
    .filter((candidate) => isOnlineAuthoritativeCandidate(candidate));
  return mergeAuthoritativeArtistCandidates([...grouped, ...knownCandidates, ...relaxedOnlineCandidates]);
}

function shouldUseChineseArtistExpansion(title, rawSeed, context) {
  return inferPlatformPreference(context) === "chinese" || hasHan(title) || hasChineseLanguageHint(rawSeed);
}

function buildChineseKnownArtistCandidates(title, rawSeed, existingCandidates = []) {
  const used = new Set(existingCandidates.map((candidate) => normalizeText(candidate.artist)));
  const matchedArtists = findChineseFallbackArtists(title, rawSeed);
  const selectedArtists = uniqueStrings(matchedArtists);
  const seedTitle = extractSeedTitle(rawSeed) || title;

  return selectedArtists
    .filter((artist) => !used.has(normalizeText(artist)))
    .map((artist, index) => {
      return {
        artist,
        title: seedTitle,
        collection: "本地原唱参考",
        country: "CN",
        artwork: "",
        authorityProvider: "本地原唱参考",
        authorityScore: Math.max(92 - index * 2, 82),
        popularity: 88
      };
    });
}

function findChineseFallbackArtists(title, rawSeed) {
  const target = normalizeText(`${title} ${rawSeed}`);
  const normalizedSeedTitle = normalizeText(title);
  if (!target) return [];

  const matches = [];
  CHINESE_SONG_ARTIST_REFERENCES.forEach((item) => {
    const titleMatched = item.titles.some((candidateTitle) => {
      const normalizedTitle = normalizeText(candidateTitle);
      return normalizedTitle && (
        normalizedTitle === normalizedSeedTitle ||
        target.includes(normalizedTitle) ||
        (normalizedSeedTitle.length >= 3 && normalizedTitle.includes(normalizedSeedTitle))
      );
    });
    if (titleMatched) {
      matches.push(...item.artists);
    }
  });

  return uniqueStrings(matches);
}

function isOnlineAuthoritativeCandidate(candidate) {
  return candidate.authorityProvider !== "本地原唱参考";
}

function groupAuthoritativeArtistCandidates(title, rawSeed, candidates, minScore = AUTHORITATIVE_ARTIST_MIN_SCORE) {
  const artistHint = extractSeedArtistHint(rawSeed);
  const grouped = new Map();

  candidates
    .filter((song) => isUsefulArtist(song.artist))
    .map((song) => scoreAuthoritativeSeedCandidate(title, artistHint, song))
    .filter((song) => song.authorityScore >= minScore)
    .forEach((song) => {
      const key = normalizeText(song.artist);
      const previous = grouped.get(key);
      if (!previous || song.authorityScore > previous.authorityScore) {
        grouped.set(key, song);
      }
    });

  return [...grouped.values()].sort((a, b) => {
    return b.authorityScore - a.authorityScore || a.artist.localeCompare(b.artist, "zh-CN");
  });
}

function scoreAuthoritativeSeedCandidate(title, artistHint, song) {
  const titleScore = scoreTitleMatch(title, song.title);
  const hintScore = artistHint && sameArtist(song.artist, artistHint) ? 24 : 0;
  const exactTitleBonus = normalizeText(title) === normalizeText(song.title) ? 12 : 0;
  const popularityScore = Math.min(8, (Number(song.popularity) || 58) * 0.08);
  const computedScore = titleScore + hintScore + exactTitleBonus + popularityScore;
  const authorityScore = Math.max(Number(song.authorityScore) || 0, computedScore);
  return {
    ...song,
    titleScore,
    authorityScore
  };
}

function toAuthoritativeArtist(candidate, source = candidate.authorityProvider || "Apple Music") {
  return {
    artist: candidate.artist,
    title: candidate.title,
    source,
    authorityScore: clampPercentScore(candidate.authorityScore)
  };
}

function showArtistSelectionModal(seed, candidates, serial, options = {}) {
  closeArtistModal();

  return new Promise((resolve, reject) => {
    if (serial !== requestSerial) {
      resolve(null);
      return;
    }

    let settled = false;
    const safeCandidates = candidates.filter((candidate) => isUsefulArtist(candidate.artist));
    const seedTitle = extractSeedTitle(seed) || seed;
    const providerText = options.providerText || uniqueStrings(safeCandidates.map((candidate) => candidate.authorityProvider || "Apple Music")).join("、") || "Apple Music";
    elements.artistModalHint.textContent = safeCandidates.length
      ? `${providerText} 检索到可能的《${seedTitle}》原唱歌手，系统不会自动确认，请选择最符合参考歌曲的一项。系统会单独展示该歌手的歌曲，目标至少 ${ARTIST_RECOMMENDATION_MIN} 首。`
      : `${providerText} 没有检索到足够可靠的《${seedTitle}》原唱歌手。请手动填写原唱歌手，系统会单独展示该歌手的歌曲，目标至少 ${ARTIST_RECOMMENDATION_MIN} 首。`;
    elements.artistManualInput.value = "";
    elements.artistCandidateList.innerHTML = safeCandidates.length
      ? safeCandidates.map(renderArtistCandidate).join("")
      : `<div class="empty-state">暂无可靠候选，请在下方填写原唱歌手。</div>`;
    elements.artistModal.hidden = false;
    animateArtistModalOpen();

    const cleanup = () => {
      elements.artistCandidateList.removeEventListener("click", onCandidateClick);
      elements.artistManualBtn.removeEventListener("click", onManualClick);
      elements.artistCancelBtn.removeEventListener("click", onCancelClick);
      document.removeEventListener("keydown", onKeydown);
      pendingArtistModalCleanup = null;
      animateArtistModalClose(() => {
        elements.artistModal.hidden = true;
      });
    };

    const finish = (type, value) => {
      if (settled) return;
      settled = true;
      cleanup();
      if (type === "resolve") {
        resolve(value);
      } else {
        reject(value);
      }
    };

    function onCandidateClick(event) {
      const button = event.target.closest("[data-candidate-index]");
      if (!button) return;
      const candidate = safeCandidates[Number(button.dataset.candidateIndex)];
      if (!candidate) return;
      finish("resolve", toAuthoritativeArtist(candidate));
    }

    function onManualClick() {
      const manualArtist = elements.artistManualInput.value.trim();
      if (!manualArtist) {
        elements.artistManualInput.focus();
        return;
      }
      finish("resolve", {
        artist: manualArtist,
        title: extractSeedTitle(seed) || seed,
        source: "用户确认",
        authorityScore: AUTHORITATIVE_ARTIST_MIN_SCORE
      });
    }

    function onCancelClick() {
      finish("reject", new Error("已取消本次推荐"));
    }

    function onKeydown(event) {
      if (event.key === "Escape") {
        onCancelClick();
      }
    }

    pendingArtistModalCleanup = () => finish("resolve", null);
    elements.artistCandidateList.addEventListener("click", onCandidateClick);
    elements.artistManualBtn.addEventListener("click", onManualClick);
    elements.artistCancelBtn.addEventListener("click", onCancelClick);
    document.addEventListener("keydown", onKeydown);
    elements.artistManualInput.focus();
  });
}

function closeArtistModal() {
  if (pendingArtistModalCleanup) {
    pendingArtistModalCleanup();
    return;
  }
  elements.artistModal.hidden = true;
}

function renderArtistCandidate(candidate, index) {
  const artwork = safeImageUrl(candidate.artwork)
    ? `<img src="${escapeAttribute(candidate.artwork)}" alt="${escapeAttribute(candidate.artist)}封面" />`
    : `<div class="artist-candidate-cover" aria-hidden="true"></div>`;
  const score = clampPercentScore(candidate.authorityScore);
  const country = countryLabel(candidate.country);
  const provider = candidate.authorityProvider || "Apple Music";

  return `
    <button class="artist-candidate" type="button" data-candidate-index="${index}">
      ${artwork}
      <span>
        <strong>${escapeHtml(candidate.artist)}</strong>
        <span>匹配曲目：${escapeHtml(candidate.title)}${candidate.collection ? ` · ${escapeHtml(candidate.collection)}` : ""}</span>
        <span>来源：${escapeHtml(provider)} · 权威度：${score} / 100 · ${country}</span>
      </span>
    </button>
  `;
}

function clampPercentScore(value) {
  return Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
}

async function fetchAuthoritativeSeedCandidates(title, rawSeed, countries, serial, context) {
  const providerMode = isNeteasePreferredContext(context) ? "netease-first" : "standard";
  const cacheKey = `authoritative|${inferPlatformPreference(context)}|${providerMode}|${normalizeText(rawSeed || title)}|${countries.join(",")}`;
  if (authoritativeCandidateCache.has(cacheKey)) {
    return authoritativeCandidateCache.get(cacheKey);
  }

  const results = [];
  const finish = () => {
    const uniqueResults = dedupeSongs(results, context);
    if (uniqueResults.length && serial === requestSerial) {
      authoritativeCandidateCache.set(cacheKey, uniqueResults);
    }
    return uniqueResults;
  };

  const primaryPlan = buildAuthoritativeSearchPlan(
    getAuthoritativeArtistProviders(context),
    getAuthoritativeArtistSearchTerms(title, context)
  );

  results.push(...await runAuthoritativeSearchPlan(primaryPlan, countries, serial, 12, title, rawSeed, context));
  if (hasEnoughAuthoritativeCandidates(title, rawSeed, results, context)) {
    return finish();
  }

  if (shouldExpandAuthoritativeSeedSearch(title, rawSeed, results, context)) {
    setStatusText("候选不足，正在扩大平台检索");
    const expandedPlan = buildAuthoritativeSearchPlan(
      getExpandedAuthoritativeArtistProviders(context),
      getExpandedAuthoritativeArtistSearchTerms(title, rawSeed, context)
    );
    results.push(...await runAuthoritativeSearchPlan(expandedPlan, countries, serial, 18, title, rawSeed, context));
    if (hasEnoughAuthoritativeCandidates(title, rawSeed, results, context)) {
      return finish();
    }
  }

  if (shouldSearchWebForAuthoritativeArtist(title, rawSeed, results, context)) {
    setStatusText("音乐平台候选不足，正在网页搜索可能歌手");
    results.push(...await fetchWebArtistCandidates(title, rawSeed, serial));
  }

  return finish();
}

function shouldExpandAuthoritativeSeedSearch(title, rawSeed, candidates, context) {
  if (!shouldUseChineseArtistExpansion(title, rawSeed, context)) return false;
  return !hasEnoughAuthoritativeCandidates(title, rawSeed, candidates, context);
}

function shouldSearchWebForAuthoritativeArtist(title, rawSeed, candidates, context) {
  if (!shouldUseChineseArtistExpansion(title, rawSeed, context)) return false;
  return !hasEnoughAuthoritativeCandidates(title, rawSeed, candidates, context);
}

function buildAuthoritativeSearchPlan(providers, terms) {
  const seen = new Set();
  return providers.flatMap((provider) => {
    return terms.map((term) => ({ provider, term })).filter((item) => {
      const key = `${item.provider}|${normalizeText(item.term)}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  });
}

async function runAuthoritativeSearchPlan(searchPlan, countries, serial, limit, title = "", rawSeed = "", context = null) {
  const results = [];

  for (let index = 0; index < searchPlan.length; index += AUTHORITATIVE_SEARCH_CONCURRENCY) {
    if (serial !== requestSerial) return [];
    const batch = searchPlan.slice(index, index + AUTHORITATIVE_SEARCH_CONCURRENCY);
    const settled = await Promise.allSettled(batch.map(async ({ provider, term }) => {
      if (serial !== requestSerial) return [];
      try {
        return await fetchAuthoritativeProviderCandidates(provider, term, countries, serial, limit);
      } catch {
        return [];
      }
    }));

    results.push(...settled.flatMap((item, offset) => {
      const term = batch[offset].term;
      return (item.status === "fulfilled" ? item.value : []).map((song) => ({
        ...song,
        authoritySearchTerm: term
      }));
    }));

    if (title && hasEnoughAuthoritativeCandidates(title, rawSeed, results, context)) {
      break;
    }
  }

  return results;
}

function getAuthoritativeArtistProviders(context) {
  const preference = inferPlatformPreference(context);
  if (preference === "chinese") return getDomesticProviderOrder(context);
  if (preference === "english") return ["itunes"];
  return [...getDomesticProviderOrder(context), "itunes"];
}

function getExpandedAuthoritativeArtistProviders(context) {
  const preference = inferPlatformPreference(context);
  if (preference === "chinese") return [...getDomesticProviderOrder(context), "itunes", "ytmusic", "spotify"];
  return getAuthoritativeArtistProviders(context);
}

function authoritativeProviderText(context, candidates = []) {
  const onlineProviders = getAuthoritativeArtistProviders(context).map(providerName);
  const candidateProviders = candidates.map((candidate) => candidate.authorityProvider).filter(Boolean);
  return uniqueStrings([...onlineProviders, ...candidateProviders]).join("、");
}

function getAuthoritativeArtistSearchTerms(title, context) {
  const preference = inferPlatformPreference(context);
  if (preference === "chinese") {
    return uniqueStrings([title, `${title} 原唱`, `${title} 歌手`]);
  }
  if (preference === "english") {
    return uniqueStrings([title, `${title} song`]);
  }
  return uniqueStrings([title, `${title} song`, `${title} 原唱`]);
}

function getExpandedAuthoritativeArtistSearchTerms(title, rawSeed, context) {
  const preference = inferPlatformPreference(context);
  if (preference !== "chinese") return getAuthoritativeArtistSearchTerms(title, context);
  return uniqueStrings([
    title,
    rawSeed,
    `${title} 原唱`,
    `${title} 歌手`,
    `${title} 完整版`,
    `${title} 官方`,
    `${title} MV`,
    `${title} lyrics`,
    `${title} song`
  ]).slice(0, AUTHORITATIVE_EXPANDED_TERM_LIMIT);
}

async function fetchAuthoritativeProviderCandidates(provider, title, countries, serial, limit = 12) {
  const results = [];

  if (provider === "itunes") {
    for (let index = 0; index < countries.length; index += AUTHORITATIVE_SEARCH_CONCURRENCY) {
      if (serial !== requestSerial) return [];
      const batch = countries.slice(index, index + AUTHORITATIVE_SEARCH_CONCURRENCY);
      const settled = await Promise.allSettled(batch.map((country) => fetchItunes(title, country, limit)));
      results.push(...settled.flatMap((item) => (item.status === "fulfilled" ? item.value : [])));
      if (results.length >= limit) break;
    }
  } else if (DOMESTIC_PROVIDERS.includes(provider)) {
    results.push(...await fetchDomestic(provider, title, limit));
  } else if (STREAMING_PROVIDERS.includes(provider)) {
    results.push(...await fetchStreaming(provider, title, limit));
  }

  return results.map((song) => ({
    ...song,
    authorityProvider: providerName(provider)
  }));
}

async function fetchWebArtistCandidates(title, rawSeed, serial) {
  if (serial !== requestSerial) return [];
  const term = extractSeedTitle(rawSeed) || title;
  const cacheKey = `web-artist|${normalizeText(rawSeed || title)}`;
  const params = new URLSearchParams({
    term,
    seed: rawSeed || title,
    limit: String(AUTHORITATIVE_ARTIST_MIN_CANDIDATES + 2)
  });

  try {
    return await fetchLocalJson(
      `/api/search/web-artist?${params.toString()}`,
      cacheKey,
      (payload) => (payload.candidates || []).map((item) => mapWebArtistCandidate(item, title)).filter(Boolean),
      false
    );
  } catch {
    return [];
  }
}

function mapWebArtistCandidate(item, title) {
  if (!item || !isUsefulArtist(item.artist)) return null;
  const score = clampPercentScore(item.score || 70);
  return {
    id: `web-artist-${normalizeText(item.artist)}-${item.rank || ""}`,
    trackId: `web-${normalizeText(item.artist)}-${item.rank || ""}`,
    title: item.matchedTitle || title,
    artist: item.artist,
    collection: item.sourceTitle || item.snippet || "",
    rawGenre: "网页搜索",
    type: "流行",
    language: "华语",
    country: "CN",
    releaseYear: null,
    artwork: "",
    sourceUrl: item.sourceUrl || "",
    previewUrl: "",
    explicitness: "notExplicit",
    searchTerm: item.query || title,
    provider: "web",
    providerName: WEB_ARTIST_SEARCH_PROVIDER,
    source: "web-artist",
    searchRank: Number(item.rank) || null,
    popularity: score,
    authorityProvider: WEB_ARTIST_SEARCH_PROVIDER,
    authorityScore: score
  };
}

async function fetchSeedMatchedCharts(context) {
  if (inferPlatformPreference(context) === "chinese") {
    return [];
  }

  const profile = context.seedProfile || emptyProfile();
  const countries = profile.countries.length ? profile.countries : getSearchCountries(context);
  const chartRequests = countries.slice(0, 4).map((country) => fetchItunesChart(country, 30));

  const settled = await Promise.allSettled(chartRequests);
  const songs = settled.flatMap((item) => (item.status === "fulfilled" ? item.value : []));
  addToOnlinePool(songs);
  return getUsableSongs(songs, context).filter((song) => seedProfileMatchesSong(profile, song));
}

async function fetchLanguageRecommendations(context) {
  const language = getLanguageConfig(context.language);
  let results = await fetchMany(uniqueStrings([...tasteSearchTerms(context), ...language.popularTerms, ...language.queries, ...language.typeHints]), 24, FETCH_POOL_SIZE, context.serial, context);

  if (dedupeSongs(results, context).length < TARGET_COUNT) {
    results = results.concat(await fetchPopularCharts(context));
  }

  if (dedupeSongs(results, context).length < TARGET_COUNT) {
    results = results.concat(await fetchMany(getBackupTerms(context), 20, FETCH_POOL_SIZE, context.serial, context));
  }

  return getUsableSongs(results, context);
}

async function fetchPopularCharts(context) {
  if (inferPlatformPreference(context) === "chinese") {
    return [];
  }

  const language = getLanguageConfig(context.language);
  const chartCountries = (language.chartCountries || language.countries || SEARCH_COUNTRIES).slice(0, 5);
  const chartRequests = chartCountries.map((country) => fetchItunesChart(country, 30));

  const settled = await Promise.allSettled(chartRequests);
  const songs = settled.flatMap((item) => (item.status === "fulfilled" ? item.value : []));
  addToOnlinePool(songs);
  return getUsableSongs(songs, context);
}

async function ensureTenSongs(songs, context) {
  let pool = getUsableSongs([...songs, ...selectCachedSongs(context)], context);
  if (recommendationPoolIsReady(pool, context)) return pool;

  const backupTerms = getBackupTerms(context);
  for (const term of backupTerms) {
    if (recommendationPoolIsReady(pool, context)) break;
    if (context.serial !== requestSerial) return [];
    const extraSongs = await fetchMany([term], 25, TARGET_COUNT, context.serial, context);
    pool = getUsableSongs([...pool, ...extraSongs, ...selectCachedSongs(context)], context);
  }

  return pool;
}

function recommendationPoolIsReady(pool, context) {
  if (pool.length < TARGET_COUNT) return false;
  if (!platformCoverageIsReady(pool, context)) return false;
  if (!hasArtistProfile(context)) return true;

  const profile = context.seedProfile || emptyProfile();
  const artistCount = pool.filter((song) => artistMatchesProfile(profile, song)).length;
  const otherSongs = pool.filter((song) => {
    return !artistMatchesProfile(profile, song) && isFamousOtherArtistCandidate(song, profile);
  });
  const otherCount = otherSongs.length;
  const otherArtistCount = uniqueArtistCount(otherSongs);
  return artistCount >= ARTIST_RECOMMENDATION_MIN
    && otherCount >= OTHER_ARTIST_RECOMMENDATION_MIN
    && otherArtistCount >= Math.min(OTHER_ARTIST_RECOMMENDATION_MIN, 4);
}

function platformCoverageIsReady(pool, context) {
  if (inferPlatformPreference(context) !== "chinese") return true;

  const requiredProviderCount = pool.filter((song) => isRequiredChineseProvider(sourceProvider(song))).length;
  const appleCount = pool.filter((song) => sourceProvider(song) === "itunes").length;
  const preferredTarget = Math.min(TARGET_COUNT - CHINESE_PROVIDER_ITUNES_MAX, pool.length);
  return requiredProviderCount >= preferredTarget || appleCount <= CHINESE_PROVIDER_ITUNES_MAX;
}

function isRequiredChineseProvider(provider) {
  return DOMESTIC_PROVIDERS.includes(provider) || STREAMING_PROVIDERS.includes(provider);
}

function buildSeedProfile(seedSongs, context, authoritativeArtist) {
  const language = getLanguageConfig(context.language);
  const textProfile = inferProfileFromSeedTexts(context.seeds);
  const types = topValues([...seedSongs.map((song) => song.type), ...textProfile.types], 5);
  const rawGenres = topValues([...seedSongs.map((song) => song.rawGenre), ...textProfile.rawGenres], 5);
  const tags = topValues([...seedSongs.flatMap((song) => cleanRecommendationTags(song.tags || [])), ...textProfile.tags], 14);
  const artists = authoritativeArtist && isUsefulArtist(authoritativeArtist.artist) ? [authoritativeArtist.artist] : [];
  artists.forEach(addRuntimeFamousArtist);
  const languages = resolveSeedLanguages(context, seedSongs, textProfile, language);
  const countries = context.language === "不限"
    ? topValues([...seedSongs.map((song) => song.country), ...textProfile.countries], 3)
    : language.countries;

  return {
    types: types.length ? types : language.typeHints.slice(0, 3),
    rawGenres,
    tags,
    artists,
    artistSource: authoritativeArtist ? authoritativeArtist.source : "",
    artistTrack: authoritativeArtist ? authoritativeArtist.title : "",
    artistConfidence: authoritativeArtist ? authoritativeArtist.authorityScore : 0,
    artistWeight: authoritativeArtist ? ARTIST_MATCH_WEIGHT : 0,
    languages: languages.filter(Boolean),
    countries: countries.filter(Boolean)
  };
}

function resolveSeedLanguages(context, seedSongs, textProfile, language) {
  if (context.language !== "不限") return [context.language];

  const inputLanguage = inferInputLanguageFromSeeds(context.seeds || []);
  if (inputLanguage) return [inputLanguage];

  const detectedLanguages = topValues([...textProfile.languages, ...seedSongs.map((song) => song.language)], 1);
  if (detectedLanguages.length) return detectedLanguages;

  return language.name === "不限" ? [] : [language.name];
}

function inferInputLanguageFromSeeds(seeds) {
  const rawText = String((seeds || []).join(" "));
  if (!rawText.trim()) return "";

  if (/instrumental|piano|classical|ambient|soundtrack|轻音乐|纯音乐|古典|钢琴/i.test(rawText)) return "纯音乐";
  if (hasHangul(rawText) || hasKoreanLanguageHint(rawText)) return "韩语";
  if (hasJapaneseScript(rawText) || hasJapaneseLanguageHint(rawText)) return "日语";
  if (hasHan(rawText) || hasChineseLanguageHint(rawText)) return "华语";
  if (/[A-Za-z]/.test(rawText) && !hasCjkScript(rawText)) return "英语";
  return "";
}

function inferProfileFromSeedTexts(seeds) {
  const text = normalizeText(seeds.join(" "));
  const rawText = seeds.join(" ");
  const profile = emptyProfile();

  if (hasHan(rawText) || hasChineseLanguageHint(rawText)) {
    profile.languages.push("华语");
    profile.countries.push("CN");
    profile.tags.push("华语", "中文");
  }
  if (hasJapaneseScript(rawText) || hasJapaneseLanguageHint(rawText)) {
    profile.languages.push("日语");
    profile.countries.push("JP");
    profile.tags.push("日语", "日韩流行");
  }
  if (hasHangul(rawText) || hasKoreanLanguageHint(rawText)) {
    profile.languages.push("韩语");
    profile.countries.push("KR");
    profile.tags.push("韩语", "K-Pop");
  }
  if (!profile.languages.length && /taylor swift|billie eilish|ed sheeran|dua lipa|ariana grande|the weeknd|sabrina carpenter|love story|english/i.test(rawText)) {
    profile.languages.push("英语");
    profile.countries.push("US", "GB");
    profile.tags.push("英语", "欧美");
  }

  if (/rock|摇滚|metal|punk/.test(text)) pushProfileStyle(profile, "摇滚", ["高能", "乐队", "吉他"]);
  if (/rap|hip hop|hiphop|trap|说唱|嘻哈/.test(text)) pushProfileStyle(profile, "说唱", ["节奏", "低音", "街头"]);
  if (/r b|rnb|soul|blues|节奏布鲁斯/.test(text)) pushProfileStyle(profile, "R&B", ["律动", "柔和", "人声"]);
  if (/electronic|edm|dance|house|电子|电音|舞曲/.test(text)) pushProfileStyle(profile, "电子", ["高能", "舞曲", "节奏"]);
  if (/folk|acoustic|country|民谣|乡村|原声|love story|毛不易|告五人/.test(text)) pushProfileStyle(profile, "民谣", ["原声", "叙事", "舒缓"]);
  if (/piano|instrumental|classical|ambient|soundtrack|钢琴|纯音乐|轻音乐|古典/.test(text)) {
    pushProfileStyle(profile, "轻音乐", ["钢琴", "安静", "学习"]);
    profile.languages.push("纯音乐");
  }
  if (/love|romantic|情歌|爱情|告白|love story/.test(text)) profile.tags.push("爱情", "情歌");
  if (/sad|breakup|失恋|伤感|emo/.test(text)) profile.tags.push("伤感", "低沉");
  if (/workout|run|运动|跑步|健身/.test(text)) profile.tags.push("运动", "高能");
  if (!profile.types.length) pushProfileStyle(profile, "流行", ["热门", "人声"]);
  profile.rawGenres.push(...profile.types);

  return {
    types: uniqueStrings(profile.types),
    rawGenres: uniqueStrings(profile.rawGenres),
    tags: uniqueStrings(profile.tags),
    languages: uniqueStrings(profile.languages),
    countries: uniqueStrings(profile.countries)
  };
}

function pushProfileStyle(profile, type, tags) {
  profile.types.push(type);
  profile.rawGenres.push(type);
  profile.tags.push(type, ...tags);
}

function buildTypeSearchTerms(context) {
  const language = getLanguageConfig(context.language);
  const profile = context.seedProfile || emptyProfile();
  const personalizedTerms = tasteSearchTerms(context);
  if (context.mode !== "seed") {
    return uniqueStrings([
      ...personalizedTerms,
      ...profile.rawGenres,
      ...profile.types,
      ...profile.tags,
      ...profile.artists,
      ...profile.languages.map((name) => `${name} 热门`).filter(Boolean),
      ...profile.languages.flatMap((name) => getLanguageConfig(name).popularTerms || []),
      ...profile.tags.map((tag) => `${language.name === "不限" ? "" : language.name} ${tag}`).filter(Boolean),
      ...profile.types.map((type) => `${language.name === "不限" ? "" : language.name} ${type}`).filter(Boolean),
      ...language.queries,
      ...language.typeHints
    ]);
  }

  const seedTerms = buildSeedSpecificSearchTerms(context, profile, language);
  const distinctiveTags = getDistinctiveProfileTags(profile);
  const styleTerms = uniqueStrings([
    ...profile.rawGenres,
    ...profile.types,
    ...distinctiveTags,
    ...distinctiveTags.map((tag) => `${language.name === "不限" ? "" : language.name} ${tag}`),
    ...profile.types.map((type) => `${language.name === "不限" ? "" : language.name} ${type}`),
    ...profile.languages.map((name) => `${name} ${profile.types[0] || "歌曲"}`).filter(Boolean)
  ]);

  return uniqueStrings([
    ...personalizedTerms.slice(0, 10),
    ...seedTerms,
    ...styleTerms,
    ...language.queries.slice(0, 2),
    ...language.typeHints.slice(0, 2)
  ]);
}

function buildSeedSpecificSearchTerms(context, profile, language) {
  const seedTitles = uniqueStrings((context.seeds || []).map(extractSeedTitle).filter(Boolean));
  const seedArtistHints = uniqueStrings((context.seeds || []).map(extractSeedArtistHint).filter(Boolean));
  const profileArtists = uniqueStrings([...(profile.artists || []), ...seedArtistHints]);
  const relatedArtists = rotateList(relatedArtistsForProfile(profile), context.serial || 0);
  const types = uniqueStrings([...(profile.types || []), ...(language.typeHints || [])]).filter(Boolean).slice(0, 3);
  const primaryType = types[0] || (language.name === "不限" ? "流行" : language.name);

  return uniqueStrings([
    ...relatedArtists,
    ...relatedArtists.flatMap((artist) => [types.length ? `${artist} ${primaryType}` : artist, `${artist} 热门歌曲`]),
    ...profileArtists.flatMap((artist) => [`${artist} 同风格`, `${artist} 相似歌手`, `${artist} 推荐歌曲`]),
    ...seedTitles.flatMap((title) => [`${title} 同风格`, `${title} 相似歌曲`])
  ]);
}

function relatedArtistsForProfile(profile) {
  const artists = profile && Array.isArray(profile.artists) ? profile.artists : [];
  const related = [];

  artists.forEach((artist) => {
    RELATED_ARTIST_GROUPS.forEach((group) => {
      if (group.artists.some((item) => sameArtist(item, artist))) {
        related.push(...group.related);
      }
    });
  });

  return uniqueStrings(related).filter((artist) => !artists.some((current) => sameArtist(current, artist))).slice(0, 8);
}

function buildFamousArtistNameSet() {
  const names = [
    ...RELATED_ARTIST_GROUPS.flatMap((group) => [...(group.artists || []), ...(group.related || [])]),
    ...LANGUAGES.flatMap((language) => language.popularTerms || []),
    ...CHINESE_SONG_ARTIST_REFERENCES.flatMap((item) => item.artists || []),
    ...Object.entries(ARTIST_ALIASES).flatMap(([name, aliases]) => [name, ...(aliases || [])]),
    ...loadRuntimeFamousArtists()
  ];

  return new Set(uniqueStrings(names.flatMap(artistNameVariants)).map(normalizeArtistText).filter(Boolean));
}

function isFamousArtistName(artist) {
  return artistNameVariants(artist).some((name) => FAMOUS_ARTIST_NAMES.has(name));
}

function isFamousOtherArtistCandidate(song, profile = emptyProfile()) {
  if (!song || !song.artist) return false;
  if (isFamousArtistName(song.artist)) return true;
  return relatedArtistsForProfile(profile).some((artist) => sameArtist(song.artist, artist));
}

function addRuntimeFamousArtist(artist) {
  if (!isUsefulArtist(artist)) return;
  artistNameVariants(artist).forEach((name) => FAMOUS_ARTIST_NAMES.add(name));

  const stored = loadRuntimeFamousArtists();
  if (stored.some((item) => sameArtist(item, artist))) return;
  saveRuntimeFamousArtists([...stored, artist].slice(-120));
}

function loadRuntimeFamousArtists() {
  try {
    const parsed = JSON.parse(localStorage.getItem(RUNTIME_FAMOUS_ARTISTS_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter(isUsefulArtist) : [];
  } catch {
    return [];
  }
}

function saveRuntimeFamousArtists(artists) {
  try {
    localStorage.setItem(RUNTIME_FAMOUS_ARTISTS_KEY, JSON.stringify(uniqueStrings(artists).filter(isUsefulArtist)));
  } catch {
    // 本地知名歌手缓存失败不影响推荐。
  }
}

function emptyProfile() {
  return {
    types: [],
    rawGenres: [],
    tags: [],
    artists: [],
    artistSource: "",
    artistTrack: "",
    artistConfidence: 0,
    artistWeight: 0,
    languages: [],
    countries: []
  };
}

function formatSeedProfile(context) {
  const profile = context.seedProfile || emptyProfile();
  const languages = profile.languages.length ? profile.languages.join("、") : context.language;
  const types = profile.types.length ? profile.types.join("、") : "热门风格";
  const artistTrack = profile.artistTrack ? `《${profile.artistTrack}》` : "参考歌曲";
  const artistWeight = profile.artistWeight ? `；歌手权重 +${profile.artistWeight}` : "";
  const artistConfidence = profile.artistConfidence ? `，权威度 ${profile.artistConfidence}/100` : "";
  const artists = profile.artists.length ? `；原唱歌手 ${profile.artists[0]}（${profile.artistSource}：${artistTrack}${artistConfidence}）${artistWeight}；歌手栏至少 ${ARTIST_RECOMMENDATION_MIN} 首，其他歌手栏至少 ${OTHER_ARTIST_RECOMMENDATION_MIN} 首` : "";
  const tags = profile.tags.length ? `；标签 ${profile.tags.slice(0, 7).join("、")}` : "";
  return `已根据参考歌曲识别：语言 ${languages}；类型 ${types}${artists}${tags}`;
}

function getUsableSongs(songs, context) {
  const language = getLanguageConfig(context.language);
  const profile = context.seedProfile || emptyProfile();
  let usable = dedupeSongs(songs, context)
    .filter((song) => ALL_PROVIDERS.includes(sourceProvider(song)))
    .filter((song) => !isSameAsSeed(song, context.seeds))
    .filter((song) => artistMatchesProfile(profile, song) || languageMatchesSong(language, song))
    .filter((song) => {
      return isPopularCandidate(song)
        || (context.mode === "seed" && !artistMatchesProfile(profile, song) && isFamousOtherArtistCandidate(song, profile));
    });

  if (context.mode === "seed" && context.language === "不限" && profile.languages.length) {
    usable = usable.filter((song) => artistMatchesProfile(profile, song) || profile.languages.includes(song.language));
  }

  return usable;
}

function selectCachedSongs(context) {
  const language = getLanguageConfig(context.language);
  const profile = context.seedProfile || emptyProfile();
  const preferred = onlineSongPool.filter((song) => {
    const artistMatches = artistMatchesProfile(profile, song);
    const languageMatches = languageMatchesSong(language, song);
    const seedMatches = seedProfileMatchesSong(profile, song);
    if (context.mode === "seed") {
      return artistMatches || (languageMatches && seedMatches && cachedSongMatchesSeedContext(song, context));
    }
    return languageMatches && (seedMatches || profile.types.length === 0);
  });

  return context.mode === "seed" ? dedupeSongs(preferred, context) : dedupeSongs([...preferred, ...onlineSongPool], context);
}

function cachedSongMatchesSeedContext(song, context) {
  const profile = context.seedProfile || emptyProfile();
  if (artistMatchesProfile(profile, song)) return true;
  if (relatedArtistsForProfile(profile).some((artist) => sameArtist(song.artist, artist))) return true;
  if (getDistinctiveMatchedTags(profile, song).length >= 1) return true;

  const term = normalizeText(song.searchTerm || "");
  return buildSeedSpecificSearchTerms(context, profile, getLanguageConfig(context.language)).some((seedTerm) => {
    const normalizedTerm = normalizeText(seedTerm);
    return normalizedTerm && term && (term.includes(normalizedTerm) || normalizedTerm.includes(term));
  });
}

function getBackupTerms(context) {
  const language = getLanguageConfig(context.language);
  const profile = context.seedProfile || emptyProfile();
  const personalizedTerms = tasteSearchTerms(context);
  if (context.mode === "seed") {
    const distinctiveTags = getDistinctiveProfileTags(profile);
    const famousArtistTerms = getFamousOtherArtistFallbackTerms(context, profile, language);
    return uniqueStrings([
      ...buildSeedSpecificSearchTerms(context, profile, language),
      ...personalizedTerms.slice(0, 10),
      ...famousArtistTerms,
      ...profile.types,
      ...profile.rawGenres,
      ...distinctiveTags,
      ...profile.languages.map((name) => `${name} ${profile.types[0] || "歌曲"}`).filter(Boolean),
      ...language.queries.slice(0, 3),
      ...language.typeHints.slice(0, 2),
      language.name === "不限" ? "" : `${language.name} 流行`
    ]);
  }

  return uniqueStrings([
    ...personalizedTerms,
    ...profile.rawGenres,
    ...profile.types,
    ...profile.tags,
    ...profile.artists,
    ...profile.languages.map((name) => `${name} 热门`).filter(Boolean),
    ...profile.languages.flatMap((name) => getLanguageConfig(name).popularTerms || []),
    ...language.popularTerms,
    ...language.queries,
    ...language.typeHints,
    language.name === "不限" ? "" : `${language.name} 流行`,
    "热门歌曲",
    "经典歌曲",
    ...FALLBACK_TERMS
  ]);
}

function getFamousOtherArtistFallbackTerms(context, profile, language) {
  const relatedArtists = relatedArtistsForProfile(profile);
  const languageArtists = (language.popularTerms || []).filter((artist) => isFamousArtistName(artist));
  const storedArtists = loadRuntimeFamousArtists();
  const fallbackArtists = uniqueStrings([
    ...relatedArtists,
    ...languageArtists,
    ...storedArtists
  ]).filter((artist) => !(profile.artists || []).some((current) => sameArtist(current, artist)));

  return rotateList(fallbackArtists, context.serial || 0)
    .slice(0, 10)
    .flatMap((artist) => [artist, `${artist} 热门歌曲`, `${artist} 代表作`, `${artist} hits`]);
}

function markArtistSongs(songs, artist) {
  return dedupeSongs(songs, { seedProfile: { artists: [artist] } })
    .filter((song) => sameArtist(song.artist, artist))
    .map((song) => enrichSong({
      ...song,
      source: "artist",
      popularity: Math.max(Number(song.popularity) || 0, 78)
    }));
}

function hasArtistProfile(context) {
  const profile = context && context.seedProfile ? context.seedProfile : emptyProfile();
  return Boolean(context && context.mode === "seed" && profile.artists.length);
}

function artistMatchesProfile(profile, song) {
  return (profile.artists || []).some((artist) => sameArtist(song.artist, artist));
}

function sameArtist(a, b) {
  const leftVariants = artistNameVariants(a);
  const rightVariants = artistNameVariants(b);
  if (!leftVariants.length || !rightVariants.length) return false;

  return leftVariants.some((left) => {
    return rightVariants.some((right) => {
      if (left === right) return true;
      if (left.length < 2 || right.length < 2) return false;
      return left.includes(right) || right.includes(left);
    });
  });
}

function artistNameVariants(value) {
  const raw = String(value || "").trim();
  if (!raw) return [];

  const parts = raw
    .split(/\s*(?:\/|、|,|，|&|和|feat\.?|ft\.?)\s*/i)
    .map((part) => part.trim())
    .filter(Boolean);
  const values = uniqueStrings([raw, ...parts, ...artistAliasesFor(raw), ...parts.flatMap(artistAliasesFor)]);
  return uniqueStrings(values.map(normalizeArtistText)).filter(Boolean);
}

function artistAliasesFor(value) {
  const normalized = normalizeArtistText(value);
  const aliases = [];
  Object.entries(ARTIST_ALIASES).forEach(([name, items]) => {
    const allNames = [name, ...items];
    if (allNames.some((item) => normalizeArtistText(item) === normalized)) {
      aliases.push(...allNames);
    }
  });
  return aliases;
}

function normalizeArtistText(value) {
  return normalizeText(value).replace(/\s*(?:的|official|music)$\s*/i, "").trim();
}

function extractSeedTitle(seed) {
  const text = String(seed || "").trim();
  if (!text) return "";
  return text.split(/\s+(?:-|–|—|by|BY|By)\s+|\s*[|｜]\s+|\s*-\s*/g)[0].trim();
}

function extractSeedArtistHint(seed) {
  const text = String(seed || "").trim();
  const parts = text
    .split(/\s+(?:-|–|—|by|BY|By)\s+|\s*[|｜]\s+|\s*-\s*/g)
    .map((part) => part.trim())
    .filter(Boolean);
  return parts.length >= 2 ? parts[parts.length - 1] : "";
}

function scoreTitleMatch(query, title) {
  const left = normalizeText(query);
  const right = normalizeText(title);
  if (!left || !right) return 0;
  if (left === right) return 100;
  if (right.includes(left)) return 82;
  if (left.includes(right)) return 72;

  const leftTokens = left.split(" ").filter(Boolean);
  const rightTokens = new Set(right.split(" ").filter(Boolean));
  if (!leftTokens.length) return 0;
  const hits = leftTokens.filter((token) => rightTokens.has(token)).length;
  return (hits / leftTokens.length) * 64;
}

function isUsefulArtist(value) {
  const text = normalizeText(value);
  return text.length >= 2 && !/未知|unknown|various artists/.test(text);
}

function isPopularCandidate(song) {
  if (song.source === "chart") return true;
  if (song.source === "popular-search") return true;
  if (song.source === "artist") return true;
  if (DOMESTIC_PROVIDERS.includes(song.source)) return true;
  return (Number(song.platformPopularity) || Number(song.popularity) || 0) >= MIN_RECOMMENDATION_POPULARITY;
}

function sourceLabel(song) {
  if (song.source === "chart") return "热门榜单";
  if (song.source === "artist") return "原唱歌手";
  if (song.source === "popular-search") return "热门艺人";
  if (song.source === "netease") return "网易云音乐";
  if (song.source === "qq") return "QQ音乐";
  if (ALL_PROVIDERS.includes(song.source)) return providerName(sourceProvider(song));
  if (song.source === "search") return providerName(sourceProvider(song));
  return "高热度";
}

function sourceProvider(song) {
  if (song.provider) return song.provider;
  if (ALL_PROVIDERS.includes(song.source)) return song.source;
  if (song.country === "WY") return "netease";
  if (song.country === "QQ") return "qq";
  if (song.country === "YT") return "ytmusic";
  if (song.country === "SP") return "spotify";
  return "itunes";
}

function providerName(provider) {
  if (provider === "netease") return "网易云音乐";
  if (provider === "qq") return "QQ音乐";
  if (provider === "itunes") return "Apple Music";
  if (provider === "ytmusic") return "YouTube Music";
  if (provider === "spotify") return "Spotify";
  if (provider === "web") return WEB_ARTIST_SEARCH_PROVIDER;
  return provider || "在线音乐";
}

function providerPreferenceScore(provider, context) {
  if (isNeteasePreferredContext(context)) {
    return {
      netease: 66,
      qq: 60,
      ytmusic: 18,
      spotify: 12,
      itunes: -36
    }[provider] ?? 0;
  }

  const preference = inferPlatformPreference(context);
  if (preference === "chinese") {
    return {
      qq: 66,
      netease: 60,
      ytmusic: 18,
      spotify: 12,
      itunes: -36
    }[provider] ?? 0;
  }
  if (preference === "english") {
    return {
      itunes: 34,
      ytmusic: 28,
      spotify: 24,
      qq: -16,
      netease: -16
    }[provider] ?? 0;
  }

  const groupIndex = getProviderGroups(context).findIndex((group) => group.includes(provider));
  if (groupIndex === 0) return 18;
  if (groupIndex === 1) return 6;
  return 0;
}

function isPopularSearchTerm(term) {
  const text = String(term || "");
  return LANGUAGES.some((language) => (language.popularTerms || []).some((artist) => {
    return normalizeText(text).includes(normalizeText(artist)) || normalizeText(artist).includes(normalizeText(text));
  }));
}

function addToOnlinePool(songs) {
  onlineSongPool = dedupeSongs([...onlineSongPool, ...songs]).slice(0, 240);
  saveOnlinePool();
}

function platformMetricLabel(song) {
  const provider = providerName(sourceProvider(song));
  if (Number(song.playCount) > 0) return `${provider}播放 ${formatCompactNumber(song.playCount)}`;
  if (Number(song.favoriteCount) > 0) return `${provider}收藏 ${formatCompactNumber(song.favoriteCount)}`;
  if (Number(song.platformScore) > 0) return `${provider}热度 ${formatCompactNumber(song.platformScore)}`;
  if (Number(song.chartRank) > 0) return `${provider}榜单 #${song.chartRank}`;
  if (Number(song.searchRank) > 0) return `${provider}搜索 #${song.searchRank}`;
  return `${provider}热度 ${Math.round(normalizePlatformPopularity(song))}`;
}

function normalizePlatformPopularity(song) {
  const direct = Number(song.platformPopularity);
  if (direct > 0) return clampPopularity(direct);

  const playCount = Number(song.playCount);
  if (playCount > 0) return scoreLargeMetric(playCount, 52, 8);

  const favoriteCount = Number(song.favoriteCount);
  if (favoriteCount > 0) return scoreLargeMetric(favoriteCount, 54, 9);

  const platformScore = Number(song.platformScore);
  if (platformScore > 0) return scoreLargeMetric(platformScore, 56, 7);

  const chartRank = Number(song.chartRank);
  if (chartRank > 0) return clampPopularity(112 - chartRank);

  const searchRank = Number(song.searchRank);
  if (searchRank > 0) return clampPopularity(99 - searchRank * 3);

  return clampPopularity(Number(song.popularity) || 50);
}

function scoreLargeMetric(value, base, multiplier) {
  return clampPopularity(base + Math.log10(Number(value) + 1) * multiplier);
}

function clampPopularity(value) {
  return Math.max(40, Math.min(100, Math.round(Number(value) || 0)));
}

function formatCompactNumber(value) {
  const number = Number(value) || 0;
  if (number >= 100000000) return `${(number / 100000000).toFixed(number >= 1000000000 ? 1 : 2)}亿`;
  if (number >= 10000) return `${(number / 10000).toFixed(number >= 100000 ? 1 : 2)}万`;
  return String(Math.round(number));
}

function cancelActiveRequests() {
  // 本地代理请求使用超时控制；切换查询时通过 requestSerial 忽略旧响应。
}

async function fetchMany(terms, limit, desiredCount = TARGET_COUNT, serial = requestSerial, context = null, broadSearch = false) {
  if (serial !== requestSerial) return [];

  const countries = broadSearch ? uniqueStrings([...getSearchCountries(context), ...SEARCH_COUNTRIES]) : getSearchCountries(context);
  const termList = uniqueStrings(terms.map((term) => String(term || "").trim())).filter(Boolean).slice(0, context && context.mode === "seed" ? 16 : 10);
  const searchPlan = buildProviderSearchPlan(termList, countries, limit, context);

  const results = [];
  for (let index = 0; index < searchPlan.length; index += MAX_CONCURRENT_SEARCHES) {
    if (serial !== requestSerial) return [];

    const batch = searchPlan.slice(index, index + MAX_CONCURRENT_SEARCHES);
    const settled = await Promise.allSettled(batch.map(fetchProviderSearch));
    if (serial !== requestSerial) return [];

    results.push(...settled.flatMap((item) => (item.status === "fulfilled" ? item.value : [])));

    if (dedupeSongs(results, context).length >= desiredCount) {
      break;
    }
  }

  const uniqueResults = dedupeSongs(results, context);
  addToOnlinePool(uniqueResults);
  return uniqueResults;
}

function buildProviderSearchPlan(termList, countries, limit, context) {
  const providerOrder = getProviderOrder(context);
  const searchPlan = inferPlatformPreference(context) === "english"
    ? buildProviderMajorSearchPlan(providerOrder, termList, countries, limit)
    : buildTermMajorSearchPlan(providerOrder, termList, countries, limit);

  const primaryGroup = getProviderGroups(context)[0] || providerOrder.slice(0, 2);
  const primaryProviders = providerOrder
    .filter((provider) => primaryGroup.includes(provider))
    .slice(0, primaryGroup.length)
    .map(providerName)
    .join("、");
  setStatusText(`优先平台：${primaryProviders}`);
  return searchPlan;
}

function buildTermMajorSearchPlan(providerOrder, termList, countries, limit) {
  const searchPlan = [];

  termList.forEach((term, termIndex) => {
    providerOrder.forEach((provider) => {
      appendProviderSearchItems(searchPlan, provider, term, termIndex, countries, limit);
    });
  });

  return searchPlan;
}

function buildProviderMajorSearchPlan(providerOrder, termList, countries, limit) {
  const searchPlan = [];

  providerOrder.forEach((provider) => {
    termList.forEach((term, termIndex) => {
      appendProviderSearchItems(searchPlan, provider, term, termIndex, countries, limit);
    });
  });

  return searchPlan;
}

function appendProviderSearchItems(searchPlan, provider, term, termIndex, countries, limit) {
  if (provider === "itunes") {
    const countrySet = termIndex < 2 ? countries : countries.slice(0, 2);
    countrySet.forEach((country) => {
      searchPlan.push({ provider, term, country, limit });
    });
    return;
  }

  searchPlan.push({ provider, term, limit });
}

function getProviderOrder(context = null) {
  const preference = isNeteasePreferredContext(context) ? "chinese" : inferPlatformPreference(context);
  return getProviderGroups(context).flatMap((group) => {
    return [...group].sort((a, b) => {
      const defaultDelta = providerRankForContext(a, context) - providerRankForContext(b, context);
      if (preference === "chinese" && isChineseDomesticProvider(a) && isChineseDomesticProvider(b)) {
        return defaultDelta;
      }
      return providerNetworkScore(a) - providerNetworkScore(b) || defaultDelta;
    });
  });
}

function isChineseDomesticProvider(provider) {
  return provider === "qq" || provider === "netease";
}

function getDomesticProviderOrder(context = null) {
  const providers = [...DOMESTIC_PROVIDERS];
  return providers.sort((a, b) => providerRankForContext(a, context) - providerRankForContext(b, context));
}

function providerRankForContext(provider, context = null) {
  if (isNeteasePreferredContext(context) && isChineseDomesticProvider(provider)) {
    return provider === "netease" ? 0 : 1;
  }
  return providerDefaultRank(provider);
}

function getProviderGroups(context = null) {
  if (isNeteasePreferredContext(context)) return PROVIDER_GROUPS.chinese;
  const preference = inferPlatformPreference(context);
  return PROVIDER_GROUPS[preference] || PROVIDER_GROUPS.default;
}

function isNeteasePreferredContext(context = null) {
  if (!context) return false;

  const seedTexts = Array.isArray(context.seeds) ? context.seeds : [];
  const profile = context.seedProfile || {};
  const profileArtists = Array.isArray(profile.artists) ? profile.artists : [];
  const directTexts = [
    ...seedTexts,
    ...profileArtists,
    profile.artistSource,
    profile.artistTrack
  ];

  if (directTexts.some(isNeteasePreferredArtistText)) return true;

  return seedTexts.some((seed) => {
    const title = extractSeedTitle(seed);
    return findChineseFallbackArtists(title, seed).some(isNeteasePreferredArtistText);
  });
}

function isNeteasePreferredArtistText(value) {
  return NETEASE_FIRST_ARTISTS.some((artist) => sameArtist(value, artist));
}

function providerNetworkScore(provider) {
  const health = providerHealth.get(provider);
  if (!health) return providerDefaultRank(provider) * 100;
  const failurePenalty = health.failures > health.successes ? 5000 : health.failures * 900;
  const emptyPenalty = health.lastCount === 0 ? 700 : 0;
  return health.avgMs + failurePenalty + emptyPenalty + providerDefaultRank(provider) * 20;
}

function providerDefaultRank(provider) {
  return {
    qq: 0,
    netease: 1,
    itunes: 2,
    ytmusic: 3,
    spotify: 4
  }[provider] ?? 9;
}

function inferPlatformPreference(context = null) {
  if (isNeteasePreferredContext(context)) return "chinese";
  if (context && context.platformPreference) return context.platformPreference;
  const selectedLanguage = context && context.language ? context.language : currentLanguage;
  const seedText = context && Array.isArray(context.seeds) ? context.seeds.join(" ") : "";

  if (selectedLanguage === "华语") return "chinese";
  if (selectedLanguage === "英语") return "english";
  if (seedText && (hasHan(seedText) || hasChineseLanguageHint(seedText))) return "chinese";
  if (seedText && !hasCjkScript(seedText) && /[A-Za-z]/.test(seedText)) return "english";
  return "default";
}

function getSearchCountries(context) {
  if (!context) return SEARCH_COUNTRIES;
  const language = getLanguageConfig(context.language);
  const preference = inferPlatformPreference(context);
  if (language.name === "不限" && preference === "english") {
    return ["US", "GB", "CN", "JP", "KR"];
  }
  if (language.name === "不限" && preference === "chinese") {
    return ["CN", "US", "GB", "JP", "KR"];
  }
  return language.countries.length ? language.countries : SEARCH_COUNTRIES;
}

async function fetchProviderSearch(item) {
  const startedAt = performance.now();
  try {
    let songs;
    if (DOMESTIC_PROVIDERS.includes(item.provider)) {
      songs = await fetchDomestic(item.provider, item.term, item.limit);
    } else if (STREAMING_PROVIDERS.includes(item.provider)) {
      songs = await fetchStreaming(item.provider, item.term, item.limit);
    } else {
      songs = await fetchItunes(item.term, item.country, item.limit);
    }
    recordProviderHealth(item.provider, true, performance.now() - startedAt, songs.length);
    return songs;
  } catch {
    recordProviderHealth(item.provider, false, performance.now() - startedAt, 0);
    return [];
  }
}

function recordProviderHealth(provider, ok, elapsedMs, count) {
  const previous = providerHealth.get(provider) || {
    avgMs: elapsedMs,
    successes: 0,
    failures: 0,
    lastCount: 0
  };

  providerHealth.set(provider, {
    avgMs: Math.round(previous.avgMs * 0.65 + elapsedMs * 0.35),
    successes: previous.successes + (ok ? 1 : 0),
    failures: previous.failures + (ok ? 0 : 1),
    lastCount: count
  });
}

function fetchItunes(term, country, limit) {
  const cacheKey = `itunes|${normalizeText(term)}|${country}|${limit}`;
  const params = new URLSearchParams({
    term,
    country,
    limit: String(limit)
  });

  return fetchLocalJson(
    `/api/search/itunes?${params.toString()}`,
    cacheKey,
    (payload) => (payload.results || []).map((item, index) => mapItunesSong(item, country, term, index + 1)).filter(Boolean)
  );
}

function fetchDomestic(provider, term, limit) {
  const cacheKey = `domestic|${provider}|${normalizeText(term)}|${limit}`;
  const params = new URLSearchParams({
    provider,
    term,
    limit: String(limit)
  });

  return fetchLocalJson(
    `/api/search/domestic?${params.toString()}`,
    cacheKey,
    (payload) => (payload.songs || []).map((item) => mapDomesticSong(item, term)).filter(Boolean)
  );
}

function fetchStreaming(provider, term, limit) {
  const cacheKey = `streaming|${provider}|${normalizeText(term)}|${limit}`;
  const params = new URLSearchParams({
    provider,
    term,
    limit: String(limit)
  });

  return fetchLocalJson(
    `/api/search/streaming?${params.toString()}`,
    cacheKey,
    (payload) => (payload.songs || []).map((item) => mapStreamingSong(item, term)).filter(Boolean)
  );
}

async function fetchDomesticArtistSongs(artist, serial, context = null) {
  if (serial !== requestSerial) return [];
  const providerOrder = getDomesticProviderOrder(context || { seedProfile: { artists: [artist] } });
  const directPlan = providerOrder.map((provider) => ({ provider, artist }));
  const directResults = [];

  for (let index = 0; index < directPlan.length; index += MAX_CONCURRENT_SEARCHES) {
    if (serial !== requestSerial) return [];
    const batch = directPlan.slice(index, index + MAX_CONCURRENT_SEARCHES);
    const settled = await Promise.allSettled(batch.map((item) => fetchDomesticArtistProviderSongs(item.provider, item.artist, 40)));
    directResults.push(...settled.flatMap((item) => (item.status === "fulfilled" ? item.value : [])));
    if (markArtistSongs(directResults, artist).length >= ARTIST_RECOMMENDATION_TARGET + 4) {
      return markArtistSongs(directResults, artist);
    }
  }

  const terms = uniqueStrings([
    artist,
    `${artist} 热门歌曲`,
    `${artist} 代表作`,
    `${artist} 专辑`
  ]);
  const searchPlan = terms.flatMap((term) => providerOrder.map((provider) => ({ provider, term })));
  const results = [];

  for (let index = 0; index < searchPlan.length; index += MAX_CONCURRENT_SEARCHES) {
    if (serial !== requestSerial) return [];
    const batch = searchPlan.slice(index, index + MAX_CONCURRENT_SEARCHES);
    const settled = await Promise.allSettled(batch.map((item) => fetchDomestic(item.provider, item.term, 40)));
    results.push(...settled.flatMap((item) => (item.status === "fulfilled" ? item.value : [])));
    if (markArtistSongs(results, artist).length >= ARTIST_RECOMMENDATION_TARGET + 4) {
      break;
    }
  }

  return markArtistSongs(results, artist);
}

function fetchDomesticArtistProviderSongs(provider, artist, limit) {
  const cacheKey = `artist-songs|${provider}|${normalizeText(artist)}|${limit}`;
  const params = new URLSearchParams({
    provider,
    artist,
    limit: String(limit)
  });

  return fetchLocalJson(
    `/api/search/artist-songs?${params.toString()}`,
    cacheKey,
    (payload) => (payload.songs || []).map((item) => mapDomesticSong(item, artist)).filter(Boolean)
  );
}

function fetchItunesChart(country, limit) {
  const store = String(country || "US").toLowerCase();
  const cacheKey = `itunes-chart|${store}|${limit}`;
  const params = new URLSearchParams({
    country: store,
    limit: String(limit)
  });

  return fetchLocalJson(
    `/api/chart/itunes?${params.toString()}`,
    cacheKey,
    (payload) => {
      const entries = payload && payload.feed && payload.feed.entry
        ? Array.isArray(payload.feed.entry) ? payload.feed.entry : [payload.feed.entry]
        : [];
      return entries.map((entry, index) => mapItunesChartSong(entry, country, index + 1)).filter(Boolean);
    }
  );
}

async function fetchLocalJson(url, cacheKey, mapPayload, addMappedToPool = true) {
  if (searchCache.has(cacheKey)) {
    return searchCache.get(cacheKey);
  }

  let lastError = null;

  for (const targetUrl of localProxyUrls(url)) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch(targetUrl, { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`本地代理请求失败：${response.status}`);
      }
      rememberLocalProxyOrigin(targetUrl);
      const payload = await response.json();
      const mapped = mapPayload(payload);
      searchCache.set(cacheKey, mapped);
      if (addMappedToPool) {
        addToOnlinePool(mapped);
      }
      return mapped;
    } catch (error) {
      lastError = error;
      if (!shouldTryNextLocalProxy(url)) {
        throw error;
      }
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  throw lastError || new Error("本地代理请求失败");
}

function localProxyUrls(url) {
  if (!url.startsWith("/api/")) return [url];
  if (window.location.protocol === "file:") {
    const origins = resolvedLocalProxyOrigin
      ? [resolvedLocalProxyOrigin, ...LOCAL_PROXY_ORIGINS.filter((origin) => origin !== resolvedLocalProxyOrigin)]
      : LOCAL_PROXY_ORIGINS;
    return origins.map((origin) => `${origin}${url}`);
  }
  return [url];
}

function shouldTryNextLocalProxy(url) {
  return window.location.protocol === "file:" && url.startsWith("/api/");
}

function rememberLocalProxyOrigin(url) {
  if (window.location.protocol !== "file:") return;
  try {
    resolvedLocalProxyOrigin = new URL(url).origin;
  } catch {
    // 忽略无法解析的本地代理地址。
  }
}

function mapItunesSong(item, country, term, rank = null) {
  if (!item || item.wrapperType !== "track" || item.kind !== "song" || !item.trackId) return null;

  const rawGenre = item.primaryGenreName || "Pop";
  const type = classifyGenre(rawGenre);
  const releaseYear = item.releaseDate ? Number(String(item.releaseDate).slice(0, 4)) : null;
  const artwork = String(item.artworkUrl100 || "").replace("100x100", "300x300");

  return enrichSong({
    id: `${country}-${item.trackId}`,
    trackId: String(item.trackId),
    title: item.trackName || "未知歌曲",
    artist: item.artistName || "未知艺人",
    collection: item.collectionName || "",
    rawGenre,
    type,
    language: inferLanguage(country, `${term} ${rawGenre}`),
    country,
    releaseYear,
    artwork,
    sourceUrl: item.trackViewUrl || "",
    previewUrl: item.previewUrl || "",
    explicitness: item.trackExplicitness || "notExplicit",
    searchTerm: term,
    source: isPopularSearchTerm(term) ? "popular-search" : "search",
    searchRank: rank,
    popularity: isPopularSearchTerm(term) ? 76 : 58
  });
}

function mapItunesChartSong(entry, country, rank) {
  if (!entry) return null;
  const title = readFeedLabel(entry["im:name"]);
  const artist = readFeedLabel(entry["im:artist"]);
  if (!title || !artist) return null;

  const rawGenre = entry.category && entry.category.attributes
    ? entry.category.attributes.label || entry.category.attributes.term || "Pop"
    : "Pop";
  const type = classifyGenre(rawGenre);
  const imageList = Array.isArray(entry["im:image"]) ? entry["im:image"] : [];
  const image = imageList.length ? readFeedLabel(imageList[imageList.length - 1]) : "";
  const sourceLink = readFeedHref(entry.link, "alternate");
  const previewLink = readFeedHref(entry.link, "enclosure");
  const releaseDate = readFeedLabel(entry["im:releaseDate"]);
  const id = entry.id && entry.id.attributes ? entry.id.attributes["im:id"] : `${country}-${rank}-${title}`;
  const text = `${title} ${artist} ${rawGenre}`;

  return enrichSong({
    id: `chart-${country}-${id}`,
    trackId: String(id),
    title,
    artist,
    collection: entry["im:collection"] ? readFeedLabel(entry["im:collection"]["im:name"]) : "",
    rawGenre,
    type,
    language: inferLanguage(country, text),
    country,
    releaseYear: releaseDate ? Number(String(releaseDate).slice(0, 4)) || null : null,
    artwork: image,
    sourceUrl: sourceLink,
    previewUrl: previewLink,
    explicitness: "notExplicit",
    searchTerm: `${country} top songs`,
    source: "chart",
    chartRank: rank,
    popularity: Math.max(70, 115 - rank)
  });
}

function mapDomesticSong(item, term) {
  if (!item || !item.trackId || !item.title || !item.artist) return null;
  const provider = item.provider || "domestic";
  const rawGenre = item.rawGenre || "华语流行";
  const type = classifyGenre(`${rawGenre} ${term} ${item.title} ${item.artist}`);

  return enrichSong({
    id: `${provider}-${item.trackId}`,
    trackId: String(item.trackId),
    title: item.title,
    artist: item.artist,
    collection: item.collection || "",
    rawGenre,
    type,
    language: inferLanguage("CN", `${term} ${item.title} ${item.artist} ${rawGenre}`),
    country: provider === "qq" ? "QQ" : "WY",
    releaseYear: null,
    artwork: item.artwork || "",
    sourceUrl: item.sourceUrl || "",
    previewUrl: item.previewUrl || "",
    explicitness: "notExplicit",
    searchTerm: term,
    provider,
    providerName: item.providerName || providerName(provider),
    source: provider,
    searchRank: Number(item.rank) || null,
    playCount: Number(item.playCount) || null,
    favoriteCount: Number(item.favoriteCount) || null,
    platformScore: Number(item.platformScore) || null,
    popularity: Number(item.popularity) || (isPopularSearchTerm(term) ? 82 : 74)
  });
}

function mapStreamingSong(item, term) {
  if (!item || !item.trackId || !item.title || !item.artist) return null;
  const provider = item.provider || "streaming";
  const rawGenre = item.rawGenre || (provider === "ytmusic" ? "Music" : "Pop");
  const type = classifyGenre(`${rawGenre} ${term} ${item.title} ${item.artist}`);

  return enrichSong({
    id: `${provider}-${item.trackId}`,
    trackId: String(item.trackId),
    title: item.title,
    artist: item.artist,
    collection: item.collection || "",
    rawGenre,
    type,
    language: inferLanguage(provider === "ytmusic" ? "US" : "GB", `${term} ${item.title} ${item.artist} ${rawGenre}`),
    country: provider === "ytmusic" ? "YT" : "SP",
    releaseYear: item.releaseYear || null,
    artwork: item.artwork || "",
    sourceUrl: item.sourceUrl || "",
    previewUrl: item.previewUrl || "",
    explicitness: item.explicitness || "notExplicit",
    searchTerm: term,
    provider,
    providerName: item.providerName || providerName(provider),
    source: provider,
    searchRank: Number(item.rank) || null,
    playCount: Number(item.playCount) || null,
    favoriteCount: Number(item.favoriteCount) || null,
    platformScore: Number(item.platformScore) || Number(item.popularity) || null,
    popularity: Number(item.popularity) || (isPopularSearchTerm(term) ? 82 : 72)
  });
}

function enrichSong(song) {
  const platformPopularity = normalizePlatformPopularity(song);
  const metricLabel = song.platformMetricLabel || platformMetricLabel({ ...song, platformPopularity });
  const enriched = {
    ...song,
    platformPopularity,
    platformMetricLabel: metricLabel
  };

  return {
    ...enriched,
    tags: buildSongTags(enriched)
  };
}

function buildSongTags(song) {
  const text = normalizeText(songText(song));
  const tags = [
    song.language,
    song.type,
    song.rawGenre
  ];

  if ((Number(song.platformPopularity) || Number(song.popularity) || 0) >= 95) tags.push("高热度");
  if ((Number(song.platformPopularity) || Number(song.popularity) || 0) >= 80) tags.push("热门");
  if (song.releaseYear && song.releaseYear >= 2023) tags.push("新歌");
  if (song.releaseYear && song.releaseYear < 2015) tags.push("经典");

  if (song.type === "摇滚") tags.push("高能", "乐队", "吉他", "运动");
  if (song.type === "电子") tags.push("高能", "节奏", "舞曲", "运动");
  if (song.type === "说唱") tags.push("节奏", "低音", "街头");
  if (song.type === "R&B") tags.push("律动", "柔和", "人声");
  if (song.type === "民谣") tags.push("原声", "叙事", "舒缓", "通勤");
  if (song.type === "轻音乐") tags.push("安静", "学习", "睡前", "钢琴");
  if (song.type === "爵士") tags.push("松弛", "夜晚", "律动");
  if (song.type === "日韩流行") tags.push("偶像", "旋律", "流行");
  if (song.type === "流行") tags.push("人声", "旋律", "热门");

  if (/love|romantic|情歌|爱情|告白|恋|心动/.test(text)) tags.push("爱情", "情歌");
  if (/sad|breakup|失恋|伤感|lonely|alone|眼泪|雨/.test(text)) tags.push("伤感", "低沉");
  if (/summer|dance|party|club|夜店|派对/.test(text)) tags.push("派对", "明亮");
  if (/piano|钢琴/.test(text)) tags.push("钢琴", "安静");
  if (/acoustic|unplugged|原声|木吉他/.test(text)) tags.push("原声", "舒缓");
  if (/anime|动画|映画|ost|soundtrack|主题曲/.test(text)) tags.push("OST", "影视");

  return cleanRecommendationTags(tags).slice(0, 18);
}

function readFeedLabel(value) {
  return value && typeof value === "object" && "label" in value ? String(value.label || "") : "";
}

function readFeedHref(links, rel) {
  const list = Array.isArray(links) ? links : links ? [links] : [];
  const match = list.find((link) => link && link.attributes && link.attributes.rel === rel);
  return match && match.attributes ? String(match.attributes.href || "") : "";
}

function rankAndLimit(songs, context) {
  const language = getLanguageConfig(context.language);
  const profile = context.seedProfile || emptyProfile();
  const personalProfile = normalizeTasteProfile(context.tasteProfile || tasteProfile);
  const personalSettings = normalizeTasteSettings(context.tasteSettings || tasteSettings);
  const isSeedMode = context.mode === "seed";

  const scored = dedupeSongs(songs, context).map((song) => {
    let score = 24;
    const selectedLanguageMatch = languageMatchesSong(language, song);
    const seedLanguageMatch = profile.languages.includes(song.language) || profile.countries.includes(song.country);
    const typeMatch = profile.types.includes(song.type);
    const rawGenreMatch = profile.rawGenres.includes(song.rawGenre);
    const languageStyleHint = language.typeHints.includes(song.type);
    const popularity = Number(song.platformPopularity) || Number(song.popularity) || 45;
    const seedMatch = seedProfileMatchesSong(profile, song);
    const matchedTags = getMatchedTags(profile, song);
    const tagScore = matchedTags.reduce((sum, tag) => sum + (TAG_WEIGHTS[tag] || 4), 0);
    const artistMatch = artistMatchesProfile(profile, song);
    const artistWeight = isSeedMode && artistMatch ? ARTIST_MATCH_WEIGHT : 0;
    const personalScore = tasteAffinityScore(song, personalProfile, personalSettings);
    const moodScore = moodAffinityScore(song, personalSettings.mood);
    const blockedPenalty = personalProfile.blockedKeys.includes(songIdentityKey(song)) ? 180 : 0;
    const likedBonus = personalProfile.likedKeys.includes(songIdentityKey(song)) ? 36 : 0;
    const popularityPreference = (personalSettings.popularity - 50) * 0.28;
    const noveltyPreference = (personalSettings.novelty - 50) * 0.22;

    score += popularity * (isSeedMode ? 0.82 : 0.92);
    score += popularity * popularityPreference / 10;
    score += noveltyPreferenceForSong(song, noveltyPreference, personalProfile);
    if (song.source === "chart") score += isSeedMode ? 10 : 24;
    score += providerPreferenceScore(sourceProvider(song), context);
    score += personalScore + moodScore + likedBonus - blockedPenalty;
    if (selectedLanguageMatch) score += language.name === "不限" ? 6 : 42;
    if (seedLanguageMatch) score += isSeedMode ? 42 : 22;
    if (typeMatch) score += isSeedMode ? 58 : 34;
    if (rawGenreMatch) score += isSeedMode ? 30 : 18;
    if (tagScore) score += isSeedMode ? tagScore * 1.35 : tagScore;
    if (artistWeight) score += artistWeight;
    if (isSeedMode && seedMatch) score += 28;
    if (isSeedMode && !seedMatch) score -= 60;
    if (languageStyleHint) score += 12;
    if (song.explicitness === "explicit") score -= 14;
    if (song.releaseYear && song.releaseYear >= 2020) score += 4;

    return {
      ...song,
      score,
      matchedTags,
      artistWeight,
      personalScore,
      reason: buildReason(song, context, typeMatch || rawGenreMatch || matchedTags.length > 0 || personalScore > 10 || moodScore > 8, selectedLanguageMatch, artistMatch)
    };
  });

  const sorted = sortByPlatformPopularity(scored, context);
  let selected;
  if (hasArtistProfile(context)) {
    selected = diversifyRecommendationsWithArtistQuota(sorted, profile, context);
  } else {
    selected = diversifyRecommendations(sorted, context);
  }
  return enforcePlatformBalance(selected, sorted, context);
}

function languageMatchesSong(language, song) {
  if (language.name === "不限") return true;
  if (language.name === "纯音乐") return song.language === "纯音乐" || song.type === "轻音乐";
  if (language.name === "华语") return song.language === "华语" && isChineseSong(song);
  if (language.name === "英语") return song.language === "英语" && !hasCjkScript(songText(song));
  if (language.name === "日语") return song.language === "日语" && (hasJapaneseScript(songText(song)) || hasJapaneseLanguageHint(song.searchTerm));
  if (language.name === "韩语") return song.language === "韩语" && (hasHangul(songText(song)) || hasKoreanLanguageHint(song.searchTerm));
  return song.language === language.name;
}

function seedProfileMatchesSong(profile, song) {
  const hasTypeProfile = profile.types.length > 0 || profile.rawGenres.length > 0;
  const hasLanguageProfile = profile.languages.length > 0 || profile.countries.length > 0;
  const hasTagProfile = profile.tags.length > 0;
  const typeMatches = profile.types.includes(song.type) || profile.rawGenres.includes(song.rawGenre);
  const languageMatches = profile.languages.includes(song.language) || profile.countries.includes(song.country);
  const tagMatches = getMatchedTags(profile, song).length;
  const distinctiveTagMatches = getDistinctiveMatchedTags(profile, song).length;
  const artistMatches = artistMatchesProfile(profile, song);

  if (artistMatches) return true;
  if (distinctiveTagMatches >= 1 && languageMatches) return true;
  if (hasTypeProfile && hasLanguageProfile) return languageMatches && (typeMatches || tagMatches >= 1);
  if (hasTypeProfile) return typeMatches;
  if (hasTagProfile) return tagMatches >= 2;
  if (hasLanguageProfile) return languageMatches;
  return true;
}

function getMatchedTags(profile, song) {
  const profileTags = new Set([
    ...cleanRecommendationTags(profile.tags),
    ...profile.types,
    ...profile.rawGenres,
    ...profile.languages
  ]);
  return cleanRecommendationTags(song.tags || []).filter((tag) => profileTags.has(tag));
}

function getDistinctiveMatchedTags(profile, song) {
  const distinctiveTags = new Set(getDistinctiveProfileTags(profile));
  return cleanRecommendationTags(song.tags || []).filter((tag) => distinctiveTags.has(tag));
}

function getDistinctiveProfileTags(profile) {
  return cleanRecommendationTags([
    ...(profile.tags || []),
    ...(profile.types || []),
    ...(profile.rawGenres || [])
  ]).filter((tag) => !GENERIC_PROFILE_TAGS.has(tag));
}

function sortByPlatformPopularity(items, context = null) {
  return [...items].sort((a, b) => compareByPlatformPopularity(a, b, context));
}

function compareByPlatformPopularity(a, b, context = null) {
  const providerDelta = providerPriorityRank(sourceProvider(a), context) - providerPriorityRank(sourceProvider(b), context);
  if (providerDelta) return providerDelta;
  const heatDelta = (Number(b.platformPopularity) || 0) - (Number(a.platformPopularity) || 0);
  if (heatDelta) return heatDelta;
  const scoreDelta = (Number(b.score) || 0) - (Number(a.score) || 0);
  if (scoreDelta) return scoreDelta;
  return String(a.title || "").localeCompare(String(b.title || ""), "zh-CN");
}

function providerPriorityRank(provider, context = null) {
  const order = getProviderOrder(context);
  const index = order.indexOf(provider);
  return index >= 0 ? index : 99;
}

function diversifyRecommendations(items, context = null) {
  return selectDiverseSongs(items, TARGET_COUNT, context);
}

function diversifyRecommendationsWithArtistQuota(items, profile, context = null) {
  const artistItems = sortByPlatformPopularity(items.filter((item) => artistMatchesProfile(profile, item)), context);
  const otherItems = sortByPlatformPopularity(
    items.filter((item) => !artistMatchesProfile(profile, item) && isFamousOtherArtistCandidate(item, profile)),
    context
  );
  const otherOptions = {
    allowArtistRepeats: false,
    requireHighPopularity: true,
    allowFamousLowPopularityFallback: true,
    avoidRecentSongs: true,
    recentSongKeys: recentOtherArtistSongKeySet(),
    targetLanguage: seedTargetLanguage(context),
    explorationJitter: true
  };
  const eligibleOtherItems = filterDiverseEligibleSongs(otherItems, OTHER_ARTIST_RECOMMENDATION_MIN, otherOptions);
  const requiredOther = Math.min(OTHER_ARTIST_RECOMMENDATION_MIN, eligibleOtherItems.length);
  const maxArtistCount = Math.min(artistItems.length, TARGET_COUNT - requiredOther);
  const requiredArtist = Math.min(ARTIST_RECOMMENDATION_MIN, maxArtistCount);
  const artistCount = Math.max(requiredArtist, Math.min(ARTIST_RECOMMENDATION_TARGET, maxArtistCount));
  const otherCount = Math.min(TARGET_COUNT - artistCount, eligibleOtherItems.length);
  const selectedArtist = artistItems.slice(0, artistCount);
  const selectedOther = selectDiverseSongs(eligibleOtherItems, otherCount, context, otherOptions);
  const selectedKeys = new Set([...selectedArtist, ...selectedOther].map(songIdentityKey));
  const remaining = sortByPlatformPopularity(
    [...artistItems, ...eligibleOtherItems].filter((item) => !selectedKeys.has(songIdentityKey(item))),
    context
  ).slice(0, TARGET_COUNT - selectedKeys.size);

  return [...selectedArtist, ...selectedOther, ...remaining].slice(0, TARGET_COUNT);
}

function selectDiverseSongs(items, count, context = null, options = {}) {
  const selected = [];
  const eligibleItems = filterDiverseEligibleSongs(items, count, options);
  const remaining = sortByPlatformPopularity(eligibleItems, context);
  const allowArtistRepeats = Boolean(options.allowArtistRepeats);
  const profile = context && context.seedProfile ? context.seedProfile : emptyProfile();

  while (selected.length < count && remaining.length) {
    let bestIndex = 0;
    let bestScore = -Infinity;

    remaining.forEach((item, index) => {
      const artistRepeats = selected.filter((song) => sameArtist(song.artist, item.artist)).length;
      const typeRepeats = selected.filter((song) => song.type === item.type).length;
      const providerRepeats = selected.filter((song) => sourceProvider(song) === sourceProvider(item)).length;
      const searchTermRepeats = selected.filter((song) => normalizeText(song.searchTerm) === normalizeText(item.searchTerm)).length;
      const languageRepeats = selected.filter((song) => song.language === item.language).length;
      const sharedTags = selected.reduce((sum, song) => sum + tagIntersection(song.tags || [], item.tags || []).length, 0);
      const adjustedScore = item.score
        + seedSpecificAffinity(item, profile, context)
        + popularityEvidenceScore(item) * 1.05
        + explorationJitterScore(item, context, options)
        + (Number(item.favoriteCount) > 0 ? 10 : 0)
        - (options.requireHighPopularity && !isHighPopularityCandidate(item) ? 72 : 0)
        - (isRecentOtherArtistSong(item, options) ? OTHER_ARTIST_RECENT_REPEAT_PENALTY : 0)
        - (allowArtistRepeats ? Math.max(0, artistRepeats - 1) * 28 : artistRepeats * 120)
        - Math.max(0, typeRepeats - 1) * 18
        - Math.max(0, providerRepeats - 2) * 10
        - searchTermRepeats * 24
        - Math.max(0, languageRepeats - 6) * 5
        - Math.max(0, sharedTags - 6) * 2.2;

      if (adjustedScore > bestScore) {
        bestScore = adjustedScore;
        bestIndex = index;
      }
    });

    selected.push(remaining.splice(bestIndex, 1)[0]);
  }

  return selected;
}

function filterDiverseEligibleSongs(items, count, options = {}) {
  let eligible = [...items];
  if (options.targetLanguage) {
    const sameLanguage = eligible.filter((song) => song.language === options.targetLanguage);
    eligible = sameLanguage;
  }

  if (options.avoidRecentSongs) {
    const fresh = eligible.filter((song) => !isRecentOtherArtistSong(song, options));
    const requiredCount = Math.max(1, Number(count) || 1);
    if (fresh.length >= requiredCount) {
      eligible = fresh;
    }
  }

  if (options.requireHighPopularity) {
    const highPopularity = eligible.filter(isHighPopularityCandidate);
    const requiredCount = Math.max(1, Number(count) || 1);
    if (highPopularity.length >= requiredCount || !options.allowFamousLowPopularityFallback) {
      eligible = highPopularity;
    }
  }

  return eligible;
}

function isRecentOtherArtistSong(song, options = {}) {
  const recentSongKeys = options.recentSongKeys;
  return Boolean(recentSongKeys && recentSongKeys.has(songIdentityKey(song)));
}

function isHighPopularityCandidate(song) {
  if (song.source === "artist") return true;
  return popularityEvidenceScore(song) >= MIN_OTHER_ARTIST_POPULARITY;
}

function popularityEvidenceScore(song) {
  const favoriteCount = Number(song.favoriteCount);
  if (favoriteCount > 0) return Math.min(100, normalizePlatformPopularity(song) + 6);

  const playCount = Number(song.playCount);
  if (playCount > 0) return normalizePlatformPopularity(song);

  const platformScore = Number(song.platformScore);
  if (platformScore > 0) return normalizePlatformPopularity(song);

  const chartRank = Number(song.chartRank);
  if (chartRank > 0) return normalizePlatformPopularity(song);

  const searchRank = Number(song.searchRank);
  if (searchRank > 0) return normalizePlatformPopularity(song);

  return Number(song.platformPopularity) || Number(song.popularity) || 0;
}

function seedTargetLanguage(context = null) {
  const profile = context && context.seedProfile ? context.seedProfile : emptyProfile();
  return profile.languages && profile.languages.length === 1 ? profile.languages[0] : "";
}

function seedSpecificAffinity(song, profile, context = null) {
  if (!context || context.mode !== "seed") return 0;

  let score = getDistinctiveMatchedTags(profile, song).length * 18;
  if (relatedArtistsForProfile(profile).some((artist) => sameArtist(song.artist, artist))) score += 32;
  if (artistMatchesProfile(profile, song)) score += 18;
  if (isGenericSearchTerm(song.searchTerm, context)) score -= 18;
  return score;
}

function tasteAffinityScore(song, profile, settings) {
  const tags = cleanRecommendationTags([...(song.tags || []), song.rawGenre, song.type, song.language]);
  let score = 0;
  score += weightedTasteValue(profile.languages, song.language) * 0.56;
  score += weightedTasteValue(profile.types, song.type) * 0.72;
  score += weightedTasteValue(profile.tags, song.rawGenre) * 0.48;
  score += weightedTasteValue(profile.artists, song.artist) * 0.86;
  score += weightedTasteValue(profile.providers, sourceProvider(song)) * 0.35;
  tags.forEach((tag) => {
    score += weightedTasteValue(profile.tags, tag) * 0.32;
  });

  const exploration = Math.max(0, Number(settings.novelty) - 50);
  if (exploration > 0 && weightedTasteValue(profile.artists, song.artist) <= 0) {
    score += exploration * 0.16;
  }
  return Math.max(-140, Math.min(160, score));
}

function weightedTasteValue(map, key) {
  const label = String(key || "").trim();
  return label ? Number((map || {})[label]) || 0 : 0;
}

function moodAffinityScore(song, moodName) {
  const mood = MOOD_PRESETS[moodName] || MOOD_PRESETS.auto;
  if (!mood.tags.length && !mood.types.length) return 0;
  const tags = new Set(cleanRecommendationTags([...(song.tags || []), song.rawGenre, song.type]));
  const tagHits = mood.tags.filter((tag) => tags.has(tag)).length;
  const typeHits = mood.types.includes(song.type) ? 1 : 0;
  return tagHits * 9 + typeHits * 14;
}

function noveltyPreferenceForSong(song, noveltyPreference, profile) {
  if (!noveltyPreference) return 0;
  const year = Number(song.releaseYear) || 0;
  const recentBonus = year >= 2023 ? 16 : year >= 2020 ? 8 : year && year < 2015 ? -6 : 0;
  const knownArtistPenalty = weightedTasteValue(profile.artists, song.artist) > 35 ? -8 : 4;
  return noveltyPreference * (recentBonus + knownArtistPenalty) / 10;
}

function explorationJitterScore(song, context = null, options = {}) {
  if (!options.explorationJitter || !context || context.mode !== "seed") return 0;
  const serial = Number(context.serial) || 0;
  const hash = stableHash(`${songIdentityKey(song)}|${serial}`);
  return (hash % (OTHER_ARTIST_EXPLORATION_WEIGHT + 1)) - Math.floor(OTHER_ARTIST_EXPLORATION_WEIGHT / 2);
}

function isGenericSearchTerm(term, context = null) {
  const normalized = normalizeText(term);
  if (!normalized) return false;
  const language = getLanguageConfig(context && context.language ? context.language : currentLanguage);
  const genericTerms = [
    ...GENERIC_PROFILE_TAGS,
    ...language.queries,
    ...language.typeHints,
    ...language.popularTerms,
    "热门歌曲",
    "经典歌曲",
    "top songs",
    "new music",
    "pop hits"
  ];
  return genericTerms.some((item) => normalizeText(item) === normalized);
}

function enforcePlatformBalance(selected, pool, context = null) {
  if (inferPlatformPreference(context) !== "chinese") return selected;

  const balanced = [...selected];
  const selectedKeys = new Set(balanced.map(songIdentityKey));
  let replacements = pool
    .filter((song) => !selectedKeys.has(songIdentityKey(song)))
    .filter((song) => isRequiredChineseProvider(sourceProvider(song)));

  for (let index = balanced.length - 1; index >= 0 && countProvider(balanced, "itunes") > CHINESE_PROVIDER_ITUNES_MAX; index -= 1) {
    const current = balanced[index];
    if (sourceProvider(current) !== "itunes") continue;

    const replacementIndex = findPlatformReplacementIndex(replacements, current, context);
    if (replacementIndex < 0) continue;

    const [replacement] = replacements.splice(replacementIndex, 1);
    selectedKeys.delete(songIdentityKey(current));
    selectedKeys.add(songIdentityKey(replacement));
    balanced[index] = replacement;
  }

  return balanced.slice(0, TARGET_COUNT);
}

function findPlatformReplacementIndex(replacements, current, context) {
  if (!replacements.length) return -1;
  const profile = context && context.seedProfile ? context.seedProfile : emptyProfile();
  const currentIsArtistSong = hasArtistProfile(context) && artistMatchesProfile(profile, current);
  if (!currentIsArtistSong) return 0;
  const artistReplacementIndex = replacements.findIndex((song) => artistMatchesProfile(profile, song));
  return artistReplacementIndex >= 0 ? artistReplacementIndex : 0;
}

function countProvider(songs, provider) {
  return songs.filter((song) => sourceProvider(song) === provider).length;
}

function uniqueArtistCount(songs) {
  const artists = [];
  songs.forEach((song) => {
    if (!artists.some((artist) => sameArtist(artist, song.artist))) {
      artists.push(song.artist);
    }
  });
  return artists.filter(Boolean).length;
}

function rememberRecentOtherArtistRecommendations(songs, context) {
  if (!hasArtistProfile(context)) return;
  const profile = context.seedProfile || emptyProfile();
  const keys = uniqueStrings(
    songs
      .filter((song) => !artistMatchesProfile(profile, song) && isFamousOtherArtistCandidate(song, profile))
      .map(songIdentityKey)
  );
  if (!keys.length) return;

  const history = loadRecentOtherArtistHistory();
  saveRecentOtherArtistHistory([...history, keys].slice(-OTHER_ARTIST_HISTORY_LIMIT));
}

function recentOtherArtistSongKeySet() {
  return new Set(loadRecentOtherArtistHistory().flat());
}

function loadRecentOtherArtistHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(OTHER_ARTIST_HISTORY_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(Array.isArray)
      .map((entry) => uniqueStrings(entry).filter(Boolean))
      .filter((entry) => entry.length)
      .slice(-OTHER_ARTIST_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

function saveRecentOtherArtistHistory(history) {
  try {
    localStorage.setItem(OTHER_ARTIST_HISTORY_KEY, JSON.stringify(history.slice(-OTHER_ARTIST_HISTORY_LIMIT)));
  } catch {
    // 最近推荐历史只用于增强多样性，写入失败不影响推荐。
  }
}

function rotateList(values, offset) {
  const list = [...values];
  if (!list.length) return list;
  const index = Math.abs(Number(offset) || 0) % list.length;
  return [...list.slice(index), ...list.slice(0, index)];
}

function stableHash(value) {
  let hash = 0;
  const text = String(value || "");
  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash + text.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

function songIdentityKey(song) {
  return normalizeText(`${song.title}-${song.artist}-${sourceProvider(song)}-${song.trackId || song.id || ""}`);
}

function tagIntersection(a, b) {
  const set = new Set(cleanRecommendationTags(b));
  return cleanRecommendationTags(a).filter((tag) => set.has(tag));
}

function cleanRecommendationTags(tags) {
  return uniqueStrings(tags).filter(isRecommendationTag);
}

function isRecommendationTag(tag) {
  const value = String(tag || "").trim();
  if (!value) return false;
  const nonMusicTags = new Set([
    "Apple Music",
    "网易云音乐",
    "网易云",
    "QQ音乐",
    "YouTube Music",
    "Spotify",
    "在线音乐",
    "热门榜单",
    "热门艺人",
    "原唱歌手",
    "中国区",
    "美国区",
    "日本区",
    "韩国区",
    "英国区"
  ]);
  return !nonMusicTags.has(value);
}

function buildReason(song, context, typeMatchesSeed, languageMatches, artistMatch) {
  if (context.mode === "seed" && artistMatch) {
    return `来自参考歌曲原唱歌手 ${escapeReasonArtist(song.artist)} 的热门作品，歌手权重 +${ARTIST_MATCH_WEIGHT}，并继续匹配当前语言与风格画像。`;
  }
  if (Number(song.personalScore) > 18) {
    const personalTags = topPersonalMatches(song, context).slice(0, 3).join("、");
    return personalTags
      ? `根据你的历史反馈上调：匹配 ${personalTags}，同时兼顾当前语言与热度。`
      : `根据你的历史反馈上调，并兼顾当前语言、风格与热度。`;
  }
  if (context.mode === "seed" && typeMatchesSeed) {
    const profileTypes = (context.seedProfile.types || []).slice(0, 3).join("、") || song.type;
    const matched = (song.matchedTags || []).slice(0, 5).join("、");
    return matched
      ? `根据参考歌曲识别出的风格：${profileTypes}；匹配标签：${matched}。`
      : `根据参考歌曲识别出的风格：${profileTypes}，匹配到${song.type}类型。`;
  }
  if (languageMatches && context.language !== "不限") {
    return `匹配所选语言：${context.language}，类型为${song.type}。`;
  }
  return `根据在线曲库的语言与风格标签推荐，类型为${song.type}。`;
}

function topPersonalMatches(song, context) {
  const profile = normalizeTasteProfile(context.tasteProfile || tasteProfile);
  return uniqueStrings([
    song.language,
    song.type,
    song.rawGenre,
    song.artist,
    ...cleanRecommendationTags(song.tags || [])
  ]).filter((item) => {
    return weightedTasteValue(profile.languages, item) > 0
      || weightedTasteValue(profile.types, item) > 0
      || weightedTasteValue(profile.tags, item) > 0
      || weightedTasteValue(profile.artists, item) > 0;
  });
}

function escapeReasonArtist(value) {
  return String(value || "该歌手");
}

function renderRecommendations(songs, context) {
  renderedSongMap.clear();
  songs.forEach((song) => renderedSongMap.set(songIdentityKey(song), song));
  elements.resultTitle.textContent = context.title;
  elements.resultCount.textContent = `${songs.length} / ${TARGET_COUNT}`;
  const profile = context.seedProfile || emptyProfile();
  const hasArtist = hasArtistProfile(context);
  const artistSongs = hasArtist ? songs.filter((song) => artistMatchesProfile(profile, song)) : [];
  const otherSongs = hasArtist ? songs.filter((song) => !artistMatchesProfile(profile, song)) : [];
  setStatusText(hasArtist
    ? `原唱歌手 ${artistSongs.length} 首，其他歌手 ${otherSongs.length} 首`
    : songs.length === TARGET_COUNT ? "热门推荐完成" : "热门结果不足 10 首");

  if (songs.length === 0) {
    elements.recommendationList.innerHTML = `<div class="empty-state">没有找到可推荐歌曲，请换一种语言或输入其他参考歌曲。</div>`;
    animateMessageState();
    return;
  }

  if (hasArtist) {
    elements.recommendationList.innerHTML = renderRecommendationColumns(artistSongs, otherSongs, context);
    setupRecommendationDecks();
    animateRecommendationResults();
    return;
  }

  elements.recommendationList.innerHTML = songs.map((song, index) => renderSongCard(song, index + 1, context)).join("");
  setupRecommendationDecks();
  animateRecommendationResults();
}

function renderRecommendationColumns(artistSongs, otherSongs, context) {
  const artistName = (context.seedProfile.artists || [])[0] || "原唱歌手";
  return `
    <div class="recommendation-columns">
      ${renderRecommendationColumn(`${artistName} 的歌`, `至少 ${ARTIST_RECOMMENDATION_MIN} 首`, artistSongs, context)}
      ${renderRecommendationColumn("其他歌手的歌", `至少 ${OTHER_ARTIST_RECOMMENDATION_MIN} 首`, otherSongs, context)}
    </div>
  `;
}

function renderRecommendationColumn(title, targetText, songs, context) {
  return `
    <section class="recommendation-column">
      <div class="recommendation-column-head">
        <h3>${escapeHtml(title)}</h3>
        <span>${songs.length} 首 · ${targetText}</span>
      </div>
      <div class="recommendation-column-list">
        ${songs.length
          ? songs.map((song, index) => renderSongCard(song, index + 1, context)).join("")
          : `<div class="empty-state">暂无足够候选。</div>`}
      </div>
    </section>
  `;
}

function renderSongCard(song, rank, context) {
  const songKey = songIdentityKey(song);
  const isLiked = normalizeTasteProfile(tasteProfile).likedKeys.includes(songKey);
  const isDisliked = normalizeTasteProfile(tasteProfile).blockedKeys.includes(songKey);
  const coverStyle = safeImageUrl(song.artwork) ? `style="background-image:url('${safeImageUrl(song.artwork)}')"` : "";
  const sourceLink = safeExternalUrl(song.sourceUrl)
    ? `<a class="source-link" href="${escapeAttribute(song.sourceUrl)}" target="_blank" rel="noopener" data-song-action="open">在线查看</a>`
    : "";
  const previewLink = safeExternalUrl(song.previewUrl)
    ? `<a class="source-link" href="${escapeAttribute(song.previewUrl)}" target="_blank" rel="noopener" data-song-action="play">试听片段</a>`
    : "";
  const extraTags = cleanRecommendationTags(song.tags || [])
    .filter((tag) => ![song.type, song.language, song.rawGenre, "热门榜单", "热门艺人", "原唱歌手", "热门相关", "高热度"].includes(tag))
    .slice(0, 6);
  const artistWeightTag = context.mode === "seed"
    ? `<span class="artist-weight-pill">歌手权重：${song.artistWeight ? `+${song.artistWeight}` : "0"}</span>`
    : "";

  return `
    <article class="song-card ${isLiked ? "is-liked" : ""} ${isDisliked ? "is-disliked" : ""}" data-song-key="${escapeAttribute(songKey)}">
      <div class="cover" ${coverStyle} aria-label="${escapeHtml(song.title)}封面"></div>
      <div class="song-main">
        <div class="song-head">
          <div>
            <h3 class="song-title">${escapeHtml(song.title)}</h3>
            <p class="song-meta">${escapeHtml(song.artist)}${song.releaseYear ? ` · ${song.releaseYear}` : ""} · ${countryLabel(song.country)}</p>
          </div>
          <div class="song-head-actions">
            <span class="rank-pill">#${rank}</span>
            <button class="feedback-button like-button" type="button" data-song-action="like" aria-label="喜欢这首歌">喜欢</button>
            <button class="feedback-button dislike-button" type="button" data-song-action="dislike" aria-label="不喜欢这首歌">不喜欢</button>
          </div>
        </div>
        <div class="tag-row">
          <span class="type-pill">类型：${escapeHtml(song.type)}</span>
          <span class="language-pill">语言：${escapeHtml(song.language)}</span>
          <span class="hot-pill">${sourceLabel(song)}</span>
          <span class="metric-pill">${escapeHtml(song.platformMetricLabel || platformMetricLabel(song))}</span>
          ${artistWeightTag}
          ${song.rawGenre && song.rawGenre !== song.type ? `<span class="type-pill">${escapeHtml(song.rawGenre)}</span>` : ""}
          ${extraTags.map((tag) => `<span class="tag-pill">${escapeHtml(tag)}</span>`).join("")}
        </div>
        <p class="song-reason">${escapeHtml(song.reason)}</p>
        <div class="song-actions">
          ${sourceLink}${previewLink}
        </div>
      </div>
    </article>
  `;
}

function setupRecommendationDecks() {
  const deckContainers = [
    elements.recommendationList,
    ...elements.recommendationList.querySelectorAll(".recommendation-column-list")
  ];

  deckContainers.forEach((deck) => {
    const cards = Array.from(deck.children).filter((child) => child.classList.contains("song-card"));
    if (cards.length <= 1) return;

    let activeIndex = 0;
    let lastWheelAt = 0;

    deck.classList.add("wheel-deck");
    deck.tabIndex = 0;
    deck.dataset.activeLabel = `${activeIndex + 1} / ${cards.length}`;
    cards.forEach((card, index) => {
      card.dataset.deckIndex = String(index);
      card.addEventListener("click", () => {
        if (activeIndex === index) {
          animateDeckBoundary(deck, 1);
          return;
        }
        activeIndex = index;
        applyRecommendationDeckState(deck, cards, activeIndex);
      });
    });

    deck.addEventListener("wheel", (event) => {
      const direction = event.deltaY > 0 ? 1 : -1;
      const nextIndex = Math.max(0, Math.min(cards.length - 1, activeIndex + direction));
      if (nextIndex === activeIndex) {
        animateDeckBoundary(deck, direction);
        return;
      }

      event.preventDefault();
      const now = Date.now();
      if (now - lastWheelAt < 170) return;
      lastWheelAt = now;
      activeIndex = nextIndex;
      applyRecommendationDeckState(deck, cards, activeIndex);
    }, { passive: false });

    deck.addEventListener("keydown", (event) => {
      if (!["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"].includes(event.key)) return;
      const direction = ["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1;
      const nextIndex = Math.max(0, Math.min(cards.length - 1, activeIndex + direction));
      if (nextIndex === activeIndex) {
        animateDeckBoundary(deck, direction);
        return;
      }

      event.preventDefault();
      activeIndex = nextIndex;
      applyRecommendationDeckState(deck, cards, activeIndex);
    });

    applyRecommendationDeckState(deck, cards, activeIndex);
  });
}

function applyRecommendationDeckState(deck, cards, activeIndex) {
  deck.dataset.activeLabel = `${activeIndex + 1} / ${cards.length}`;

  cards.forEach((card, index) => {
    const delta = index - activeIndex;
    const distance = Math.min(Math.abs(delta), 4);
    const hidden = Math.abs(delta) > 4;
    const afterActive = delta > 0;
    const beforeActive = delta < 0;
    const x = afterActive ? -10 * distance : beforeActive ? 10 * distance : 0;
    const y = afterActive ? 18 * distance : beforeActive ? -12 * distance : 0;
    const scale = Math.max(0.86, 1 - distance * 0.035);
    const rotate = afterActive ? -distance * 0.8 : beforeActive ? distance * 0.6 : 0;
    const opacity = hidden ? 0 : Math.max(0.18, 1 - distance * 0.16);
    const zIndex = 80 - distance - (afterActive ? 0 : 8);

    card.classList.toggle("is-active", delta === 0);
    card.classList.toggle("is-visible", !hidden);
    card.classList.toggle("is-hidden", hidden);
    card.style.setProperty("--deck-z-index", String(delta === 0 ? 90 : zIndex));
    animateRecommendationCardState(card, { x, y, scale, rotate, opacity });
    card.querySelectorAll("a, button").forEach((control) => {
      control.tabIndex = delta === 0 ? 0 : -1;
    });
  });
  animateActiveCardDetails();
}

function animateDeckBoundary(deck, direction) {
  if (!hasGsap() || reduceMotion) return;
  const activeCard = deck.querySelector(".song-card.is-active");
  if (!activeCard) return;
  gsap.fromTo(activeCard, { "--deck-boundary-y": `${direction > 0 ? 8 : -8}px` }, {
    "--deck-boundary-y": "0px",
    duration: 0.28,
    ease: "back.out(2.4)",
    onComplete: () => activeCard.style.removeProperty("--deck-boundary-y")
  });
}

function animateRecommendationCardState(card, state) {
  const vars = {
    "--deck-x": `${state.x}px`,
    "--deck-y": `${state.y}px`,
    "--deck-scale": state.scale,
    "--deck-rotate": `${state.rotate}deg`,
    "--deck-opacity": state.opacity
  };

  if (!hasGsap()) {
    Object.entries(vars).forEach(([name, value]) => {
      card.style.setProperty(name, String(value));
    });
    return;
  }

  gsap.to(card, {
    ...vars,
    duration: reduceMotion ? 0.01 : 0.46,
    ease: "power3.out",
    overwrite: "auto"
  });
}

function renderError(error) {
  elements.resultCount.textContent = "0 / 10";
  setStatusText("联网推荐失败");
  elements.recommendationList.innerHTML = `<div class="error-state">${escapeHtml(error.message || "联网推荐失败，请稍后重试。")}</div>`;
  animateMessageState();
}

function parseSeedSongs(value) {
  return uniqueStrings(
    String(value)
      .split(/[\n,，;；]+/g)
      .map((item) => item.trim())
      .filter(Boolean)
  ).slice(0, 8);
}

function getLanguageConfig(name) {
  return LANGUAGES.find((language) => language.name === name) || LANGUAGES[0];
}

function classifyGenre(value) {
  const text = normalizeText(value);
  if (/mandopop|cantopop|c pop|chinese pop|华语|中文|国语|粤语/.test(text)) return "流行";
  if (/j pop|k pop|kpop|anime|kayokyoku|korean|japanese|日韩|韩流|日语|韩语/.test(text)) return "日韩流行";
  if (/hip hop|rap|trap|说唱|嘻哈/.test(text)) return "说唱";
  if (/electronic|dance|house|techno|edm|garage|电子|电音|舞曲/.test(text)) return "电子";
  if (/rock|metal|punk|alternative|摇滚|金属/.test(text)) return "摇滚";
  if (/folk|singer songwriter|country|acoustic|民谣|乡村|原声/.test(text)) return "民谣";
  if (/r b|soul|blues|节奏布鲁斯|灵魂乐/.test(text)) return "R&B";
  if (/jazz|爵士/.test(text)) return "爵士";
  if (/classical|instrumental|new age|ambient|piano|soundtrack|轻音乐|古典|钢琴|纯音乐|氛围/.test(text)) return "轻音乐";
  if (/latin|reggaeton|拉丁/.test(text)) return "拉丁";
  if (/indie|独立/.test(text)) return "独立";
  return "流行";
}

function inferLanguage(country, value) {
  const text = normalizeText(value);
  if (/instrumental|piano|classical|ambient|soundtrack|轻音乐|纯音乐|古典/.test(text)) return "纯音乐";
  if (hasHangul(value) || hasKoreanLanguageHint(value)) return "韩语";
  if (hasJapaneseScript(value) || hasJapaneseLanguageHint(value)) return "日语";
  if (hasHan(value) || hasChineseLanguageHint(value)) return "华语";
  if (country === "JP" && hasJapaneseLanguageHint(value)) return "日语";
  if (country === "KR" && hasKoreanLanguageHint(value)) return "韩语";
  return "英语";
}

function isChineseSong(song) {
  const text = songText(song);
  return hasHan(text) || hasChineseLanguageHint(song.searchTerm);
}

function songText(song) {
  return `${song.title || ""} ${song.artist || ""} ${song.collection || ""} ${song.rawGenre || ""} ${song.searchTerm || ""}`;
}

function hasHan(value) {
  return /\p{Script=Han}/u.test(String(value || ""));
}

function hasHangul(value) {
  return /\p{Script=Hangul}/u.test(String(value || ""));
}

function hasJapaneseScript(value) {
  const text = String(value || "");
  return /\p{Script=Hiragana}|\p{Script=Katakana}/u.test(text);
}

function hasCjkScript(value) {
  return hasHan(value) || hasJapaneseScript(value) || hasHangul(value);
}

function hasChineseLanguageHint(value) {
  return /mandopop|cantopop|c pop|chinese|华语|中文|国语|粤语|周杰伦|林俊杰|邓紫棋|陈奕迅|五月天|告五人|薛之谦|汪苏泷|毛不易|王菲/i.test(String(value || ""));
}

function hasJapaneseLanguageHint(value) {
  return /j pop|j-pop|japanese|anime|日语|日本|米津|髭男|宇多田|ヒカル|yoasobi|ado|king gnu/i.test(String(value || ""));
}

function hasKoreanLanguageHint(value) {
  return /k pop|k-pop|kpop|korean|韩语|韩国|bts|blackpink|newjeans|ive|seventeen|aespa|iu/i.test(String(value || ""));
}

function dedupeSongs(songs, context = null) {
  const seen = new Map();
  songs.forEach((song) => {
    const key = normalizeText(`${song.title}-${song.artist}`);
    const previous = seen.get(key);
    if (!previous || dedupeSongPreference(song, context) > dedupeSongPreference(previous, context)) {
      seen.set(key, song);
    }
  });
  return [...seen.values()];
}

function dedupeSongPreference(song, context = null) {
  const providerScore = (isNeteasePreferredContext(context)
    ? {
        netease: 90,
        qq: 88,
        ytmusic: 60,
        spotify: 55,
        itunes: 35
      }
    : {
        qq: 90,
        netease: 88,
        ytmusic: 60,
        spotify: 55,
        itunes: 35
      })[sourceProvider(song)] || 0;
  const artistBonus = song.source === "artist" ? 12 : 0;
  const heat = Math.min(10, Math.round((Number(song.platformPopularity) || Number(song.popularity) || 0) / 10));
  return providerScore + artistBonus + heat;
}

function isSameAsSeed(song, seeds) {
  const title = normalizeText(song.title);
  const artist = normalizeText(song.artist);
  return seeds.some((seed) => {
    const text = normalizeText(seed);
    if (text === title) return true;
    return title && artist && text.includes(title) && text.includes(artist);
  });
}

function topValues(values, limit) {
  const counts = new Map();
  values.filter(Boolean).forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-CN"))
    .slice(0, limit)
    .map(([value]) => value);
}

function uniqueStrings(values) {
  return [...new Set(values.map((value) => String(value || "").trim()).filter(Boolean))];
}

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function countryLabel(country) {
  const labels = {
    CN: "中国区",
    US: "美国区",
    JP: "日本区",
    KR: "韩国区",
    GB: "英国区",
    WY: "网易云",
    QQ: "QQ音乐",
    YT: "YouTube Music",
    SP: "Spotify"
  };
  return labels[country] || country;
}

function loadOnlinePool() {
  try {
    const raw = localStorage.getItem(ONLINE_POOL_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed
        .filter((song) => song.language && song.type)
        .filter((song) => ALL_PROVIDERS.includes(sourceProvider(song)))
        .map((song) => ({ ...song, tags: cleanRecommendationTags(song.tags || []) }))
      : [];
  } catch {
    return [];
  }
}

function saveOnlinePool() {
  try {
    localStorage.setItem(ONLINE_POOL_KEY, JSON.stringify(onlineSongPool.slice(0, 240)));
  } catch {
    // 缓存失败不影响在线推荐。
  }
}

function safeImageUrl(value) {
  const url = String(value || "");
  return /^https:\/\/[^"'<> ]+$/i.test(url) ? url : "";
}

function safeExternalUrl(value) {
  const url = String(value || "");
  return /^https:\/\/[^"'<> ]+$/i.test(url) ? url : "";
}

function escapeAttribute(value) {
  return escapeHtml(value);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
