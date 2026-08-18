"""
LangGraph Agent Core: System prompt, agents, and routing
"""

import os
import re
from threading import RLock
from typing import Any, NamedTuple
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
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


# This is deliberately small, session-scoped memory. It complements LangGraph's
# message history with preferences that remain useful after old turns are trimmed.
_travel_profiles: dict[str, dict[str, str]] = {}
_pending_profile_updates: dict[str, dict[str, str]] = {}
_profile_lock = RLock()
_MAX_PROFILE_SESSIONS = 1_000


class AgentSelection(NamedTuple):
    """The model and request category selected for a user turn."""

    agent: Any
    model: str
    intent: str


def _extract_travel_preferences(message: str) -> dict[str, str]:
    """Extracts only general trip preferences; no personal identifiers are stored."""
    normalized = re.sub(r"\s+", " ", message.strip())
    preferences: dict[str, str] = {}

    duration = re.search(r"\b(\d{1,2}\s*(?:d[ií]as?|semanas?|days?|weeks?))\b", normalized, re.IGNORECASE)
    if duration:
        preferences["duracion"] = duration.group(1)

    budget = re.search(
        r"\b(?:presupuesto(?:\s+(?:de|es|ser[ií]a))?|budget(?:\s+(?:of|is|will be))?)\s*[:=]?\s*"
        r"((?:\$|usd|eur|cop|mxn)?\s*[\d.,]+(?:\s*(?:usd|eur|cop|mxn|pesos?|d[oó]lares?|euros?))?)",
        normalized,
        re.IGNORECASE,
    )
    if budget and re.search(r"\d", budget.group(1)):
        preferences["presupuesto"] = budget.group(1).strip()

    style = re.search(
        r"\b(?:viaje|trip|estilo)\s+(?:de\s+)?"
        r"(econ[oó]mico|barato|lujo|relajado|aventura|familiar|rom[aá]ntico|mochilero|"
        r"budget|cheap|luxury|relaxed|adventure|family|romantic|backpacking)\b",
        normalized,
        re.IGNORECASE,
    )
    if style:
        preferences["estilo"] = style.group(1).lower()

    companions = re.search(
        r"\b(?:viajo|viajamos|voy|vamos|travel(?:ing)?|going)\s+(?:con|with)\s+"
        r"(mi\s+(?:pareja|familia|amigo(?:s)?|hijo(?:s)?)|"
        r"my\s+(?:partner|family|friend(?:s)?|child(?:ren)?))\b",
        normalized,
        re.IGNORECASE,
    )
    if companions:
        preferences["acompanantes"] = companions.group(1).lower()

    return preferences


def _is_confirmation(message: str) -> bool:
    """Accept short affirmative replies only when a preference change is pending."""
    normalized = re.sub(r"[^\w\sáéíóúüñ]", "", message.lower()).strip()
    return normalized in {"si", "sí", "confirmo", "confirmar", "yes", "confirm", "correcto", "correct"}


def _update_travel_profile(session_id: str, message: str) -> tuple[dict[str, str], dict[str, str], bool]:
    """Updates a new preference or returns changes that still need confirmation."""
    candidate = _extract_travel_preferences(message)
    with _profile_lock:
        confirmed_pending_update = _is_confirmation(message) and session_id in _pending_profile_updates
        if confirmed_pending_update:
            _travel_profiles.setdefault(session_id, {}).update(_pending_profile_updates.pop(session_id))
        elif candidate:
            profile = _travel_profiles.setdefault(session_id, {})
            replacements = {
                field: value for field, value in candidate.items()
                if field in profile and profile[field] != value
            }
            if replacements:
                # New fields are safe to keep; only conflicting values need consent.
                profile.update({field: value for field, value in candidate.items() if field not in replacements})
                _pending_profile_updates.setdefault(session_id, {}).update(replacements)
            else:
                profile.update(candidate)

        # Bound memory growth on long-running deployments.
        if len(_travel_profiles) > _MAX_PROFILE_SESSIONS:
            oldest_session = next(iter(_travel_profiles))
            _travel_profiles.pop(oldest_session, None)
            _pending_profile_updates.pop(oldest_session, None)

        return (
            dict(_travel_profiles.get(session_id, {})),
            dict(_pending_profile_updates.get(session_id, {})),
            confirmed_pending_update,
        )


