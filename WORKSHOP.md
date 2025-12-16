# 🏨 Workshop: Building an AI Agentic Application for Hospitality

## 📋 Overview

This workshop guides you through building an AI-powered agentic application for the hospitality industry using **LangChain**. You will create intelligent agents capable of answering complex queries about hotels, rooms, and bookings.

## 🎯 Business Case: Hospitality Management System

### The Challenge

Hotel management companies need to provide quick and accurate information to their staff and customers about:
- **Hotel Information**: Location, addresses, meal plans, pricing policies, discounts
- **Room Details**: Types (single/double/triple), categories (standard/premium), seasonal pricing
- **Booking Analytics**: Occupancy rates, revenue reports, booking trends, RevPAR calculations

### The Solution

An AI-powered chatbot assistant that can:
1. **Answer natural language questions** about hotels and rooms using RAG (Retrieval Augmented Generation)
2. **Generate analytics reports** by querying the bookings database with AI-generated SQL
3. **Provide real-time insights** on occupancy, revenue, and performance metrics

### Data Model

The system works with three main data entities:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     HOTELS      │     │     ROOMS       │     │    BOOKINGS     │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • Name          │     │ • RoomId        │     │ • hotel_name    │
│ • Country       │────▶│ • Floor         │     │ • room_id       │
│ • City          │     │ • Category      │◀────│ • check_in_date │
│ • Address       │     │ • Type          │     │ • check_out_date│
│ • MealPlans     │     │ • Guests        │     │ • guest_info    │
│ • Discounts     │     │ • PriceOffSeason│     │ • meal_plan     │
│ • Charges       │     │ • PricePeakSeason│    │ • total_price   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Synthetic Data Generation

The project includes a synthetic data generator that creates realistic hotel and booking data.

📖 **See**: [HOWTO: Generate Synthetic Data](./HOWTO_generate_synthetic_data.md)

---

## 🧪 Try the Mock Application

Before starting the exercises, you can test the current mock implementation to understand the expected behavior:

```bash
# Start the application (uses hardcoded responses)
cd ai_agents_hospitality-api
pip install -r requirements.txt
python main.py

# Access the chatbot UI
# URL: http://localhost:8001
```

### Sample Queries to Test

**Hotel Configuration Queries:**
- "List the hotels in France"
- "Tell me the prices for triple premium rooms in Paris"
- "Compare the triple room prices at off season for room and breakfast at the hotels in Nice"
- "Tell me the lowest price for a standard single room in Nice considering no meal plan"
- "Tell me for hotels in Paris the meal charge for half board"
- "Tell me the amount of rooms per type for hotels in Paris"

**Booking Analytics Queries (Exercise 2):**
- "Tell me the amount of bookings for Royal Sovereign in 2025"
- "Tell me the occupancy per month for Imperial Crown in 2025"
- "Tell me the revenues in August considering the current bookings in Grand Victoria"
- "Show me the RevPAR for May 2025 for Obsidian Tower"

---

## 🏗️ Target Agent Architecture

The goal is to implement an agent system with the following structure:

### Agent Roles

| Agent | Type | Description |
|-------|------|-------------|
| **Hotel Configuration Orchestrator** | Super Agent | Coordinates queries about hotel details, rooms, and pricing |
| **Hotel Report Bookings Orchestrator** | Super Agent | Coordinates analytics and reporting queries |
| **Hotel Details Agent** | RAG Agent | Retrieves hotel information from vector store |
| **Hotel Rooms Agent** | RAG Agent | Retrieves room details and pricing from vector store |
| **Hotel Bookings Analytics Agent** | SQL Agent | Generates and executes SQL queries on PostgreSQL |
| **Message Response Agent** | Custom Agent | Formats final responses in markdown |

### Architecture Diagram

