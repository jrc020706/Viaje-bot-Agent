"""
Orquestacion: run_agent().

Punto de entrada que usa el backend (/chat). Detecta idioma, aplica el
guardrail de viajes, arma el mensaje para el agente, selecciona el modelo,
invoca al agente y hace el post-procesamiento de la respuesta (galerias,
mapas y resumenes de respaldo). Devuelve texto, tools usadas, destino y
modelo usado.
"""

from langchain_core.messages import HumanMessage, AIMessage

from .config import TRAVEL_SCOPE_MESSAGE_ES
from .vocabulary import IMAGE_REQUEST_TERMS, MAP_REQUEST_TERMS, GENERIC_SCOPE_REFUSALS
from .helpers import _retry, _contains_any
from .language import (
    _detect_language,
    _is_travel_related,
    _extract_destination_from_location_question,
)
from .media import fetch_destination_summary
from .core import _select_agent


def run_agent(session_id: str, user_message: str, mode: str = "text") -> dict:
    """
    Run the agent for a given session.
    Returns: { text, tool_used, tool_name, tools_used }
    """
    # Detect user language early
    user_language = _detect_language(user_message)
    user_is_spanish = (user_language == 'es')

    if not _is_travel_related(user_message):
        return {
            "text": TRAVEL_SCOPE_MESSAGE_ES,
            "tool_used": False,
            "tools_used": [],
            "tool_name": None,
        }

    config  = {"configurable": {"thread_id": session_id}}
    agent_message = user_message
    destination_for_location = _extract_destination_from_location_question(user_message)

    # Add language hint to the agent
    language_hint = "[RESPOND IN SPANISH]" if user_is_spanish else "[RESPOND IN ENGLISH]"

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

    inputs  = {"messages": [HumanMessage(content=agent_message)]}

    selected_agent, model_used = _select_agent(user_message, mode=mode)
    result  = _retry(lambda: selected_agent.invoke(inputs, config=config))
    messages: list = result.get("messages", [])

    # ── Extract last AI response ────────────────────────────────────────────
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    output_text = ai_messages[-1].content if ai_messages else "Sorry, I didn't get a response."
    if isinstance(output_text, list):                # handle multi-part content
        output_text = " ".join(
            p.get("text", "") if isinstance(p, dict) else str(p)
            for p in output_text
        )

    normalized_output = output_text.lower()
    # user_is_spanish already detected at the beginning of run_agent
    if _contains_any(user_message, IMAGE_REQUEST_TERMS) and (
        "no puedo mostrar" in normalized_output
        or "cannot show" in normalized_output
        or "can't show" in normalized_output
        or "can’t show" in normalized_output
        or "couldn't find specific images" in normalized_output
        or "could not find specific images" in normalized_output
        or "no image results found" in normalized_output
    ):
        if user_is_spanish:
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
        or "can’t provide information about the location" in normalized_output
    ):
        summary = fetch_destination_summary(destination_for_location) if destination_for_location else ""
        if summary:
            if user_is_spanish:
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
            ) if user_is_spanish else (
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
            ) if user_is_spanish else (
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
            ) if user_is_spanish else (
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
        ) if user_is_spanish else (
            "Sure, below I am showing a visual gallery of the destination with images I found. "
            "I can also help with the most photogenic places, best areas to stay, and a route to visit it."
        )

    # ── Detect tools used in THIS turn (after last HumanMessage) ───────────
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

    # ── Final Fallback for destination (from tool calls) ──────────────────
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
        "text":       output_text,
        "tool_used":  len(tools_used) > 0,
        "tools_used": tools_used,
        "tool_name":  tools_used[0] if tools_used else None,
        "destination": destination_for_location,
        "model_used": model_used,
    }
