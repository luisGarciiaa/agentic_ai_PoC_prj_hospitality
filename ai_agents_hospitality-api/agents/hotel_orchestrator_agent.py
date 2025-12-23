# agents/hotel_orchestrator_agent.py
from __future__ import annotations
import os
import asyncio
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from config.agent_config import get_agent_config
from util.logger_config import logger

from agents.hotel_rag_agent import answer_hotel_question_rag
from agents.booking_sql_agent import answer_booking_question_sql


from config.agent_config import get_agent_config
from agents.llm_factory import build_llm


# --------------------------------------------------
# Router LLM: decide "RAG" vs "SQL"
# --------------------------------------------------

_router_chain = None


def _get_router_chain():
    """
    LLM que clasifica la pregunta en dos tipos de agente:

    - "RAG": preguntas sobre configuración de hoteles, habitaciones y precios
      (rooms, tipos, categorías, floors, peak/off season prices, etc.)

    - "SQL": preguntas sobre bookings reales y analítica:
      reservas, revenue, total nights, occupancy, RevPAR, etc.

    La respuesta DEBE ser SOLO:
      - RAG
      - SQL
    """
    global _router_chain
    if _router_chain is not None:
        return _router_chain

    config = get_agent_config()
    # Para el router queremos temperatura 0 siempre
    config.temperature = 0.0
    llm = build_llm(config)


    system_msg = """
You are a routing assistant in a hospitality AI system.

Decide which AGENT should handle the user's question:

Use agent "RAG" when the question is about:
- hotel configuration or static data
- room prices (peak / off season)
- room types (single, double, triple)
- room categories (standard, premium)
- number of rooms per hotel or per floor
- distribution of rooms by type or by floor
- hotel location (country, city, address, zip code)
These are answered from:
- hotels.json
- hotel_details.md
- hotel_rooms.md

Use agent "SQL" when the question is about:
- bookings, reservations, stays
- number of bookings
- total revenue from bookings
- total nights stayed
- occupancy rate
- RevPAR
- any analytics that need the real bookings table in PostgreSQL.

Answer STRICTLY with ONE WORD:
- "RAG"
- "SQL"

No explanation, no markdown, no extra text.
"""

    # few-shot con tus ejemplos
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_msg),

            # --- Ejemplos RAG ---
            ("human", "How much does a double room cost during peak season in 'Royal Sovereign'?"),
            ("ai", "RAG"),
            ("human", "How many double rooms are available on the top floor in 'Noble Abode'?"),
            ("ai", "RAG"),
            (
                "human",
                "What is the distribution of rooms by type (single, double, triple) on each floor "
                "in 'Imperial Crown'?"
            ),
            ("ai", "RAG"),
            ("human", "How many single rooms are there in 'Stellar Hotel'?"),
            ("ai", "RAG"),

            # --- Ejemplos SQL ---
            ("human", "What is the occupancy rate for Imperial Crown in January 2025?"),
            ("ai", "SQL"),
            ("human", "How many bookings did we have in 2025 for Royal Sovereign?"),
            ("ai", "SQL"),
            ("human", "What was the total revenue from bookings in Q1 2025?"),
            ("ai", "SQL"),

            # --- Pregunta actual ---
            ("human", "User question:\n{question}\n\nAgent:"),
        ]
    )

    _router_chain = prompt | llm
    return _router_chain


def _route_question(question: str) -> Literal["RAG", "SQL"]:
    """
    Ejecuta el router y devuelve 'RAG' o 'SQL'.
    En caso de error o etiqueta rara, hace fallback a 'RAG'.
    """
    try:
        chain = _get_router_chain()
        resp = chain.invoke({"question": question})
        label = getattr(resp, "content", str(resp)).strip().upper()
        if label not in {"RAG", "SQL"}:
            logger.warning(f"[ORCH] Router returned unexpected label={label!r}, falling back to RAG")
            return "RAG"
        logger.info(f"[ORCH] Router decision for question='{question}': {label}")
        return label  # type: ignore
    except Exception as e:
        logger.error(f"[ORCH] Error in router: {e}", exc_info=True)
        # fallback conservador: RAG (no toca BBDD)
        return "RAG"


# --------------------------------------------------
# Lógica principal del Orquestador
# --------------------------------------------------

def _looks_like_sql_error(text: str) -> bool:
    """
    Heurística simple para detectar que el SQL agent ha devuelto un error
    en lugar de una respuesta normal.
    """
    if not text:
        return True
    stripped = text.lstrip()
    # El SQL agent suele empezar errores con "❌"
    return stripped.startswith("❌")


