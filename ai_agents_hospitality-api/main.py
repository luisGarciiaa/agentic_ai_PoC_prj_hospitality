"""
FastAPI application for hosting a WebSocket-based chat interface.

- Exposes a WebSocket endpoint for real-time chat
- Uses Super SQL agent (Hotels + Rooms + Bookings) as primary
- Falls back to legacy agents (SQL / RAG / Exercise 0) if needed
"""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from util.logger_config import logger
from util.configuration import settings, PROJECT_ROOT


# --------------------------------------------------
# Exercise 0 agent (simple / legacy)
# --------------------------------------------------
EXERCISE_0_AVAILABLE = False
try:
    from agents.hotel_simple_agent import handle_hotel_query_simple, load_hotel_data
    try:
        load_hotel_data()
        EXERCISE_0_AVAILABLE = True
        logger.info("✅ Exercise 0 agent loaded successfully and hotel data verified")
    except Exception as e:
        logger.warning(f"Exercise 0 agent code loaded but data/files not ready: {e}")
        logger.warning("Will not use Exercise 0 until data is ready")
        EXERCISE_0_AVAILABLE = False
except ImportError as e:
    logger.warning(f"Exercise 0 agent not available (ImportError): {e}")
    EXERCISE_0_AVAILABLE = False
except Exception as e:
    logger.warning(f"Error loading Exercise 0 agent: {e}.")
    EXERCISE_0_AVAILABLE = False


# --------------------------------------------------
# Exercise 1: RAG agent
# --------------------------------------------------
EXERCISE_1_AVAILABLE = False
try:
    from agents.hotel_rag_agent import handle_hotel_query_rag
    EXERCISE_1_AVAILABLE = True
    logger.info("✅ Exercise 1 (RAG) agent loaded successfully")
except Exception as e:
    logger.warning(f"Exercise 1 (RAG) not available: {e}")
    EXERCISE_1_AVAILABLE = False


# --------------------------------------------------
# Exercise 2: SQL agent (bookings only)
# --------------------------------------------------
EXERCISE_2_AVAILABLE = False
try:
    from agents.booking_sql_agent import handle_booking_query_sql
    EXERCISE_2_AVAILABLE = True
    logger.info("✅ Exercise 2 (SQL) agent loaded successfully")
except Exception as e:
    logger.warning(f"Exercise 2 (SQL) agent not available: {e}")
    EXERCISE_2_AVAILABLE = False


# --------------------------------------------------
# Super Orchestrator (RAG + SQL) - IMPORTADO PERO NO USADO
# --------------------------------------------------
ORCHESTRATOR_AVAILABLE = False
try:
    from agents.hotel_orchestrator_agent import handle_hotel_query_orchestrator
    ORCHESTRATOR_AVAILABLE = True
    logger.info("✅ Super Orchestrator agent loaded successfully")
except Exception as e:
    logger.warning(f"Super Orchestrator not available: {e}")
    ORCHESTRATOR_AVAILABLE = False


# --------------------------------------------------
# SUPER SQL Agent (Rooms + Hotels + Bookings)
# --------------------------------------------------
SUPER_SQL_AVAILABLE = False
try:
    from agents.super_sql_agent import handle_super_sql_query
    SUPER_SQL_AVAILABLE = True
    logger.info("✅ Super SQL agent loaded successfully")
except Exception as e:
    logger.warning(f"Super SQL agent not available: {e}")
    SUPER_SQL_AVAILABLE = False


GENERIC_UNAVAILABLE_MESSAGE = (
    "The system could not process your request because no agent is currently available.\n\n"
    "Please try again later."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Hospitality API...")
    yield
    logger.info("Shutting down AI Hospitality API...")


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))


