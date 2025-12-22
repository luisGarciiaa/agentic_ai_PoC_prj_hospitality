"""
FastAPI application for hosting a WebSocket-based chat interface.

This module provides a FastAPI application that serves as a WebSocket server for real-time
communication. It includes endpoints for serving the main web interface
and handling WebSocket connections for chat interactions.

Exercise 0 Implementation:
- Uses LangChain agent with file context (3 hotels sample)
- Falls back to hardcoded responses if agent is unavailable
- Integrates with WebSocket API for real-time chat
"""

import json
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from util.logger_config import logger
from util.configuration import settings, PROJECT_ROOT





# Import Exercise 0 agent
EXERCISE_0_AVAILABLE = False
try:
    from agents.hotel_simple_agent import handle_hotel_query_simple, load_hotel_data
    # Try to load hotel data to verify everything is set up correctly
    try:
        load_hotel_data()
        EXERCISE_0_AVAILABLE = True
        logger.info("✅ Exercise 0 agent loaded successfully and hotel data verified")
    except Exception as e:
        logger.warning(f"Exercise 0 agent code loaded but data/files not ready: {e}")
        logger.warning("Will use hardcoded responses until hotel data is available")
        EXERCISE_0_AVAILABLE = False
except ImportError as e:
    logger.warning(f"Exercise 0 agent not available (ImportError): {e}")
    logger.warning("Using hardcoded responses. Install LangChain dependencies if needed.")
    EXERCISE_0_AVAILABLE = False
except Exception as e:
    logger.warning(f"Error loading Exercise 0 agent: {e}. Using hardcoded responses.")
    EXERCISE_0_AVAILABLE = False


# Import Exercise 1 RAG agent
EXERCISE_1_AVAILABLE = False
try:
    from agents.hotel_rag_agent import handle_hotel_query_rag
    EXERCISE_1_AVAILABLE = True
    logger.info("✅ Exercise 1 (RAG) agent loaded successfully")
except Exception as e:
    logger.warning(f"Exercise 1 (RAG) not available: {e}")
    EXERCISE_1_AVAILABLE = False



# Import Exercise 2 SQL agent
EXERCISE_2_AVAILABLE = False
try:
    from agents.booking_sql_agent import handle_booking_query_sql
    EXERCISE_2_AVAILABLE = True
    logger.info("✅ Exercise 2 (SQL) agent loaded successfully")
except Exception as e:
    logger.warning(f"Exercise 2 (SQL) agent not available: {e}")
    EXERCISE_2_AVAILABLE = False




# Hardcoded responses for demo queries
HARDCODED_RESPONSES = {
    "list the hotels in france": """Here are the hotels in France:

**Paris:**
- Grand Victoria
- Majestic Plaza
- Obsidian Tower

**Nice:**
- Imperial Crown
- Royal Sovereign""",
    
    "prices for triple premium rooms in paris": """Triple Premium Room prices in Paris:

**Grand Victoria:**
- Peak Season: €450/night
- Off Season: €320/night

**Majestic Plaza:**
- Peak Season: €480/night
- Off Season: €350/night

**Obsidian Tower:**
- Peak Season: €520/night
- Off Season: €380/night""",
    
    "compare the triple room prices at off season for room and breakfast at the hotels in nice": """Triple Room prices at Off Season with Room and Breakfast in Nice:

**Imperial Crown:**
- Standard Triple: €180/night + €25/person breakfast = €255/night total
- Premium Triple: €240/night + €25/person breakfast = €315/night total

**Royal Sovereign:**
- Standard Triple: €190/night + €25/person breakfast = €265/night total
- Premium Triple: €250/night + €25/person breakfast = €325/night total""",
    
    "lowest price for a standard sigle room in nice considering no meal plan": """Lowest price for Standard Single Room in Nice (No Meal Plan):

**Imperial Crown:** €80/night (Off Season)
**Royal Sovereign:** €85/night (Off Season)

The lowest price is at **Imperial Crown** with €80/night during off season.""",
    
    "hotels in paris the meal charge for half board": """Meal charges for Half Board in Paris hotels:

**Grand Victoria:** €45/person/day
**Majestic Plaza:** €50/person/day
**Obsidian Tower:** €55/person/day

*Half Board includes breakfast and dinner*""",
    
    "amount of rooms per type for hotels in paris": """Room distribution by type in Paris hotels:

**Grand Victoria:**
- Single: 30 rooms
- Double: 50 rooms
- Triple: 20 rooms

**Majestic Plaza:**
- Single: 25 rooms
- Double: 45 rooms
- Triple: 30 rooms

**Obsidian Tower:**
- Single: 40 rooms
- Double: 60 rooms
- Triple: 25 rooms""",
    
    "price of a double room standard category in g victoria for peak and off season": """Double Room Standard Category pricing at Grand Victoria:

**Peak Season:** €280/night
**Off Season:** €180/night

Difference: €100/night (35.7% discount in off season)""",
    
    "price for a premium triple room for obsidian tower next october 14th considering room and breakfast and 4 guests": """Price calculation for Premium Triple Room at Obsidian Tower (October 14th):

**Room Rate:** €380/night (Off Season - October)
**Breakfast:** €25/person × 4 guests = €100
**Total:** €480/night

*Note: October is considered off season, and the premium triple room can accommodate up to 4 guests.*"""
}


