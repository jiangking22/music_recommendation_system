"""Bounded catalog expansion, fixed-endpoint link parsing and confirmed recording memory."""

import hashlib
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from time import perf_counter
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    RecordingResolveResponse,
    ResolvedChoice,
    SearchAttempt,
    SearchReport,
)
from app.domain.artist_names import artist_aliases, artist_identity, enrich_track
from app.domain.discovery import (
    TITLE_ALIASES,
    SeedResolution,
    original_hint,
    recording_title,
    resolve_seed,
)
from app.domain.music import (
    ProviderError,
    ProviderResult,
    SearchResult,
    Track,
    normalize_text,
)
from app.observability.events import emit, request_id
from app.providers.base import safe_https_url
from app.providers.registry import ProviderRegistry
from app.repository.feedback import _insert
from app.repository.models import RecordingResolution, VerifiedRecording

PLATFORM_NAMES = {"apple": "itunes", "apple music": "itunes", "itunes": "itunes",
                  "网易云": "netease", "网易云音乐": "netease", "netease": "netease",
                  "qq": "qq", "qq音乐": "qq", "qq music": "qq", "musicbrainz": "musicbrainz",
                  "酷狗": "kugou", "kugou": "kugou", "酷我": "kuwo", "kuwo": "kuwo"}


class ResolutionError(Exception):
    def __init__(self, code, status, message):
        self.code, self.status, self.message = code, status, message
        super().__init__(message)


def parse_song_link(url: str) -> tuple[str, str, str | None] | None:
    if not safe_https_url(url):
        return None
    parsed = urlparse(url)
    if parsed.port not in (None, 443):
        return None
    host, path = parsed.hostname, parsed.path
    if host in {"y.qq.com", "i.y.qq.com"}:
        match = re.fullmatch(r"/n/ryqq/songDetail/([A-Za-z0-9-]{1,30})/?", path)
        identifier = match[1] if match else parse_qs(parsed.query).get("songmid", [""])[0]
        if re.fullmatch(r"[A-Za-z0-9-]{1,30}", identifier):
            return "qq", identifier, None
    if host == "music.163.com":
        fragment = urlparse(parsed.fragment)
        identifier = parse_qs(fragment.query or parsed.query).get("id", [""])[0]
        if (path in {"/song", "/"} and fragment.path in {"", "/song"}
                and re.fullmatch(r"\d{1,20}", identifier)):
            return "netease", identifier, None
    if host == "music.apple.com":
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[0].upper() in {"US", "TW", "HK"} and parts[1] in {"song", "album"}:
            identifier = parse_qs(parsed.query).get("i", [parts[-1] if parts[1] == "song" else ""])[0]
            if re.fullmatch(r"\d{1,20}", identifier):
                return "itunes", identifier, parts[0].upper()
    if host == "musicbrainz.org" and path.startswith("/recording/"):
        try:
            return "musicbrainz", str(UUID(path.removeprefix("/recording/").rstrip("/"))), None
        except ValueError:
            pass
    return None


