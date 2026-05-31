"""
Configuración de RAG (Retrieval Augmented Generation) con FAISS
"""

import requests
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from bs4 import BeautifulSoup

from config import GEMINI_API_KEY, RAG_URL
from utils import _retry

# Retriever global de RAG
_rag_retriever = None


def setup_rag() -> None:
    """
    Descarga contenido de RAG_URL, lo divide en chunks, crea embeddings
    y los almacena en FAISS. Se llama una vez al iniciar el servidor.
    """
    global _rag_retriever
    try:
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


def get_rag_retriever():
    """Retorna el retriever de RAG."""
    return _rag_retriever
