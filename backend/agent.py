"""
ViajeBot — Travel Agent (LangGraph ReAct + LangChain 1.x compatible)
Este archivo es el punto de entrada principal que importa todos los módulos organizados.

Módulos organizados:
- config.py: Constantes y configuración
- utils.py: Funciones de utilidad general
- rag.py: Setup de RAG y FAISS
- image_utils.py: Funciones de búsqueda de imágenes
- tools.py: Tools de LangChain
- agent_core.py: System prompt, agentes LangGraph y routing
"""

# Importar configuración
from config import (
    GEMINI_API_KEY,
    RAG_URL,
    GROQ_FAST_MODEL,
    GROQ_THINKING_MODEL,
    TRAVEL_SCOPE_MESSAGE_ES,
)

# Importar setup de RAG
from rag import setup_rag, get_rag_retriever

# Importar utilidades
from utils import (
    _retry,
    _ddg_text_search,
    _ddg_image_search,
    _contains_any,
    _detect_language,
    _clean_destination_name,
    _get_image_search_variants,
    _extract_destination_from_location_question,
    _is_travel_related,
)

# Importar funciones de imágenes
from image_utils import (
    search_destination_images,
    fetch_destination_summary,
    _is_non_travel_image_url,
)

# Importar tools
from tools import (
    web_search,
    currency_converter,
    travel_knowledge,
    place_image_search,
)

# Importar core del agente
from agent_core import run_agent

# Exportar función principal para uso en main.py
__all__ = [
    'setup_rag',
    'run_agent',
    'web_search',
    'currency_converter',
    'travel_knowledge',
    'place_image_search',
    'search_destination_images',
]