```
                    ┌─────────────────────────────┐
                    │      User Query             │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │      Router/Orchestrator     │
                    └─────────────┬───────────────┘
                                  │
           ┌──────────────────────┴──────────────────────┐
           │                                             │
┌──────────▼──────────┐                    ┌─────────────▼─────────────┐
│ Hotel Configuration │                    │  Hotel Report Bookings   │
│   Orchestrator      │                    │      Orchestrator        │
└──────────┬──────────┘                    └─────────────┬─────────────┘
           │                                             │
    ┌──────┴──────┐                              ┌───────┴───────┐
    │             │                              │               │
┌───▼───┐   ┌─────▼─────┐                  ┌─────▼─────┐   ┌─────▼─────┐
│ Hotel │   │   Hotel   │                  │  Bookings │   │  Message  │
│Details│   │   Rooms   │                  │ Analytics │   │  Response │
│ (RAG) │   │   (RAG)   │                  │   (SQL)   │   │   Agent   │
└───────┘   └───────────┘                  └───────────┘   └───────────┘
    │             │                              │
    ▼             ▼                              ▼
┌─────────────────────┐                  ┌─────────────────┐
│    Vector Store     │                  │   PostgreSQL    │
│  (Hotels & Rooms)   │                  │   (Bookings)    │
└─────────────────────┘                  └─────────────────┘
```

---

## 📚 Exercise 0: Simple Agentic Assistant with File Context

### Objective

Build a simple AI agentic assistant that answers questions about hotels configuration and rooms (no bookings required) by passing hotel files directly to the LLM context. This exercise introduces the basic scaffolding for an agentic application without the complexity of RAG.

### Prerequisites

1. Install LangChain dependencies:
```bash
pip install langchain langchain-google-genai
```

2. Set up your API credentials:
```bash
export AI_AGENTIC_API_KEY=your-api-key-here
```

3. Generate a small sample of hotel data (5 hotels -> set param num_of_hotels: 5 at generate_hotels_param.yaml) :
```bash
cd bookings-db
python src/gen_synthetic_hotels.py
```

This will create hotel files in `bookings-db/output_files/hotels/` with a small sample.

### Step 1: Load Hotel Files

Load the hotel data files directly into memory:

```python
import json
from pathlib import Path

# Load hotel data from JSON
hotels_file = Path("bookings-db/output_files/hotels/hotels.json")
with open(hotels_file, 'r', encoding='utf-8') as f:
    hotels_data = json.load(f)

# Load hotel details markdown
hotel_details_file = Path("bookings-db/output_files/hotels/hotel_details.md")
with open(hotel_details_file, 'r', encoding='utf-8') as f:
    hotel_details_text = f.read()
```

### Step 2: Create Simple Agent with Context

Create a basic agent that uses the loaded files as context:

```python
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0, google_api_key=os.getenv("AI_AGENTIC_API_KEY"))

# Create a prompt template that includes the hotel context
prompt_template = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful hotel assistant. Use the following hotel information to answer questions.

Hotel Data:
{hotel_context}

When answering questions:
- Be accurate and specific
- Reference hotel names, locations, and details from the data
- If information is not available, say so clearly
- Format responses in a clear, readable way"""),
    ("human", "{question}")
])

# Create the chain
chain = prompt_template | llm
```

### Step 3: Implement the Agent Function

```python
def answer_hotel_question(question: str) -> str:
    """Simple agent that answers questions using hotel files as context."""
    
    # Prepare context from loaded files
    hotel_context = f"""
{hotel_details_text}

Hotels JSON Summary:
{json.dumps(hotels_data, indent=2, ensure_ascii=False)}
"""
    
    # Invoke the chain
    response = chain.invoke({
        "hotel_context": hotel_context,
        "question": question
    })
    
    return response.content
```

### Step 4: Test the Agent

Test with simple queries:

```python
# Test queries
queries = [
    "List all hotels and their cities",
    "What is the address of the first hotel?",
    "What meal plans are available?",
    "Tell me about room types in these hotels"
]

for query in queries:
    answer = answer_hotel_question(query)
    print(f"Q: {query}")
    print(f"A: {answer}\n")
```

### Step 5: Integrate with WebSocket API (Basic)

Create a simple integration point for the WebSocket API:

