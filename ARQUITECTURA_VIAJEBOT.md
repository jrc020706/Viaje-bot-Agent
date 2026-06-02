# Arquitectura tecnica de ViajeBot

Este documento explica como se conectan las partes principales de ViajeBot: frontend, backend FastAPI, agentes LangGraph, tools, RAG con FAISS, busqueda de imagenes, audio/TTS, memoria, cache y costos aproximados por tokens.

## 1. Vision general del flujo

Flujo principal cuando el usuario envia un mensaje:

```text
Usuario en frontend
  -> frontend/app.js envia POST /chat
  -> backend/main.py recibe la solicitud
  -> backend/agent.py importa run_agent() desde agent_core.py
  -> LangGraph decide si usa tools
  -> tools consultan web, moneda, RAG o imagenes
  -> el agente genera respuesta
  -> backend devuelve texto, tools usadas, destino y modelo usado
  -> frontend renderiza respuesta, mapa, galeria y audio si aplica
```

Donde verlo:

- Frontend envia `/chat`: `frontend/app.js`, lineas 586-643.
- Endpoint `/chat`: `backend/main.py`, lineas 90-110.
- Ejecucion del agente: `backend/agent_core.py`, funcion `run_agent()`.
- Render de respuesta, mapa e imagenes: `frontend/app.js`, lineas 453-538.

## 2. Backend FastAPI: main.py

El archivo `backend/main.py` es la entrada HTTP del backend.

Responsabilidades:

- Crear la app FastAPI: lineas 29-33.
- Configurar CORS para permitir llamadas desde el frontend: lineas 35-41.
- Inicializar RAG en el arranque: lineas 44-47.
- Definir modelos Pydantic de request/response: lineas 53-79.
- Exponer endpoints:
  - `GET /health`: lineas 85-87.
  - `POST /chat`: lineas 90-110.
  - `POST /tts`: lineas 132-145.
  - `POST /transcribe`: lineas 148-170.
  - `POST /destination-media`: lineas 173-183.

### Endpoint /chat

Ubicacion: `backend/main.py`, lineas 90-110.

Recibe:

```python
message: str
session_id: str
mode: "text" | "voice"
```

Llama a:

```python
run_agent(request.session_id, request.message, mode=request.mode)
```

Devuelve:

- `text`: respuesta del agente.
- `tool_used`: si se uso alguna tool.
- `tool_name`: primera tool usada.
- `tools_used`: lista de tools usadas.
- `mode`: modo texto o voz.
- `destination`: destino detectado.
- `model_used`: modelo rapido o modelo pensador.

## 3. Agentes usados

Los agentes estan en `backend/agent_core.py`.

Modelos configurados (definidos en `backend/config.py`):

- `GROQ_FAST_MODEL`: `llama-3.1-8b-instant`.
- `GROQ_THINKING_MODEL`: `llama-3.3-70b-versatile`.

Se crean dos agentes con LangGraph:

- `_agent`: agente rapido.
- `_thinking_agent`: agente pensador.

Ambos comparten:

- Las mismas tools (definidas en `backend/tools.py`).
- La misma memoria (MemorySaver).
- El mismo prompt dinamico (definido en `backend/config.py`).
- El mismo RAG/FAISS a traves de la tool `travel_knowledge` (definido en `backend/rag.py`).

### Router de agente

Ubicacion: `backend/agent_core.py`, funcion `_select_agent`.

Funcion:

```python
_select_agent(user_message, mode)
```

Reglas principales:

- Si `mode` es `voice` o `audio`, usa el modelo rapido.
- Si la pregunta es de imagenes, mapas o conversion de moneda, usa el modelo rapido.
- Si la pregunta es larga o contiene temas como itinerario, presupuesto, seguridad, visa, comparacion o recomendaciones, usa el modelo pensador.
- Si no cae en ningun caso complejo, usa el modelo rapido.

Como explicarlo:

> ViajeBot usa un modelo rapido para tareas simples y de voz, y un modelo mas grande para tareas que requieren razonamiento, como itinerarios, seguridad, presupuestos y comparaciones. Esto reduce costo y latencia sin perder calidad en preguntas complejas.

