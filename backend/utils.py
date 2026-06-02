"""
General utility functions for ViajeBot
"""

import re
import requests
from langdetect import detect_langs, LangDetectException

from config import (
    TRAVEL_KEYWORDS,
    KNOWN_DESTINATIONS,
    IMAGE_SEARCH_ALIASES,
)


def _retry(operation: callable, attempts: int = 2) -> any:
    """Run a small retry loop for flaky network/model calls."""
    last_error = None
    for _ in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
    raise last_error


def _ddg_text_search(query: str, max_results: int = 4) -> list[dict[str, str]]:
    """Text search using DuckDuckGo."""
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def _ddg_image_search(query: str, max_results: int = 6) -> list[dict[str, str]]:
    """Image search using DuckDuckGo."""
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        return list(ddgs.images(query, max_results=max_results, safesearch="moderate"))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    """Verifies if the text contains any of the given terms."""
    normalized = text.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return any(term in normalized for term in terms)


def _detect_language(text: str) -> str:
    """
    Detects if the text is primarily in Spanish or English.
    Returns: 'es' for Spanish, 'en' for English, or 'es' by default if unsure.
    """
    if not text or len(text.strip()) < 3:
        return 'es'  # Default to Spanish for very short text
    
    try:
        # langdetect returns a list of Language objects with probabilities
        detections = detect_langs(text)
        if detections:
            # Get the language with the highest probability
            primary_lang = str(detections[0]).split(':')[0]  # e.g., 'en' or 'es'
            # Check if it's English, otherwise assume Spanish
            if primary_lang == 'en':
                return 'en'
            elif primary_lang == 'es':
                return 'es'
    except (LangDetectException, Exception):
        # Fallback to checking Spanish keywords if detection fails
        normalized = text.lower()
        spanish_markers = (
            "donde", "dónde", "esta", "está", "ubicado", "ubicada", "imagenes",
            "imágenes", "fotos", "muestrame", "muéstrame", "lugares", "viaje",
            "viajar", "pais", "país", "ciudad",
        )
        if any(marker in normalized for marker in spanish_markers):
            return 'es'
    
    return 'es'  # Default to Spanish


def _clean_destination_name(value: str) -> str:
    """Cleans the destination name by removing common words."""
    destination = re.sub(r"\s+", " ", value).strip(" .¿?¡!")
    destination = re.sub(
        r"^(ubicado|ubicada|ubica|queda|esta|está|en|de|del|la|el|a)\s+",
        "",
        destination,
        flags=re.IGNORECASE,
    )
    destination = re.sub(
        r"\b(google maps|maps|mapa|imagenes|imágenes|imagen|fotos|foto|galeria|galería|por favor|please)\b",
        "",
        destination,
        flags=re.IGNORECASE,
    )
    destination = re.sub(r"\s+", " ", destination).strip(" .¿?¡!")
    return destination


def _get_image_search_variants(query: str) -> list[str]:
    """Generates search variants for images."""
    cleaned = _clean_destination_name(query)
    if not cleaned:
        return []
    normalized = cleaned.lower()
    variants: list[str] = []
    alias = IMAGE_SEARCH_ALIASES.get(normalized)
    if alias:
        variants.append(alias)
    if cleaned not in variants:
        variants.append(cleaned)
    lowercase_variant = cleaned.lower()
    if lowercase_variant != cleaned and lowercase_variant not in [v.lower() for v in variants]:
        variants.append(lowercase_variant)
    return variants


def _extract_destination_from_location_question(text: str) -> str | None:
    """Extracts the destination from a location question."""
    normalized = text.strip()
    patterns = [
        r"(?:donde\s+queda|dónde\s+queda|donde\s+esta|dónde\s+está)\s+(?:ubicado|ubicada|ubicada\s+en|ubicado\s+en)?\s*(.+?)(?:\?|$)",
        r"(?:donde\s+esta\s+ubicado|dónde\s+está\s+ubicado|donde\s+esta\s+ubicada|dónde\s+está\s+ubicada)\s+(.+?)(?:\?|$)",
        r"(?:where\s+is|where's)\s+(.+?)(?:\s+located|\s+situated|\?|$)",
        r"(?:location\s+of|map\s+of|google\s+maps\s+of|photos\s+of|images\s+of|pictures\s+of)\s+(?:of\s+|in\s+)?(.+?)(?:\?|$)",
        r"(?:donde\s+esta|dónde\s+está|donde\s+queda|dónde\s+queda|ubicacion\s+de|ubicación\s+de|donde\s+se\s+ubica|dónde\s+se\s+ubica|visitar|viaje\s+a)\s+(?:en\s+|de\s+|a\s+)?(.+?)(?:\?|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            destination = _clean_destination_name(match.group(1))
            return destination or None
    return None


def _is_travel_related(user_message: str) -> bool:
    """Verifies if the message is travel-related."""
    normalized = user_message.lower()
    normalized = re.sub(r"[^\w\sáéíóúüñ]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if any(keyword in normalized for keyword in TRAVEL_KEYWORDS):
        return True
    if any(destination in normalized for destination in KNOWN_DESTINATIONS):
        return True
    return False
