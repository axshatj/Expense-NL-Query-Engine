# CLAUDE.md — Expense NL Query Engine Guide

Welcome to the **Expense NL Query Engine** repository! This document provides a complete overview of the project's technology stack, architecture, setup instructions, development commands, and directory structure.

---

## 📌 Project Overview

The **Expense NL Query Engine** is a full-stack, AI-powered personal finance assistant with an anti-hallucination natural language RAG interface built over personal transaction data. Users ask questions in plain English (*"How much did I spend on dining last month?"*, *"Compare this month vs last month"*, *"Show me my last 5 Swiggy orders"*) and get back answers strictly grounded in actual database transactions.

### Key Highlights
- **No LLM-Generated SQL**: The LLM converts natural language into a strictly typed JSON Intermediate Representation (`QueryIR`). Plain Python code deterministically converts `QueryIR` into parameterized SQL, preventing injection and syntax errors.
- **Anti-Hallucination Guardrail**: Every numeric figure in the generated natural language response is regex-verified against the retrieved database data. Any response containing ungrounded figures is rejected and replaced by a deterministic, templated answer.
- **Multi-Source Ingestion**: Ingests transactions via regex SMS parsing (HDFC, ICICI, SBI, UPI) and Account Aggregator (Setu Bridge FI sandbox flow).
- **Comprehensive Benchmark Suite**: 22-question benchmark suite measuring IR Field Accuracy, Numeric Accuracy, and Hallucination Rates.

---

## 🛠️ Technology Stack & Versions

### Backend (Python)
- **Language**: Python `3.12+`
- **Database**: SQLite 3 (embedded zero-config ACID relational DB)
- **Data Validation & Schemas**: Pydantic `^2.5.0`
- **Web API Framework**: FastAPI `^0.109.0`
- **ASGI Server**: Uvicorn `^0.27.0`
- **LLM SDK**: OpenAI Python SDK `^1.12.0` (supports OpenAI, Claude, or any OpenAI-compatible provider)
- **Environment Management**: `python-dotenv` `^1.0.0`
- **Test Framework**: Pytest `^8.0.0` (with `httpx` for API TestClient testing)

### Frontend (React / Vite)
- **Runtime Environment**: Node.js `v18+` / npm `v9+`
- **Framework & Build Tool**: React `^18.2.0` + Vite `^5.1.6`
- **Styling**: Tailwind CSS `^3.4.1`, PostCSS `^8.4.38`, Autoprefixer `^10.4.19`
- **Design System**: Modern Dark Glassmorphism (`#090d16` background with HSL glows & backdrop-blur blurs)
- **Icons**: Lucide React `^0.344.0`

---

## 🚀 Quick Start Guide

### Prerequisites
Make sure you have installed:
- [Python 3.12+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/) and `npm`

---

### Step 1: Clone & Configure Environment

```bash
# Navigate to the project root
cd expense-rag

# Copy environment template file
cp .env.example .env
```

Edit `.env` to configure your settings:
```env
DATABASE_PATH=data/expenses.db
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-4o-mini
LOG_LEVEL=INFO
```

### 🌐 OpenRouter Integration (Optional)
If you wish to use **OpenRouter** instead of OpenAI direct endpoints:
1. Provide your OpenRouter API key as `OPENAI_API_KEY`.
2. Add `OPENAI_BASE_URL=https://openrouter.ai/api/v1` to your `.env` file.
3. Configure `LLM_MODEL` to your choice (e.g. `google/gemini-flash-1.5` or `meta-llama/llama-3-8b-instruct:free`).

*(Note: If `OPENAI_API_KEY` is omitted, the engine automatically runs in **Offline Rule Fallback** mode for local testing without API costs.)*

---

### Step 2: Set Up Python Backend

```bash
# Create a virtual environment (optional but recommended)
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
```

---

### Step 3: Seed Synthetic Transaction Data

Seed the database with ~300 realistic synthetic transactions spanning the past 12 months across all 12 categories:

```bash
python -m src.ingestion.synthetic
```

---

### Step 4: Run Backend Unit Tests

Execute the full automated test suite (45 unit tests across 10 test modules):

```bash
pytest
```

---

### Step 5: Run Evaluation Benchmark Suite

Execute the 22-question benchmark suite to measure IR Field Accuracy, Numeric Accuracy, and Hallucination Rates:

```bash
# Compute ground-truth values against current database snapshot
python -m src.eval.compute_ground_truth

# Run evaluation runner
python -m src.eval.run_eval
```

---

### Step 6: Start FastAPI REST Server

Start the API backend server on port `8000`:

```bash
uvicorn src.api.server:app --reload --port 8000
```

The API will be live at `http://localhost:8000`. You can explore interactive Swagger documentation at `http://localhost:8000/docs`.