def _format_profile_context(profile: dict[str, str], pending_updates: dict[str, str], language: str) -> str:
    """Creates a compact profile hint for the model without exposing internal data."""
    if not profile and not pending_updates:
        return ""

    labels = {
        "presupuesto": "presupuesto" if language == "es" else "budget",
        "estilo": "estilo" if language == "es" else "style",
        "acompanantes": "acompanantes" if language == "es" else "companions",
        "duracion": "duracion" if language == "es" else "duration",
    }
    profile_text = ", ".join(f"{labels[key]}: {value}" for key, value in profile.items())
    if pending_updates:
        pending_text = ", ".join(f"{labels[key]}: {value}" for key, value in pending_updates.items())
        confirmation = (
            f"Detectaste un posible cambio ({pending_text}). Pide una confirmacion breve antes de usarlo."
            if language == "es"
            else f"You detected a possible change ({pending_text}). Ask for brief confirmation before using it."
        )
        return f"[TRAVEL PROFILE: {profile_text}. {confirmation}]"
    return f"[TRAVEL PROFILE: {profile_text}]"


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
def _select_agent(user_message: str, mode: str = "text") -> AgentSelection:
    """
    Routes a turn according to its intent. Complex travel decisions take
    precedence over visual requests so a full plan with photos is not rushed.
    """
    normalized = user_message.lower()
    normalized = re.sub(r"\s+", " ", normalized)

    if mode in {"voice", "audio"}:
        return AgentSelection(_agent, GROQ_FAST_MODEL, "voice")

    visual_terms = (
        "imagen", "imagenes", "imágenes", "foto", "fotos", "mapa", "maps",
        "google maps", "donde queda", "dónde queda", "donde esta", "dónde está",
        "galeria", "galería", "gallery", "image", "images", "photo", "photos",
        "where is", "location of",
    )
    conversion_terms = (
        "convierte", "convertir", "currency", "cambio", "tasa",
        "convert", "rate", "exchange", "conversion",
    )
    planning_terms = (
        "itinerario", "plan", "ruta", "presupuesto", "budget", "seguridad",
        "safety", "riesgo", "visa", "comparar", "compare", "recomienda",
        "recommend", "familia", "family", "dias", "días", "weeks", "semanas",
        "barato", "lujo", "hotel", "hoteles",
        "itinerary", "route", "risk", "cheap", "luxury", "hotels",
    )
    time_sensitive_terms = (
        "hoy", "actual", "actualizado", "latest", "current", "now", "ahora",
        "alerta", "advisory", "requisitos", "requirements", "horario", "schedule",
    )

    planning_matches = sum(term in normalized for term in planning_terms)
    is_complex = len(normalized.split()) >= 18 or planning_matches >= 1
    if is_complex:
        return AgentSelection(_thinking_agent, GROQ_THINKING_MODEL, "planning")
    if _contains_any(normalized, time_sensitive_terms):
        return AgentSelection(_thinking_agent, GROQ_THINKING_MODEL, "current_info")
    if _contains_any(normalized, conversion_terms):
        return AgentSelection(_agent, GROQ_FAST_MODEL, "currency")
    if _contains_any(normalized, visual_terms):
        return AgentSelection(_agent, GROQ_FAST_MODEL, "visual")

    return AgentSelection(_agent, GROQ_FAST_MODEL, "quick_question")


