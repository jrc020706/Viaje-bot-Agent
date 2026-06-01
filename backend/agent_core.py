"""
LangGraph Agent Core: System prompt, agents, and routing
"""

import os
import re
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver

from config import (
    GROQ_FAST_MODEL,
    GROQ_THINKING_MODEL,
    GROQ_API_KEY,
    SYSTEM_PROMPT,
    TRAVEL_SCOPE_MESSAGE,
    IMAGE_REQUEST_TERMS,
    MAP_REQUEST_TERMS,
    GENERIC_SCOPE_REFUSALS,
)
from tools import web_search, currency_converter, travel_knowledge, place_image_search
from utils import _retry, _contains_any, _detect_language, _extract_destination_from_location_question
from image_utils import fetch_destination_summary


# ---------------------------------------------------------------------------
# LangGraph Agents
# ---------------------------------------------------------------------------
_tools = [web_search, currency_converter, travel_knowledge, place_image_search]
_llm = ChatGroq(model=GROQ_FAST_MODEL, groq_api_key=GROQ_API_KEY, temperature=0.1)
_thinking_llm = ChatGroq(model=GROQ_THINKING_MODEL, groq_api_key=GROQ_API_KEY, temperature=0.1)
_memory = MemorySaver()


def _trim_to_window(messages: list, window: int = 8) -> list:
    """Keeps only the last `window` non-system messages for model context."""
    other_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
    return other_msgs[-window:] if len(other_msgs) > window else other_msgs


def _agent_prompt(state: dict) -> list:
    """Reduces model context by keeping only the latest interaction turns."""
    messages = state.get("messages", [])
    return [SystemMessage(content=SYSTEM_PROMPT)] + _trim_to_window(messages, window=8)


# Build both agents. They share tools, FAISS-backed RAG, and session memory.
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


# ---------------------------------------------------------------------------
# Agent Router
# ---------------------------------------------------------------------------
def _select_agent(user_message: str, mode: str = "text"):
    """
    Routes simple/voice turns to the fast model and complex text turns
    to the stronger reasoning model. Tool functions and FAISS are shared.
    """
    normalized = user_message.lower()
    normalized = re.sub(r"\s+", " ", normalized)

    if mode in {"voice", "audio"}:
        return _agent, GROQ_FAST_MODEL

    fast_only_terms = (
        "imagen", "imagenes", "imágenes", "foto", "fotos", "mapa", "maps",
        "google maps", "donde queda", "dónde queda", "donde esta", "dónde está",
        "convierte", "convertir", "currency", "cambio", "tasa",
        "image", "images", "photo", "photos", "map", "convert", "rate",
    )
    if _contains_any(normalized, fast_only_terms):
        return _agent, GROQ_FAST_MODEL

    thinking_terms = (
        "itinerario", "plan", "ruta", "presupuesto", "budget", "seguridad",
        "safety", "riesgo", "visa", "comparar", "compare", "recomienda",
        "recommend", "familia", "family", "dias", "días", "weeks", "semanas",
        "barato", "lujo", "hotel", "hoteles",
        "itinerary", "route", "risk", "cheap", "luxury", "hotels",
    )
    is_long = len(normalized.split()) >= 18
    if is_long or _contains_any(normalized, thinking_terms):
        return _thinking_agent, GROQ_THINKING_MODEL

    return _agent, GROQ_FAST_MODEL


