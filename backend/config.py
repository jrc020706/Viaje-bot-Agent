"""
ViajeBot Configuration and Constants
"""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys and URLs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAG_URL = os.getenv("RAG_URL", "https://en.wikipedia.org/wiki/Tourism_in_Colombia")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq Models
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")
GROQ_THINKING_MODEL = os.getenv("GROQ_THINKING_MODEL", "llama-3.3-70b-versatile")

# System Messages
TRAVEL_SCOPE_MESSAGE = (
    "I can help you with travel, destinations, maps, itineraries, hotels, flights, "
    "visas, budgets, safety, local gastronomy, and places to visit. "
    "To keep me focused, please rephrase your question within this travel context."
)

SYSTEM_PROMPT = """You are ViajeBot, a warm travel assistant for Colombia and worldwide destinations.

Scope: answer only travel topics: destinations, itineraries, maps, photos, flights, hotels, visas, budgets, currency, food, transport, seasons, safety and travel risks.

Style:
- Match the user's language: Spanish or English.
- Keep responses concise unless user requests details.
- For destination planning, use short sections when useful: Overview, Budget, Safety, Best season, Food, Transportation.

Tools:
- Use travel_knowledge first for Colombia-specific context.
- Use web_search for time-sensitive or uncertain facts: prices, routes, visas, safety alerts, schedules.
- Use currency_converter for exchange requests.
- Use place_image_search when users ask for images/photos/gallery.

Accuracy:
- Never invent exact prices, hotels, routes, visa rules, opening hours or safety facts.
- For safety questions, answer directly with balanced risks and precautions.
- Mention that travel details can change when using current facts.

Memory:
- Remember user preferences in this session: budget, travel style, companions and trip duration.
- Confirm before replacing an existing preference.

Visual UI:
- The frontend renders maps and image galleries. Mention that the map/gallery appears below.
- Do not print raw image URLs.
"""

# Travel Keywords
TRAVEL_KEYWORDS = {
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
    "museo", "restaurante", "comida", "seguridad", "transporte", "aeropuerto",
    "tren", "bus", "empacar", "temporada", "vacaciones", "imagenes", "fotos",
    "lugares", "ciudades", "actividades", "hacer", "alla", "allá", "alli", "allí", "google maps", "donde esta", "donde queda", "donde se ubica", "llegar", "arrive", "how to", "como llegar", "cómo llegar", "como viajo", "cómo viajo",
    "peligroso", "peligroso", "seguro", "peligro", "peligros", "delito", "violencia", "advertencia", "consejo", "recomendacion", "evitar", "riesgo",
    "asia", "africa", "europe", "america", "center america", "central america", "south america", "north america", "oceania", "middle east",
    "europa", "sudamerica", "suramerica", "centroamerica", "norteamerica", "oceania", "medio oriente",
}

# Known Destinations
KNOWN_DESTINATIONS = {
    "colombia", "bogota", "bogotá", "medellin", "medellín", "cartagena",
    "santa marta", "tayrona", "san andres", "san andrés", "providencia",
    "tokio", "tokyo", "japon", "japón", "kyoto", "osaka", "paris", "londres",
    "madrid", "barcelona", "roma", "venecia", "new york", "nueva york",
    "miami", "mexico", "méxico", "cancun", "cancún", "buenos aires", "lima",
    "cusco", "machu picchu", "rio de janeiro", "rio", "panama", "panamá",
    "costa rica", "chile", "argentina", "peru", "perú", "brasil", "españa",
    "italia", "francia", "alemania", "portugal", "tailandia", "dubai",
    "spain", "japan", "united states", "usa", "canada", "morocco", "egypt",
    "turkey", "greece", "iceland", "norway", "sweden", "finland", "india",
    "vietnam", "indonesia", "philippines", "australia", "new zealand",
    "south africa", "kenya", "tanzania", "namibia", "georgia", "armenia",
    "albania", "montenegro", "slovenia", "croatia", "estonia", "latvia",
    "lithuania", "nepal", "bhutan", "uzbekistan", "kazakhstan", "jordania", "jordan", "venice", "venezia", "italy", "italia",
    "moscu", "moscú", "moscow", "rotterdam", "netherlands", "paises bajos", "países bajos", "holanda",
}

# Aliases for Image Search
IMAGE_SEARCH_ALIASES = {
    "bogota": "Bogotá, Colombia",
    "bogotá": "Bogotá, Colombia",
    "medellin": "Medellín, Colombia",
    "medellín": "Medellín, Colombia",
    "san andres": "San Andrés, Colombia",
    "san andrés": "San Andrés, Colombia",
    "seville": "Seville, Spain",
    "sevilla": "Seville, Spain",
    "cancun": "Cancún, Mexico",
    "cancún": "Cancún, Mexico",
    "new york": "New York City, USA",
    "nueva york": "New York City, USA",
    "moscu": "Moscow, Russia",
    "moscú": "Moscow, Russia",
    "moscow": "Moscow, Russia",
    "rotterdam": "Rotterdam, Netherlands",
}

# Request Detection Terms
IMAGE_REQUEST_TERMS = ("imagen", "imagenes", "foto", "fotos", "galeria", "gallery", "image", "images", "photo", "photos")
MAP_REQUEST_TERMS = ("mapa", "maps", "google maps", "ubicacion", "ubicado", "donde queda", "donde esta", "location", "located", "where is")
COLOMBIA_RAG_TERMS = (
    "colombia", "colombiano", "colombiana", "bogota", "bogotá", "medellin", "medellín",
    "cartagena", "santa marta", "tayrona", "san andres", "san andrés", "providencia",
    "eje cafetero", "amazonas", "amazon", "cali", "barranquilla", "guatape", "guatapé",
)
GENERIC_SCOPE_REFUSALS = (
    "i'm here to help with travel",
    "i'm here to help you with travel",
    "if you're interested in visiting",
    "i can help you with travel",
)