## 4. System prompt

Ubicacion: `backend/config.py`, constante `SYSTEM_PROMPT`.

El prompt esta dividido en bloques:

- Identidad: ViajeBot como asistente de viajes.
- Scope: limita el sistema a temas de viaje.
- Style: idioma del usuario, respuestas cortas y estructura.
- Tools: indica cuando usar `travel_knowledge`, `web_search`, `currency_converter` y `place_image_search`.
- Accuracy: evita inventar precios, visas, rutas, horarios y datos de seguridad.
- Memory: recuerda presupuesto, estilo de viaje, acompanantes y duracion.
- Visual UI: indica que el frontend renderiza mapas y galerias y que no debe imprimir URLs crudas.

Tambien se reduce el historial enviado al modelo:

- `_trim_to_window`: funcion en `backend/agent_core.py`.
- `_agent_prompt`: funcion en `backend/agent_core.py`.

Actualmente se mandan maximo 8 mensajes no-system al modelo.

## 5. Tools implementadas

Las tools son funciones decoradas con `@tool` de LangChain. Estan en `backend/tools.py` y se conectan al agente en la lista `_tools` en `backend/agent_core.py`.

### 5.1 web_search

Ubicacion: `backend/tools.py`, funcion `web_search`.

Que hace:

- Busca informacion actualizada usando DuckDuckGo.
- Devuelve maximo 4 resultados.
- Incluye titulo, resumen y fuente.
- Usa `_retry` para reintentar si falla la red.

Cuando se usa:

- Visas.
- Seguridad actual.
- Rutas o vuelos.
- Precios.
- Horarios.
- Informacion que puede cambiar.

Limitacion:

- DuckDuckGo puede bloquear, limitar o devolver resultados irregulares.
- No reemplaza fuentes oficiales para visas, alertas o precios.

### 5.2 currency_converter

Ubicacion: `backend/tools.py`, funcion `currency_converter`.

Que hace:

- Consulta `open.er-api.com`.
- Convierte una cantidad entre monedas.
- Usa cache en memoria con `@lru_cache(maxsize=64)` para no pedir la misma tasa muchas veces.

Ejemplo:

```text
100 USD a COP
```

Limitacion:

- La tasa queda cacheada mientras el proceso este vivo.
- Si el servidor se reinicia, se pierde la cache.
- Para tasas exactas financieras se debe verificar con fuente oficial.

### 5.3 travel_knowledge

Ubicacion: `backend/tools.py`, funcion `travel_knowledge`.

Que hace:

- Consulta la base vectorial FAISS.
- Solo debe usarse para turismo de Colombia.
- Si la consulta no parece de Colombia, devuelve un mensaje indicando que el RAG solo cubre Colombia.

Como explicarlo:

> `travel_knowledge` es la tool RAG. Sirve para traer contexto especializado de una base vectorial creada a partir de contenido turistico de Colombia.

Limitacion:

- No sirve como base de conocimiento internacional.
- Para Moscu, Amsterdam, Santorini o Rotterdam debe usarse conocimiento general o `web_search`, no FAISS de Colombia.

### 5.4 place_image_search

Ubicacion: `backend/tools.py`, funcion `place_image_search`.

Funciones de apoyo en `backend/image_utils.py`:

- Variantes/alias de busqueda: `_get_image_search_variants`.
- DuckDuckGo images: `_ddg_image_search` (en `backend/utils.py`).
- Busqueda principal de imagenes: `_cached_destination_images`.
- Fallback Wikimedia: `_wikimedia_destination_images`.
- Filtro de imagenes no turisticas: `_is_non_travel_image_url`.

Que hace:

1. Limpia el nombre del destino.
2. Crea variantes de busqueda.
3. Busca imagenes con DuckDuckGo Images.
4. Si no encuentra, intenta Wikimedia/Wikipedia.
5. Filtra banderas, mapas, escudos, SVGs y elementos no turisticos.
6. Devuelve URLs internas para que el frontend pinte la galeria.

