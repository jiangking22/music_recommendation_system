"""Optional web clues; only catalog detail lookup can turn a URL into a recording."""

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

    def links(self, query: str) -> list[str]:
        payload = self._request("GET", "https://api.search.brave.com/res/v1/web/search",
            params={"q": query[:120], "count": 5},
            headers={"X-Subscription-Token": self._api_key.get_secret_value(), "Accept": "application/json"})
        return [url for item in require_list(optional_object(payload.get("web")).get("results", []))[:5]
                if (url := safe_https_url(optional_object(item).get("url")))]
