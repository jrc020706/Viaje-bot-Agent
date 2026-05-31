"""
Nucleo del agente: modelos, memoria y router.

Construye dos agentes ReAct con LangGraph (uno rapido y uno "pensador") que
comparten las mismas tools, la misma memoria por sesion (MemorySaver) y el
mismo prompt dinamico. _select_agent() decide cual usar segun el mensaje.
"""

import re

from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq

# LangGraph (modern agent API — replaces AgentExecutor in LangChain 1.x)
from langgraph.prebuilt import create_react_agent
try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver

from .config import GROQ_FAST_MODEL, GROQ_THINKING_MODEL, GROQ_API_KEY, SYSTEM_PROMPT
from .helpers import _contains_any
from .tools import web_search, currency_converter, travel_knowledge, place_image_search


# ---------------------------------------------------------------------------
# Agent — LangGraph ReAct (modern replacement for AgentExecutor)
# ---------------------------------------------------------------------------
_tools = [web_search, currency_converter, travel_knowledge, place_image_search]
_llm = ChatGroq(model=GROQ_FAST_MODEL, groq_api_key=GROQ_API_KEY, temperature=0.1)
_thinking_llm = ChatGroq(model=GROQ_THINKING_MODEL, groq_api_key=GROQ_API_KEY, temperature=0.1)
_memory = MemorySaver()


def _trim_to_window(messages: list, window: int = 8) -> list:
    """Keep only the last `window` non-system messages for model context."""
    other_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
    return other_msgs[-window:] if len(other_msgs) > window else other_msgs


def _agent_prompt(state: dict) -> list:
    """Reduce model context while keeping the latest conversation turns."""
    messages = state.get("messages", [])
    return [SystemMessage(content=SYSTEM_PROMPT)] + _trim_to_window(messages, window=8)


# Build both agents once. They share tools, FAISS-backed RAG and session memory.
_agent = create_react_agent(
    _llm,
    _tools,
    checkpointer=_memory,
    prompt=_agent_prompt,
)
_thinking_agent = create_react_agent(
    _thinking_llm,
    _tools,
    checkpointer=_memory,
    prompt=_agent_prompt,
)


def _select_agent(user_message: str, mode: str = "text"):
    """
    Route simple/voice turns to the fast model and complex text turns to the
    stronger reasoning model. Tool functions and FAISS stay shared.
    """
    normalized = user_message.lower()
    normalized = re.sub(r"\s+", " ", normalized)

    if mode in {"voice", "audio"}:
        return _agent, GROQ_FAST_MODEL

    fast_only_terms = (
        "imagen", "imagenes", "imágenes", "foto", "fotos", "mapa", "maps",
        "google maps", "donde queda", "dónde queda", "donde esta", "dónde está",
        "convierte", "convertir", "currency", "cambio", "tasa",
    )
    if _contains_any(normalized, fast_only_terms):
        return _agent, GROQ_FAST_MODEL

    thinking_terms = (
        "itinerario", "plan", "ruta", "presupuesto", "budget", "seguridad",
        "safety", "riesgo", "visa", "comparar", "compare", "recomienda",
        "recommend", "familia", "family", "dias", "días", "weeks", "semanas",
        "barato", "lujo", "hotel", "hoteles",
    )
    is_long = len(normalized.split()) >= 18
    if is_long or _contains_any(normalized, thinking_terms):
        return _thinking_agent, GROQ_THINKING_MODEL

    return _agent, GROQ_FAST_MODEL
