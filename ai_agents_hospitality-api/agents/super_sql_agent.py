"""
Super SQL Agent: unified agent for hotel configuration + bookings analytics.

Uses PostgreSQL database with 3 tables:
- hotels   (static hotel metadata)
- rooms    (static room configuration and prices)
- bookings (booking facts for analytics: revenue, occupancy, RevPAR, etc.)

Flow:
1) LLM generates a SINGLE SQL query (PostgreSQL)
2) We sanitize/execute it
3) LLM explains the raw result in markdown
"""

from __future__ import annotations

import os
import asyncio
import re
from typing import Optional

from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate

from util.logger_config import logger
from config.agent_config import get_agent_config
from agents.llm_factory import build_llm


# --------------------------------------------------
# Database connection
# --------------------------------------------------

_DB: Optional[SQLDatabase] = None
_LLM = None  # tipo genérico, vale para OpenAI, Gemini, etc.
_SQL_GEN_CHAIN = None
_SQL_ANSWER_CHAIN = None


def _get_db() -> SQLDatabase:
    global _DB
    if _DB is not None:
        return _DB

    uri = os.getenv(
        "BOOKINGS_DB_URI",
        "postgresql://postgres:postgres@bookings-db:5432/bookings_db",
    )

    logger.info(f"[SUPER-SQL] Connecting to bookings database: {uri}")
    _DB = SQLDatabase.from_uri(uri)
    logger.info("[SUPER-SQL] ✅ Connected to bookings database")
    return _DB


def _get_llm():
    global _LLM
    if _LLM is not None:
        return _LLM

    config = get_agent_config()
    logger.info(
        f"[SUPER-SQL] Using LLM provider={config.provider} model={config.model} "
        f"temperature={config.temperature}"
    )
    _LLM = build_llm(config)
    return _LLM


# --------------------------------------------------
# SQL generation + explanation chains
# --------------------------------------------------

