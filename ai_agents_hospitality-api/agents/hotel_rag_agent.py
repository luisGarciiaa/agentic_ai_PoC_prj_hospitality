"""
Exercise 1: RAG Agent for Hotel Details + Rooms

Builds a vector store (Chroma Server) from hotel documents and answers queries by retrieval.

Implements the workshop checklist:
- JSONLoader for hotels.json
- TextLoader for hotel_details.md + hotel_rooms.md
- RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
- HuggingFaceEmbeddings (LOCAL)
- ChromaDB vector store (Chroma Server via HttpClient)
- Persistence handled by Chroma Server + docker volume (vector_db_data)
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import List, Optional, Tuple
from typing import List, Tuple, Dict

import chromadb
from chromadb.config import Settings as ChromaSettings

from util.configuration import PROJECT_ROOT
from util.logger_config import logger
from config.agent_config import get_agent_config

# LangChain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader, JSONLoader
from langchain_community.embeddings import HuggingFaceEmbeddings

# Splitter (new + fallback)
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

# LLM (RAG still uses an LLM to write the final answer)
from langchain_google_genai import ChatGoogleGenerativeAI


# --------------------------------------------------
# Paths (same strategy as Exercise 0)
# --------------------------------------------------
HOTELS_DATA_PATH_LOCAL = PROJECT_ROOT / "data" / "hotels"
HOTELS_DATA_PATH_EXTERNAL = PROJECT_ROOT.parent / "bookings-db" / "output_files" / "hotels"


def _get_hotels_data_path() -> Path:
    if HOTELS_DATA_PATH_LOCAL.exists() and (HOTELS_DATA_PATH_LOCAL / "hotels.json").exists():
        logger.info(f"[RAG] Using local hotel data path: {HOTELS_DATA_PATH_LOCAL}")
        return HOTELS_DATA_PATH_LOCAL
    logger.info(f"[RAG] Using external hotel data path: {HOTELS_DATA_PATH_EXTERNAL}")
    return HOTELS_DATA_PATH_EXTERNAL


# --------------------------------------------------
# Globals (cached)
# --------------------------------------------------
_vectorstore: Optional[Chroma] = None
_rag_chain = None
_embeddings: Optional[HuggingFaceEmbeddings] = None


# --------------------------------------------------
# Document loading (Phase 2: JSONLoader + TextLoader)
# --------------------------------------------------
def _load_documents() -> List[Document]:
    data_path = _get_hotels_data_path()

    hotels_json = data_path / "hotels.json"
    details_md = data_path / "hotel_details.md"
    rooms_md = data_path / "hotel_rooms.md"



    if not hotels_json.exists() or not details_md.exists() or not rooms_md.exists():
        raise FileNotFoundError(
            f"Missing hotel files in {data_path}\n"
            f"Expected: hotels.json, hotel_details.md, hotel_rooms.md\n"
            f"Generate them with:\n"
            f"cd bookings-db && python src/gen_synthetic_hotels.py --num_hotels 50"
        )

    docs: List[Document] = []

    json_loader = JSONLoader(
        file_path=str(hotels_json),
        jq_schema=".Hotels[]",
        text_content=False,
    )
    json_docs = json_loader.load()
    for d in json_docs:
        d.metadata = {**(d.metadata or {}), "source": "hotels.json"}
    docs.extend(json_docs)

    details_docs = TextLoader(str(details_md), encoding="utf-8").load()
    for d in details_docs:
        d.metadata = {**(d.metadata or {}), "source": "hotel_details.md"}
    docs.extend(details_docs)

    rooms_docs = TextLoader(str(rooms_md), encoding="utf-8").load()
    for d in rooms_docs:
        d.metadata = {**(d.metadata or {}), "source": "hotel_rooms.md"}
    docs.extend(rooms_docs)



    logger.info(f"[RAG] Loaded {len(docs)} raw documents (JSON per hotel + markdown)")
    return docs


def _get_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


# --------------------------------------------------
# LOCAL embeddings only (no Google)
# --------------------------------------------------
def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    model_name = os.getenv("HF_EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    logger.info(f"[RAG] Using LOCAL HuggingFaceEmbeddings: {model_name}")

    _embeddings = HuggingFaceEmbeddings(model_name=model_name)
    return _embeddings


# --------------------------------------------------
# Vector store (Chroma Server) + indexing (Phase 2)
# --------------------------------------------------
def _get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    chroma_host = os.getenv("VECTOR_DB_HOST", "vector-db")
    chroma_port = int(os.getenv("VECTOR_DB_PORT", "8000"))
    collection = os.getenv("VECTOR_DB_COLLECTION", "hotels_rag")

    force_reindex = os.getenv("RAG_FORCE_REINDEX", "0") == "1"

    logger.info(
        f"[RAG] Connecting to Chroma at {chroma_host}:{chroma_port} "
        f"collection='{collection}' force_reindex={force_reindex}"
    )

    chroma_client = chromadb.HttpClient(
        host=chroma_host,
        port=chroma_port,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    embeddings = _get_embeddings()

    _vectorstore = Chroma(
        client=chroma_client,
        collection_name=collection,
        embedding_function=embeddings,
    )

    try:
        count = _vectorstore._collection.count()
    except Exception:
        count = 0

    if force_reindex:
        logger.warning("[RAG] Force reindex enabled → deleting and rebuilding collection")
        try:
            chroma_client.delete_collection(collection)
        except Exception:
            pass

        _vectorstore = Chroma(
            client=chroma_client,
            collection_name=collection,
            embedding_function=embeddings,
        )
        count = 0

    if count == 0:
        logger.info("[RAG] Collection empty → indexing documents now...")

        docs = _load_documents()
        splitter = _get_splitter()
        chunks = splitter.split_documents(docs)

        logger.info(f"[RAG] Adding {len(chunks)} chunks to Chroma...")
        _vectorstore.add_documents(chunks)
        logger.info("[RAG] ✅ Indexing done.")
    else:
        logger.info(f"[RAG] Collection already has {count} items → skip indexing")

    return _vectorstore


# --------------------------------------------------
# Retrieval strategy: threshold + min 5 + max 50
# --------------------------------------------------
def _retrieve_docs_adaptive(
    vs: Chroma,
    question: str,
    *,
    min_docs: int = 5,
    max_docs: int = 50,
    candidate_pool: int = 120,
    abs_threshold: float = 0.90,
    rel_mult: float = 1.25,
) -> Tuple[List[Document], Dict]:
    """
    Retrieval adaptativo (sin hardcode):
    - Siempre devuelve mínimo `min_docs`
    - A partir de ahí, incluye chunks mientras sean "lo bastante cercanos"
      usando un corte adaptativo: cutoff = min(abs_threshold, best_distance * rel_mult)
    - Nunca supera `max_docs`

    IMPORTANTE: `similarity_search_with_score` en Chroma suele devolver DISTANCIA (menor = mejor).
    """
    candidates = vs.similarity_search_with_score(question, k=candidate_pool)
    if not candidates:
        return [], {"mode": "no_candidates", "candidates": 0}

    # Ordena por distancia ascendente (mejor primero)
    candidates.sort(key=lambda x: x[1])

    best = float(candidates[0][1])
    cutoff = min(abs_threshold, best * rel_mult)

    chosen: List[Tuple[Document, float]] = []

    # 🔍 DEBUG: info de todos los candidatos (hasta candidate_pool)
    debug_candidates = []

    # 1) mínimo garantizado
    for idx, (doc, score) in enumerate(candidates, start=1):
        score = float(score)
        # Por defecto no elegido; lo marcamos luego
        debug_entry = {
            "rank": idx,
            "score": score,
            "source": doc.metadata.get("source", "?"),
            # estos campos los rellenamos después de decidir chosen
            "chosen": False,
            "reason": "",
        }
        debug_candidates.append((doc, score, debug_entry))

    # Aplicamos la lógica original sobre la lista ordenada
    for idx, (doc, score, debug_entry) in enumerate(debug_candidates, start=1):
        score = float(score)

        if idx <= min_docs:
            chosen.append((doc, score))
            debug_entry["chosen"] = True
            debug_entry["reason"] = "within_min_docs"
            continue

        if len(chosen) >= max_docs:
            debug_entry["reason"] = "max_docs_reached"
            break

        if score <= cutoff:
            chosen.append((doc, score))
            debug_entry["chosen"] = True
            debug_entry["reason"] = "score<=cutoff"
        else:
            debug_entry["reason"] = "score>cutoff_break"
            # Como está ordenado, todo lo que venga después será peor
            break

    docs = [d for d, _ in chosen]

    # Formateamos debug compactado (no meter todo el tocho, solo los primeros N)
    debug_rows = []
    for doc, score, entry in debug_candidates[:60]:  # recortamos a 60 para no petar logs
        row = {
            "rank": entry["rank"],
            "score": entry["score"],
            "source": entry["source"],
            "chosen": entry["chosen"],
            "reason": entry["reason"],
            # opcionalmente puedes meter más cosas:
            # "preview": doc.page_content[:80].replace("\n", " "),
        }
        debug_rows.append(row)

    dbg = {
        "mode": "adaptive",
        "candidates": len(candidates),
        "min_docs": min_docs,
        "max_docs": max_docs,
        "candidate_pool": candidate_pool,
        "best_distance": best,
        "abs_threshold": abs_threshold,
        "rel_mult": rel_mult,
        "cutoff": cutoff,
        "returned": len(docs),
        "debug_candidates": debug_rows,
    }
    return docs, dbg



# --------------------------------------------------
# RAG chain (Phase 3)
# --------------------------------------------------
def _create_rag_chain():
    global _rag_chain
    if _rag_chain is not None:
        return _rag_chain

    config = get_agent_config()

    llm = ChatGoogleGenerativeAI(
        model=config.model,
        temperature=config.temperature,
        google_api_key=config.api_key,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a hotel assistant for a hospitality management system.
Use ONLY the provided context to answer.
If the answer is not present in the context, say you don't have enough information.

Rules:
- Be precise and factual
- Use markdown
- Prefer tables for lists
- When giving prices, include currency and conditions (season, meal plan, guests)
""",
            ),
            ("human", "Context:\n{context}\n\nQuestion:\n{question}"),
        ]
    )

    _rag_chain = prompt | llm
    return _rag_chain


