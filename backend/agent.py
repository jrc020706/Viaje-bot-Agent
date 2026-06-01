"""
ViajeBot — Travel Agent (LangGraph ReAct + LangChain 1.x compatible)
This file is the main entry point that imports all organized modules.

Organized Modules:
- config.py: Constants and configuration
- utils.py: General utility functions
- rag.py: RAG and FAISS setup
- image_utils.py: Image search functions
- tools.py: LangChain tools
- agent_core.py: System prompt, LangGraph agents, and routing
"""

# Import configuration
from config import (
    GEMINI_API_KEY,
    RAG_URL,
    GROQ_FAST_MODEL,
    GROQ_THINKING_MODEL,
    TRAVEL_SCOPE_MESSAGE,
)

# Import RAG setup
from rag import setup_rag, get_rag_retriever

# Import utilities
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

# Import image functions
from image_utils import (
    search_destination_images,
    fetch_destination_summary,
    _is_non_travel_image_url,
)

# Import tools
from tools import (
    web_search,
    currency_converter,
    travel_knowledge,
    place_image_search,
)

# Import agent core
from agent_core import run_agent

# Export main functions for use in main.py
__all__ = [
    'setup_rag',
    'run_agent',
    'web_search',
    'currency_converter',
    'travel_knowledge',
    'place_image_search',
    'search_destination_images',
]
