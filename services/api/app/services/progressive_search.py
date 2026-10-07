"""Deterministic staged recall; every outbound operation shares one deadline and budget."""
import asyncio
from time import perf_counter

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.attribute_assistance import infer_attributes
from app.agent.schemas import AgentSearchReport, RecommendInput, WebReference
from app.api.schemas import RecommendationItem, SearchAttempt
from app.domain.artist_names import enrich_track
from app.domain.discovery import resolve_seed
from app.domain.listening import AttributeEvidence
from app.domain.music import ProviderError, ProviderResult, normalize_text
from app.domain.pipeline import deduplicate, rank, rerank_diverse
from app.infrastructure.workers import run_blocking
from app.observability.events import emit
from app.providers.base import safe_https_url
from app.services.recommendation import local_catalog
from app.services.recording_resolution import parse_song_link

SEARCH_SECONDS = 45
MAX_OPERATIONS = 24


class SongClue(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    title: str = Field(min_length=1, max_length=120)
    artist: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=2000)


class SongClues(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    songs: list[SongClue] = Field(default_factory=list, max_length=5)

class SearchBudget:
    def __init__(self):
        self.deadline = perf_counter() + SEARCH_SECONDS
        self.count = 0
        self.end_reason = None

    async def call(self, operation):
        if self.count >= MAX_OPERATIONS:
            self.end_reason = 'budget_exhausted'
            return None
        remaining = self.deadline - perf_counter()
        if remaining <= 0:
            self.end_reason = 'deadline'
            return None
        self.count += 1
        try:
            async with asyncio.timeout(remaining):
                return await run_blocking(operation)
        except TimeoutError:
            self.end_reason = 'deadline'
            return None
        except Exception:  # noqa: BLE001 - isolate upstream failures, never log raw messages.
            emit('progressive_search', status='error', code='upstream_unavailable')
            return None

    async def attributes(self, provider, tracks, constraints, snippets):
        if not tracks or provider.name == 'local' or not hasattr(provider, 'assess_attributes'):
            return []
        if self.count >= MAX_OPERATIONS:
            self.end_reason = 'budget_exhausted'
            return []
        remaining = self.deadline - perf_counter()
        if remaining <= 0:
            self.end_reason = 'deadline'
            return []
        self.count += 1
        return await infer_attributes(provider, tracks, constraints, timeout=min(10, remaining), clues=snippets)


def qualifying(context):
    constraints = context.conversation.constraints
    if context.pool.intent == 'song' and not context.pool.seed_track:
        return []
    return [item for item in context.pool.ranked(context.profile)
            if constraints.matches(item.track, context.pool.evidence)
            and (not context.more or item.key not in context.pool.shown)]


def query_variants(context, args):
    seed = context.pool.seed
    constraints = context.conversation.constraints
    base = ' '.join(seed.split()[:5])[:120]
    # Short theme/artist queries; constraints are verified after recall, not concatenated prose.
    variants = [base, *args.queries]
    if context.pool.intent == 'theme':
        if constraints.language == 'zh' or constraints.vocals == 'vocal':
            variants += ['华语抒情', '舒缓民谣'] if 'calm' in seed or '慢' in seed else [f'{base} 华语', f'{base} vocal']
        elif constraints.vocals == 'instrumental':
            variants += [f'{base} instrumental', 'piano']
        else:
            variants += [f'{base} music', f'{base} songs']
    else:
        variants += [f'{base} song', f'{base} recording']
    unique = {}
    for query in variants:
        query = query[:120].strip()
        unique.setdefault(normalize_text(query), query)
    return list(unique.values())


def add_result(context, result):
    tracks = [t for t in result.tracks[:25] if len(t.title) <= 200 and len(t.artist.name) <= 200
              and len(t.canonical_key) <= 450 and len(t.source.provider_track_id) <= 200
              and t.source.provider == result.provider]
    tracks = [t.model_copy(update={'tags': [v[:60] for v in t.tags[:10]],
        'genres': [v[:60] for v in t.genres[:10]], 'language': t.language[:32] if t.language else None,
        'artwork_url': t.artwork_url if t.artwork_url and len(t.artwork_url) <= 2000 else None}) for t in tracks]
    canonical = result.model_copy(update={'tracks': tracks})
    context.pool.merge(rank(deduplicate(tracks), context.pool.seed, context.profile), {result.provider: canonical})
    return len(tracks)


def render(context):
    songs = rerank_diverse(qualifying(context), context.requested)
    context.candidates = context.pool.ranked(context.profile)
    context.items = [RecommendationItem(id=s.key, title=s.track.title, artist=s.track.artist.name,
        explanation=s.explanation, track=enrich_track(s.track), score=s.score,
        score_breakdown=s.score_breakdown, provenance=list(s.provenance),
        attribute_evidence=[e for e in context.pool.evidence if e.track_id == s.track.canonical_key][:10]) for s in songs]
    context.sources = context.pool.sources
    context.conversation.recommendation_context = [
        {'title': i.title, 'artist': i.artist, 'explanation': i.explanation, 'score_breakdown': i.score_breakdown}
        for i in context.items]


async def progressive_recommendation(call, context, provider, output):
    args = RecommendInput.model_validate(call.arguments)
    pool, constraints = context.pool, context.conversation.constraints
    budget = SearchBudget()
    report = AgentSearchReport(requested=context.requested, returned=0,
        reused=bool(pool.candidates), web_search='not_needed' if getattr(context.registry, 'web_search', None) else 'not_configured')
    yield {'stage': 'filtering', 'label': '筛选已有歌曲'}
    attempted_attributes = set()
    snippets = []

    async def supplement():
        unknown = [t for t in pool.candidates if t.source.provider != 'fixture'
                   and t.canonical_key not in attempted_attributes and constraints.assess(t, pool.evidence) == 'unknown']
        batch = list({t.canonical_key: t for t in unknown}.values())[:20]
        attempted_attributes.update(t.canonical_key for t in batch)
        evidence = await budget.attributes(provider, batch, constraints, snippets)
        pool.evidence = (pool.evidence + evidence)[-450:]

    if len(qualifying(context)) < context.requested:
        await supplement()
    queries = query_variants(context, args)
    catalogs = context.registry.catalogs() if hasattr(context.registry, 'catalogs') else []
    ambiguous = None
    tried = set()
    for round_number in range(3):
        if len(qualifying(context)) >= context.requested or budget.end_reason:
            break
        pending = [q for q in queries if normalize_text(q) not in tried]
        pending.sort(key=lambda q: f'query:{normalize_text(q)}' in pool.queries)
        if not pending:
            break
        query = pending[0]
        tried.add(normalize_text(query))
        pool.queries = [*pool.queries, f'query:{normalize_text(query)}'][-60:]
        report.expanded |= round_number > 0 or report.reused
        yield {'stage': 'catalog_search', 'label': '扩大音乐平台检索'}
        providers = list(catalogs)
        if round_number > 0 and constraints.language == 'zh' and hasattr(context.registry, 'catalog'):
            providers += [p for region in ('TW', 'HK') if (p := context.registry.catalog('itunes', region))]
        if not providers and not hasattr(context.registry, 'catalogs'):
            result = await budget.call(lambda query=query: context.registry.search_tracks(query, 25))
            if result:
                for source in result.sources.values():
                    add_result(context, source)
                for name in {t.source.provider for t in result.tracks} - result.sources.keys():
                    add_result(context, ProviderResult(provider=name,
                        tracks=[t for t in result.tracks if t.source.provider == name]))
            report.attempts.append(SearchAttempt(platform='catalog', stage='recall',
                status='hit' if result and result.tracks else 'no_results', result_count=len(result.tracks) if result else 0))
        for catalog in providers:
            if len(qualifying(context)) >= context.requested or budget.end_reason:
                break
            try:
                result = await budget.call(lambda catalog=catalog, query=query: catalog.search_tracks(query, 25))
            except Exception:  # noqa: BLE001 - safe adapter boundary, never expose payload/errors.
                result = ProviderResult(provider=catalog.name, error=ProviderError(code='unavailable', message='Catalog unavailable.'))
            if result is None:
                if budget.end_reason:
                    break
                result = ProviderResult(provider=catalog.name,
                    error=ProviderError(code='unavailable', message='Catalog unavailable.'))
            count = add_result(context, result)
            report.attempts.append(SearchAttempt(platform=catalog.name, region=getattr(catalog, 'storefront', None),
                stage='recall' if round_number == 0 else 'expanded', status='error' if result.error else 'hit' if count else 'no_results',
                result_count=count, error_code=result.error.code if result.error else None))
            emit('provider_call', provider=catalog.name, operation='search_tracks',
                 status='error' if result.error else 'ok', result_count=count, code=result.error.code if result.error else None)
        if pool.intent in ('song', 'auto') and not pool.seed_track:
            resolution = resolve_seed(pool.seed, pool.candidates)
            if resolution.status == 'ambiguous':
                ambiguous = resolution
                break
            pool.seed_track = resolution.track
            if pool.seed_track:
                queries += [pool.seed_track.artist.name, *pool.seed_track.genres[:1]]
        if round_number == 0 and not any(constraints.model_dump().values()) and pool.intent != 'song' and not pool.seed_track:
            pool.merge(rank(deduplicate(local_catalog()), pool.seed, context.profile), {})
        yield {'stage': 'verifying', 'label': '核实歌曲信息'}
        await supplement()
    # Optional identity/metadata source; exact recording title and artist must agree.
    if len(qualifying(context)) < context.requested and not budget.end_reason and not ambiguous:
        extensions = getattr(context.registry, 'extensions', [])
        for track in pool.candidates[:3]:
            if len(qualifying(context)) >= context.requested or budget.end_reason:
                break
            if track.source.provider == 'fixture' or constraints.assess(track, pool.evidence) != 'unknown':
                continue
            for catalog in extensions[:1]:
                yield {'stage': 'verifying', 'label': '核实歌曲信息'}
                result = await budget.call(lambda catalog=catalog, track=track:
                    catalog.search_recording(track.title, track.artist.name, 3))
                if result:
                    for found in result.tracks:
                        if normalize_text(found.title) != normalize_text(track.title) or normalize_text(found.artist.name) != normalize_text(track.artist.name):
                            continue
                        labels = {normalize_text(v) for v in (*found.tags, *found.genres)}
                        if 'instrumental' in labels:
                            pool.evidence.append(AttributeEvidence(track_id=track.canonical_key, attribute='vocals',
                                value='instrumental', origin='provider', basis='Recording metadata: instrumental',
                                source_url=safe_https_url(found.source.external_url)))
    web = getattr(context.registry, 'web_search', None)
    for web_round in range(2):
        if len(qualifying(context)) >= context.requested or budget.end_reason or ambiguous or not web:
            break
        report.expanded = True
        yield {'stage': 'web_search', 'label': '搜索网页线索'}
        report.web_search = 'used'
        query = f'{pool.seed} 歌曲 歌手' if web_round == 0 else f'{pool.seed} 推荐 音乐'
        try:
            clues = await budget.call(lambda query=query: web.search(query))
        except Exception:  # noqa: BLE001 - no external messages/private content in logs.
            clues = []
            report.web_search = 'error'
        report.attempts.append(SearchAttempt(platform='brave', stage='web', operation='web',
            status='error' if report.web_search == 'error' else 'hit' if clues else 'no_results', result_count=len(clues or [])))
        snippets = [clue.model_dump() for clue in clues or []]
        suggestions = []
        extractor = getattr(provider, 'extract_web_clues', None)
        if clues and extractor and provider.name != 'local' and budget.count < MAX_OPERATIONS and not budget.end_reason:
            budget.count += 1
            try:
                async with asyncio.timeout(max(.01, min(10, budget.deadline - perf_counter()))):
                    suggestions = SongClues.model_validate(await extractor({'clues': snippets})).songs
                allowed = {clue.url for clue in clues}
                suggestions = [s for s in suggestions if s.source_url in allowed]
            except (httpx.HTTPError, ValidationError, ValueError, TypeError, TimeoutError):
                suggestions = []
        for clue in clues or []:
            if len(qualifying(context)) >= context.requested or budget.end_reason:
                break
            parsed = parse_song_link(clue.url)
            hits = []
            yield {'stage': 'verifying', 'label': '核实歌曲信息'}
            if parsed and hasattr(context.registry, 'catalog'):
                catalog = context.registry.catalog(parsed[0], parsed[2])
                if catalog:
                    result = await budget.call(lambda catalog=catalog, parsed=parsed: catalog.lookup_track(parsed[1]))
                    if result and not result.error:
                        hits = [t for t in result.tracks if t.source.provider_track_id == parsed[1]]
                        add_result(context, result.model_copy(update={'tracks': hits}))
            elif catalogs:
                # Search a bounded title clue; never fetch the page or accept invented recording IDs.
                for catalog in catalogs[:2]:
                    suggested = next((s for s in suggestions if s.source_url == clue.url), None)
                    title_query = f'{suggested.title} {suggested.artist}'[:120] if suggested else clue.title[:120]
                    result = await budget.call(lambda catalog=catalog, title_query=title_query: catalog.search_tracks(title_query, 5))
                    if result:
                        text = normalize_text(clue.title + ' ' + clue.description)
                        matched = [t for t in result.tracks if normalize_text(t.title) in text and normalize_text(t.artist.name) in text
                                   and (not suggested or (normalize_text(t.title) == normalize_text(suggested.title)
                                   and normalize_text(t.artist.name) == normalize_text(suggested.artist)))]
                        hits.extend(matched)
                        add_result(context, result.model_copy(update={'tracks': matched}))
                    if hits or budget.end_reason:
                        break
            if hits and safe_https_url(clue.url):
                context.web_references.append(WebReference(title=clue.title, url=clue.url,
                    track_ids=[t.canonical_key for t in hits][:25]))
            await supplement()
    if ambiguous:
        context.items = []
        output.update(seed_status='ambiguous', seed_candidates=[{'title': t.title, 'artist': t.artist.name}
            for t in ambiguous.candidates[:5]])
        report.end_reason = 'ambiguous'
    elif pool.intent == 'song' and not pool.seed_track:
        context.items = []
        report.end_reason = budget.end_reason or 'insufficient_matches'
    else:
        render(context)
        unknown = any(constraints.assess(t, pool.evidence) == 'unknown' for t in pool.candidates)
        failed = any(s.error for s in pool.sources.values())
        report.end_reason = ('enough' if len(context.items) >= context.requested else budget.end_reason
            or ('insufficient_evidence' if unknown else 'upstream_failure' if failed else 'insufficient_matches'))
    report.returned = len(context.items)
    report.external_requests = budget.count
    context.search_report = report
    emit('recommendation', candidate_count=len(pool.candidates), result_count=report.returned,
         source_count=len(pool.sources), failed_sources=sum(bool(s.error) for s in pool.sources.values()),
         personalized=True, latency_ms=round((SEARCH_SECONDS - max(0, budget.deadline - perf_counter())) * 1000, 3))
    pool.shown = list(dict.fromkeys([*pool.shown, *(i.id for i in context.items)]))[-500:]
    pool.save(context.conversation)
    context.sources = pool.sources
    output.update(items=[{'title': i.title, 'artist': i.artist, 'explanation': i.explanation,
        'language': i.track.language, 'genres': i.track.genres[:5], 'tags': i.track.tags[:5],
        'attribute_evidence': [e.model_dump() for e in i.attribute_evidence]} for i in context.items],
        search_report=report.model_dump(), web_references=[r.model_dump() for r in context.web_references],
        partial_sources=any(s.error for s in pool.sources.values()))
    if context.items:
        output.pop('empty_reason', None)
        output.pop('seed_status', None)
        output.pop('seed_candidates', None)
    yield {'output': output}
