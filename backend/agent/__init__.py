"""
Paquete `agent` de ViajeBot (antes un unico archivo agent.py).

Se dividio por secciones para que sea mas facil de leer y de explicar:

- config.py     -> Configuracion: variables de entorno, modelos y system prompt.
- vocabulary.py -> Vocabulario: palabras clave, destinos y alias.
- helpers.py    -> Helpers genericos: retry, comparacion de texto, limpieza.
- language.py   -> Comprension del mensaje: idioma, guardrail y destino.
- rag.py        -> RAG (FAISS) de turismo de Colombia.
- media.py      -> Busqueda de imagenes y resumenes de destinos.
- tools.py      -> Las 4 tools LangChain del agente.
- core.py       -> Modelos, memoria, construccion del agente y router.
- runner.py     -> run_agent(): orquestacion y post-procesamiento.

Este __init__ re-exporta la API publica para mantener la compatibilidad con
`from agent import run_agent, search_destination_images, setup_rag`.
"""

from .runner import run_agent
from .rag import setup_rag
from .media import search_destination_images
from .tools import (
    web_search,
    currency_converter,
    travel_knowledge,
    place_image_search,
)

__all__ = [
    "run_agent",
    "setup_rag",
    "search_destination_images",
    "web_search",
    "currency_converter",
    "travel_knowledge",
    "place_image_search",
]