def _get_sql_generation_chain():
    """
    Step 1:
    Given the user's natural language question, generate a SINGLE SQL query
    for PostgreSQL using the bookings / hotels / rooms schema.
    """
    global _SQL_GEN_CHAIN
    if _SQL_GEN_CHAIN is not None:
        return _SQL_GEN_CHAIN

    llm = _get_llm()

    db_schema_description = """
Tables and relationships:

1) Table: hotels
   Columns:
   - hotel_key  (VARCHAR, PRIMARY KEY): synthetic hotel identifier
   - hotel_name (VARCHAR): human-readable name of the hotel, e.g. 'Royal Sovereign'
   - country    (VARCHAR)
   - city       (VARCHAR)
   - zip_code   (VARCHAR)
   - address    (TEXT)

   Typical uses:
   - Count how many hotels exist
   - Filter by city / country
   - Compare hotels by location
   - Join to rooms to get all room configuration of a hotel
   - Join to bookings by hotel_name when you need bookings for a given hotel

2) Table: rooms
   Columns:
   - hotel_key         (VARCHAR, NOT NULL, FK -> hotels.hotel_key)
   - room_id           (VARCHAR, NOT NULL)
   - floor             (VARCHAR): e.g. '01', '02'
   - room_category     (VARCHAR): e.g. 'Standard', 'Premium'
   - room_type         (VARCHAR): e.g. 'Single', 'Double', 'Triple'
   - guests            (INTEGER): capacity
   - price_off_season  (DECIMAL): price per night in off season (EUR)
   - price_peak_season (DECIMAL): price per night in peak season (EUR)

   Constraints:
   - PRIMARY KEY (hotel_key, room_id)

   Typical uses:
   - Get the price for a given room type/category in a given hotel
   - Count how many rooms of each type exist in each hotel
   - Count how many rooms per floor, per category, etc.
   - Compare prices between hotels, categories, types and seasons
   - Distribution of room types (single/double/triple) per hotel or per floor

   Relationship:
   - Join to hotels on rooms.hotel_key = hotels.hotel_key

3) Table: bookings
   Columns:
   - id               (SERIAL, PRIMARY KEY)
   - hotel_name       (VARCHAR): name of the hotel, same concept as hotels.hotel_name
   - room_id          (VARCHAR): room identifier
   - room_type        (VARCHAR): Single, Double, Triple
   - room_category    (VARCHAR): Standard, Premium
   - check_in_date    (DATE)
   - check_out_date   (DATE)
   - total_nights     (INTEGER): nights between check-in and check-out
   - guest_first_name (VARCHAR)
   - guest_last_name  (VARCHAR)
   - guest_email      (VARCHAR)
   - guest_phone      (VARCHAR)
   - guest_country    (VARCHAR)
   - guest_city       (VARCHAR)
   - guest_address    (TEXT)
   - guest_zip_code   (VARCHAR)
   - meal_plan        (VARCHAR): Room Only, Room and Breakfast, Half Board, etc.
   - total_price      (DECIMAL): total booking price for the stay (EUR)

   Typical uses:
   - Count bookings by:
     - hotel
     - period (year, month, quarter)
     - country, city, meal_plan, room_type, etc.
   - Compute total revenue from bookings using SUM(total_price)
   - Compute total occupied nights using SUM(total_nights)

   Relationship with the other tables:
   - bookings.hotel_name matches hotels.hotel_name (for location or filtering by hotel)
   - You can join bookings to hotels on bookings.hotel_name = hotels.hotel_name
   - For configuration-only questions (prices, number of rooms, etc.),
     you usually DO NOT need the bookings table.


Analytics definitions:
- Bookings count:
  COUNT(*) over the bookings table with appropriate filters.

- Total revenue:
  SUM(total_price) over the bookings table with appropriate filters.

- Total occupied nights:
  SUM(total_nights) over the bookings table with appropriate filters.

- Total available room-nights (approximation for analytics queries):
  Number of distinct rooms * number of days in the period.
  For example:
    rooms_per_hotel = COUNT(DISTINCT room_id) FROM rooms (optionally filtered by hotel)
    days_in_period = number of days between start_date and end_date (inclusive or exclusive,
                    but be consistent in numerator and denominator).

- Occupancy Rate:
  (Total Occupied Nights / Total Available Room-Nights) * 100

- RevPAR (Revenue Per Available Room):
  Total Revenue / Total Available Room-Nights
"""

    system_message = f"""
You are an expert SQL assistant for a hotel management + analytics system.

You must generate a SINGLE PostgreSQL SQL query to answer the user's question
using the following database schema and definitions:

{db_schema_description}

Guidelines:
- Choose the RIGHT table(s) depending on the question:
  * For static hotel/room configuration (prices, room counts, distributions, floors, etc.):
    - Use hotels and/or rooms.
  * For bookings, revenue, guests, occupancy, RevPAR, meal plans, etc.:
    - Use bookings, optionally joined with hotels or rooms if needed.

- Use valid PostgreSQL syntax.
- Use explicit column names as given.
- Use DATE filters with 'YYYY-MM-DD' format.
- For quarterly filters (Q1, Q2, etc.), map them to explicit date ranges.

- When joining:
  * Join rooms to hotels on: rooms.hotel_key = hotels.hotel_key
  * Join bookings to hotels on: bookings.hotel_name = hotels.hotel_name

- Avoid unnecessary tables: do not include bookings if the question is purely about room configuration.

IMPORTANT:
- Use only these tables: bookings, hotels, rooms.
- Never invent table or column names.
- Never use reserved keywords as table aliases, especially:
  ON, USING, JOIN, WHERE, ORDER, GROUP, SELECT, FROM.
- DO NOT explain the query.
- DO NOT include markdown.
- Output ONLY the SQL statement, nothing else (no backticks, no comments).
"""

    sql_gen_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            (
                "human",
                "User question:\n{question}\n\nWrite the SQL query now:",
            ),
        ]
    )

    _SQL_GEN_CHAIN = sql_gen_prompt | llm
    return _SQL_GEN_CHAIN


def _get_sql_answer_chain():
    """
    Step 2:
    Given the SQL query text and the database results,
    generate a natural language answer in markdown,
    covering both configuration and analytics questions.
    """
    global _SQL_ANSWER_CHAIN
    if _SQL_ANSWER_CHAIN is not None:
        return _SQL_ANSWER_CHAIN

    llm = _get_llm()

    system_message = """
You are a hotel data assistant.

You receive:
- The original user question
- The SQL query that was executed
- The raw result of that query

Your job:
- Interpret the result and answer the question clearly.
- Use markdown formatting.
- Adapt the explanation to the type of question:

  * If the question is about room prices or configuration:
    - Clearly state the hotel(s), room_type, room_category, floor, season (off/peak), etc.
    - Explain whether the price is off-season or peak-season based on the columns used.
    - Provide small tables when returning multiple rows (e.g. distributions or comparisons).

  * If the question is about room counts or distributions:
    - Explain the counts by hotel, room_type, floor, or category as relevant.
    - Use tables for breakdowns (e.g. type vs count, floor vs count).

  * If the question is about bookings analytics:
    - bookings count: explain the count and the filters (hotel, period, etc.).
    - total revenue: show the revenue in EUR and the period/hotel(s) used.
    - occupancy rate: use the numbers returned to compute the rate and show the formula.
    - RevPAR: compute it as Revenue / Available room-nights and show the formula if data is available.

- If the result is empty, explain that there are no matching rows for that query.
- When listing breakdowns (by hotel, city, meal_plan, room_type, etc.), use small markdown tables.
"""

    answer_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            (
                "human",
                "User question:\n{question}\n\n"
                "Executed SQL:\n```sql\n{sql}\n```\n\n"
                "Raw result from database:\n{result}\n\n"
                "Now answer the user's question based on this result. Use markdown:",
            ),
        ]
    )

    _SQL_ANSWER_CHAIN = answer_prompt | llm
    return _SQL_ANSWER_CHAIN