@app.get("/")
async def get(request: Request):
    """
    Serve the main web interface.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws/{uuid}")
async def websocket_endpoint(websocket: WebSocket, uuid: str):
    """
    Handle WebSocket connections for real-time chat.

    Priority:
    1) Super SQL agent (hotels + rooms + bookings)
    2) Exercise 2 (SQL - bookings only)
    3) Exercise 1 (RAG)
    4) Exercise 0 (simple)
    """
    await websocket.accept()
    logger.info("WebSocket connection opened for %s", uuid)

    try:
        while True:
            try:
                raw_data = await websocket.receive_text()
                logger.info(f"Received from {uuid}: {raw_data}")

                # Parse JSON {"content": "..."} o texto plano
                try:
                    message_data = json.loads(raw_data)
                    user_query = message_data.get("content", raw_data)
                except json.JSONDecodeError:
                    user_query = raw_data

                # --------------------------------------------------
                # 1️⃣ Super SQL como primera opción
                # --------------------------------------------------
                if SUPER_SQL_AVAILABLE:
                    try:
                        logger.info(
                            f"Using SUPER SQL agent for query: {user_query[:100]}..."
                        )
                        response_content = await handle_super_sql_query(user_query)
                        logger.info(
                            f"✅ SUPER SQL response generated successfully for {uuid}"
                        )
                    except Exception as e:
                        logger.error(f"❌ Error in SUPER SQL agent: {e}", exc_info=True)
                        logger.warning(
                            "Falling back to classic agents (SQL → RAG → Exercise 0)"
                        )

                        # 🔁 Fallback: SQL → RAG → Exercise 0
                        if EXERCISE_2_AVAILABLE:
                            try:
                                logger.info(
                                    f"Using Exercise 2 (SQL) agent for query (fallback): {user_query[:100]}..."
                                )
                                response_content = await handle_booking_query_sql(
                                    user_query
                                )
                            except Exception as e2:
                                logger.error(
                                    f"❌ Error in Exercise 2 (SQL): {e2}", exc_info=True
                                )
                                if EXERCISE_1_AVAILABLE:
                                    try:
                                        logger.info(
                                            f"Using Exercise 1 (RAG) agent for query (fallback): {user_query[:100]}..."
                                        )
                                        response_content = (
                                            await handle_hotel_query_rag(user_query)
                                        )
                                    except Exception as e3:
                                        logger.error(
                                            f"❌ Error in Exercise 1 (RAG): {e3}",
                                            exc_info=True,
                                        )
                                        if EXERCISE_0_AVAILABLE:
                                            response_content = (
                                                await handle_hotel_query_simple(
                                                    user_query
                                                )
                                            )
                                        else:
                                            response_content = (
                                                GENERIC_UNAVAILABLE_MESSAGE
                                            )
                                elif EXERCISE_0_AVAILABLE:
                                    response_content = await handle_hotel_query_simple(
                                        user_query
                                    )
                                else:
                                    response_content = GENERIC_UNAVAILABLE_MESSAGE
                        elif EXERCISE_1_AVAILABLE:
                            try:
                                logger.info(
                                    f"Using Exercise 1 (RAG) agent for query (fallback): {user_query[:100]}..."
                                )
                                response_content = await handle_hotel_query_rag(
                                    user_query
                                )
                            except Exception as e2:
                                logger.error(
                                    f"❌ Error in Exercise 1 (RAG): {e2}", exc_info=True
                                )
                                if EXERCISE_0_AVAILABLE:
                                    response_content = await handle_hotel_query_simple(
                                        user_query
                                    )
                                else:
                                    response_content = GENERIC_UNAVAILABLE_MESSAGE
                        elif EXERCISE_0_AVAILABLE:
                            try:
                                logger.info(
                                    f"Using Exercise 0 agent for query (fallback): {user_query[:100]}..."
                                )
                                response_content = await handle_hotel_query_simple(
                                    user_query
                                )
                            except Exception as e2:
                                logger.error(
                                    f"❌ Error in Exercise 0 agent: {e2}", exc_info=True
                                )
                                response_content = GENERIC_UNAVAILABLE_MESSAGE
                        else:
                            logger.warning(
                                "No agents available (SUPER_SQL/SQL/RAG/Exercise 0). Sending generic message."
                            )
                            response_content = GENERIC_UNAVAILABLE_MESSAGE

                # --------------------------------------------------
                # 2️⃣ Si SUPER SQL no está disponible: fallback clásico SQL → RAG → Exercise 0
                # --------------------------------------------------
                else:
                    if EXERCISE_2_AVAILABLE:
                        try:
                            logger.info(
                                f"Using Exercise 2 (SQL) agent for query: {user_query[:100]}..."
                            )
                            response_content = await handle_booking_query_sql(
                                user_query
                            )
                            logger.info(
                                f"✅ Exercise 2 (SQL) response generated successfully for {uuid}"
                            )
                        except Exception as e:
                            logger.error(
                                f"❌ Error in Exercise 2 (SQL): {e}", exc_info=True
                            )
                            logger.warning(
                                "Falling back to Exercise 1 / Exercise 0 (no SUPER_SQL)"
                            )

                            if EXERCISE_1_AVAILABLE:
                                try:
                                    logger.info(
                                        f"Using Exercise 1 (RAG) agent for query (fallback): {user_query[:100]}..."
                                    )
                                    response_content = await handle_hotel_query_rag(
                                        user_query
                                    )
                                    logger.info(
                                        f"✅ Exercise 1 (RAG) response generated successfully for {uuid}"
                                    )
                                except Exception as e2:
                                    logger.error(
                                        f"❌ Error in Exercise 1 (RAG): {e2}",
                                        exc_info=True,
                                    )
                                    if EXERCISE_0_AVAILABLE:
                                        response_content = (
                                            await handle_hotel_query_simple(user_query)
                                        )
                                    else:
                                        response_content = GENERIC_UNAVAILABLE_MESSAGE
                            elif EXERCISE_0_AVAILABLE:
                                response_content = await handle_hotel_query_simple(
                                    user_query
                                )
                            else:
                                response_content = GENERIC_UNAVAILABLE_MESSAGE

                    elif EXERCISE_1_AVAILABLE:
                        try:
                            logger.info(
                                f"Using Exercise 1 (RAG) agent for query: {user_query[:100]}..."
                            )
                            response_content = await handle_hotel_query_rag(user_query)
                            logger.info(
                                f"✅ Exercise 1 (RAG) response generated successfully for {uuid}"
                            )
                        except Exception as e:
                            logger.error(
                                f"❌ Error in Exercise 1 (RAG): {e}", exc_info=True
                            )
                            if EXERCISE_0_AVAILABLE:
                                response_content = await handle_hotel_query_simple(
                                    user_query
                                )
                            else:
                                response_content = GENERIC_UNAVAILABLE_MESSAGE

                    elif EXERCISE_0_AVAILABLE:
                        try:
                            logger.info(
                                f"Using Exercise 0 agent for query: {user_query[:100]}..."
                            )
                            response_content = await handle_hotel_query_simple(
                                user_query
                            )
                            logger.info(
                                f"✅ Exercise 0 agent response generated successfully for {uuid}"
                            )
                        except Exception as e:
                            logger.error(
                                f"❌ Error in Exercise 0 agent: {e}", exc_info=True
                            )
                            response_content = GENERIC_UNAVAILABLE_MESSAGE
                    else:
                        logger.warning(
                            "No agents available (SUPER_SQL/SQL/RAG/Exercise 0). Sending generic message."
                        )
                        response_content = GENERIC_UNAVAILABLE_MESSAGE

                # Enviar respuesta al cliente
                agent_message = {
                    "role": "assistant",
                    "content": response_content,
                }

                await websocket.send_text(
                    f"JSONSTART{json.dumps(agent_message)}JSONEND"
                )
                logger.info(f"Sent response to {uuid}")

            except WebSocketDisconnect:
                logger.info("WebSocket connection closed for %s", uuid)
                break
            except (RuntimeError, ConnectionError) as e:
                logger.error(
                    "Error in WebSocket connection for %s: %s",
                    uuid,
                    str(e),
                )
                break
    except Exception as e:
        logger.error(
            "Unexpected error in WebSocket for %s: %s",
            uuid,
            str(e),
        )
    finally:
        try:
            await websocket.close()
        except (RuntimeError, ConnectionError) as e:
            logger.error(
                "Error closing WebSocket for %s: %s",
                uuid,
                str(e),
            )


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run("main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