Endpoint relacionado:

- `/destination-media`: `backend/main.py`, lineas 173-183.

Limitaciones actuales:

- Las imagenes dependen de servicios externos.
- Algunas imagenes pueden no ser perfectas para la ciudad, por ranking del buscador.
- Barcelona ha dado resultados medianos porque algunas fuentes devuelven fotos generales o no tan representativas.
- Para destinos comunes se mitiga con imagenes locales en frontend.

## 6. RAG, FAISS y base vectorial

RAG significa Retrieval Augmented Generation. En vez de depender solo del modelo, se recuperan fragmentos relevantes desde una base vectorial y se entregan al agente como contexto.

### Donde se inicializa

Ubicacion: `backend/rag.py`, funcion `setup_rag()`.

`setup_rag()` se llama al iniciar FastAPI:

- `backend/main.py`, lineas 44-47.

### Fuente del RAG

Ubicacion: `backend/config.py`, constante `RAG_URL`.

```python
RAG_URL = "https://en.wikipedia.org/wiki/Tourism_in_Colombia"
```

Se descarga el HTML:

- Linea 171.

Se limpia con BeautifulSoup:

- Lineas 172-175.

### Chunks

Ubicacion: `backend/rag.py`, funcion `setup_rag()`.

Configuracion:

```python
chunk_size=650
chunk_overlap=80
```

Que significa:

- Cada fragmento tiene hasta 650 caracteres aproximados.
- Cada fragmento comparte 80 caracteres con el anterior para no cortar ideas importantes.

Cuantos chunks se usan:

- Chunks totales indexados: dependen del tamano del texto descargado. El sistema lo imprime al arrancar en la linea 183.
- Chunks recuperados por pregunta: `k=2`, linea 182.

### Embeddings

Ubicacion: `backend/rag.py`, funcion `setup_rag()`.

```python
GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
```

Funcionamiento:

1. Cada chunk de texto se convierte en un vector numerico.
2. La pregunta del usuario tambien se convierte en vector.
3. FAISS compara vectores por similitud.
4. Devuelve los chunks mas parecidos.

### FAISS

Ubicacion: `backend/rag.py`, funcion `setup_rag()`.

```python
vectorstore = FAISS.from_documents(chunks, embeddings)
_rag_retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
```

Importante:

- La base vectorial es en memoria.
- Se crea al iniciar el servidor.
- No esta persistida en disco.
- Si el servidor reinicia, se vuelve a construir.

Como explicarlo:

> La base vectorial FAISS almacena representaciones numericas de fragmentos de texto. Cuando el usuario pregunta algo de turismo en Colombia, el sistema busca semanticamente los dos fragmentos mas parecidos y se los entrega al modelo como contexto adicional.

## 7. Cache y retry

### Retry

Ubicacion: `backend/utils.py`, funcion `_retry`.

`_retry` reintenta operaciones que pueden fallar por red o servicio externo:

- Descarga RAG.
- Web search.
- Imagenes.
- Summaries.
- Invocacion del agente.

### Cache

Cache implementada con `@lru_cache`:

- Monedas: `backend/tools.py`, funcion `_currency_rates`.
- RAG: `backend/tools.py`, funcion `_cached_travel_knowledge`.
- Imagenes: `backend/image_utils.py`, funcion `_cached_destination_images`.
- Wikimedia: `backend/image_utils.py`, funcion `_wikimedia_destination_images`.
- Summaries: `backend/image_utils.py`, funcion `fetch_destination_summary`.

Limitacion:

- Es cache en memoria.
- No sobrevive reinicios.
- No hay Redis, base de datos ni persistencia de cache.

## 8. TTS, voz y transcripcion

### Texto a voz

Ubicacion: `backend/main.py`, lineas 132-145.

Funcionamiento:

1. El frontend recibe la respuesta del agente.
2. Si esta en modo voz, envia el texto a `/tts`.
3. El backend detecta idioma con `detect_text_language`, lineas 113-129.
4. Usa `gTTS` para convertir texto a MP3.
5. Devuelve un `StreamingResponse` con `media_type="audio/mpeg"`.

Frontend:

- Solicitud a `/tts`: `frontend/app.js`, lineas 620-638.
- Reproductor de audio: lineas 468-486.
- Reproduccion: lineas 540-567.

Limitaciones:

- gTTS depende de internet.
- No usa voz personalizada.
- Si TTS falla, el frontend conserva el texto y muestra error de audio.

### Voz a texto

Ubicacion backend: `backend/main.py`, lineas 148-170.

Funcionamiento:

1. El frontend graba audio.
2. Envia archivo a `/transcribe`.
3. El backend usa Groq Whisper `whisper-large-v3`.
4. Devuelve texto transcrito.

Frontend:

- Grabacion con `MediaRecorder`: `frontend/app.js`, lineas 332-380.
- Envio a `/transcribe`: lineas 391-414.

Limitacion:

- La transcripcion deja el texto en el input.
- El auto-envio esta comentado en lineas 408-409.
- Requiere permisos de microfono y HTTPS o entorno seguro.

## 9. Frontend

Archivos:

- `frontend/index.html`: estructura visual.
- `frontend/styles.css`: estilos.
- `frontend/app.js`: logica.

### Estructura visual

Ubicacion: `frontend/index.html`.

- Header: lineas 23-38.
- Galeria principal de destinos: lineas 40-231.
- Boton flotante del chat: lineas 235-241.
- Panel flotante de chat: desde linea 244.

Cada tarjeta de destino tiene un `data-prompt`, por ejemplo:

- Paris: lineas 70-78.
- Santorini: lineas 130-138.
- Medellin: lineas 170-178.
- Amsterdam: lineas 180-188.
- Barcelona: lineas 200-208.

### Estado y API base

Ubicacion: `frontend/app.js`.

- `API_BASE`: linea 6.
- Estado global: lineas 8-16.
- Referencias DOM: lineas 18-28.

### Imagenes locales y deteccion de destino

Ubicacion: `frontend/app.js`.

- Imagenes locales: lineas 30-60.
- Lista de destinos comunes: lineas 62-81.
- Normalizacion de texto: lineas 118-123.
- Extraccion de destino: lineas 125-149.
- Limpieza de destino: lineas 151-159.
- Contexto visual: lineas 161-175.
- Seleccion de imagenes locales: lineas 177-185.
- Busqueda dinamica por backend: lineas 187-200.
- Hidratacion/reemplazo de galeria: lineas 202-218.

Diseno actual:

- Si el destino existe en `DESTINATION_IMAGES`, usa imagenes locales.
- Si no existe, muestra "Buscando imagenes..." y consulta `/destination-media`.
- Si el backend devuelve imagenes, reemplaza la galeria.
- Si no devuelve, muestra un mensaje de que no encontro imagenes especificas.

### Chat

Ubicacion: `frontend/app.js`.

- Render usuario: lineas 416-428.
- Indicador de escritura: lineas 430-451.
- Render bot, mapa, galeria y audio: lineas 453-538.
- Envio del mensaje a backend: lineas 586-657.

### Mapas

Ubicacion: `frontend/app.js`, lineas 488-504.

Usa iframe de Google Maps:

```text
https://www.google.com/maps?q=<destino>&output=embed
```

Tambien agrega links:

- Open map.
- Directions.

## 10. LangChain y LangGraph

### LangChain

Se usa para:

- Definir tools con `@tool`: `backend/tools.py`.
- Manejar mensajes: `HumanMessage`, `AIMessage`, `SystemMessage` en `backend/agent_core.py`.
- Conectar Groq con `ChatGroq`: `backend/agent_core.py`.
- Crear embeddings con Gemini: `backend/rag.py`.
- Usar FAISS desde LangChain Community: `backend/rag.py`.

Como explicarlo:

> LangChain aporta las piezas: modelo, tools, mensajes, embeddings y vectorstore.

### LangGraph

