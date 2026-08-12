# Topological Process Roadmap & Task Tracker

This document tracks the step-by-step implementation of the **Expense NL Query Engine** in topological dependency order. Tasks are organized so that no step is blocked by an unbuilt dependency. Mark tasks with `[x]` as they are completed.

---

## Topological Dependency Graph

```
[Phase 1: Setup] ──► [Phase 2: DB Schema] ──► [Phase 3: Synthetic Data] ──► [Phase 4: Normalizer]
                           │                                                      │
                           ▼                                                      ▼
                  [Phase 5: Ingestion] ◄──────────────────────────────────────────┘
                           │
                           ▼
                  [Phase 6: Stage 1 IR Engine]
                           │
                           ▼
                  [Phase 7: Stage 2 SQL Builder & Router]
                           │
                           ▼
                  [Phase 8: Stage 3 Grounding & Anti-Hallucination]
                           │
                           ▼
                  [Phase 9: Unified Pipeline / CLI]
                           │
                           ▼
                  [Phase 10: Evaluation Harness]
                           │
                           ▼
                  [Phase 11: Real Data Swap & Validation]
```

---

## Phase 1: Environment & Project Setup
> **Prerequisites:** None  
> **Goal:** Establish project dependencies, environment configuration, and directory layout.

- [x] **Task 1.1**: Define project dependencies (`requirements.txt` or `pyproject.toml` with `sqlite3`, `pydantic`, `pytest`, LLM client libraries).
- [x] **Task 1.2**: Create directory structure (`src/`, `src/db/`, `src/ingestion/`, `src/query_engine/`, `src/prompts/`, `src/eval/`, `tests/`).
- [x] **Task 1.3**: Create environment configuration (`src/config.py`) to manage API keys, database paths, and log levels.

---

## Phase 2: Database Schema & Core Tables
> **Prerequisites:** Phase 1  
> **Goal:** Create SQLite database schema and connection management.

- [x] **Task 2.1**: Implement database connection and initialization scripts (`src/db/connection.py`, `src/db/schema.sql`).
- [x] **Task 2.2**: Create `transactions` table with indices on `date`, `category`, and `merchant_normalized`.
- [x] **Task 2.3**: Create `merchant_aliases` table (`raw_pattern`, `normalized_name`, `default_category`).
- [x] **Task 2.4**: Write basic DB CRUD unit tests (`tests/test_db.py`).

---

## Phase 3: Synthetic Data Generator
> **Prerequisites:** Phase 2  
> **Goal:** Generate realistic mock transaction data to unblock downstream query engine development.

- [x] **Task 3.1**: Implement `src/ingestion/synthetic.py` script to generate ~300 realistic transactions across all 12 taxonomy categories.
- [x] **Task 3.2**: Seed SQLite database with synthetic transactions spanning past 12 months.
- [x] **Task 3.3**: Verify database queries against synthetic data via hand-written SQL test scripts.

---

## Phase 4: Merchant & Category Normalizer
> **Prerequisites:** Phase 2, Phase 3  
> **Goal:** Clean raw merchant strings and assign categories automatically.

- [x] **Task 4.1**: Implement exact/substring pattern matching against `merchant_aliases` in `src/ingestion/normalizer.py`.
- [x] **Task 4.2**: Implement LLM fallback batching for unmapped merchants (writing new rules into `merchant_aliases`).
- [x] **Task 4.3**: Implement recurring transaction (`subscriptions`) detection heuristic (same merchant + amount across 2+ consecutive months).

---

## Phase 5: Ingestion Pipeline (SMS Parsing + Setu AA Sandbox)
> **Prerequisites:** Phase 2, Phase 4  
> **Goal:** Build real data ingestion adapters for SMS exports and Account Aggregator data.

- [x] **Task 5.1**: Implement regex SMS parser in `src/ingestion/sms_parser.py` (HDFC, ICICI, SBI, UPI sender templates).
- [x] **Task 5.2**: Implement promotional/OTP SMS denylist filter.
- [x] **Task 5.3**: Implement unparsed SMS LLM fallback batch processor.
- [x] **Task 5.4**: Implement Setu AA Sandbox integration (`src/ingestion/aa_setu.py`) for consent creation, polling, and FI transaction fetching.
- [x] **Task 5.5**: Map AA JSON responses (`map_aa_transaction`) to `transactions` schema and pass through normalizer.

---

## Phase 6: Stage 1 LLM Engine (NL Question → IR)
> **Prerequisites:** Phase 1, Phase 4  
> **Goal:** Convert free-form user questions into a strictly constrained JSON Intermediate Representation.

