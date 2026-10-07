"""Optional web clues; only catalog detail lookup can turn a URL into a recording."""

import re
from html import unescape

from app.domain.music import WebClue
from app.providers.base import (
    HTTPMusicProvider,
    optional_object,
    require_list,
    safe_https_url,
)


class BraveSearch(HTTPMusicProvider):
    name = "brave"

    def __init__(self, api_key, client=None):
        super().__init__(client)
        self._api_key = api_key

    def search(self, query: str) -> list[WebClue]:
        payload = self._request("GET", "https://api.search.brave.com/res/v1/web/search",
            params={"q": query[:120], "count": 5},
            headers={"X-Subscription-Token": self._api_key.get_secret_value(), "Accept": "application/json"})
        clues = []
        for raw in require_list(optional_object(payload.get('web')).get('results', []))[:5]:
            item = optional_object(raw)
            url = safe_https_url(item.get('url'))
            if not url or len(url) > 2000:
                continue
            def text(key, limit, item=item):
                value = item.get(key)
                return unescape(re.sub(r'<[^>]*>', '', value))[:limit] if isinstance(value, str) else ''
            clues.append(WebClue(title=text('title', 200), url=url, description=text('description', 700)))
        return clues

    def links(self, query: str) -> list[str]:
        return [clue.url for clue in self.search(query)]