class RecordingResolver:
    """One worker owns this object; all upstream calls share one deadline and request budget."""

    max_discovery_operations = 24

    def __init__(self, registry: ProviderRegistry, engine: Engine, seed: str, artist: str | None = None, *, manual=False):
        self.registry, self.engine, self.seed, self.artist = registry, engine, seed, artist
        self.deadline = perf_counter() + (30 if manual else 37)
        # Reserve one of the 24 external requests for the optional model call.
        self.max_requests = 6 if manual else 23
        self.manual = manual
        self.attempts: list[SearchAttempt] = []
        self.external_requests = 0
        self.results: list[ProviderResult] = []
        self.cached: dict[tuple, ProviderResult] = {}
        self.regions: dict[tuple[str, str], str | None] = {}
        self.preferred = None
        self.end_reason = "not_found"
        self.memory_checked = False

    @property
    def tracks(self):
        return [track for result in self.results for track in result.tracks]

    @property
    def sources(self):
        sources = {}
        for result in self.results:
            previous = sources.get(result.provider)
            sources[result.provider] = ProviderResult(provider=result.provider,
                tracks=((previous.tracks if previous else []) + result.tracks)[:100],
                error=result.error or (previous.error if previous else None))
        return sources

    def _allowed(self, *, reserve=0):
        if perf_counter() >= self.deadline:
            self.end_reason = "deadline"
            return False
        if self.external_requests >= self.max_requests - reserve:
            self.end_reason = "budget_exhausted"
            return False
        return True

    def _call(self, provider, value, stage, operation="search", limit=25):
        region = getattr(provider, "storefront", None)
        query_key = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
        key = (provider.name, region, operation, query_key if operation == "search" else value)
        if key in self.cached:
            return self.cached[key]
        if not self._allowed():
            return ProviderResult(provider=provider.name)
        self.external_requests += 1
        started = perf_counter()
        try:
            result = (provider.lookup_track(value) if operation == "lookup"
                      else provider.search_recording(self.seed, self.artist, limit)
                      if provider.name == "musicbrainz" and self.artist and stage != "recall"
                      else provider.search_tracks(value[:120], limit))
            # Bound canonical metadata before it reaches UI, persistence or the model context.
            valid = [t for t in result.tracks[:limit] if len(t.title) <= 200 and len(t.artist.name) <= 200
                     and 0 < len(t.source.provider_track_id) <= 200 and t.source.provider == provider.name]
            result = result.model_copy(update={"tracks": valid})
        except Exception:  # noqa: BLE001 - isolate one failed adapter without exposing payloads.
            result = ProviderResult(provider=provider.name,
                error=ProviderError(code="unavailable", message="Catalog temporarily unavailable."))
        self.cached[key] = result
        if perf_counter() >= self.deadline:
            self.end_reason = "deadline"
            result = ProviderResult(provider=provider.name,
                error=ProviderError(code="timeout", message="Recording search deadline reached."))
            self.cached[key] = result
        self.results.append(result)
        for track in result.tracks:
            self.regions[(provider.name, track.source.provider_track_id)] = region
        self.attempts.append(SearchAttempt(platform=provider.name, region=region, stage=stage,
            operation=operation, status="auth_required" if result.error and result.error.code == "auth_required"
            else "error" if result.error else "hit" if result.tracks else "no_results",
            result_count=len(result.tracks), error_code=result.error.code if result.error else None))
        emit("recording_lookup", provider=provider.name, operation=operation, stage=stage,
             status=self.attempts[-1].status, code=self.attempts[-1].error_code,
             latency_ms=round((perf_counter() - started) * 1000, 3))
        return result

    def _match(self):
        return resolve_seed(self.seed, self.tracks, self.artist)

    def _remembered(self):
        if self.memory_checked:
            return
        self.memory_checked = True
        hint = original_hint(self.seed, self.artist)
        titles = {recording_title(self.seed), recording_title(hint[0]) if hint else recording_title(self.seed)}
        with Session(self.engine) as session:
            records = session.scalars(select(VerifiedRecording).where(
                VerifiedRecording.normalized_title.in_(titles), VerifiedRecording.stale.is_(False))
                .order_by(VerifiedRecording.verified_at.desc()).limit(10)).all()
            for row in records:
                if self.artist and row.artist_identity != artist_identity(self.artist):
                    continue
                provider = self.registry.catalog(row.platform, row.region)
                if not provider:
                    continue
                result = self._call(provider, row.recording_id, "memory", "lookup")
                match = resolve_seed(self.seed, result.tracks, self.artist or row.artist_identity)
                if match.track:
                    self.preferred = provider
                    if self.artist:
                        break
                elif not result.error and self._allowed():
                    row.stale = True
            session.commit()

    def search_tracks(self, query: str, limit: int) -> SearchResult:
        self._remembered()
        if query == self.seed and self._match().track:
            return SearchResult(tracks=self.tracks, sources=self.sources)
        providers = self.registry.catalogs()
        if self.preferred:
            providers = [self.preferred, *[p for p in providers if p.name != self.preferred.name]]
        stage = "recall" if self.preferred and query != self.seed else "common"
        for provider in providers:
            self._call(provider, query, stage, limit=limit if stage == "recall" else 25)
            if stage != "recall" and self.artist and self._match().track:
                break
        return SearchResult(tracks=self.tracks, sources=self.sources)

    def _queries(self):
        hint = original_hint(self.seed, self.artist)
        titles = [self.seed, normalize_text(self.seed), *(TITLE_ALIASES.get(hint[0], ()) if hint else ())]
        artists = list(dict.fromkeys([self.artist, *(artist_aliases(self.artist) if self.artist else ())]))[:3]
        # Try title spelling variants before artist aliases so punctuation recovery has a slot.
        queries = [f"{title} {self.artist}" if self.artist else title for title in titles[:3]]
        queries += [f"{self.seed} {artist}" for artist in artists if artist]
        # Keep the exact title query as a fallback even when an artist-qualified search is weak.
        queries.append(self.seed)
        unique = {}
        for query in queries:
            query = query[:120]
            key = " ".join(unicodedata.normalize("NFKC", query).casefold().split())
            unique.setdefault(key, query)
        return list(unique.values())[:5]

    def expand(self, artist: str | None = None) -> SeedResolution:
        if artist:
            self.artist = artist
        for query in self._queries()[:2]:
            if not self._allowed(reserve=4 if not self.manual else 0):
                break
            self.search_tracks(query, 25)
            if self._match().track:
                return self._success()
        extensions = []
        if self.registry.catalog("itunes"):
            extensions += [self.registry.catalog("itunes", region) for region in ("TW", "HK")]
        extensions += self.registry.extensions
        for provider in extensions:
            for query in self._queries()[:2]:
                if not self._allowed(reserve=4 if not self.manual else 0):
                    return self._match()
                self._call(provider, query, "expanded")
                if self._match().track:
                    return self._success()
        self._web()
        return self._success() if self._match().track else self._match()

    def _success(self):
        match = self._match()
        self.end_reason = "matched"
        if match.track:
            self.preferred = self.registry.catalog(match.track.source.provider, self.region(match.track))
        return match

    def _web(self):
        web = self.registry.web_search
        if not web or not self._allowed(reserve=4 if not self.manual else 0):
            return
        self.external_requests += 1
        try:
            links = web.links(self._queries()[0])
            self.attempts.append(SearchAttempt(platform="brave", stage="web", operation="web",
                status="hit" if links else "no_results", result_count=len(links)))
        except Exception:  # noqa: BLE001 - no snippets or credentials in error logs.
            self.attempts.append(SearchAttempt(platform="brave", stage="web", operation="web",
                                              status="error", error_code="upstream_error"))
            return
        for link in links:
            parsed = parse_song_link(link)
            if parsed and (provider := self.registry.catalog(parsed[0], parsed[2])):
                if not self._allowed(reserve=4 if not self.manual else 0):
                    break
                self._call(provider, parsed[1], "web", "lookup")
                if self._match().track:
                    break

    def region(self, track: Track) -> str | None:
        return self.regions.get((track.source.provider, track.source.provider_track_id))

    def issue(self, track: Track) -> str:
        identifier = str(uuid4())
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            session.execute(delete(RecordingResolution).where(RecordingResolution.expires_at < now))
            session.add(RecordingResolution(resolution_id=identifier, seed=self.seed,
                track=track.model_dump(mode="json"), region=self.region(track), expires_at=now + timedelta(minutes=30)))
            session.commit()
        return identifier

    def confirm(self, identifier: str, artist: str | None) -> SeedResolution:
        self.memory_checked = True
        with Session(self.engine) as session:
            row = session.get(RecordingResolution, identifier)
            if not row or row.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
                raise ResolutionError("resolution_expired", 410, "Recording confirmation expired. Search again.")
            old = Track.model_validate(row.track)
            if (normalize_text(row.seed) != normalize_text(self.seed) or not artist
                    or artist_identity(artist) != artist_identity(old.artist.name)):
                raise ResolutionError("resolution_mismatch", 422, "Recording confirmation does not match this query.")
            provider = self.registry.catalog(old.source.provider, row.region)
            if not provider:
                raise ResolutionError("resolution_unavailable", 503, "The verified catalog is unavailable.")
            self.artist = artist
            result = self._call(provider, old.source.provider_track_id, "confirmation", "lookup")
            track = resolve_seed(self.seed, result.tracks, artist).track
            if not track or track.source.provider_track_id != old.source.provider_track_id:
                raise ResolutionError("resolution_unavailable", 503, "The recording could not be reverified. Search again.")
            self.preferred = provider
            self._save(session, track, row.region)
            session.commit()
            return self._success()

    def _save(self, session, track, region):
        values = {"normalized_title": recording_title(track.title), "artist_identity": artist_identity(track.artist.name),
            "platform": track.source.provider, "recording_id": track.source.provider_track_id, "region": region,
            "source_url": track.source.external_url, "track": track.model_dump(mode="json"),
            "verified_at": datetime.now(UTC), "stale": False}
        key = hashlib.sha256(f"{values['normalized_title']}|{values['artist_identity']}|{values['platform']}|"
                             f"{values['recording_id']}|{region}".encode()).hexdigest()
        session.execute(_insert(session, VerifiedRecording).values(knowledge_key=key, **values)
                        .on_conflict_do_update(index_elements=["knowledge_key"], set_=values))

    def report(self) -> SearchReport:
        attempts = list(self.attempts)
        platforms = [(p.name, getattr(p, "storefront", None)) for p in self.registry.catalogs()] + [
            ("itunes", "TW"), ("itunes", "HK"), ("musicbrainz", None), ("kugou", None), ("kuwo", None), ("brave", None)]
        for name, region in platforms:
            if not any(a.platform == name and a.region == region for a in attempts):
                configured = name == "brave" and self.registry.web_search or self.registry.catalog(name, region)
                status = "unavailable" if name in {"kugou", "kuwo"} else "not_executed" if configured else "not_configured"
                attempts.append(SearchAttempt(platform=name, region=region, stage="web" if name == "brave" else "expanded",
                                              status=status))
        reason = self.end_reason
        errors = any(a.status in {"error", "auth_required"} for a in self.attempts)
        if reason == "not_found" and errors:
            reason = "partial_failure"
        emit("recording_resolution", status=reason, result_count=len(self.tracks),
             source_count=len(self.sources), code=reason if reason in {"deadline", "budget_exhausted"} else None)
        return SearchReport(attempts=attempts, end_reason=reason, external_requests=self.external_requests,
                            incomplete=reason in {"deadline", "budget_exhausted", "partial_failure"})

    def resolve(self, *, platform: str | None = None, song_url: str | None = None) -> RecordingResolveResponse:
        status = None
        if song_url:
            try:
                parsed = parse_song_link(song_url)
            except ValueError:
                parsed = None
            name = PLATFORM_NAMES.get((platform or "").casefold())
            if not parsed or (platform and name != parsed[0]):
                self.end_reason = status = "unsupported_platform"
                self.attempts.append(SearchAttempt(platform=name or "unsupported_link", stage="manual",
                    operation="lookup", status="not_executed", error_code="unsupported_platform"))
            else:
                provider = self.registry.catalog(parsed[0], parsed[2])
                if provider:
                    self._call(provider, parsed[1], "manual", "lookup")
                else:
                    self.end_reason = status = "unavailable"
        elif platform:
            name = PLATFORM_NAMES.get(platform.casefold())
            provider = self.registry.catalog(name) if name else None
            if not name:
                self.end_reason = status = "unsupported_platform"
                self.attempts.append(SearchAttempt(platform=platform, stage="manual", status="not_executed",
                                                  error_code="unsupported_platform"))
            elif not provider:
                self.end_reason = status = "unavailable"
                self.attempts.append(SearchAttempt(platform=name, stage="manual", status="unavailable"))
            else:
                for query in self._queries():
                    self._call(provider, query, "manual")
                    if self._match().track or not self._allowed():
                        break
        else:
            self._remembered()
            if not self._match().track:
                self.expand()
        match = self._match()
        if match.track:
            self._success()
            status = "matched"
        elif not status:
            status = "ambiguous" if match.candidates else "incomplete" if self.report().incomplete else "not_found"
            if status == "ambiguous":
                self.end_reason = "ambiguous"
        track = enrich_track(match.track) if match.track else None
        return RecordingResolveResponse(request_id=request_id(), status=status,
            matched_track=track, resolution_id=self.issue(track) if track else None,
            candidates=[ResolvedChoice(track=enrich_track(t), resolution_id=self.issue(t)) for t in match.candidates[:5]],
            search_report=self.report(), sources=self.sources)