- [x] **Task 6.1**: Define Pydantic IR data models (`src/models/ir.py`).
- [x] **Task 6.2**: Create external Prompt 1 template (`src/prompts/prompt1_nl_to_ir.txt`) with dynamic date injection and few-shot examples.
- [x] **Task 6.3**: Implement Stage 1 generator (`src/query_engine/ir_generator.py`) with relative date resolution ("last month" $\rightarrow$ absolute YYYY-MM-DD).
- [x] **Task 6.4**: Add out-of-domain classification logic (`intent: "unrelated"`) to Prompt 1.

---

## Phase 7: Stage 2 Deterministic Query Builder & Router
> **Prerequisites:** Phase 2, Phase 6  
> **Goal:** Convert JSON IR safely into parameterized SQL without exposing raw SQL to the LLM.

- [x] **Task 7.1**: Implement `build_query(ir)` in `src/query_engine/sql_builder.py` (handles metrics, dates, categories, merchants, transfers exclusion, group_by, limit).
- [x] **Task 7.2**: Implement Out-of-Domain Router: if `ir["intent"] == "unrelated"`, bypass DB/Prompt 2 and immediately return domain refusal message.
- [x] **Task 7.3**: Implement DB execution wrapper (`src/query_engine/db_executor.py`).
- [x] **Task 7.4**: Comprehensive unit testing of `build_query()` for all IR shapes (`tests/test_sql_builder.py`).

---

## Phase 8: Stage 3 Grounded Response & Anti-Hallucination Guardrail
> **Prerequisites:** Phase 7  
> **Goal:** Produce natural language answers strictly backed by query results with post-hoc verification.

- [x] **Task 8.1**: Create external Prompt 2 template (`src/prompts/prompt2_grounding.txt`).
- [x] **Task 8.2**: Implement Stage 3 answer generator (`src/query_engine/grounded_answer.py`).
- [x] **Task 8.3**: Implement `verify_grounded(answer, query_result)` regex numeric verification function.
- [x] **Task 8.4**: Implement deterministic templated fallback answer generator when `verify_grounded` fails.

---

## Phase 9: Unified Pipeline & React Web App (FastAPI + React + Tailwind v3)
> **Prerequisites:** Phase 5, Phase 8  
> **Goal:** Assemble all stages into a cohesive API pipeline and build a rich React + Tailwind CSS v3 web interface.

- [x] **Task 9.1**: Create main query orchestration class (`src/query_engine/pipeline.py`).
- [x] **Task 9.2**: Create FastAPI REST API server (`src/api/server.py`) exposing endpoints for query execution (`/api/query`), ingestion (`/api/ingest`), and metrics (`/api/stats`).
- [x] **Task 9.3**: Initialize React + Vite frontend application with Tailwind CSS v3 (`frontend/`).
- [x] **Task 9.4**: Build interactive UI components (Natural Language Query Console, Transaction Table, Grounded Source Badges, Dark Mode Theme).
- [x] **Task 9.5**: Add logging & trace telemetry for IR generation, SQL queries, grounding verification status, and fallback triggers.

---

## Phase 10: Evaluation Harness & Benchmark Suite
> **Prerequisites:** Phase 9  
> **Goal:** Measure IR accuracy, numeric accuracy, and hallucination rates.

- [x] **Task 10.1**: Create evaluation benchmark dataset (`src/eval/benchmark.json`) containing 22 questions (including out-of-domain edge cases).
- [x] **Task 10.2**: Implement ground-truth computer script (`src/eval/compute_ground_truth.py`).
- [x] **Task 10.3**: Implement runner script (`src/eval/run_eval.py`) reporting IR Field Accuracy, Numeric Accuracy, and Hallucination Rate.
- [x] **Task 10.4**: Run evaluation against synthetic data and record initial baseline metrics.

---

## Phase 11: Real Data Swap & Final Validation
> **Prerequisites:** Phase 5, Phase 10  
> **Goal:** Run the full pipeline against real SMS/AA data and produce final resume metrics.

- [x] **Task 11.1**: Ingest real SMS inbox export and Setu AA sandbox transactions into SQLite database.
- [x] **Task 11.2**: Recompute ground-truth values against real database snapshot.
- [x] **Task 11.3**: Run full evaluation suite on real data, tune merchant aliases and regex rules.
- [x] **Task 11.4**: Finalize project README and log final benchmark metrics.