Se usa para crear el agente ReAct:

- Importacion: `backend/agent_core.py`.
- Creacion de agentes: `backend/agent_core.py`.
- Memoria: `backend/agent_core.py`.

Patron ReAct:

```text
Modelo razona
  -> decide si necesita tool
  -> ejecuta tool
  -> recibe resultado
  -> genera respuesta final
```

Como explicarlo:

> LangGraph organiza el flujo del agente como un grafo de razonamiento y acciones. El modelo puede decidir ejecutar herramientas y luego usar sus resultados para responder.

## 11. Memoria conversacional

Ubicacion:

- MemorySaver import: `backend/agent_core.py`.
- Instancia `_memory`: `backend/agent_core.py`.
- Config por sesion: `backend/agent_core.py`, funcion `run_agent`.

El frontend genera `sessionId`:

- `frontend/app.js`, linea 10.

Y lo envia en cada `/chat`:

- `frontend/app.js`, lineas 605-609.

Como explicarlo:

> Cada conversacion se identifica por `session_id`. LangGraph usa ese id como `thread_id`, por lo que puede mantener contexto por usuario durante la sesion.

Limitacion:

- La memoria es en memoria.
- Si el servidor reinicia, se pierde.
- No hay persistencia en base de datos.

## 12. Tokens y costos aproximados

Modelos configurados:

- Rapido: `llama-3.1-8b-instant`.
- Pensador: `llama-3.3-70b-versatile`.

Segun precios oficiales de Groq, revisables en:

- https://groq.com/pricing/
- https://console.groq.com/docs/rate-limits

Formula general:

```text
costo = (tokens_input / 1,000,000 * precio_input) + (tokens_output / 1,000,000 * precio_output)
```

Estimacion practica por pregunta en ViajeBot:

- Pregunta simple sin tools:
  - Input: 600 a 1,200 tokens.
  - Output: 100 a 300 tokens.
- Pregunta con tools:
  - Input: 1,200 a 3,500 tokens.
  - Output: 200 a 700 tokens.
- Pregunta con RAG:
  - Input adicional por RAG: hasta 2 chunks recuperados.
  - Cada chunk se recorta a 450 caracteres en la linea 288.
  - En total suele sumar alrededor de 200 a 300 tokens extra.

Ejemplo aproximado con 2,000 tokens de entrada y 400 de salida:

- Con `llama-3.1-8b-instant`, el costo es muy bajo, del orden de fracciones pequenas de centavo.
- Con `llama-3.3-70b-versatile`, cuesta mas, pero se usa solo en preguntas complejas.

Como explicarlo:

> El sistema minimiza tokens con un prompt corto, maximo 8 mensajes de historial, RAG limitado a 2 chunks y respuestas concisas. Ademas enruta preguntas simples al modelo 8B y reserva el 70B para razonamiento complejo.

## 13. Que no termina de funcionar perfecto y como explicarlo

### Imagenes

Estado:

- Para destinos conocidos se usan imagenes locales.
- Para destinos desconocidos se consulta DuckDuckGo Images y Wikimedia.

Problemas posibles:

- Las APIs externas pueden fallar.
- El buscador puede devolver imagenes no exactamente de la ciudad.
- Algunas imagenes pueden ser genericas o poco representativas.

Como explicarlo:

> La galeria combina imagenes curadas para destinos principales con busqueda dinamica para destinos no predefinidos. La busqueda dinamica depende de fuentes externas, por eso puede tener variacion en calidad o disponibilidad.

### RAG

Estado:

- El RAG esta enfocado en turismo de Colombia.

Problema:

- No debe usarse como fuente para destinos internacionales.

Como explicarlo:

> La base vectorial actual esta especializada en Colombia. Para destinos internacionales el agente debe usar conocimiento general o busqueda web.

### Memoria y cache

Estado:

- Memoria y cache estan en RAM.

Problema:

- Se pierden al reiniciar el servidor.

Como explicarlo:

> Para el alcance del prototipo se usa memoria en proceso. En produccion se podria migrar a Redis, PostgreSQL o una base vectorial persistente.

