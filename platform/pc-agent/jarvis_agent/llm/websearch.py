"""Web arama — Özellik 1 doğrulama katmanı.

Sağlayıcı seçimi (.env):
- JARVIS_SEARCH_PROVIDER = duckduckgo (varsayılan, anahtar gerekmez) | serpapi
- JARVIS_SERPAPI_KEY      → serpapi seçilmişse zorunlu

DuckDuckGo: önce ``duckduckgo-search`` paketi denenir; kurulu değilse
httpx ile HTML "lite" ucu kazınır (ek bağımlılık zorunluluğu yok).
Her hata zarif biçimde işlenir: ağ yoksa {"error": "offline"}, sonuç yoksa
{"results": []} döner — arama arızası asla sohbeti bozmaz.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx

from .. import config

logger = logging.getLogger("jarvis.llm.websearch")

MAX_RESULTS = 3  # hız/token dengesi (Özellik 1.4)
_TIMEOUT = 8.0

# duckduckgo-search paketi opsiyoneldir:
try:  # pragma: no cover - paket varlığı ortama bağlı
    from duckduckgo_search import DDGS  # type: ignore

    _DDGS_AVAILABLE = True
except Exception:  # noqa: BLE001
    DDGS = None  # type: ignore[assignment]
    _DDGS_AVAILABLE = False

_DDGS_OFFLINE = ("offline",)


def _offline(reason: str = "offline") -> dict[str, Any]:
    return {"results": [], "provider": "", "error": reason}


def _provider_choice() -> str:
    return (config.env("JARVIS_SEARCH_PROVIDER", "duckduckgo") or "duckduckgo").lower()


# ── SerpAPI ──────────────────────────────────────────────────────────────────
def _search_serpapi(query: str, max_results: int) -> dict[str, Any]:
    api_key = config.env("JARVIS_SERPAPI_KEY") or config.env("SERPAPI_KEY")
    if not api_key:
        return _offline("no_serpapi_key")
    try:
        resp = httpx.get(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "api_key": api_key},
            timeout=_TIMEOUT,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError):
        return _offline("offline")
    except httpx.HTTPError as exc:
        logger.warning("SerpAPI isteği başarısız: %s", exc)
        return _offline("network_error")
    if resp.status_code != 200:
        logger.warning("SerpAPI HTTP %s", resp.status_code)
        return _offline("http_error")
    try:
        organic = resp.json().get("organic_results") or []
    except ValueError:
        return _offline("parse_error")
    results = [
        {
            "title": str(item.get("title") or "").strip(),
            "url": str(item.get("link") or "").strip(),
            "snippet": str(item.get("snippet") or "").strip(),
        }
        for item in organic[:max_results]
    ]
    return {"results": results, "provider": "serpapi", "error": ""}


# ── DuckDuckGo (paketsiz httpx yedeği) ───────────────────────────────────────
_A_TAG_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL
)
_SNIPPET_RE = re.compile(
    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(raw: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", raw or "")).strip()


def _search_ddgo_httpx(query: str, max_results: int) -> dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JARVIS-Assistant/1.0)"}
    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError):
        return _offline("offline")
    except httpx.HTTPError as exc:
        logger.warning("DuckDuckGo isteği başarısız: %s", exc)
        return _offline("network_error")
    if resp.status_code != 200:
        return _offline("http_error")
    html = resp.text
    titles = _A_TAG_RE.findall(html)
    snippets = _SNIPPET_RE.findall(html)
    results: list[dict[str, Any]] = []
    for i, (href, title) in enumerate(titles[:max_results]):
        url = href
        # DuckDuckGo yönlendirme bağlantılarını gerçek adrese çevir.
        m = re.search(r"uddg=([^&]+)", url)
        if m:
            from urllib.parse import unquote

            url = unquote(m.group(1))
        snippet = _clean_html(snippets[i]) if i < len(snippets) else ""
        results.append(
            {"title": _clean_html(title), "url": url, "snippet": snippet}
        )
    return {"results": results, "provider": "duckduckgo", "error": ""}


def _search_ddgo(query: str, max_results: int) -> dict[str, Any]:
    if _DDGS_AVAILABLE:
        try:
            raw = DDGS().text(query, max_results=max_results)  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001 — kütüphane ağ hatası da fırlatabilir
            message = str(exc).lower()
            if any(flag in message for flag in _DDGS_OFFLINE):
                return _offline("offline")
            logger.warning("duckduckgo-search hatası, httpx yedeğine geçiliyor: %s", exc)
            return _search_ddgo_httpx(query, max_results)
        results = [
            {
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("href") or item.get("url") or "").strip(),
                "snippet": str(item.get("body") or item.get("snippet") or "").strip(),
            }
            for item in (raw or [])[:max_results]
        ]
        return {"results": results, "provider": "duckduckgo", "error": ""}
    return _search_ddgo_httpx(query, max_results)


def web_search(query: str, max_results: Optional[int] = None) -> dict[str, Any]:
    """Metin araması yapar; {'results': [{title,url,snippet}...]} döndürür.

    Zaman uyumsuz katman (execute_tool) ``asyncio.to_thread`` ile çağırır.
    """
    q = (query or "").strip()
    if not q:
        return {"results": [], "provider": "", "error": "empty_query"}
    limit = max(1, min(int(max_results or MAX_RESULTS), 10))
    provider_name = _provider_choice()
    if provider_name == "serpapi":
        return _search_serpapi(q, limit)
    return _search_ddgo(q, limit)
