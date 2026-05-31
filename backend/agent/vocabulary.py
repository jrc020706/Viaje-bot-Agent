"""
Vocabulario y datos de ViajeBot.

Conjuntos de palabras y diccionarios que el bot usa como "vocabulario":
- TRAVEL_KEYWORDS / KNOWN_DESTINATIONS: guardrail para saber si la pregunta es de viajes.
- IMAGE_SEARCH_ALIASES: normaliza nombres de ciudades para buscar imagenes.
- IMAGE_REQUEST_TERMS / MAP_REQUEST_TERMS: detectan pedidos de imagenes o mapas.
- COLOMBIA_RAG_TERMS: limita el RAG a turismo de Colombia.
- GENERIC_SCOPE_REFUSALS: frases de rechazo generico del modelo a reemplazar.

Son solo datos (sin logica), para poder ampliarlos sin tocar el codigo.
"""

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
    "puedo ayudarte con viajes",
)