# ---------------------------------------------------------------------------
# Main Agent Execution Function
# ---------------------------------------------------------------------------
def run_agent(session_id: str, user_message: str, mode: str = "text") -> dict:
    """
    Executes the agent for a given session.
    Returns: { text, tool_used, tool_name, tools_used, destination, model_used }
    """
    # Detect user language early
    user_language = _detect_language(user_message)
    user_lang_es = (user_language == 'es')
    
    if not _contains_any(user_message, (
        "travel", "trip", "tourism", "tourist", "destination", "destinations", "city",
        "country", "countries", "visit", "visiting", "itinerary", "flight", "flights",
        "hotel", "hotels", "hostel", "airbnb", "visa", "passport", "budget", "currency",
        "exchange", "rate", "usd", "eur", "cop", "gbp", "mxn", "brl", "weather", "route", "map", "maps", "location", "located", "beach",
        "museum", "restaurant", "food", "safety", "transport", "airport", "train",
        "bus", "packing", "season", "vacation", "holidays", "images", "photos",
        "ticket", "tickets", "price", "prices", "cost", "costs", "fare", "fares", "how much",
        "dangerous", "danger", "safe", "unsafe", "risky", "risk", "crime", "criminal", "violence", "violent", "advice", "warning",
        "advisory", "secure", "security", "warning", "precaution", "cautious", "avoid", "threat",
        "viaje", "viajar", "viajo", "turismo", "turista", "destino", "destinos", "ciudad",
        "pais", "paises", "visitar", "itinerario", "vuelo", "vuelos", "hotel",
        "hoteles", "hostal", "visa", "pasaporte", "presupuesto", "moneda", "cambio",
        "tasa", "dolar", "dolares", "euro", "euros", "pesos", "precio", "precios",
        "costo", "costos", "tarifa", "tarifas", "boleto", "boletos", "tiquete", "tiquetes",
        "pasaje", "pasajes", "cuanto cuesta", "cuánto cuesta",
        "clima", "ruta", "mapa", "mapas", "ubicacion", "ubicado", "queda", "playa",
        "museum", "restaurante", "comida", "seguridad", "transporte", "aeropuerto",
        "tren", "bus", "empacar", "temporada", "vacaciones", "imagenes", "fotos",
        "lugares", "ciudades", "actividades", "hacer", "alla", "allá", "alli", "allí", "google maps", "donde esta", "donde queda", "donde se ubica", "llegar", "arrive", "how to", "como llegar", "cómo llegar", "como viajo", "cómo viajo",
        "peligroso", "peligroso", "seguro", "peligro", "peligros", "delito", "violencia", "advertencia", "consejo", "recomendacion", "evitar", "riesgo",
        "asia", "africa", "europe", "america", "center america", "central america", "south america", "north america", "oceania", "middle east",
        "europa", "sudamerica", "suramerica", "centroamerica", "norteamerica", "oceania", "medio oriente",
    )):
        return {
            "text": TRAVEL_SCOPE_MESSAGE,
            "tool_used": False,
            "tools_used": [],
            "tool_name": None,
            "destination": None,
            "model_used": GROQ_FAST_MODEL,
        }

    config = {"configurable": {"thread_id": session_id}}
    agent_message = user_message
    destination_for_location = _extract_destination_from_location_question(user_message)
    
    # Add language hint to the agent
    language_hint = "[RESPOND IN SPANISH]" if user_lang_es else "[RESPOND IN ENGLISH]"
    
    mode_hint = ""
    if mode in {"voice", "audio"}:
        mode_hint = " [VOICE MODE: answer in 2-4 short sentences.]"

    if destination_for_location:
        agent_message = (
            f"{language_hint}{mode_hint} Travel destination location question. Answer briefly with where this "
            f"place is located and mention the map/gallery below: {user_message}"
        )
    else:
        agent_message = f"{language_hint}{mode_hint} {user_message}"

    inputs = {"messages": [HumanMessage(content=agent_message)]}

    selected_agent, model_used = _select_agent(user_message, mode=mode)
    result = _retry(lambda: selected_agent.invoke(inputs, config=config))
    messages: list = result.get("messages", [])

    # ── Extract latest AI response ────────────────────────────────────────────
    # Look for the last AI message that actually has content.
    output_text = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content:
            if isinstance(m.content, list):
                output_text = " ".join(
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in m.content
                )
            else:
                output_text = str(m.content)
            if output_text.strip():
                break

    # If the AI response is empty but tools were used, check if we should show tool results.
    # This is a fallback in case the model only generates tool calls without final content.
    if not output_text.strip():
        for m in reversed(messages):
            if hasattr(m, "content") and m.content and not isinstance(m, HumanMessage):
                output_text = str(m.content)
                break
    
    if not output_text:
        output_text = "Sorry, I didn't get a response."

    normalized_output = output_text.lower()
    # user_lang_es already detected at the beginning of run_agent
    if _contains_any(user_message, IMAGE_REQUEST_TERMS) and (
        "no puedo mostrar" in normalized_output
        or "cannot show" in normalized_output
        or "can't show" in normalized_output
        or "can't show" in normalized_output
        or "couldn't find specific images" in normalized_output
        or "could not find specific images" in normalized_output
        or "no image results found" in normalized_output
    ):
        if user_lang_es:
            output_text = (
                "Claro, te muestro una galeria de imagenes abajo en la interfaz. "
                "Tambien puedo ayudarte a elegir barrios, miradores, templos, museos "
                "y zonas seguras para visitar en ese destino."
            )
        else:
            output_text = (
                "Sure, I am showing an image gallery below in the interface. "
                "I can also help you choose neighborhoods, viewpoints, temples, museums, "
                "and safe areas to visit in that destination."
            )
    elif _contains_any(user_message, MAP_REQUEST_TERMS) and (
        "no puedo" in normalized_output
        or "cannot" in normalized_output
        or "can't provide information about the location" in normalized_output
        or "can't provide information about the location" in normalized_output
    ):
        summary = fetch_destination_summary(destination_for_location) if destination_for_location else ""
        if summary:
            if user_lang_es:
                output_text = (
                    f"{summary}\n\nAbajo te dejo el mapa de referencia y una galeria de imagenes. "
                    "Desde ahi puedes abrir Google Maps, revisar la ubicacion y calcular rutas."
                )
            else:
                output_text = (
                    f"{summary}\n\nBelow, I am showing the reference map and an image gallery. "
                    "From there you can open Google Maps, check the location, and calculate routes."
                )
        else:
            output_text = (
                "Claro, te dejo el mapa de referencia abajo en la interfaz. "
                "Desde ahi puedes abrir Google Maps, revisar la ubicacion y calcular rutas."
            ) if user_lang_es else (
                "Sure, I am showing the reference map below in the interface. "
                "From there you can open Google Maps, check the location, and calculate routes."
            )
    elif destination_for_location and any(phrase in normalized_output for phrase in GENERIC_SCOPE_REFUSALS):
        summary = fetch_destination_summary(destination_for_location)
        if summary:
            output_text = (
                f"{summary}\n\nAbajo te muestro el mapa y una galeria de imagenes "
                "para que tengas una referencia visual del lugar. Tambien puedo ayudarte "
                "con zonas recomendadas, temporada ideal, seguridad y presupuesto."
            ) if user_lang_es else (
                f"{summary}\n\nBelow, I am showing the map and an image gallery so you have "
                "a visual reference for the place. I can also help with recommended areas, "
                "best season, safety, and budget."
            )
        else:
            output_text = (
                f"{destination_for_location} es un destino o lugar que puedes ubicar en el mapa "
                "que aparece abajo en la interfaz. Tambien te muestro una galeria de imagenes "
                "para que tengas una referencia visual del lugar. Si quieres, puedo ayudarte "
                "con mejores zonas para visitar, temporada ideal, seguridad y presupuesto."
            ) if user_lang_es else (
                f"{destination_for_location} is a destination or place you can locate on the map "
                "shown below in the interface. I am also showing an image gallery for visual context. "
                "I can help with the best areas to visit, ideal season, safety, and budget."
            )

    if _contains_any(user_message, IMAGE_REQUEST_TERMS) and (
        "![" in output_text or "upload.wikimedia.org" in output_text or "http://" in output_text or "https://" in output_text
    ):
        output_text = (
            "Claro, abajo te muestro una galeria visual del destino con imagenes encontradas. "
            "Tambien puedo ayudarte con los lugares mas fotogenicos, mejores zonas para hospedarte "
            "y una ruta para visitarlo."
        ) if user_lang_es else (
            "Sure, below I am showing a visual gallery of the destination with images I found. "
            "I can also help with the most photogenic places, best areas to stay, and a route to visit it."
        )

    # ── Detect tools used in THIS turn (after the latest HumanMessage) ───────────
    last_human_idx = -1
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            last_human_idx = i

    tools_used: list[str] = []
    if last_human_idx >= 0:
        for m in messages[last_human_idx:]:
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    if name:
                        tools_used.append(name)

    # ── Final fallback for destination (from tool calls) ──────────────────
    if not destination_for_location and tools_used:
        for m in messages[last_human_idx:]:
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    t_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    if t_name == "place_image_search":
                        args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                        destination_for_location = args.get("query")
                        break

    return {
        "text": output_text,
        "tool_used": len(tools_used) > 0,
        "tools_used": tools_used,
        "tool_name": tools_used[0] if tools_used else None,
        "destination": destination_for_location,
        "model_used": model_used,
    }
