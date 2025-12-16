# 📋 TODO - Agentic AI Hospitality PoC

> Last updated: 2025-12-16

---

## 🔥 In Progress (Current)

| Task | Priority | Started | Notes |
|------|----------|---------|-------|
| Documentación Exercise 0 | High | 2025-12-16 | README_EXERCISE_0.md en /doc con pruebas reales |
| Pruebas manuales del agente | High | 2025-12-16 | Preguntas reales desde UI y terminal |

---

## 📌 Pending (Backlog)

### High Priority

| # | Task | Created | Context |
|---|------|--------|---------|
| 1 | Probar preguntas variadas al agente | 2025-12-16 | Direcciones, precios, habitaciones, idiomas |
| 2 | Probar comportamiento sin algunos ficheros | 2025-12-16 | hotels.json movido / restaurado |
| 3 | Probar reinicio del contenedor y cache | 2025-12-16 | Ver qué datos se recargan |
| 4 | Probar aumento del número de hoteles | 2025-12-16 | Detectar límites sin RAG |

---

### Medium Priority

| # | Task | Created | Context |
|---|------|--------|---------|
| 1 | Comparar uso de data/hotels vs datos generados | 2025-12-16 | Rutas local vs bookings-db |
| 2 | Probar preguntas complejas | 2025-12-16 | Agregaciones y comparativas |

---

### Low Priority

| # | Task | Created | Context |
|---|------|--------|---------|
| 1 | Anotar limitaciones del enfoque sin RAG | 2025-12-16 | Para justificar Exercise 1 |

---

## ✅ Completed (Done)

| Task | Completed | Commit | Notes |
|------|-----------|--------|-------|
| Instalación WSL2 + Docker | 2025-12-16 | — | Entorno Linux operativo |
| Fork actualizado desde upstream | 2025-12-16 | — | Main alineado |
| Rama exercise0 creada | 2025-12-16 | — | Trabajo aislado |
| Exercise 0 funcionando | 2025-12-16 | — | UI + WebSocket + LLM |
| Tests automáticos Exercise 0 | 2025-12-16 | — | test_exercise_0.py OK |
| Pruebas manuales del agente | 2025-12-16 | — | UI y terminal |
| Debug carga de ficheros | 2025-12-16 | — | Verificado origen de datos |

---

## 🐛 Technical Notes / Observations

| Description | Detected | Notes |
|-------------|----------|-------|
| El agente cachea datos en memoria | 2025-12-16 | Requiere restart para recargar |
| Todo el contexto se envía al LLM | 2025-12-16 | No escalable sin RAG |


## 📝 Usage Notes

### How to manage this file

1. **New task** → Add to **Backlog** with date and priority
2. **Start task** → Move to **In Progress** with start date
3. **Complete task** → Move to **Completed** with date and commit hash
4. **Technical debt** → Register in specific section to not forget it

### Commit format
When you complete a task, reference the commit like this:
- Short hash: `abc1234`
- With link (if using GitHub): `[abc1234](url-to-commit)`

### Priorities
- 🔴 **High**: Blocks other tasks or is critical
- 🟡 **Medium**: Important but not urgent
- 🟢 **Low**: Nice-to-have, minor improvements

---

## 🎓 Workshop Exercise Plans

### Exercise 0: Simple Agentic Assistant with File Context

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

---

### Exercise 1: Hotel Details with RAG

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

---

### Exercise 2: Booking Analytics with SQL Agent

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

---

## 📊 Quick Summary

```
📌 Pending:  4
🔥 In progress: 0
✅ Completed: 0
🐛 Technical debt: 0
🎓 Workshop Exercises: 3 (Exercise 0, 1, 2)
```

> ⚠️ **Remember**: Update this file after each work session
