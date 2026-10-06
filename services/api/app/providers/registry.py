import logging
from functools import lru_cache
from time import perf_counter

from app.domain.music import (
    ProviderCapabilities,
    ProviderError,
    ProviderHealth,
    ProviderResult,
    SearchResult,
)
from app.infrastructure.config import get_settings
from app.observability.events import emit
from app.providers.base import MAX_RESULTS, MusicProvider
from app.providers.itunes import ITunesProvider
from app.providers.netease import NetEaseProvider
from app.providers.qq import QQProvider


class ProviderRegistry:
    def __init__(self, providers: list[MusicProvider]) -> None:
        names = [provider.name for provider in providers]
        if len(names) != len(set(names)):
            raise ValueError("duplicate provider name")
        self._providers = dict(zip(names, providers, strict=True))

    def capabilities(self) -> list[ProviderCapabilities]:
        return [provider.capabilities() for provider in self._providers.values()]

    def health(self) -> dict[str, ProviderHealth]:
        return {name: provider.health() for name, provider in self._providers.items()}

    def for_storefront(self, storefront: str) -> "ProviderRegistry":
        """Request-local Apple region; retain configured sources and offline mode."""
        if storefront not in {"TW", "HK"}:
            raise ValueError("Unsupported verification storefront")
        return ProviderRegistry([
            ITunesProvider(client=provider.client, storefront=storefront)
            if isinstance(provider, ITunesProvider) else provider
            for provider in self._providers.values()
        ])

    def search_tracks(self, query: str, limit: int) -> SearchResult:
        if not query.strip() or not 1 <= limit <= MAX_RESULTS:
            raise ValueError("invalid search query or limit")
        sources: dict[str, ProviderResult] = {}
        tracks = []
        # Sequential calls bound upstream concurrency to one. Every adapter has its own timeout.
        for name, provider in self._providers.items():
            started = perf_counter()
            try:
                result = provider.search_tracks(query, limit)
            except Exception:  # noqa: BLE001 - isolate a broken third-party adapter.
                error = ProviderError(code="unavailable", message=f"{name} provider unavailable.")
                result = ProviderResult(provider=name, error=error)
            sources[name] = result
            tracks.extend(result.tracks[:limit])
            emit("provider_call", provider=name, operation="search_tracks",
                 status="error" if result.error else "ok", code=result.error.code if result.error else None,
                 result_count=len(result.tracks[:limit]), latency_ms=round((perf_counter() - started) * 1000, 3),
                 level=logging.WARNING if result.error else logging.INFO)
        return SearchResult(tracks=tracks, sources=sources)


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    if not get_settings().enable_music_providers:
        return ProviderRegistry([])
    providers: list[MusicProvider] = [ITunesProvider(), NetEaseProvider()]
    if get_settings().enable_qq_provider:
        providers.append(QQProvider())
    return ProviderRegistry(providers)