```python
# In main.py or a new agent module
async def handle_hotel_query_simple(user_query: str) -> str:
    """Handle hotel queries using simple file context approach."""
    try:
        response = answer_hotel_question(user_query)
        return response
    except Exception as e:
        return f"Error processing query: {str(e)}"
```

### Expected Queries to Handle

- "List all hotels and their locations"
- "What is the address of [hotel name]?"
- "What meal plans are available?"
- "Tell me about the rooms in [hotel name]"
- "What discounts are available?"

### Key Differences from Exercise 1

| Aspect | Exercise 0 | Exercise 1 |
|--------|------------|------------|
| **Data Size** | 3 hotels (small sample) | 50 hotels (full dataset) |
| **Method** | Direct file context | RAG with vector store |
| **Complexity** | Simple, straightforward | Advanced retrieval |
| **Use Case** | Learning scaffolding | Production-ready |

### 📋 Plan

#### Phase 1: Setup & Data Preparation
- [ ] Install LangChain dependencies (`langchain`, `langchain-google-genai`)
- [ ] Configure Google Gemini API key as environment variable (`AI_AGENTIC_API_KEY`)
- [ ] Generate synthetic hotel data (3 hotels) using `gen_synthetic_hotels.py`
- [ ] Verify hotel files are created in `bookings-db/output_files/hotels/`

#### Phase 2: Core Implementation
- [ ] Create function to load hotel JSON file (`hotels.json`)
- [ ] Create function to load hotel details markdown (`hotel_details.md`)
- [ ] Implement `answer_hotel_question()` function with file context
- [ ] Create ChatPromptTemplate with system prompt for hotel assistant
- [ ] Build LangChain chain (prompt template + LLM)

#### Phase 3: Integration & Testing
- [ ] Create `handle_hotel_query_simple()` async function for WebSocket API
- [ ] Test with basic queries (hotel names, addresses, locations)
- [ ] Test with meal plan queries
- [ ] Test with room information queries
- [ ] Verify error handling works correctly

#### Phase 4: Documentation & Cleanup
- [ ] Add code comments and docstrings
- [ ] Test integration with WebSocket API endpoint
- [ ] Verify responses are properly formatted

### Deliverables

- [ ] Function to load hotel files (3 hotels sample)
- [ ] Simple agent chain with file context
- [ ] Basic prompt template for hotel queries
- [ ] Integration point for WebSocket API
- [ ] Test with sample queries

### Next Steps

After completing Exercise 0, you'll be ready to move to Exercise 1, which implements RAG with the full dataset (50 hotels) for better scalability and performance.

---

## 📚 Exercise 1: Hotel Details with RAG

### Objective

Implement a RAG (Retrieval Augmented Generation) agent that can answer questions about hotels and rooms by retrieving information from a vector store. This exercise uses the **full dataset of 50 hotels** for production-ready scalability.

### Prerequisites

1. Install LangChain dependencies:
```bash
pip install langchain langchain-google-genai langchain-community chromadb
```

2. Set up your Google Gemini API key:
```bash
export AI_AGENTIC_API_KEY=your-api-key-here
```

3. Generate the full hotel dataset (50 hotels -> set param num_of_hotels: 50 at generate_hotels_param.yaml):
```bash
cd bookings-db
python src/gen_synthetic_hotels.py
```

### Step 1: Prepare the Data for RAG

The hotel data needs to be loaded into a vector store. Use the generated files with the **full dataset of 50 hotels**:
- `bookings-db/output_files/hotels/hotels.json` - Complete hotel data (50 hotels)
- `bookings-db/output_files/hotels/hotel_details.md` - Hotel details in markdown (50 hotels)
- `bookings-db/output_files/hotels/hotel_rooms.md` - Room information (50 hotels)

> **Note**: Unlike Exercise 0 which used 3 hotels with direct file context, Exercise 1 uses RAG with 50 hotels for better scalability and efficient retrieval.

### Step 2: Create the Vector Store

