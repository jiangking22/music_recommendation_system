from __future__ import annotations

import argparse
import base64
import html as html_lib
import json
import os
import re
import socket
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import parse, request


ROOT = Path(__file__).resolve().parent
REQUEST_TIMEOUT = 4
REQUEST_CACHE_TTL = 600
MAX_REQUEST_CACHE_ITEMS = 256
REQUEST_CACHE: dict[tuple[str, str], tuple[float, object]] = {}
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}


class StaticHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path == "/api/search/domestic":
            self.handle_domestic_search(parsed)
            return
        if parsed.path == "/api/search/itunes":
            self.handle_itunes_search(parsed)
            return
        if parsed.path == "/api/chart/itunes":
            self.handle_itunes_chart(parsed)
            return
        if parsed.path == "/api/search/artist-songs":
            self.handle_artist_song_search(parsed)
            return
        if parsed.path == "/api/search/streaming":
            self.handle_streaming_search(parsed)
            return
        if parsed.path == "/api/search/web-artist":
            self.handle_web_artist_search(parsed)
            return
        super().do_GET()

    def handle_domestic_search(self, parsed: parse.ParseResult) -> None:
        params = parse.parse_qs(parsed.query)
        provider = read_param(params, "provider").lower()
        term = read_param(params, "term")
        limit = clamp_int(read_param(params, "limit"), 1, 50, 20)

        if provider not in {"netease", "qq"} or not term:
            self.send_json(400, {"ok": False, "songs": [], "error": "Invalid provider or term."})
            return

        try:
            songs = search_netease(term, limit) if provider == "netease" else search_qq(term, limit)
            self.send_json(200, {"ok": True, "provider": provider, "songs": songs})
        except Exception as exc:  # noqa: BLE001 - local demo should degrade gracefully.
            self.send_json(502, {"ok": False, "provider": provider, "songs": [], "error": str(exc)})

    def handle_itunes_search(self, parsed: parse.ParseResult) -> None:
        params = parse.parse_qs(parsed.query)
        term = read_param(params, "term")
        country = read_param(params, "country") or "US"
        limit = clamp_int(read_param(params, "limit"), 1, 50, 20)

        if not term:
            self.send_json(400, {"ok": False, "results": [], "error": "Invalid term."})
            return

        try:
            results = search_itunes(term, country, limit)
            self.send_json(200, {"ok": True, "provider": "itunes", "country": country, "results": results})
        except Exception as exc:  # noqa: BLE001 - local demo should degrade gracefully.
            self.send_json(502, {"ok": False, "provider": "itunes", "country": country, "results": [], "error": str(exc)})

    def handle_itunes_chart(self, parsed: parse.ParseResult) -> None:
        params = parse.parse_qs(parsed.query)
        country = read_param(params, "country") or "US"
        limit = clamp_int(read_param(params, "limit"), 1, 100, 30)

        try:
            payload = fetch_itunes_chart(country, limit)
            self.send_json(200, {"ok": True, "provider": "itunes", "country": country, "feed": payload.get("feed", {})})
        except Exception as exc:  # noqa: BLE001 - local demo should degrade gracefully.
            self.send_json(502, {"ok": False, "provider": "itunes", "country": country, "feed": {}, "error": str(exc)})

    def handle_artist_song_search(self, parsed: parse.ParseResult) -> None:
        params = parse.parse_qs(parsed.query)
        provider = read_param(params, "provider").lower()
        artist = read_param(params, "artist")
        limit = clamp_int(read_param(params, "limit"), 1, 50, 30)

        if provider not in {"netease", "qq"} or not artist:
            self.send_json(400, {"ok": False, "songs": [], "error": "Invalid provider or artist."})
            return

        try:
            songs = search_netease_artist_songs(artist, limit) if provider == "netease" else search_qq_artist_songs(artist, limit)
            self.send_json(200, {"ok": True, "provider": provider, "artist": artist, "songs": songs})
        except Exception as exc:  # noqa: BLE001 - local demo should degrade gracefully.
            self.send_json(502, {"ok": False, "provider": provider, "artist": artist, "songs": [], "error": str(exc)})

    def handle_streaming_search(self, parsed: parse.ParseResult) -> None:
        params = parse.parse_qs(parsed.query)
        provider = read_param(params, "provider").lower()
        term = read_param(params, "term")
        limit = clamp_int(read_param(params, "limit"), 1, 50, 20)

        if provider not in {"ytmusic", "spotify"} or not term:
            self.send_json(400, {"ok": False, "songs": [], "error": "Invalid provider or term."})
            return

        try:
            songs = search_youtube_music(term, limit) if provider == "ytmusic" else search_spotify(term, limit)
            self.send_json(200, {"ok": True, "provider": provider, "songs": songs})
        except Exception as exc:  # noqa: BLE001 - local demo should degrade gracefully.
            self.send_json(502, {"ok": False, "provider": provider, "songs": [], "error": str(exc)})

    def handle_web_artist_search(self, parsed: parse.ParseResult) -> None:
        params = parse.parse_qs(parsed.query)
        term = read_param(params, "term")
        seed = read_param(params, "seed") or term
        limit = clamp_int(read_param(params, "limit"), 1, 8, 5)

        if not term:
            self.send_json(400, {"ok": False, "candidates": [], "error": "Invalid term."})
            return

        try:
            candidates = search_web_artist(term, seed, limit)
            self.send_json(200, {"ok": True, "provider": "web", "candidates": candidates})
        except Exception as exc:  # noqa: BLE001 - web search is only a fallback.
            self.send_json(502, {"ok": False, "provider": "web", "candidates": [], "error": str(exc)})

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def read_param(params: dict[str, list[str]], name: str) -> str:
    values = params.get(name) or [""]
    return values[0].strip()