# --------------------------------------------------
# Public API (Phase 4)
# --------------------------------------------------
def answer_hotel_question_rag(question: str, k: int = 5) -> str:
    """
    Retrieve chunks then ask LLM with that context.
    NOTE: `k` is kept for compatibility, but retrieval now uses threshold strategy.
    """
    try:
        vs = _get_vectorstore()

        # Threshold-based retrieval (min 5, max 50)
        min_docs = int(os.getenv("RAG_MIN_DOCS", "5"))
        max_docs = int(os.getenv("RAG_MAX_DOCS", "50"))
        candidate_pool = int(os.getenv("RAG_CANDIDATE_POOL", "120"))
        abs_thr = float(os.getenv("RAG_ABS_THRESHOLD", "2.00"))
        rel_mult = float(os.getenv("RAG_REL_MULT", "2.0"))

        logger.info(
            f"[RAG] Params: min_docs={min_docs} max_docs={max_docs} "
            f"candidate_pool={candidate_pool} abs_threshold={abs_thr} rel_mult={rel_mult}"
        )

        docs, dbg = _retrieve_docs_adaptive(
            vs,
            question,
            min_docs=min_docs,
            max_docs=max_docs,
            candidate_pool=candidate_pool,
            abs_threshold=abs_thr,
            rel_mult=rel_mult,
        )


        logger.info(f"[RAG] Question: {question}")
        logger.info(f"[RAG] Retrieval debug: {dbg}")

        if not docs:
            return "I couldn't find relevant information in the knowledge base for that question."

