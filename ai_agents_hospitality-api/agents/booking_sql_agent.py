"""
Exercise 2: Booking Analytics with SQL Agent

SQL agent that:
- Connects to the PostgreSQL bookings database
- Generates a query SQL from natural language (step 1)
- Executes that query and then formats the answer (step 2)

Key metrics:
- Bookings count
- Total revenue
- Occupancy rate
- RevPAR
"""

from __future__ import annotations

import os
import asyncio
import re
from typing import Optional

from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from util.logger_config import logger
from config.agent_config import get_agent_config


# --------------------------------------------------
# Database connection
# --------------------------------------------------

_DB: Optional[SQLDatabase] = None
_LLM: Optional[ChatGoogleGenerativeAI] = None
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

    logger.info(f"[SQL] Connecting to bookings database: {uri}")
    _DB = SQLDatabase.from_uri(uri)
    logger.info("[SQL] ✅ Connected to bookings database")
    return _DB



def _get_llm() -> ChatGoogleGenerativeAI:
    global _LLM
    if _LLM is not None:
        return _LLM

    config = get_agent_config()
    logger.info(
        f"[SQL] Using LLM provider={config.provider} model={config.model} "
        f"temperature={config.temperature}"
    )
    _LLM = ChatGoogleGenerativeAI(
        model=config.model,
        temperature=config.temperature,
        google_api_key=config.api_key,
    )
    return _LLM


# --------------------------------------------------
# Generation and explanation chains (2 steps)
# --------------------------------------------------

def _get_sql_generation_chain():
    """
    Step 1:
    Given the user's natural language question, generate a SINGLE SQL query
    for PostgreSQL based on the "bookings" table schema.
    """
    global _SQL_GEN_CHAIN
    if _SQL_GEN_CHAIN is not None:
        return _SQL_GEN_CHAIN

    llm = _get_llm()

    bookings_schema_description = """
Table: bookings

Columns:
- id (INTEGER): Unique booking identifier
- hotel_name (VARCHAR): Hotel name
- room_id (VARCHAR): Room identifier
- room_type (VARCHAR): Single, Double, Triple
- room_category (VARCHAR): Standard, Premium
- check_in_date (DATE): Check-in date
- check_out_date (DATE): Check-out date
- total_nights (INTEGER): Number of nights
- guest_first_name (VARCHAR): Guest first name
- guest_last_name (VARCHAR): Guest last name
- guest_country (VARCHAR): Guest's country
- guest_city (VARCHAR): Guest's city
- meal_plan (VARCHAR): Room Only, B&B, Half Board, etc.
- total_price (DECIMAL): Total booking price (EUR)

Analytics definitions:
- Bookings count: COUNT(*) with filters
- Total revenue: SUM(total_price) with filters
- Total occupied nights: SUM(total_nights)
- Total available room-nights (approximation for analytics queries):
  Number of distinct rooms * number of days in the period
  (rooms = COUNT(DISTINCT room_id), days = date range length)
- Occupancy Rate = (Total Occupied Nights / Total Available Room-Nights) * 100
- RevPAR = Total Revenue / Total Available Room-Nights
"""

    sql_gen_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""You are an expert SQL assistant for a hotel bookings analytics system.

You must generate a SINGLE PostgreSQL SQL query to answer the user's question
based on the following table and definitions:

{bookings_schema_description}

Rules:
- Use only the "bookings" table.
- Use valid PostgreSQL syntax.
- Use explicit column names as given.
- Use DATE filters with 'YYYY-MM-DD' format.
- For quarterly filters (Q1, Q2, etc.), map them to date ranges.
- IMPORTANT: Never use reserved keywords as table aliases, especially:
  ON, USING, JOIN, WHERE, ORDER, GROUP, SELECT, FROM.
- DO NOT explain the query.
- DO NOT include markdown.
- Output ONLY the SQL statement, nothing else (no backticks, no comments).
""",
            ),
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
    applying formulas like Occupancy and RevPAR when relevant.
    """
    global _SQL_ANSWER_CHAIN
    if _SQL_ANSWER_CHAIN is not None:
        return _SQL_ANSWER_CHAIN

    llm = _get_llm()

    answer_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a hotel booking analytics assistant.

You receive:
- The original user question
- The SQL query that was executed
- The raw result of that query

Your job:
- Interpret the result and answer the question clearly.
- Use markdown formatting.
- If the question is about:
  - bookings count: explain the count and filters.
  - total revenue: show the revenue in EUR and period/hotel(s) involved.
  - occupancy rate: use the numbers returned to compute the rate, and show the formula.
  - RevPAR: compute it as Revenue / Available room-nights and show the formula.
- If the result is empty, explain that there are no matching bookings.
- Include small tables when listing breakdowns (by hotel, city, meal_plan, etc.).
""",
            ),
            (
                "human",
                """User question:
{question}

Executed SQL:
```sql
{sql}
```

Raw result from database:
{result}

Now answer the user's question based on this result. Use markdown:""",
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
# Main sync function for the SQL agent
# --------------------------------------------------

def answer_booking_question_sql(question: str) -> str:
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
            logger.error(f"[SQL] Could not extract SQL from LLM output: {raw_sql_text!r}")
            return (
                "❌ I couldn't generate a valid SQL query for that question.\n\n"
                "Please try rephrasing your question."
            )

        # 🔧 Sanitizar: corregir alias problemáticos como 'on'
        sanitized_sql = _sanitize_sql(sql_query)

        logger.info(f"[SQL] Generated RAW SQL for question='{question}': {sql_query}")
        logger.info(f"[SQL] Sanitized SQL to execute: {sanitized_sql}")

        # Step 2: execute SQL against the DB
        try:
            raw_result = db.run(sanitized_sql)
            logger.info(f"[SQL] Query executed successfully. Raw result: {raw_result}")
        except Exception as e:
            logger.error(f"[SQL] Error executing query: {e}", exc_info=True)
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
        logger.error(f"[SQL] Unexpected error in SQL agent: {e}", exc_info=True)
        return f"❌ Unexpected error while processing your question with the SQL agent: {e}"






# --------------------------------------------------
# Async wrapper for FastAPI/WebSocket
# --------------------------------------------------

async def handle_booking_query_sql(user_query: str) -> str:
    """
    Async wrapper to use in the WebSocket endpoint.
    Runs the sync SQL agent logic in an executor.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, answer_booking_question_sql, user_query)