```python
from langchain_community.document_loaders import JSONLoader, TextLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os

# Load hotel data
# TODO: Implement document loading from hotels.json

# Split into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

# Create embeddings and vector store
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=os.getenv("AI_AGENTIC_API_KEY"))
vectorstore = Chroma.from_documents(documents, embeddings)
```

### Step 3: Create the RAG Chain

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import RetrievalQA
import os

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0, google_api_key=os.getenv("AI_AGENTIC_API_KEY"))

# Create retrieval chain
# TODO: Implement the RAG chain with proper prompting
```

### Step 4: Implement the Hotel Details Agent

Create an agent that:
1. Receives natural language queries about hotels
2. Retrieves relevant context from the vector store
3. Generates accurate responses based on the retrieved information

### Expected Queries to Handle

- "What is the full address of Obsidian Tower?"
- "What are the meal charges for Half Board in hotels in Paris?"
- "List all hotels in France with their cities"
- "What is the discount for extra bed in Grand Victoria?"
- "Compare room prices between peak and off season for hotels in Nice"

### 📋 Plan

#### Phase 1: Setup & Data Preparation
- [ ] Install RAG dependencies (`langchain-community`, `chromadb`)
- [ ] Generate full hotel dataset (50 hotels) using `gen_synthetic_hotels.py`
- [ ] Verify all hotel files are created (JSON, markdown files)

#### Phase 2: Vector Store Creation
- [ ] Implement document loader for `hotels.json` (JSONLoader)
- [ ] Implement document loader for `hotel_details.md` (TextLoader)
- [ ] Implement document loader for `hotel_rooms.md` (TextLoader)
- [ ] Configure RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
- [ ] Create GoogleGenerativeAIEmbeddings instance
- [ ] Build ChromaDB vector store from all documents
- [ ] Persist vector store to disk for reuse

#### Phase 3: RAG Chain Implementation
- [ ] Create ChatGoogleGenerativeAI LLM instance (gemini-2.5-flash-lite, temperature=0)
- [ ] Implement RetrievalQA chain with vector store
- [ ] Design system prompt for hotel assistant context
- [ ] Configure retrieval parameters (k=5 documents)
- [ ] Test retrieval quality with sample queries

#### Phase 4: Agent Implementation
- [ ] Create hotel details agent function
- [ ] Implement query preprocessing (normalization, validation)
- [ ] Add response formatting (markdown structure)
- [ ] Handle edge cases (no results, ambiguous queries)

#### Phase 5: Integration & Testing
- [ ] Integrate RAG agent with WebSocket API
- [ ] Test with hotel location queries
- [ ] Test with meal plan and pricing queries
- [ ] Test with room comparison queries
- [ ] Verify performance (response time < 10s)
- [ ] Compare results with Exercise 0 (should be more accurate)

#### Phase 6: Optimization
- [ ] Tune chunk size and overlap if needed
- [ ] Optimize retrieval k parameter
- [ ] Add caching for frequent queries (optional)
- [ ] Document vector store persistence strategy

### Deliverables

- [ ] Vector store populated with hotel and room data
- [ ] RAG chain that retrieves relevant information
- [ ] Agent that formats responses appropriately
- [ ] Integration with the WebSocket API

---

## 📊 Exercise 2: Booking Analytics with SQL Agent

### Objective

Implement an SQL agent that can generate and execute queries against the PostgreSQL bookings database to provide analytics and reports.

### Prerequisites

1. Start the PostgreSQL database:
```bash
./start-app.sh --no_ai_agent
```

2. Install additional dependencies:
```bash
pip install langchain-community psycopg2-binary
```

### Database Schema

The `bookings` table contains:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Unique booking identifier |
| `hotel_name` | VARCHAR | Hotel name |
| `room_id` | VARCHAR | Room identifier |
| `room_type` | VARCHAR | Single, Double, Triple |
| `room_category` | VARCHAR | Standard, Premium |
| `check_in_date` | DATE | Check-in date |
| `check_out_date` | DATE | Check-out date |
| `total_nights` | INTEGER | Number of nights |
| `guest_first_name` | VARCHAR | Guest first name |
| `guest_last_name` | VARCHAR | Guest last name |
| `guest_country` | VARCHAR | Guest's country |
| `guest_city` | VARCHAR | Guest's city |
| `meal_plan` | VARCHAR | Room Only, B&B, Half Board, etc. |
| `total_price` | DECIMAL | Total booking price (EUR) |

### Step 1: Create Database Connection

```python
from langchain_community.utilities import SQLDatabase