#------------------------------------------------------------------------------------------------------------------------------------------------------
        show_chunks = os.getenv("RAG_LOG_CHUNKS", "0") == "1"
        if show_chunks:
            for i, d in enumerate(docs, 1):
                src = d.metadata.get("source", "?")
                preview = d.page_content[:180].replace("\n", " ")
                logger.info(f"[RAG] CHUNK {i}/{len(docs)} source={src} preview='{preview}...'")
#------------------------------------------------------------------------------------------------------------------------------------------------------




        context = "\n\n---\n\n".join(
            f"[source={d.metadata.get('source', '?')}] {d.page_content}"
            for d in docs
        )

        chain = _create_rag_chain()
        response = chain.invoke({"context": context, "question": question})
        return getattr(response, "content", str(response))

    except FileNotFoundError as e:
        logger.error(f"[RAG] {e}")
        return (
            "❌ Missing hotel data files.\n\n"
            "Generate them first:\n"
            "```bash\n"
            "cd bookings-db\n"
            "python src/gen_synthetic_hotels.py --num_hotels 50\n"
            "```"
        )

    except Exception as e:
        logger.error(f"[RAG] Error: {e}", exc_info=True)
        return f"❌ Error while processing the question: {e}"


async def handle_hotel_query_rag(user_query: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, answer_hotel_question_rag, user_query)
