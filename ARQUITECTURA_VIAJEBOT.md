# Arquitectura tecnica de ViajeBot

Este documento explica como se conectan las partes principales de ViajeBot: frontend, backend FastAPI, agentes LangGraph, tools, RAG con FAISS, busqueda de imagenes, audio/TTS, memoria, cache y costos aproximados por tokens.

> Nota: el agente antes vivia en un unico archivo `backend/agent.py`. Ahora esta dividido en el paquete `backend/agent/` por secciones, para que sea mas facil de leer y explicar. La API publica (`run_agent`, `setup_rag`, `search_destination_images`) se re-exporta en `backend/agent/__init__.py`, por lo que `main.py` sigue importando con `from agent import ...`.

### Estructura del paquete `backend/agent/`

- `config.py`: variables de entorno, modelos de Groq y system prompt.
- `vocabulary.py`: palabras clave, destinos conocidos y alias.
- `helpers.py`: helpers genericos (`_retry`, `_contains_any`, limpieza de destino).
- `language.py`: deteccion de idioma, guardrail de viajes y extraccion de destino.
- `rag.py`: RAG con FAISS de turismo de Colombia.
- `media.py`: busqueda de imagenes (DuckDuckGo + Wikimedia) y resumenes.
- `tools.py`: las 4 tools LangChain del agente.
- `core.py`: modelos, memoria, construccion del agente y router `_select_agent`.
- `runner.py`: `run_agent()`, orquestacion y post-procesamiento de la respuesta.

## 1. Vision general del flujo

Flujo principal cuando el usuario envia un mensaje:

```text
Usuario en frontend
  -> frontend/app.js envia POST /chat
  -> backend/main.py recibe la solicitud
  -> backend/agent/runner.py ejecuta run_agent()
  -> LangGraph decide si usa tools
  -> tools consultan web, moneda, RAG o imagenes
  -> el agente genera respuesta
  -> backend devuelve texto, tools usadas, destino y modelo usado
  -> frontend renderiza respuesta, mapa, galeria y audio si aplica
```

Donde verlo:

- Frontend envia `/chat`: `frontend/app.js`, lineas 586-643.
- Endpoint `/chat`: `backend/main.py`, lineas 90-110.
- Ejecucion del agente: `backend/agent/runner.py`, lineas 25-194.
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

Los agentes se construyen en `backend/agent/core.py`.

Modelos configurados:

- `GROQ_FAST_MODEL`: `llama-3.1-8b-instant`, `config.py` linea 23 y `core.py` linea 30.
- `GROQ_THINKING_MODEL`: `llama-3.3-70b-versatile`, `config.py` linea 24 y `core.py` linea 31.

Se crean dos agentes con LangGraph:

- `_agent`: agente rapido, `core.py` lineas 48-53.
- `_thinking_agent`: agente pensador, `core.py` lineas 54-59.

Ambos comparten:

- Las mismas tools: `core.py` linea 29.
- La misma memoria: `core.py` linea 32.
- El mismo prompt dinamico: `core.py` lineas 41-44.
- El mismo RAG/FAISS a traves de la tool `travel_knowledge`.

### Router de agente

Ubicacion: `backend/agent/core.py`, lineas 62-91.

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

Ubicacion: `backend/agent/config.py`, lineas 34-61.

El prompt esta dividido en bloques:

- Identidad: ViajeBot como asistente de viajes.
- Scope: limita el sistema a temas de viaje.
- Style: idioma del usuario, respuestas cortas y estructura.
- Tools: indica cuando usar `travel_knowledge`, `web_search`, `currency_converter` y `place_image_search`.
- Accuracy: evita inventar precios, visas, rutas, horarios y datos de seguridad.
- Memory: recuerda presupuesto, estilo de viaje, acompanantes y duracion.
- Visual UI: indica que el frontend renderiza mapas y galerias y que no debe imprimir URLs crudas.

Tambien se reduce el historial enviado al modelo:

- `_trim_to_window`: `core.py` lineas 35-38.
- `_agent_prompt`: `core.py` lineas 41-44.

Actualmente se mandan maximo 8 mensajes no-system al modelo.

## 5. Tools implementadas

Las tools son funciones decoradas con `@tool` de LangChain. Estan en `backend/agent/tools.py` y se conectan al agente en la lista `_tools` de `core.py`, linea 29.

### 5.1 web_search

Ubicacion:

- Wrapper DuckDuckGo: `tools.py`, lineas 27-30.
- Tool `web_search`: `tools.py`, lineas 34-55.

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

Ubicacion:

- Cache de tasas: `tools.py`, lineas 58-62.
- Tool `currency_converter`: `tools.py`, lineas 66-101.

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

Ubicacion:

- Tool `travel_knowledge` (envoltorio @tool): `tools.py`, lineas 105-114.
- Logica del RAG (`travel_knowledge_lookup`): `rag.py`, lineas 53-65.
- Cache RAG: `rag.py`, lineas 68-73.

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

Ubicacion:

- Alias de busqueda: `vocabulary.py`, lineas 57-74.
- Variantes de busqueda (`_get_image_search_variants`): `helpers.py`, lineas 51-65.
- DuckDuckGo images: `media.py`, lineas 22-25.
- Busqueda principal de imagenes: `media.py`, lineas 29-67.
- Fallback Wikimedia: `media.py`, lineas 71-162.
- Filtro de imagenes no turisticas: `media.py`, lineas 191-205.
- Tool `place_image_search`: `tools.py`, lineas 121-133.

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

Ubicacion: `backend/agent/rag.py`, lineas 26-50.

`setup_rag()` se llama al iniciar FastAPI:

- `backend/main.py`, lineas 44-47.

### Fuente del RAG

Ubicacion: `backend/agent/config.py`, linea 20.

```python
RAG_URL = "https://en.wikipedia.org/wiki/Tourism_in_Colombia"
```

Se descarga el HTML:

- `rag.py`, linea 35.

Se limpia con BeautifulSoup:

- `rag.py`, lineas 36-39.

### Chunks

Ubicacion: `backend/agent/rag.py`, lineas 41-42.

Configuracion:

```python
chunk_size=650
chunk_overlap=80
```

Que significa:

- Cada fragmento tiene hasta 650 caracteres aproximados.
- Cada fragmento comparte 80 caracteres con el anterior para no cortar ideas importantes.

Cuantos chunks se usan:

- Chunks totales indexados: dependen del tamano del texto descargado. El sistema lo imprime al arrancar en `rag.py`, linea 47.
- Chunks recuperados por pregunta: `k=2`, `rag.py` linea 46.

### Embeddings

Ubicacion: `backend/agent/rag.py`, linea 44.

```python
GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
```

Funcionamiento:

1. Cada chunk de texto se convierte en un vector numerico.
2. La pregunta del usuario tambien se convierte en vector.
3. FAISS compara vectores por similitud.
4. Devuelve los chunks mas parecidos.

### FAISS

Ubicacion:

- Creacion de vectorstore: `rag.py`, linea 45.
- Retriever: `rag.py`, linea 46.

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

Ubicacion: `backend/agent/helpers.py`, lineas 16-24.

`_retry` reintenta operaciones que pueden fallar por red o servicio externo:

- Descarga RAG.
- Web search.
- Imagenes.
- Summaries.
- Invocacion del agente.

### Cache

Cache implementada con `@lru_cache`:

- Monedas: `tools.py`, lineas 58-62.
- RAG: `rag.py`, lineas 68-73.
- Imagenes: `media.py`, lineas 29-67.
- Wikimedia: `media.py`, lineas 71-162.
- Summaries: `media.py`, lineas 165-188.

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

- Definir tools con `@tool`: `backend/agent/tools.py`, lineas 17, 33, 65, 104 y 120.
- Manejar mensajes: `HumanMessage`/`AIMessage` en `runner.py` linea 11; `SystemMessage` en `core.py` linea 11.
- Conectar Groq con `ChatGroq`: `core.py`, lineas 12, 30 y 31.
- Crear embeddings con Gemini: `rag.py`, lineas 16 y 44.
- Usar FAISS desde LangChain Community: `rag.py`, linea 30.

Como explicarlo:

> LangChain aporta las piezas: modelo, tools, mensajes, embeddings y vectorstore.

### LangGraph

Se usa para crear el agente ReAct:

- Importacion: `backend/agent/core.py`, linea 15.
- Creacion de agentes: `core.py`, lineas 48-59.
- Memoria: `core.py`, lineas 16-19 y 32.

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

- MemorySaver import: `backend/agent/core.py`, lineas 16-19.
- Instancia `_memory`: `core.py`, linea 32.
- Config por sesion: `runner.py`, linea 42.

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
  - Cada chunk se recorta a 450 caracteres en `rag.py`, linea 73.
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

## 14. Resumen corto para sustentacion

> ViajeBot usa FastAPI como backend, un frontend en HTML/CSS/JS y un agente LangGraph ReAct conectado a tools de busqueda web, conversion de moneda, RAG e imagenes. LangChain permite definir tools, manejar mensajes, conectar modelos y crear embeddings. El RAG toma contenido turistico de Colombia, lo divide en chunks, lo convierte en embeddings con Gemini y lo guarda en FAISS. Cuando una pregunta aplica, se recuperan los dos chunks mas relevantes y se entregan al agente. Para optimizar costos, se usa un modelo rapido 8B para tareas simples y voz, y un modelo 70B para razonamiento complejo. El frontend renderiza chat, mapas, galerias e interacciones de voz.