def _looks_like_rag_no_info(text: str) -> bool:
    """
    Heurística para detectar el mensaje estándar de 'no info' del RAG.
    """
    if not text:
        return True
    return text.strip().startswith(
        "I couldn't find relevant information in the knowledge base"
    )


def answer_hotel_query_orchestrator(question: str) -> str:
    """
    Super Orquestador con depuración opcional para la UI.

    - Usa router LLM para decidir RAG/SQL.
    - Intenta el agente primario.
    - Si detecta error o falta de info, intenta fallback.
    - Si HOSPITALITY_DEBUG_UI=1, añade un bloque de debug al principio del texto.
    """
    debug_mode = os.getenv("HOSPITALITY_DEBUG_UI", "0") == "1"

    debug_info = {
        "route_label": None,      # etiqueta del router: 'RAG' / 'SQL'
        "primary_agent": None,    # agente que se intentó primero
        "final_agent": None,      # agente que finalmente respondió
        "fallback_used": False,   # si se usó fallback o no
        "notes": [],
    }

    try:
        agent_type = _route_question(question)
        debug_info["route_label"] = agent_type

        # --- Caso SQL como primario ---
        if agent_type == "SQL":
            debug_info["primary_agent"] = "SQL"
            logger.info("[ORCH] Primary route: SQL agent")

            sql_answer = answer_booking_question_sql(question)

            if _looks_like_sql_error(sql_answer):
                debug_info["fallback_used"] = True
                debug_info["notes"].append("SQL answer looked like an error, fallback to RAG")
                logger.warning("[ORCH] SQL answer looks like an error, falling back to RAG")
                try:
                    rag_answer = answer_hotel_question_rag(question)
                    debug_info["final_agent"] = "RAG"
                    final_answer = rag_answer
                except Exception as e:
                    logger.error(f"[ORCH] Error in RAG fallback after SQL: {e}", exc_info=True)
                    debug_info["notes"].append(f"RAG fallback failed: {e}")
                    debug_info["final_agent"] = "SQL (error)"
                    final_answer = sql_answer  # al menos devolvemos el error del SQL
            else:
                debug_info["final_agent"] = "SQL"
                final_answer = sql_answer

        # --- Caso RAG como primario ---
        else:
            debug_info["primary_agent"] = "RAG"
            logger.info("[ORCH] Primary route: RAG agent")

            rag_answer = answer_hotel_question_rag(question)

            if _looks_like_rag_no_info(rag_answer):
                debug_info["fallback_used"] = True
                debug_info["notes"].append("RAG returned 'no info', fallback to SQL")
                logger.info("[ORCH] RAG could not answer (no info). Trying SQL as fallback.")
                try:
                    sql_answer = answer_booking_question_sql(question)
                    debug_info["final_agent"] = "SQL"
                    final_answer = sql_answer
                except Exception as e:
                    logger.error(f"[ORCH] Error in SQL fallback after RAG: {e}", exc_info=True)
                    debug_info["notes"].append(f"SQL fallback failed: {e}")
                    debug_info["final_agent"] = "RAG (no info)"
                    final_answer = rag_answer
            else:
                debug_info["final_agent"] = "RAG"
                final_answer = rag_answer

    except Exception as e:
        logger.error(f"[ORCH] Unexpected error in orchestrator: {e}", exc_info=True)
        debug_info["notes"].append(f"Unexpected error in orchestrator: {e}")
        debug_info["final_agent"] = "ERROR"
        final_answer = (
            "❌ Unexpected error while processing your question in the orchestrator.\n\n"
            f"Error: `{e}`"
        )

    # --------------------------------------------------
    # Bloque de depuración para la UI (markdown)
    # --------------------------------------------------
    if debug_mode:
        notes_text = (
            "- " + "\n- ".join(debug_info["notes"])
            if debug_info["notes"]
            else "- (no additional notes)"
        )
        debug_block = f"""```debug
Orchestrator route label: {debug_info['route_label']}
Primary agent: {debug_info['primary_agent']}
Final agent: {debug_info['final_agent']}
Fallback used: {debug_info['fallback_used']}
Notes:
{notes_text}
```"""

        return f"{debug_block}\n\n{final_answer}"

    # Si no hay debug para UI → devolvemos solo la respuesta normal
    return final_answer



# --------------------------------------------------
# Wrapper asíncrono para FastAPI/WebSocket
# --------------------------------------------------

async def handle_hotel_query_orchestrator(user_query: str) -> str:
    """
    Wrapper async para usar en el WebSocket.
    Ejecuta el orquestador síncrono en un executor.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, answer_hotel_query_orchestrator, user_query)
