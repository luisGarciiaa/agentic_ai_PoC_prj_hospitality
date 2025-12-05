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

## 📚 Exercise 1: Hotel Details with RAG

### Objective

Implement a RAG (Retrieval Augmented Generation) agent that can answer questions about hotels and rooms by retrieving information from a vector store.

### Prerequisites

1. Install LangChain dependencies:
```bash
pip install langchain langchain-openai langchain-community chromadb
```

2. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY=your-api-key-here
```

### Step 1: Prepare the Data for RAG

The hotel data needs to be loaded into a vector store. Use the generated files:
- `bookings-db/output_files/hotels/hotels.json` - Complete hotel data
- `bookings-db/output_files/hotels/hotel_details.md` - Hotel details in markdown
- `bookings-db/output_files/hotels/hotel_rooms.md` - Room information

### Step 2: Create the Vector Store

```python
from langchain_community.document_loaders import JSONLoader, TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Load hotel data
# TODO: Implement document loading from hotels.json

# Split into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

# Create embeddings and vector store
embeddings = OpenAIEmbeddings()
vectorstore = Chroma.from_documents(documents, embeddings)
```

### Step 3: Create the RAG Chain

```python
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA

llm = ChatOpenAI(model="gpt-4", temperature=0)

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

1. **Start Simple**: Begin with basic queries before implementing complex analytics
2. **Test Incrementally**: Test each component before integrating
3. **Use Logging**: Add logging to understand agent behavior
4. **Handle Errors Gracefully**: Users should get helpful error messages
5. **Optimize Prompts**: The system prompt is crucial for agent accuracy

---

## 📁 Project Structure After Completion

```
ai_agents_hospitality-api/
├── agents/
│   ├── hotel_rag_agent.py      # Exercise 1: RAG implementation
│   ├── bookings_sql_agent.py   # Exercise 2: SQL implementation
│   └── orchestrator.py         # Agent coordination
├── vectorstore/
│   └── chroma_db/              # Vector store data
├── main.py                     # WebSocket API (modified)
└── requirements.txt            # Updated dependencies
```

Good luck! 🚀

