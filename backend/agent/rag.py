"""
RAG: base de conocimiento de turismo en Colombia.

Al iniciar el servidor, setup_rag() descarga RAG_URL, lo divide en chunks,
los convierte en embeddings con Gemini y los guarda en una base vectorial
FAISS (en memoria). travel_knowledge_lookup() recupera los fragmentos mas
relevantes para una pregunta sobre Colombia.

Nota: la tool `travel_knowledge` (en tools.py) es solo el envoltorio @tool que
llama a travel_knowledge_lookup().
"""

from functools import lru_cache

import requests
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from .config import GEMINI_API_KEY, RAG_URL
from .helpers import _retry, _contains_any
from .vocabulary import COLOMBIA_RAG_TERMS

# Estado del retriever, poblado por setup_rag() en el arranque de FastAPI.
_rag_retriever = None


def setup_rag() -> None:
    """Scrape RAG_URL, chunk, embed, store in FAISS. Called once at startup."""
    global _rag_retriever
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from bs4 import BeautifulSoup

        print(f"[RAG] Fetching content from: {RAG_URL}")
        resp = _retry(lambda: requests.get(RAG_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"}))
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        raw_text = soup.get_text(separator="\n", strip=True)

        splitter = RecursiveCharacterTextSplitter(chunk_size=650, chunk_overlap=80)
        chunks = splitter.create_documents([raw_text], metadatas=[{"source": RAG_URL}])

        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=GEMINI_API_KEY)
        vectorstore = FAISS.from_documents(chunks, embeddings)
        _rag_retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
        print(f"[RAG] ✅ Indexed {len(chunks)} chunks from {RAG_URL}")
    except Exception as exc:
        print(f"[RAG] ⚠️  RAG setup failed (will skip): {exc}")
        _rag_retriever = None


def travel_knowledge_lookup(query: str) -> str:
    """
    Logica de la tool `travel_knowledge`.
    Recupera conocimiento especializado de turismo de Colombia desde FAISS.
    """
    if _rag_retriever is None:
        return "Knowledge base unavailable. Use web_search instead."
    if not _contains_any(query, COLOMBIA_RAG_TERMS):
        return "The RAG knowledge base only covers Colombia tourism. Use web_search or general travel knowledge for this destination."
    try:
        return _cached_travel_knowledge(query)
    except Exception as exc:
        return f"Retrieval error: {exc}"


@lru_cache(maxsize=128)
def _cached_travel_knowledge(query: str) -> str:
    docs = _retry(lambda: _rag_retriever.invoke(query))
    if not docs:
        return "No relevant information found in the knowledge base."
    return "\n\n---\n\n".join(d.page_content[:450] for d in docs)