### Audio

Problemas:

- TTS depende de gTTS e internet.
- STT depende de Groq Whisper y de permisos de microfono.
- El audio transcrito no se envia automaticamente; queda en el input.

Como explicarlo:

> El modo voz esta separado en dos pasos: transcripcion y respuesta hablada. Esto evita enviar mensajes por accidente y facilita revisar lo transcrito antes de consultar al agente.

### Seguridad/API

Estado:

- CORS esta abierto con `allow_origins=["*"]`, `backend/main.py`, lineas 35-41.

Como explicarlo:

> Para facilitar pruebas del frontend se dejo CORS abierto. En produccion se deberia restringir al dominio oficial.

## 14. Aseguramiento de Calidad (QA)

### 14.1 Pruebas Automatizadas

Ubicacion: `backend/test_tools.py`.

Que hace:

- Ejecuta tests unitarios para las herramientas principales del sistema.
- Verifica que el conversor de moneda funcione correctamente.
- Verifica que la busqueda web formatee los resultados adecuadamente.
- Usa mocks para simular APIs externas, sin dependencias reales.
- Valida manejo de errores y casos edge.

Funcionalidades implementadas:

1. **test_currency_converter_basic**: Verifica que el conversor devuelva el formato correcto con simbolos de moneda y tasas.
2. **test_currency_converter_invalid_currency**: Verifica manejo de códigos de moneda inválidos.
3. **test_currency_converter_api_failure**: Verifica manejo de fallos de API.
4. **test_web_search_basic**: Verifica que la búsqueda web formatee resultados con título, cuerpo y fuente.
5. **test_web_search_no_results**: Verifica manejo cuando no hay resultados.
6. **test_web_search_error**: Verifica manejo de errores de red.
7. **test_currency_rates_cache**: Verifica que las tasas de cambio se cacheen para evitar llamadas repetidas.
8. **test_currency_converter_tool_signature**: Verifica que la tool tenga la firma correcta y docstring.
9. **test_web_search_tool_signature**: Verifica que la tool tenga la firma correcta y docstring.

Como funciona:

```text
pytest descubre tests en test_tools.py
  -> cada test usa @patch para mockear APIs externas
  -> ejecuta la funcion de tool con datos simulados
  -> verifica que el resultado tenga el formato esperado
  -> reporta pass/fail
```

Conexiones:

- `test_tools.py` importa desde `tools.py`: `currency_converter`, `web_search`, `_currency_rates`.
- Usa `unittest.mock` para simular `requests.get` y `_ddg_text_search`.
- No depende de servicios externos reales (DuckDuckGo, open.er-api.com).

Como explicarlo:

> Los tests unitarios validan que cada herramienta funcione correctamente sin depender de servicios externos. Usamos mocks para simular las respuestas de las APIs, lo que permite ejecutar los tests rapidamente y de forma confiable en cualquier entorno.

### 14.2 Integración Continua (CI)

Ubicacion: `.github/workflows/ci.yml`.

Que hace:

- Ejecuta automaticamente los tests en cada push o pull request a GitHub.
- Corre los tests en un entorno Ubuntu con Python 3.10.
- Instala dependencias desde `requirements.txt`.
- Ejecuta `pytest` en el directorio `backend`.
- Verifica que el codigo Python sea sintacticamente valido con `py_compile`.

Flujo paso a paso:

```text
Developer hace push a GitHub
  -> GitHub Actions detecta el evento
  -> Crea un runner Ubuntu
  -> Checkout del codigo
  -> Setup Python 3.10
  -> Install dependencies (pip install -r requirements.txt)
  -> Run tests (cd backend && python -m pytest test_tools.py -v)
  -> Check syntax (python -m py_compile backend/*.py)
  -> Reporta resultado (check verde ✅ o rojo ❌)
```

Conexiones:

- El workflow se conecta automaticamente con el repositorio de GitHub.
- Usa actions oficiales: `actions/checkout@v4`, `actions/setup-python@v5`.
- Ejecuta los mismos tests que se pueden correr localmente.

