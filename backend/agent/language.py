"""
Comprension del mensaje del usuario.

Funciones para entender la entrada antes de llamar al modelo:
- _detect_language: detecta si el texto es espanol o ingles.
- _is_travel_related: guardrail que filtra preguntas que no son de viajes.
- _extract_destination_from_location_question: extrae el destino de preguntas
  tipo "donde queda X" o "where is X".
"""

import re

from langdetect import detect_langs, LangDetectException

from .vocabulary import TRAVEL_KEYWORDS, KNOWN_DESTINATIONS
from .helpers import _clean_destination_name


def _detect_language(text: str) -> str:
    """
    Detect if text is primarily in Spanish or English.
    Returns: 'es' for Spanish, 'en' for English, or 'es' by default if uncertain.
    """
    if not text or len(text.strip()) < 3:
        return 'es'  # Default to Spanish for very short text

    try:
        # langdetect returns a list of Language objects with probabilities
        detections = detect_langs(text)
        if detections:
            # Get the language with highest probability
            primary_lang = str(detections[0]).split(':')[0]  # e.g., 'en' or 'es'
            # Check if it's English, if not assume Spanish
            if primary_lang == 'en':
                return 'en'
            elif primary_lang == 'es':
                return 'es'
    except (LangDetectException, Exception):
        # Fallback to checking for Spanish keywords if detection fails
        normalized = text.lower()
        spanish_markers = (
            "donde", "dónde", "esta", "está", "ubicado", "ubicada", "imagenes",
            "imágenes", "fotos", "muestrame", "muéstrame", "lugares", "viaje",
            "viajar", "pais", "país", "ciudad",
        )
        if any(marker in normalized for marker in spanish_markers):
            return 'es'

    return 'es'  # Default to Spanish


def _is_travel_related(user_message: str) -> bool:
    """Simple hard guardrail before the LLM so off-topic chats do not slip through."""
    normalized = user_message.lower()
    normalized = re.sub(r"[^\w\sáéíóúüñ]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if any(keyword in normalized for keyword in TRAVEL_KEYWORDS):
        return True
    if any(destination in normalized for destination in KNOWN_DESTINATIONS):
        return True
    return False


def _extract_destination_from_location_question(text: str) -> str | None:
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