db = SQLDatabase.from_uri(
    "postgresql://postgres:postgres@localhost:5432/bookings_db"
)
```

### Step 2: Create the SQL Agent

```python
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents import create_sql_agent

toolkit = SQLDatabaseToolkit(db=db, llm=llm)

# Create SQL agent
# TODO: Implement with proper system prompt for hospitality context
```

### Step 3: Implement Analytics Calculations

The agent should be able to calculate:

**1. Bookings Count**
```sql
SELECT COUNT(*) FROM bookings 
WHERE hotel_name = 'Hotel Name' 
AND check_in_date >= '2025-01-01';
```

**2. Occupancy Rate**
```
Occupancy Rate = (Total Occupied Nights / Total Available Room-Nights) × 100

Where:
- Total Occupied Nights = SUM(total_nights) for the period
- Total Available Room-Nights = Number of Rooms × Number of Days
```

**3. Total Revenue**
```sql
SELECT SUM(total_price) FROM bookings 
WHERE hotel_name = 'Hotel Name' 
AND check_in_date BETWEEN '2025-01-01' AND '2025-01-31';
```

**4. RevPAR (Revenue Per Available Room)**
```
RevPAR = Total Revenue / Total Available Room-Nights
```

### Step 4: Implement Two-Step Query Process

1. **Step 1**: Agent generates the SQL query based on natural language
2. **Step 2**: Execute the query against PostgreSQL and format results

```python
# TODO: Implement the two-step process
# 1. Generate SQL from natural language
# 2. Execute and format results
```

### Expected Queries to Handle

- "Tell me the amount of bookings for Obsidian Tower in 2025"
- "What is the occupancy rate for Imperial Crown in January 2025?"
- "Show me the total revenue for hotels in Paris in Q1 2025"
- "Calculate the RevPAR for Grand Victoria in August 2025"
- "How many guests from Germany stayed at our hotels in 2025?"
- "Compare bookings by meal plan type across all hotels"

### 📋 Plan

#### Phase 1: Setup & Database Connection
- [ ] Start PostgreSQL database using `./start-app.sh --no_ai_agent`
- [ ] Install SQL dependencies (`langchain-community`, `psycopg2-binary`)
- [ ] Verify database connection (test connection string)
- [ ] Inspect database schema and understand table structure
- [ ] Load sample booking data to test queries

#### Phase 2: SQL Database Integration
- [ ] Create SQLDatabase instance from connection URI
- [ ] Test basic SQL queries manually (SELECT, COUNT, SUM)
- [ ] Verify database schema introspection works
- [ ] Test date filtering and aggregation queries

#### Phase 3: SQL Agent Implementation
- [ ] Create SQLDatabaseToolkit with database and LLM
- [ ] Implement create_sql_agent with proper system prompt
- [ ] Configure agent for hospitality context (hotel names, dates, metrics)
- [ ] Add custom system prompt explaining booking schema
- [ ] Test agent with simple queries (booking counts)

#### Phase 4: Analytics Calculations
- [ ] Implement bookings count query logic
- [ ] Implement occupancy rate calculation (two-step: query + formula)
- [ ] Implement total revenue aggregation
- [ ] Implement RevPAR calculation (revenue / available room-nights)
- [ ] Handle edge cases (no bookings, division by zero)

#### Phase 5: Two-Step Query Process
- [ ] Implement Step 1: Generate SQL from natural language
- [ ] Implement Step 2: Execute query and format results
- [ ] Add query validation before execution
- [ ] Implement result formatting (tables, markdown)
- [ ] Add error handling for SQL syntax errors

#### Phase 6: Advanced Queries & Testing
- [ ] Test with date range queries (months, quarters, years)
- [ ] Test with hotel-specific filters
- [ ] Test with guest country/city filters
- [ ] Test with meal plan comparisons
- [ ] Verify occupancy and RevPAR calculations are accurate
- [ ] Test with edge cases (empty results, invalid dates)

#### Phase 7: Integration & Error Handling
- [ ] Integrate SQL agent with WebSocket API
- [ ] Add comprehensive error handling (connection errors, query errors)
- [ ] Implement query timeout protection
- [ ] Add logging for debugging SQL generation
- [ ] Test end-to-end with WebSocket interface

#### Phase 8: Optimization & Documentation
- [ ] Optimize system prompt for better SQL generation
- [ ] Add query result caching for common queries (optional)
- [ ] Document SQL agent limitations and best practices
- [ ] Add code comments and docstrings

### Deliverables

- [ ] SQL agent that generates correct queries
- [ ] Proper handling of occupancy and RevPAR calculations
- [ ] Error handling for invalid queries
- [ ] Integration with the WebSocket API

---

## 🔧 Integration with WebSocket API

Both exercises should integrate with the existing WebSocket API in `ai_agents_hospitality-api/main.py`.

### Current Mock Implementation

The current implementation returns hardcoded responses. Replace the `find_matching_response()` function with your agent implementation:

```python
# In main.py, replace:
response_content = find_matching_response(user_query)