Costo:

- $0 (GitHub Actions free tier para repositorios publicos y privados).

Como explicarlo:

> La integracion continua asegura que cada cambio de codigo pase por los tests automaticamente antes de ser aceptado. Esto previene regresiones y mantiene la calidad del proyecto sin costo adicional.

### 14.3 Mejoras de Type Hints

Ubicaciones:

- `backend/utils.py`: funciones `_retry`, `_ddg_text_search`, `_ddg_image_search`, `_contains_any`, `_detect_language`, `_clean_destination_name`, `_get_image_search_variants`, `_extract_destination_from_location_question`, `_is_travel_related`.
- `backend/agent_core.py`: funciones `_trim_to_window`, `_agent_prompt`, `_select_agent`, `run_agent`.

Que hace:

- Hace los tipos de datos mas explicitos.
- Usa sintaxis moderna de Python (ej: `dict[str, str]` en lugar de `dict`).
- Mejora la legibilidad del codigo.
- Facilita la deteccion de errores por IDEs y linters.
- Permite mejor autocompletado y documentacion automatica.

Ejemplos de mejoras:

```python
# Antes
def _ddg_text_search(query: str, max_results: int = 4) -> list[dict]:

# Despues
def _ddg_text_search(query: str, max_results: int = 4) -> list[dict[str, str]]:

# Antes
def _select_agent(user_message: str, mode: str = "text"):

# Despues
def _select_agent(user_message: str, mode: str = "text") -> tuple:

# Antes
def run_agent(session_id: str, user_message: str, mode: str = "text") -> dict:

# Despues
def run_agent(session_id: str, user_message: str, mode: str = "text") -> dict[str, any]:
```

Como explicarlo:

> Los type hints mejorados hacen explicito que tipos de datos espera y devuelve cada funcion. Esto ayuda a prevenir errores, mejora la documentacion y permite que los IDEs ofrezcan mejor autocompletado.

### 14.4 Como Ejecutar las Mejoras de QA Localmente

Para correr los tests:

```bash
cd backend
python -m pytest test_tools.py -v
```

Para entender los resultados:

- `PASSED`: El test paso correctamente.
- `FAILED`: El test fallo y muestra el error.
- `.`: Un test paso (modo verbose muestra mas detalle).

Para verificar sintaxis del codigo:

```bash
python -m py_compile backend/*.py
```

### 14.5 Conexiones del Sistema de QA

```text
Desarrollador escribe codigo
  -> hace commit y push
  -> GitHub Actions ejecuta CI
     -> instala dependencias
     -> corre pytest
     -> verifica sintaxis
  -> si pasa: check verde ✅
  -> si falla: check rojo ❌ + notificacion
  -> desarrollador corrige y repite
```

El sistema de QA esta integrado con:

- **Desarrollo local**: Tests pueden correrse en la maquina del desarrollador.
- **GitHub**: CI automatico en cada cambio.
- **Codigo**: Type hints ayudan a prevenir errores durante desarrollo.
- **Documentacion**: REPORTE_QA.md detalla estado y mejoras.

## 15. Resumen corto para sustentacion

> ViajeBot usa FastAPI como backend, un frontend en HTML/CSS/JS y un agente LangGraph ReAct conectado a tools de busqueda web, conversion de moneda, RAG e imagenes. LangChain permite definir tools, manejar mensajes, conectar modelos y crear embeddings. El RAG toma contenido turistico de Colombia, lo divide en chunks, lo convierte en embeddings con Gemini y lo guarda en FAISS. Cuando una pregunta aplica, se recuperan los dos chunks mas relevantes y se entregan al agente. Para optimizar costos, se usa un modelo rapido 8B para tareas simples y voz, y un modelo 70B para razonamiento complejo. El frontend renderiza chat, mapas, galerias e interacciones de voz. El sistema incluye pruebas automatizadas con pytest, integracion continua con GitHub Actions, y type hints mejorados para asegurar calidad sin costo adicional.

