"""
Helpers genericos de ViajeBot.

Funciones pequenas y reutilizables que usan varios modulos:
- _retry: reintenta operaciones de red/modelo que pueden fallar.
- _contains_any: revisa si un texto contiene alguno de varios terminos.
- _clean_destination_name: limpia el nombre de un destino.
- _get_image_search_variants: genera variantes de busqueda de imagenes.
"""

import re

from .vocabulary import IMAGE_SEARCH_ALIASES


def _retry(operation, attempts: int = 2):
    """Run a small retry loop for flaky network/model calls."""
    last_error = None
    for _ in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
    raise last_error


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = text.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return any(term in normalized for term in terms)


def _clean_destination_name(value: str) -> str:
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