def clamp_int(value: str, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def cache_key(kind: str, url: str, payload: object = None) -> tuple[str, str]:
    return kind, json.dumps({"url": url, "payload": payload}, sort_keys=True, ensure_ascii=False, default=str)


def read_request_cache(key: tuple[str, str]) -> object | None:
    cached = REQUEST_CACHE.get(key)
    if not cached:
        return None
    cached_at, value = cached
    if time.monotonic() - cached_at > REQUEST_CACHE_TTL:
        REQUEST_CACHE.pop(key, None)
        return None
    return value


def write_request_cache(key: tuple[str, str], value: object) -> None:
    if len(REQUEST_CACHE) >= MAX_REQUEST_CACHE_ITEMS:
        oldest_key = min(REQUEST_CACHE, key=lambda item: REQUEST_CACHE[item][0])
        REQUEST_CACHE.pop(oldest_key, None)
    REQUEST_CACHE[key] = (time.monotonic(), value)


def request_json(url: str, *, data: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> dict:
    key = cache_key("json", url, data)
    cached = read_request_cache(key)
    if isinstance(cached, dict):
        return cached

    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    body = None
    if data is not None:
        body = parse.urlencode(data).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    req = request.Request(url, data=body, headers=request_headers)
    with request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
        text = response.read().decode("utf-8", "replace").strip()
    payload = parse_json_or_jsonp(text)
    write_request_cache(key, payload)
    return payload


def request_text(url: str, *, headers: dict[str, str] | None = None) -> str:
    key = cache_key("text", url)
    cached = read_request_cache(key)
    if isinstance(cached, str):
        return cached

    req = request.Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    with request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
        text = response.read().decode("utf-8", "replace")
    write_request_cache(key, text)
    return text


def request_json_body(url: str, payload: dict, *, headers: dict[str, str] | None = None) -> dict:
    key = cache_key("json-body", url, payload)
    cached = read_request_cache(key)
    if isinstance(cached, dict):
        return cached

    request_headers = {
        **DEFAULT_HEADERS,
        "Content-Type": "application/json; charset=UTF-8",
        **(headers or {}),
    }
    req = request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=request_headers)
    with request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
        text = response.read().decode("utf-8", "replace").strip()
    data = parse_json_or_jsonp(text)
    write_request_cache(key, data)
    return data


def parse_json_or_jsonp(text: str) -> dict:
    if "(" in text and text.endswith(")"):
        start = text.find("(")
        text = text[start + 1 : -1]
    return json.loads(text.lstrip("\ufeff"))


def search_netease(term: str, limit: int) -> list[dict]:
    payload = request_json(
        "https://music.163.com/api/search/get/web",
        data={
            "s": term,
            "type": "1",
            "offset": "0",
            "total": "true",
            "limit": str(limit),
        },
        headers={"Referer": "https://music.163.com/"},
    )
    items = payload.get("result", {}).get("songs", []) or []
    return [song for index, item in enumerate(items) if (song := map_netease_song(item, index))]


def search_qq(term: str, limit: int) -> list[dict]:
    query = parse.urlencode(
        {
            "p": "1",
            "n": str(limit),
            "w": term,
            "format": "json",
        }
    )
    payload = request_json(
        f"https://c.y.qq.com/soso/fcgi-bin/client_search_cp?{query}",
        headers={"Referer": "https://y.qq.com/"},
    )
    items = payload.get("data", {}).get("song", {}).get("list", []) or []
    return [song for index, item in enumerate(items) if (song := map_qq_song(item, index))]


def search_itunes(term: str, country: str, limit: int) -> list[dict]:
    query = parse.urlencode(
        {
            "term": term,
            "country": normalize_storefront(country),
            "media": "music",
            "entity": "song",
            "limit": str(limit),
        }
    )
    payload = request_json(f"https://itunes.apple.com/search?{query}")
    return payload.get("results", []) or []


def fetch_itunes_chart(country: str, limit: int) -> dict:
    store = normalize_storefront(country).lower()
    return request_json(f"https://itunes.apple.com/{store}/rss/topsongs/limit={limit}/json")


def normalize_storefront(country: str) -> str:
    value = re.sub(r"[^A-Za-z]", "", str(country or "US")).upper()
    return value[:2] or "US"


def search_netease_artist_songs(artist: str, limit: int) -> list[dict]:
    artist_items = search_netease_artists(artist, 8)
    matched_artists = choose_artist_matches(artist_items, artist)
    songs: list[dict] = []

    for item in matched_artists[:3]:
        artist_id = item.get("id")
        if not artist_id:
            continue
        try:
            payload = request_json(
                f"https://music.163.com/api/artist/{artist_id}",
                headers={"Referer": f"https://music.163.com/artist?id={artist_id}"},
            )
        except Exception:  # noqa: BLE001 - try the next matched artist.
            continue
        hot_songs = payload.get("hotSongs") or []
        songs.extend(song for index, song_item in enumerate(hot_songs) if (song := map_netease_song(song_item, index)))
        if len(dedupe_server_songs(songs)) >= limit:
            break

    if len(dedupe_server_songs(songs)) < min(limit, 8):
        songs.extend(search_netease(artist, limit))

    return dedupe_server_songs([song for song in songs if server_same_artist(song.get("artist", ""), artist)])[:limit]


def search_netease_artists(artist: str, limit: int) -> list[dict]:
    payload = request_json(
        "https://music.163.com/api/search/get/web",
        data={
            "s": artist,
            "type": "100",
            "offset": "0",
            "total": "true",
            "limit": str(limit),
        },
        headers={"Referer": "https://music.163.com/"},
    )
    return payload.get("result", {}).get("artists", []) or []


def search_qq_artist_songs(artist: str, limit: int) -> list[dict]:
    songs: list[dict] = []
    search_terms = unique_strings([artist, f"{artist} 热门歌曲", f"{artist} 代表作"])
    for term in search_terms:
        try:
            songs.extend(search_qq(term, limit))
        except Exception:  # noqa: BLE001 - try the next search term.
            continue
        if len(dedupe_server_songs(songs)) >= limit:
            break
    return dedupe_server_songs([song for song in songs if server_same_artist(song.get("artist", ""), artist)])[:limit]


def choose_artist_matches(items: list[dict], artist: str) -> list[dict]:
    exact: list[dict] = []
    partial: list[dict] = []
    for item in items:
        names = [item.get("name"), item.get("trans"), *(item.get("alias") or []), *(item.get("alia") or [])]
        if any(normalize_text(name) == normalize_text(artist) for name in names if name):
            exact.append(item)
        elif any(server_same_artist(str(name or ""), artist) for name in names):
            partial.append(item)
    return exact or partial or items[:2]


def dedupe_server_songs(songs: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for song in songs:
        key = normalize_text(f"{song.get('title', '')}-{song.get('artist', '')}")
        if key and key not in seen:
            seen[key] = song
    return list(seen.values())


def search_youtube_music(term: str, limit: int) -> list[dict]:
    try:
        page = request_text("https://music.youtube.com/", headers={"Referer": "https://music.youtube.com/"})
    except Exception:  # noqa: BLE001 - optional provider should degrade gracefully.
        return []
    api_key = read_regex(page, r'"INNERTUBE_API_KEY":"([^"]+)"')
    client_version = read_regex(page, r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"') or "1.20240520.01.00"
    if not api_key:
        return search_youtube_web(term, limit)

    payload = request_json_body(
        f"https://music.youtube.com/youtubei/v1/search?key={parse.quote(api_key)}",
        {
            "context": {
                "client": {
                    "clientName": "WEB_REMIX",
                    "clientVersion": client_version,
                }
            },
            "query": term,
            "params": "EgWKAQIIAWoKEAkQBRAKEAMQBQ%3D%3D",
        },
        headers={
            "Origin": "https://music.youtube.com",
            "Referer": "https://music.youtube.com/",
            "X-Goog-Visitor-Id": read_regex(page, r'"VISITOR_DATA":"([^"]+)"') or "",
        },
    )
    renderers = find_values(payload, "musicResponsiveListItemRenderer")
    songs = [song for index, item in enumerate(renderers) if (song := map_youtube_music_song(item, index))]
    return songs[:limit]


def search_youtube_web(term: str, limit: int) -> list[dict]:
    query = parse.urlencode({"search_query": f"{term} song"})
    try:
        page = request_text(
            f"https://www.youtube.com/results?{query}",
            headers={"Referer": "https://www.youtube.com/", "Accept-Language": "en-US,en;q=0.9"},
        )
        initial_data = read_regex(page, r"var ytInitialData = (\{.*?\});</script>")
        if not initial_data:
            initial_data = read_regex(page, r"ytInitialData\"\]\s*=\s*(\{.*?\});")
        if not initial_data:
            return []
        payload = json.loads(initial_data)
    except Exception:  # noqa: BLE001 - YouTube web search may be blocked or consent-gated.
        return []

    renderers = find_values(payload, "videoRenderer")
    songs = [song for index, item in enumerate(renderers) if (song := map_youtube_video_song(item, index))]
    return songs[:limit]


def search_spotify(term: str, limit: int) -> list[dict]:
    token = get_spotify_token()
    if not token:
        return []

    query = parse.urlencode({"q": term, "type": "track", "limit": str(limit)})
    payload = request_json(
        f"https://api.spotify.com/v1/search?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    items = payload.get("tracks", {}).get("items", []) or []
    return [song for index, item in enumerate(items) if (song := map_spotify_song(item, index))]


def search_web_artist(term: str, seed: str, limit: int) -> list[dict]:
    queries = unique_strings(
        [
            f"intitle:{term} 歌曲",
            f"{term} site:music.163.com/song",
            f'"{term}" 网易云音乐',
            f'"{term}" QQ音乐',
            f'"{term}" 原唱 歌手',
            f"{term} 谁唱的",
            f"{term} 歌曲 歌手",
            f"{seed} 原唱",
        ]
    )
    results: list[dict] = []

    for query in queries:
        try:
            results.extend(search_bing_results(query, 8))
        except Exception:  # noqa: BLE001 - try the next public search fallback.
            continue
        if len(extract_artist_candidates_from_web_results(term, seed, results, limit)) >= limit:
            break

    if not results:
        for query in queries[:2]:
            try:
                results.extend(search_duckduckgo_results(query, 8))
            except Exception:  # noqa: BLE001 - web fallback should degrade gracefully.
                continue
            if len(results) >= limit * 3:
                break

    return extract_artist_candidates_from_web_results(term, seed, results, limit)


def search_bing_results(query: str, limit: int) -> list[dict]:
    url = f"https://www.bing.com/search?{parse.urlencode({'q': query, 'setlang': 'zh-CN'})}"
    page = request_text(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Referer": "https://www.bing.com/",
        },
    )
    results = []
    blocks = re.findall(r'<li class="b_algo".*?</li>', page, flags=re.S)
    for index, block in enumerate(blocks[:limit]):
        link_match = re.search(r"<h2[^>]*>.*?<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", block, flags=re.S)
        if not link_match:
            continue
        snippet = read_first_regex(block, [r"<p[^>]*>(.*?)</p>", r'<div class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>'])
        results.append(
            {
                "rank": index + 1,
                "query": query,
                "title": strip_html(link_match.group(2)),
                "snippet": strip_html(snippet),
                "sourceUrl": html_lib.unescape(link_match.group(1)),
            }
        )
    return results


def search_duckduckgo_results(query: str, limit: int) -> list[dict]:
    url = f"https://duckduckgo.com/html/?{parse.urlencode({'q': query})}"
    page = request_text(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Referer": "https://duckduckgo.com/",
        },
    )
    results = []
    blocks = re.findall(r'<div class="result[^"]*".*?</div>\s*</div>', page, flags=re.S)
    for index, block in enumerate(blocks[:limit]):
        link_match = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        if not link_match:
            continue
        href = html_lib.unescape(link_match.group(1))
        parsed_href = parse.urlparse(href)
        query_params = parse.parse_qs(parsed_href.query)
        source_url = query_params.get("uddg", [href])[0]
        snippet = read_first_regex(block, [r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', r'<div[^>]+class="result__snippet"[^>]*>(.*?)</div>'])
        results.append(
            {
                "rank": index + 1,
                "query": query,
                "title": strip_html(link_match.group(2)),
                "snippet": strip_html(snippet),
                "sourceUrl": source_url,
            }
        )
    return results


def extract_artist_candidates_from_web_results(term: str, seed: str, results: list[dict], limit: int) -> list[dict]:
    candidates: dict[str, dict] = {}
    for result in results:
        text = f"{result.get('title', '')}。{result.get('snippet', '')}"
        for artist in infer_artists_from_web_text(term, text):
            normalized = normalize_text(artist)
            if not normalized:
                continue
            previous = candidates.get(normalized)
            score = score_web_artist_candidate(result, artist)
            if not previous or score > previous["score"]:
                candidates[normalized] = {
                    "artist": artist,
                    "matchedTitle": term,
                    "sourceTitle": result.get("title", ""),
                    "snippet": result.get("snippet", ""),
                    "sourceUrl": result.get("sourceUrl", ""),
                    "query": result.get("query", seed or term),
                    "rank": len(candidates) + 1,
                    "score": score,
                }

    return sorted(candidates.values(), key=lambda item: (-item["score"], item["rank"], item["artist"]))[:limit]


def infer_artists_from_web_text(term: str, text: str) -> list[str]:
    term_pattern = re.escape(term.strip())
    candidates: list[str] = []

    for segment in split_search_text_segments(text):
        bracket_match = re.search(rf"([\u4e00-\u9fffA-Za-z0-9·.&/、\-\s]{{2,32}})[《「]\s*{term_pattern}\s*[》」]", segment, flags=re.I)
        if bracket_match:
            candidates.extend(split_artist_names(bracket_match.group(1)))

        for separator in (" - ", "_", "–", "—"):
            parts = [part.strip() for part in segment.split(separator) if part.strip()]
            for index, part in enumerate(parts):
                if title_matches_term(term, part):
                    if index + 1 < len(parts):
                        candidates.extend(split_artist_names(parts[index + 1]))
                    if index > 0:
                        candidates.extend(split_artist_names(parts[index - 1]))

    patterns = [
        rf"(?:《{term_pattern}》|{term_pattern}).{{0,12}}?(?:是|由)?\s*([\u4e00-\u9fffA-Za-z0-9·.&/、\-\s]{{2,24}})\s*(?:演唱|唱)",
        rf"(?:《{term_pattern}》|{term_pattern}).{{0,18}}?(?:原唱|歌手|演唱|由|唱)[:： ]*([\u4e00-\u9fffA-Za-z0-9·.&/、\-\s]{{2,32}})",
        rf"(?:原唱|歌手|演唱)[:： ]*([\u4e00-\u9fffA-Za-z0-9·.&/、\-\s]{{2,32}}).{{0,18}}?(?:《{term_pattern}》|{term_pattern})",
        rf"由\s*([\u4e00-\u9fffA-Za-z0-9·.&/、\-\s]{{2,32}})\s*(?:演唱|唱)",
        rf"([\u4e00-\u9fffA-Za-z0-9·.&/、\-\s]{{2,32}})\s*(?:演唱|唱).{{0,18}}?(?:《{term_pattern}》|{term_pattern})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            candidates.extend(split_artist_names(match.group(1)))

    return unique_strings([artist for artist in (clean_artist_name(value, term) for value in candidates) if artist])


def split_search_text_segments(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。！？!?；;\n\r]+", text) if part.strip()]


def score_web_artist_candidate(result: dict, artist: str) -> int:
    title = str(result.get("title") or "")
    source_url = str(result.get("sourceUrl") or "")
    rank = int(result.get("rank") or 8)
    score = 82 - rank * 3
    if re.search(r"qq\.com|music\.163\.com|kugou|kuwo|baidu", source_url, re.I):
        score += 8
    if artist and artist in title:
        score += 5
    return max(45, min(92, score))


def split_artist_names(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*(?:/|、|,|，|&|和|feat\.?|ft\.?)\s*", value, flags=re.I) if part.strip()]


def clean_artist_name(value: str, term: str) -> str:
    text = strip_html(value)
    text = re.sub(r"[《》<>【】\[\]（）()]", " ", text)
    text = re.sub(r"^(?:原唱|歌手|演唱|由|唱)[:： ]*", "", text, flags=re.I)
    text = re.sub(r"(?:演唱|演|唱|原唱)$", "", text, flags=re.I)
    text = re.sub(r"(?:QQ音乐|网易云音乐|酷狗音乐|酷我音乐|百度百科|歌词|歌曲|在线试听|高音质|完整版|官方|MV|mv|谁唱的).*", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -_—–:：|｜·")
    text = re.sub(r"(?:的|经典)$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -_—–:：|｜·")
    if not is_probable_artist_name(text, term):
        return ""
    return text


def is_probable_artist_name(value: str, term: str) -> bool:
    text = value.strip()
    normalized = normalize_text(text)
    if len(text) < 2 or len(text) > 24:
        return False
    if normalize_text(term) == normalized:
        return False
    if re.search(r"^\d{2,4}年|\d+月\d+日|\d+\s*(?:天|小时|分钟)前", text):
        return False
    if re.search(r"https?://|www\.|歌曲|歌词|专辑|播放|下载|在线试听|百科|视频|评论|原唱|音乐|经典曲目|全网|详情|高清|完整版|现场|弹唱|单曲|流行|中国风|爱奇艺|搜狐|优酷|腾讯视频", text, re.I):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", text))


def title_matches_term(term: str, value: str) -> bool:
    left = normalize_text(term)
    right = normalize_text(value)
    if not left or not right:
        return False
    if left == right or left in right:
        return True
    return len(right) >= 4 and right in left


def get_spotify_token() -> str:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if client_id and client_secret:
        try:
            credentials = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
            payload = request_json(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {credentials}"},
            )
            return str(payload.get("access_token") or "")
        except Exception:  # noqa: BLE001 - optional provider should degrade gracefully.
            return ""

    try:
        payload = request_json(
            "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
            headers={"Referer": "https://open.spotify.com/"},
        )
    except Exception:  # noqa: BLE001 - Spotify web token may be blocked by region or network.
        return ""
    return str(payload.get("accessToken") or payload.get("access_token") or "")


def map_netease_song(item: dict, index: int) -> dict | None:
    song_id = item.get("id")
    title = item.get("name") or ""
    artists = item.get("artists") or item.get("ar") or []
    album = item.get("album") or item.get("al") or {}
    artist = join_names(artists)
    if not song_id or not title or not artist:
        return None
    return {
        "provider": "netease",
        "providerName": "网易云音乐",
        "trackId": str(song_id),
        "rank": index + 1,
        "title": title,
        "artist": artist,
        "collection": album.get("name") or "",
        "rawGenre": "华语流行",
        "artwork": album.get("picUrl") or album.get("blurPicUrl") or "",
        "sourceUrl": f"https://music.163.com/#/song?id={song_id}",
        "previewUrl": "",
        "playCount": read_number(item, "playCount", "play_count", "playcnt", "listenCount"),
        "favoriteCount": read_number(item, "favoriteCount", "subscribedCount", "collectCount", "likedCount"),
        "platformScore": read_number(item, "score", "popularity", "hotScore"),
        "popularity": max(70, 96 - index * 2),
    }


def map_qq_song(item: dict, index: int) -> dict | None:
    song_id = item.get("id") or item.get("songid")
    song_mid = item.get("mid") or item.get("songmid") or ""
    title = item.get("title") or item.get("songname") or ""
    singers = item.get("singer") or []
    album = item.get("album") or {}
    album_name = album.get("name") or item.get("albumname") or ""
    album_mid = album.get("mid") or item.get("albummid") or ""
    artist = join_names(singers)
    if not song_id or not title or not artist:
        return None
    return {
        "provider": "qq",
        "providerName": "QQ音乐",
        "trackId": str(song_id),
        "rank": index + 1,
        "title": title,
        "artist": artist,
        "collection": album_name,
        "rawGenre": "华语流行",
        "artwork": f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg" if album_mid else "",
        "sourceUrl": f"https://y.qq.com/n/ryqq/songDetail/{song_mid}" if song_mid else "https://y.qq.com/",
        "previewUrl": "",
        "playCount": read_number(item, "playCount", "play_count", "playcnt", "listenCount"),
        "favoriteCount": read_number(item, "favoriteCount", "subscribedCount", "collectCount", "likedCount"),
        "platformScore": read_number(item, "score", "popularity", "hotScore"),
        "popularity": max(70, 96 - index * 2),
    }


def map_youtube_music_song(item: dict, index: int) -> dict | None:
    columns = item.get("flexColumns") or []
    title = read_music_column(columns, 0)
    detail_runs = read_music_runs(columns, 1)
    artist = choose_youtube_artist(detail_runs)
    album = choose_youtube_album(detail_runs, artist)
    video_id = read_nested(item, ["playlistItemData", "videoId"]) or find_watch_video_id(item)
    thumbnails = read_nested(item, ["thumbnail", "musicThumbnailRenderer", "thumbnail", "thumbnails"]) or []
    artwork = thumbnails[-1].get("url") if thumbnails and isinstance(thumbnails[-1], dict) else ""

    if not title or not artist or not video_id:
        return None

    return {
        "provider": "ytmusic",
        "providerName": "YouTube Music",
        "trackId": str(video_id),
        "rank": index + 1,
        "title": title,
        "artist": artist,
        "collection": album,
        "rawGenre": "Music",
        "artwork": artwork,
        "sourceUrl": f"https://music.youtube.com/watch?v={video_id}",
        "previewUrl": "",
        "platformScore": max(50, 98 - index * 2),
        "popularity": max(70, 96 - index * 2),
    }


def map_youtube_video_song(item: dict, index: int) -> dict | None:
    video_id = item.get("videoId")
    title = read_text_runs(item.get("title") or {})
    artist = read_text_runs(item.get("ownerText") or {}) or read_text_runs(item.get("longBylineText") or {})
    thumbnails = read_nested(item, ["thumbnail", "thumbnails"]) or []
    artwork = thumbnails[-1].get("url") if thumbnails and isinstance(thumbnails[-1], dict) else ""
    if not video_id or not title or not artist:
        return None

    return {
        "provider": "ytmusic",
        "providerName": "YouTube Music",
        "trackId": str(video_id),
        "rank": index + 1,
        "title": title,
        "artist": artist,
        "collection": "",
        "rawGenre": "Music",
        "artwork": artwork,
        "sourceUrl": f"https://music.youtube.com/watch?v={video_id}",
        "previewUrl": "",
        "platformScore": max(50, 98 - index * 2),
        "popularity": max(70, 96 - index * 2),
    }


def map_spotify_song(item: dict, index: int) -> dict | None:
    track_id = item.get("id")
    title = item.get("name") or ""
    artist = join_names(item.get("artists") or [])
    album = item.get("album") or {}
    images = album.get("images") or []
    artwork = images[0].get("url") if images and isinstance(images[0], dict) else ""
    external_urls = item.get("external_urls") or {}
    if not track_id or not title or not artist:
        return None

    return {
        "provider": "spotify",
        "providerName": "Spotify",
        "trackId": str(track_id),
        "rank": index + 1,
        "title": title,
        "artist": artist,
        "collection": album.get("name") or "",
        "rawGenre": "Pop",
        "artwork": artwork,
        "sourceUrl": external_urls.get("spotify") or f"https://open.spotify.com/track/{track_id}",
        "previewUrl": item.get("preview_url") or "",
        "explicitness": "explicit" if item.get("explicit") else "notExplicit",
        "platformScore": item.get("popularity"),
        "popularity": Number_or_default(item.get("popularity"), max(70, 94 - index * 2)),
    }


def read_number(item: dict, *names: str) -> int | None:
    for name in names:
        value = item.get(name)
        if isinstance(value, dict):
            value = value.get("value")
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def Number_or_default(value: object, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def read_regex(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def read_first_regex(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.S)
        if match:
            return match.group(1)
    return ""


def strip_html(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\u4e00-\u9fff]+", " ", str(value or "").lower())).strip()


def server_same_artist(left: str, right: str) -> bool:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm or left_norm in right_norm or right_norm in left_norm:
        return True
    left_parts = [normalize_text(part) for part in re.split(r"\s*(?:/|、|,|，|&|和|feat\.?|ft\.?)\s*", left, flags=re.I)]
    right_parts = [normalize_text(part) for part in re.split(r"\s*(?:/|、|,|，|&|和|feat\.?|ft\.?)\s*", right, flags=re.I)]
    return any(part and (part == right_norm or part in right_parts) for part in left_parts)


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = normalize_text(text)
        if not text or key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def find_values(value: object, key: str) -> list[dict]:
    found: list[dict] = []
    if isinstance(value, dict):
        for item_key, item_value in value.items():
            if item_key == key and isinstance(item_value, dict):
                found.append(item_value)
            found.extend(find_values(item_value, key))
    elif isinstance(value, list):
        for item in value:
            found.extend(find_values(item, key))
    return found


def read_nested(value: object, path: list[str]) -> object:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def read_music_runs(columns: list[dict], index: int) -> list[dict]:
    if index >= len(columns):
        return []
    renderer = columns[index].get("musicResponsiveListItemFlexColumnRenderer") or {}
    text = renderer.get("text") or {}
    return [run for run in text.get("runs", []) if isinstance(run, dict)]


def read_music_column(columns: list[dict], index: int) -> str:
    runs = read_music_runs(columns, index)
    return str(runs[0].get("text") or "").strip() if runs else ""


def read_text_runs(value: dict) -> str:
    if not isinstance(value, dict):
        return ""
    if value.get("simpleText"):
        return str(value.get("simpleText") or "").strip()
    runs = value.get("runs") or []
    parts = [str(run.get("text") or "").strip() for run in runs if isinstance(run, dict)]
    return "".join(parts).strip()


def choose_youtube_artist(runs: list[dict]) -> str:
    for run in runs:
        text = str(run.get("text") or "").strip()
        if text and is_artist_like_youtube_text(text, run):
            return text
    return ""


def choose_youtube_album(runs: list[dict], artist: str) -> str:
    candidates = []
    for run in runs:
        text = str(run.get("text") or "").strip()
        if text and text != artist and not is_youtube_separator_or_meta(text):
            candidates.append(text)
    return candidates[1] if len(candidates) > 1 else ""


def is_artist_like_youtube_text(text: str, run: dict) -> bool:
    if is_youtube_separator_or_meta(text):
        return False
    endpoint = run.get("navigationEndpoint") or {}
    browse_id = read_nested(endpoint, ["browseEndpoint", "browseId"])
    return bool(browse_id) or not re.search(r"\d+:\d+|\d[\d,.\s]*(views|次观看)$", text, re.I)


def is_youtube_separator_or_meta(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {"", "•", "song", "video", "single", "album", "歌曲", "视频"} or bool(re.fullmatch(r"\d+:\d+", normalized))


def find_watch_video_id(value: object) -> str:
    if isinstance(value, dict):
        watch = value.get("watchEndpoint")
        if isinstance(watch, dict) and watch.get("videoId"):
            return str(watch.get("videoId"))
        for item in value.values():
            found = find_watch_video_id(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_watch_video_id(item)
            if found:
                return found
    return ""


def join_names(items: list[dict]) -> str:
    names = [str(item.get("name") or "").strip() for item in items if isinstance(item, dict)]
    return " / ".join(name for name in names if name)


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def choose_port(start: int) -> int:
    for port in range(start, start + 50):
        if port_is_free(port):
            return port
    raise RuntimeError("No free port found in the configured range.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the music recommendation demo.")
    parser.add_argument("--port", type=int, default=8010, help="Preferred local port.")
    args = parser.parse_args()

    os.chdir(ROOT)
    port = choose_port(args.port)
    server = ThreadingHTTPServer(("127.0.0.1", port), StaticHandler)
    print(f"Music Recommendation System: http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