# With your agent implementation:
response_content = await your_agent_chain.ainvoke(user_query)
```

---

## ✅ Success Criteria

### Exercise 0: Simple Agentic Assistant
- [ ] Successfully loads hotel files (3 hotels sample)
- [ ] Answers basic questions about hotels using file context
- [ ] Handles queries about hotel names, addresses, and basic details
- [ ] Provides responses in readable format
- [ ] Basic integration with WebSocket API works

### Exercise 1: RAG Agent
- [ ] Correctly answers questions about hotel details
- [ ] Retrieves accurate room pricing information
- [ ] Handles queries about meal plans and discounts
- [ ] Provides responses in proper markdown format

### Exercise 2: SQL Agent
- [ ] Generates correct SQL for booking queries
- [ ] Calculates occupancy rates accurately
- [ ] Computes revenue and RevPAR correctly
- [ ] Handles date ranges and filters properly

### Overall Integration
- [ ] Both agents work through the WebSocket interface
- [ ] Responses are formatted consistently
- [ ] Error handling is implemented
- [ ] System responds in reasonable time (<10 seconds)

---

## 📖 Additional Resources

- [LangChain Documentation](https://python.langchain.com/)
- [LangChain RAG Tutorial](https://python.langchain.com/docs/tutorials/rag/)
- [LangChain SQL Agent](https://python.langchain.com/docs/tutorials/sql_qa/)
- [ChromaDB Documentation](https://docs.trychroma.com/)

---

## 🎓 Workshop Tips

1. **Start with Exercise 0**: Begin with the simple file context approach (3 hotels) to understand the basic scaffolding before moving to RAG
2. **Progress Incrementally**: Complete Exercise 0 → Exercise 1 (RAG with 50 hotels) → Exercise 2 (SQL Agent)
3. **Test Incrementally**: Test each component before integrating
4. **Use Logging**: Add logging to understand agent behavior
5. **Handle Errors Gracefully**: Users should get helpful error messages
6. **Optimize Prompts**: The system prompt is crucial for agent accuracy

---

## 📁 Project Structure After Completion

```
ai_agents_hospitality-api/
├── agents/
│   ├── hotel_simple_agent.py   # Exercise 0: Simple file context agent
│   ├── hotel_rag_agent.py      # Exercise 1: RAG implementation (50 hotels)
│   ├── bookings_sql_agent.py   # Exercise 2: SQL implementation
│   └── orchestrator.py         # Agent coordination
├── vectorstore/
│   └── chroma_db/              # Vector store data (Exercise 1)
├── main.py                     # WebSocket API (modified)
└── requirements.txt            # Updated dependencies
```

Good luck! 🚀