def find_matching_response(query: str) -> str:
    """
    Find a matching hardcoded response based on the query.
    Uses fuzzy matching to find similar queries.
    
    Args:
        query: User query string
        
    Returns:
        Matching response or default message
    """
    query_lower = query.lower().strip()
    
    # Try exact match first
    if query_lower in HARDCODED_RESPONSES:
        return HARDCODED_RESPONSES[query_lower]
    
    # Try partial matching
    for key, response in HARDCODED_RESPONSES.items():
        # Check if key words are present
        key_words = set(key.split())
        query_words = set(query_lower.split())
        
        # If 60% or more of the key words are in the query
        if len(key_words.intersection(query_words)) / len(key_words) >= 0.6:
            return response
    
    # Default response if no match
    return """I'm a demo API with hardcoded responses. 

Try asking questions about:
- Hotels in France
- Room prices in Paris or Nice
- Meal plans and charges
- Room availability

Example: "list the hotels in France" or "tell me the prices for triple premium rooms in Paris"

*This is a workshop starter - implement your LangChain agent here!*"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown logic.
    """
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

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        TemplateResponse: Rendered HTML template for the main interface.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws/{uuid}")
async def websocket_endpoint(websocket: WebSocket, uuid: str):
    """
    Handle WebSocket connections for real-time chat.

    This endpoint establishes a WebSocket connection and handles
    bidirectional communication between the client and the server.
    
    Uses Exercise 0 agent (LangChain with file context) if available,
    otherwise falls back to hardcoded responses.

    Args:
        websocket (WebSocket): The WebSocket connection instance.
        uuid (str): Unique identifier for the WebSocket connection.
    """
    await websocket.accept()
    logger.info("WebSocket connection opened for %s", uuid)

    try:
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                logger.info(f"Received from {uuid}: {data}")
                
                # Parse the query
                try:
                    message_data = json.loads(data)
                    user_query = message_data.get("content", data)
                except json.JSONDecodeError:
                    user_query = data





                # 1️⃣ Prioridad: Exercise 2 (SQL Agent)
                if EXERCISE_2_AVAILABLE:
                    try:
                        logger.info(f"Using Exercise 2 (SQL) agent for query: {user_query[:100]}...")
                        response_content = await handle_booking_query_sql(user_query)
                        logger.info(f"✅ Exercise 2 (SQL) response generated successfully for {uuid}")
                    except Exception as e:
                        logger.error(f"❌ Error in Exercise 2 (SQL) agent: {e}", exc_info=True)
                        logger.warning("Falling back to Exercise 1 / 0 / hardcoded")

                        # Fallback a Exercise 1 (RAG) si quieres mantenerlo
                        if EXERCISE_1_AVAILABLE:
                            try:
                                logger.info(f"Using Exercise 1 (RAG) agent for query (fallback): {user_query[:100]}...")
                                response_content = await handle_hotel_query_rag(user_query)
                                logger.info(f"✅ Exercise 1 (RAG) response generated successfully for {uuid}")
                            except Exception as e2:
                                logger.error(f"❌ Error in Exercise 1 (RAG): {e2}", exc_info=True)
                                logger.warning("Falling back to Exercise 0 / hardcoded")
                                if EXERCISE_0_AVAILABLE:
                                    response_content = await handle_hotel_query_simple(user_query)
                                else:
                                    response_content = find_matching_response(user_query)

                        # Si no quieres fallback a Exercise 1, comenta el bloque anterior
                        # y deja solo este fallback:
                        elif EXERCISE_0_AVAILABLE:
                            response_content = await handle_hotel_query_simple(user_query)
                        else:
                            response_content = find_matching_response(user_query)

                
                elif EXERCISE_1_AVAILABLE:
                    try:
                        logger.info(f"Using Exercise 1 (RAG) agent for query: {user_query[:100]}...")
                        response_content = await handle_hotel_query_rag(user_query)
                        logger.info(f"✅ Exercise 1 (RAG) response generated successfully for {uuid}")
                    except Exception as e:
                        logger.exception("❌ Exercise 1 (RAG) import failed")

                        logger.error(f"❌ Error in Exercise 1 (RAG): {e}", exc_info=True)
                        logger.warning("Falling back to Exercise 0 / hardcoded")
                        if EXERCISE_0_AVAILABLE:
                            response_content = await handle_hotel_query_simple(user_query)
                        else:
                            response_content = find_matching_response(user_query)
                
                # Get response from Exercise 0 agent or fallback to hardcoded
                elif EXERCISE_0_AVAILABLE:
                    try:
                        logger.info(f"Using Exercise 0 agent for query: {user_query[:100]}...")
                        response_content = await handle_hotel_query_simple(user_query)
                        logger.info(f"✅ Exercise 0 agent response generated successfully for {uuid}")
                    except Exception as e:
                        logger.error(f"❌ Error in Exercise 0 agent: {e}", exc_info=True)
                        logger.warning(f"Falling back to hardcoded response for {uuid}")
                        response_content = find_matching_response(user_query)
                else:
                    # Fallback to hardcoded responses
                    logger.debug(f"Using hardcoded responses (Exercise 0 not available) for {uuid}")
                    response_content = find_matching_response(user_query)
                
                # Send response back to client
                agent_message = {
                    "role": "assistant",
                    "content": response_content
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
                    uuid, str(e)
                )
                break
    except Exception as e:
        logger.error(
            "Unexpected error in WebSocket for %s: %s", 
            uuid, str(e)
        )
    finally:
        try:
            await websocket.close()
        except (RuntimeError, ConnectionError) as e:
            logger.error(
                "Error closing WebSocket for %s: %s", 
                uuid, str(e)
            )


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run("main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)