# ---------------------------------------------------------------------------
# Main Agent Execution Function
# ---------------------------------------------------------------------------
def run_agent(session_id: str, user_message: str, mode: str = "text") -> dict[str, Any]:
    """
    Executes the agent for a given session.
    Returns: { text, tool_used, tool_name, tools_used, destination, model_used }
    """
    # Detect user language early
    user_language = _detect_language(user_message)
    user_lang_es = (user_language == 'es')
    profile, pending_profile_updates, is_profile_confirmation = _update_travel_profile(session_id, user_message)
    
    from config import TRAVEL_KEYWORDS, KNOWN_DESTINATIONS, COLOMBIA_RAG_TERMS
    allowed_terms = TRAVEL_KEYWORDS.union(KNOWN_DESTINATIONS).union(COLOMBIA_RAG_TERMS)

    if not _contains_any(user_message, allowed_terms) and not is_profile_confirmation:
        return {
            "text": TRAVEL_SCOPE_MESSAGE,
            "tool_used": False,
            "tools_used": [],
            "tool_name": None,
            "destination": None,
            "model_used": GROQ_FAST_MODEL,
            "intent": "out_of_scope",
        }

    if is_profile_confirmation:
        confirmation_text = (
            "Listo, actualice tus preferencias de viaje para esta sesion. "
            "Ahora puedo usar ese contexto en las siguientes recomendaciones."
            if user_lang_es
            else "Done, I updated your travel preferences for this session. "
            "I can use that context in the recommendations that follow."
        )
        return {
            "text": confirmation_text,
            "tool_used": False,
            "tools_used": [],
            "tool_name": None,
            "destination": None,
            "model_used": None,
            "intent": "preference_update",
        }

    config = {"configurable": {"thread_id": session_id}}
    agent_message = user_message
    destination_for_location = _extract_destination_from_location_question(user_message)
    
    # Add language hint and context to the agent
    if user_lang_es:
        language_hint = "[RESPONDE EN ESPAÑOL]"
        location_instruction = "Pregunta sobre la ubicación del destino. Responde brevemente indicando dónde queda y menciona el mapa/galería de abajo."
    else:
        language_hint = "[RESPOND IN ENGLISH]"
        location_instruction = "Travel destination location question. Answer briefly with where this place is located and mention the map/gallery below."

    mode_hint = ""
    if mode in {"voice", "audio"}:
        mode_hint = " [MODO VOZ: responde en 2-4 frases cortas.]" if user_lang_es else " [VOICE MODE: answer in 2-4 short sentences.]"

    profile_context = _format_profile_context(profile, pending_profile_updates, user_language)
    if destination_for_location:
        agent_message = f"{language_hint}{mode_hint} {profile_context} {location_instruction}: {user_message}"
    else:
        agent_message = f"{language_hint}{mode_hint} {profile_context} {user_message}"

    inputs = {"messages": [HumanMessage(content=agent_message)]}

    selection = _select_agent(user_message, mode=mode)
    result = _retry(lambda: selection.agent.invoke(inputs, config=config))
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

    # ── Detect latest turn (after the latest HumanMessage) ───────────
    last_human_idx = -1
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            last_human_idx = i

    # ── Extract tool results ONLY for the latest turn ─────────────────
    tool_results = []
    if last_human_idx >= 0:
        for m in messages[last_human_idx:]:
            if isinstance(m, ToolMessage):
                tool_results.append(str(m.content))
    
    # If tools were used, ensure the results are present in the output.
    if tool_results:
        combined_tool_text = "\n\n".join(tool_results)
        
        # Exchange results contain exact figures, so include them when the model omits
        # the calculation. Other tool output stays internal to avoid leaking raw URLs.
        conversion_terms = ("convertir", "cambio", "tasa", "convert", "rate", "currency", "dolar", "peso", "usd", "cop")
        is_conversion = _contains_any(user_message.lower(), conversion_terms)
        
        content_missing = not any(char.isdigit() for char in output_text) if is_conversion else False

        if is_conversion and (len(output_text.strip()) < 120 or content_missing):
            # Avoid obvious duplicates
            if combined_tool_text[:30] not in output_text:
                if output_text.strip():
                    output_text = f"{output_text}\n\n{combined_tool_text}"
                else:
                    output_text = combined_tool_text
    
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

    # ── Detect tools used in THIS turn ───────────
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
        "model_used": selection.model,
        "intent": selection.intent,
    }