---

### Step 7: Set Up & Run React Frontend Web App

In a separate terminal window:

```bash
cd frontend

# Install frontend dependencies
npm install

# Start Vite development server
npm run dev
```

Open your browser at `http://localhost:3000` to access the interactive web application.

---

## 📡 REST API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Health check endpoint returning API status |
| `POST` | `/api/query` | Executes natural language query through the 3-stage RAG pipeline |
| `POST` | `/api/ingest/sms` | Parses raw bank SMS text, normalizes merchant/category, and stores transaction |
| `GET` | `/api/stats` | Summary statistics (total spent, count, min/max dates, category breakdown) |
| `GET` | `/api/transactions` | Paginated transaction explorer (supports `?limit=50&category=dining`) |

---

## 📂 Directory Structure

```text
expense-rag/
├── .env.example                 # Sample environment configuration file
├── requirements.txt             # Python backend dependencies
├── SKILL.md                     # Skill & architectural design manifesto
├── CLAUDE.md                    # Project setup & developer reference guide
├── data/                        # SQLite database storage directory
├── references/                  # System documentation & process roadmap
│   ├── architecture-and-schema.md
│   ├── build-plan-and-resume.md
│   ├── evaluation.md
│   ├── ingestion.md
│   ├── nl-query-and-grounding.md
│   └── process-roadmap.md       # 11-phase topological process tracker
├── src/
│   ├── config.py                # Environment configuration loader
│   ├── api/
│   │   └── server.py            # FastAPI REST backend server
│   ├── db/
│   │   ├── connection.py        # SQLite connection manager & query helpers
│   │   └── schema.sql           # Core database table definitions & indices
│   ├── ingestion/
│   │   ├── aa_setu.py           # Account Aggregator Setu Bridge sandbox connector
│   │   ├── normalizer.py        # Merchant alias matcher & category normalizer
│   │   ├── sms_parser.py        # Regex SMS parser for HDFC/ICICI/SBI/UPI
│   │   └── synthetic.py         # Realistic synthetic transaction generator
│   ├── models/
│   │   └── ir.py                # Pydantic JSON Intermediate Representation (`QueryIR`)
│   ├── query_engine/
│   │   ├── date_resolver.py     # Relative date translator ("last month" -> YYYY-MM-DD)
│   │   ├── db_executor.py       # Safe SQL query executor & out-of-domain router
│   │   ├── grounded_answer.py   # Stage 3 answer generator & anti-hallucination check
│   │   ├── ir_generator.py      # Stage 1 NL to QueryIR generator
│   │   ├── pipeline.py          # Unified end-to-end query orchestrator
│   │   └── sql_builder.py       # Stage 2 deterministic parameterized SQL generator
│   ├── prompts/
│   │   ├── prompt1_nl_to_ir.txt # Prompt 1: NL question -> QueryIR JSON
│   │   └── prompt2_grounding.txt# Prompt 2: DB data -> Grounded NL Answer
│   └── eval/
│       ├── benchmark.json       # 22-question benchmark suite dataset
│       ├── compute_ground_truth.py # Ground-truth numeric computer
│       └── run_eval.py          # Benchmark evaluation runner
├── tests/                       # Complete pytest unit test suite (45 tests)
│   ├── test_api.py
│   ├── test_db.py
│   ├── test_eval.py
│   ├── test_grounded_answer.py
│   ├── test_ingestion.py
│   ├── test_ir_generator.py
│   ├── test_normalizer.py
│   ├── test_pipeline.py
│   ├── test_sql_builder.py
│   └── test_synthetic.py
└── frontend/                    # Vite + React + Tailwind CSS v3 Web App
    ├── index.html
    ├── package.json
    ├── tailwind.config.js
    ├── vite.config.js
    └── src/
        ├── App.jsx
        ├── index.css
        └── components/
            ├── GroundedResultCard.jsx
            ├── Header.jsx
            ├── InspectorModal.jsx
            ├── QueryConsole.jsx
            ├── SMSIngestModal.jsx
            ├── StatsOverview.jsx
            └── TransactionTable.jsx
```

---

## ⚡ Useful Commands Cheat Sheet

| Action | Command |
| :--- | :--- |
| **Install Python Dependencies** | `pip install -r requirements.txt` |
| **Install Frontend Dependencies** | `cd frontend && npm install` |
| **Seed Database** | `python -m src.ingestion.synthetic` |
| **Run Pytest Suite** | `pytest` |
| **Compute Benchmark Ground Truth** | `python -m src.eval.compute_ground_truth` |
| **Run Evaluation Suite** | `python -m src.eval.run_eval` |
| **Start API Backend** | `uvicorn src.api.server:app --reload --port 8000` |
| **Start Frontend Web App** | `cd frontend && npm run dev` |
