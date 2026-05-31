"""
Funciones de búsqueda de imágenes para destinos turísticos
"""

import re
import requests
from functools import lru_cache
from urllib.parse import unquote

from config import IMAGE_SEARCH_ALIASES
from utils import _retry, _ddg_image_search, _clean_destination_name, _get_image_search_variants


@lru_cache(maxsize=256)
def _cached_destination_images(query: str, max_results: int = 6) -> tuple[str, ...]:
    """
    Busca imágenes de destinos usando DuckDuckGo Images.
    Retorna URLs directas de thumbnails/imágenes adecuadas para galerías del frontend.
    """
    cleaned = _clean_destination_name(query)
    if not cleaned:
        return []

    variants = _get_image_search_variants(cleaned)
    try:
        for variant in variants:
            search_query = f"{variant} tourism city landmark"
            results = _retry(lambda: _ddg_image_search(search_query, max_results=max_results))
            images: list[str] = []
            for result in results:
                url = result.get("image") or result.get("thumbnail")
                if (
                    url
                    and url.startswith(("http://", "https://"))
                    and not _is_non_travel_image_url(url)
                    and url not in images
                ):
                    images.append(url)
            if images:
                return tuple(images[:max_results])
    except Exception:
        pass

    for variant in variants:
        images = _wikimedia_destination_images(variant, max_results=max_results)
        if images:
            return tuple(images)

    return tuple()


def search_destination_images(query: str, max_results: int = 6) -> list[str]:
    """Busca imágenes de un destino y retorna una lista de URLs."""
    return list(_cached_destination_images(query, max_results))


@lru_cache(maxsize=256)
def _wikimedia_destination_images(query: str, max_results: int = 6) -> list[str]:
    """Búsqueda alternativa de imágenes a través de Wikipedia/Wikimedia Commons."""
    queries = []
    normalized = query.lower().strip()
    alias = IMAGE_SEARCH_ALIASES.get(normalized)
    if alias:
        queries.append(alias)
    if query not in queries:
        queries.append(query)

    try:
        session = requests.Session()
        headers = {"User-Agent": "ViajeBot/1.0 travel assistant"}

        for search_query in queries:
            search_resp = _retry(lambda: session.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": search_query,
                    "format": "json",
                    "srlimit": 1,
                },
                headers=headers,
                timeout=10,
            ))
            search_resp.raise_for_status()
            search_items = search_resp.json().get("query", {}).get("search", [])
            title = search_items[0]["title"] if search_items else search_query

            page_resp = _retry(lambda: session.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": title,
                    "prop": "pageimages|images",
                    "pithumbsize": 900,
                    "imlimit": 25,
                    "format": "json",
                },
                headers=headers,
                timeout=10,
            ))
            page_resp.raise_for_status()
            pages = page_resp.json().get("query", {}).get("pages", {})

            images: list[str] = []
            file_titles: list[str] = []
            for page in pages.values():
                thumbnail = page.get("thumbnail", {}).get("source")
                if thumbnail and not _is_non_travel_image_url(thumbnail):
                    images.append(thumbnail)
                for item in page.get("images", []):
                    file_title = item.get("title", "")
                    lower = file_title.lower()
                    if any(skip in lower for skip in ("flag", "coat of arms", "map", "icon", ".svg", ".ogg", ".pdf")):
                        continue
                    file_titles.append(file_title)

            for file_title in file_titles[:12]:
                info_resp = _retry(lambda: session.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "titles": file_title,
                        "prop": "imageinfo",
                        "iiprop": "url",
                        "iiurlwidth": 900,
                        "format": "json",
                    },
                    headers=headers,
                    timeout=10,
                ))
                info_resp.raise_for_status()
                info_pages = info_resp.json().get("query", {}).get("pages", {})
                for info_page in info_pages.values():
                    for info in info_page.get("imageinfo", []):
                        url = info.get("thumburl") or info.get("url")
                        if url and url.startswith(("http://", "https://")) and not _is_non_travel_image_url(url):
                            url = unquote(url)
                            if url not in images:
                                images.append(url)
                        if len(images) >= max_results:
                            return images[:max_results]

            if images:
                return images[:max_results]

        return []
    except Exception:
        return []


@lru_cache(maxsize=256)
def fetch_destination_summary(query: str) -> str:
    """Obtiene un resumen enciclopédico corto de un destino para respuestas de fallback."""
    cleaned_query = re.sub(r"\s+", " ", query).strip()
    if not cleaned_query:
        return ""
    wiki_title = IMAGE_SEARCH_ALIASES.get(cleaned_query.lower(), cleaned_query)
    wiki_title = wiki_title.replace(" ", "_")
    try:
        resp = _retry(lambda: requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_title}",
            headers={"User-Agent": "ViajeBot/1.0 travel assistant"},
            timeout=10,
        ))
        if resp.status_code != 200:
            return ""
        data = resp.json()
        extract = data.get("extract", "")
        if not extract:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", extract)
        return " ".join(sentences[:2]).strip()
    except Exception:
        return ""


def _is_non_travel_image_url(url: str) -> bool:
    """Filtra URLs de imágenes que no son relevantes para turismo (banderas, mapas, escudos, etc.)."""
    lower = unquote(url).lower()
    blocked = (
        "flag_of",
        "coat_of_arms",
        "emblem",
        "location_map",
        "relief_location_map",
        "topo",
        "blank_map",
        "wikimedia-logo",
        ".svg",
        ".png/960px-flag",
    )
    return any(term in lower for term in blocked)
