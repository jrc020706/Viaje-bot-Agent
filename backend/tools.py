"""
Tools de LangChain para ViajeBot
"""

import requests
from functools import lru_cache
from langchain_core.tools import tool

from config import COLOMBIA_RAG_TERMS
from utils import _retry, _ddg_text_search, _contains_any
from rag import get_rag_retriever
from image_utils import search_destination_images


# ---------------------------------------------------------------------------
# Tool 1 — Web Search (DuckDuckGo, free, no API key)
# ---------------------------------------------------------------------------
@tool
def web_search(query: str) -> str:
    """
    Search the web for real-time travel information: flights, hotels,
    destinations, visa requirements, travel news, events, and weather.
    Use whenever the user needs current or up-to-date travel details.

    Args:
        query: Search query string.
    """
    try:
        results = _retry(lambda: _ddg_text_search(query, max_results=4))
        if not results:
            return "No search results found."
        lines = []
        for r in results:
            lines.append(f"**{r['title']}**\n{r['body']}\nSource: {r['href']}")
        return "\n\n".join(lines)
    except Exception as exc:
        return f"Search error: {exc}"


# ---------------------------------------------------------------------------
# Tool 2 — Currency Converter (open.er-api.com, free, no API key)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=64)
def _currency_rates(from_currency: str) -> dict:
    url = f"https://open.er-api.com/v6/latest/{from_currency.upper()}"
    resp = _retry(lambda: requests.get(url, timeout=10))
    return resp.json()


@tool
def currency_converter(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Convert monetary amounts between any two world currencies in real time.
    Essential for travelers to understand costs in their local currency
    or the destination currency.

    Args:
        amount: Numeric amount to convert.
        from_currency: ISO 4217 source code (e.g. 'USD', 'EUR', 'COP').
        to_currency: ISO 4217 target code (e.g. 'COP', 'USD', 'GBP').
    """
    try:
        source = from_currency.upper()
        data = _currency_rates(source)
        if data.get("result") != "success":
            return "Could not retrieve exchange rates. Please try again later."
        rates = data.get("rates", {})
        target = to_currency.upper()
        if target not in rates:
            return (
                f"Currency code '{to_currency}' not recognized. "
                "Use standard codes like USD, EUR, COP, GBP, MXN, BRL."
            )
        converted = amount * rates[target]
        rate = rates[target]
        return (
            f"💱 Currency Conversion\n"
            f"  {amount:,.2f} {source} → {converted:,.2f} {target}\n"
            f"  Rate: 1 {source} = {rate:,.4f} {target}\n"
            f"  Source: open.er-api.com"
        )
    except Exception as exc:
        return f"Conversion error: {exc}"


# ---------------------------------------------------------------------------
# Tool 3 — Travel Knowledge Base (RAG)
# ---------------------------------------------------------------------------
@tool
def travel_knowledge(query: str) -> str:
    """
    Retrieve specialized knowledge about Colombia tourism, national parks,
    cultural destinations, cuisine, and travel tips from the knowledge base.
    Use this for Colombia-specific questions before doing a web search.

    Args:
        query: Travel topic or destination to look up.
    """
    rag_retriever = get_rag_retriever()
    if rag_retriever is None:
        return "Knowledge base unavailable. Use web_search instead."
    if not _contains_any(query, COLOMBIA_RAG_TERMS):
        return "The RAG knowledge base only covers Colombia tourism. Use web_search or general travel knowledge for this destination."
    try:
        return _cached_travel_knowledge(query)
    except Exception as exc:
        return f"Retrieval error: {exc}"


@lru_cache(maxsize=128)
def _cached_travel_knowledge(query: str) -> str:
    rag_retriever = get_rag_retriever()
    docs = _retry(lambda: rag_retriever.invoke(query))
    if not docs:
        return "No relevant information found in the knowledge base."
    return "\n\n---\n\n".join(d.page_content[:450] for d in docs)


# ---------------------------------------------------------------------------
# Tool 4 — Place Image Search
# ---------------------------------------------------------------------------
@tool
def place_image_search(query: str) -> str:
    """
    Search for images of travel destinations, landmarks, countries, cities,
    beaches, parks, and lesser-known places when the user asks for photos,
    images, gallery, or visual references.

    Args:
        query: Destination, country, city, landmark, or place name.
    """
    images = search_destination_images(query, max_results=5)
    if not images:
        return "No image results found for that destination."
    return f"[INTERNAL DATA] I found {len(images)} images for '{query}'. (Note: Inform the user and mention the gallery below, but DO NOT print these URLs manually): " + ", ".join(images)