# --------------------------------------------------
# Helper to extract clean SQL
# --------------------------------------------------

def _extract_sql(text: str) -> str:
    """
    Extracts the SQL statement from the LLM response.
    If it is wrapped in ```sql ... ```, strips that.
    Otherwise returns the text as-is.
    """
    if not text:
        return ""

    codeblock_pattern = r"```(?:sql)?\s*(.*?)```"
    m = re.search(codeblock_pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    return text.strip()


def _sanitize_sql(sql: str) -> str:
    """
    Post-process the generated SQL to avoid invalid aliases like 'on'.
    - Replace table/CTE alias 'on' with 'occ'
    - Replace references 'on.' with 'occ.'
    This is a safety net on top of the prompt instructions.
    """

    if not sql:
        return sql

    # 1) Reemplazar alias 'on' después de un nombre de tabla/CTE:
    #    FROM occupied_nights on,
    #    JOIN occupied_nights on
    #    , occupied_nights on
    # ->  FROM occupied_nights occ
    sql = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+on\b", r"\1 occ", sql)

    # 2) Reemplazar las referencias al alias:
    #    on.total_occupied_nights -> occ.total_occupied_nights
    sql = re.sub(r"\bon\.", "occ.", sql)

    return sql


# --------------------------------------------------
# Main sync function for the Super SQL agent
# --------------------------------------------------

def answer_super_sql_question(question: str) -> str:
    """
    Two-step flow:
    1) Generate SQL from question
    2) Sanitize & execute SQL and format the answer
    """
    try:
        db = _get_db()

        # Step 1: generate SQL
        sql_chain = _get_sql_generation_chain()
        sql_resp = sql_chain.invoke({"question": question})
        raw_sql_text = getattr(sql_resp, "content", str(sql_resp))

        # Extraer solo el SQL limpio (sin backticks, etc.)
        sql_query = _extract_sql(raw_sql_text)

        if not sql_query:
            logger.error(
                f"[SUPER-SQL] Could not extract SQL from LLM output: {raw_sql_text!r}"
            )
            return (
                "❌ I couldn't generate a valid SQL query for that question.\n\n"
                "Please try rephrasing your question or checking hotel / room names."
            )

        # 🔧 Sanitizar: corregir alias problemáticos como 'on'
        sanitized_sql = _sanitize_sql(sql_query)

        logger.info(
            f"[SUPER-SQL] Generated RAW SQL for question='{question}': {sql_query}"
        )
        logger.info(f"[SUPER-SQL] Sanitized SQL to execute: {sanitized_sql}")

        # Step 2: execute SQL against the DB
        try:
            raw_result = db.run(sanitized_sql)
            logger.info(
                f"[SUPER-SQL] Query executed successfully. Raw result: {raw_result}"
            )
        except Exception as e:
            logger.error(f"[SUPER-SQL] Error executing query: {e}", exc_info=True)
            return (
                "❌ There was an error executing the SQL query generated for your question.\n\n"
                f"Error: `{e}`\n\n"
                "You might want to check date ranges, hotel names or filters."
            )

        # Step 3: let the LLM explain the result in markdown
        answer_chain = _get_sql_answer_chain()
        answer_resp = answer_chain.invoke(
            {
                "question": question,
                "sql": sanitized_sql,
                "result": str(raw_result),
            }
        )
        final_answer = getattr(answer_resp, "content", str(answer_resp))
        return final_answer

    except Exception as e:
        logger.error(
            f"[SUPER-SQL] Unexpected error in Super SQL agent: {e}", exc_info=True
        )
        return (
            "❌ Unexpected error while processing your question with the Super SQL agent: "
            f"{e}"
        )


# --------------------------------------------------
# Async wrapper for FastAPI/WebSocket
# --------------------------------------------------

async def handle_super_sql_query(user_query: str) -> str:
    """
    Async wrapper to use in the WebSocket endpoint.
    Runs the sync Super SQL agent logic in an executor.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, answer_super_sql_question, user_query)
