"""
FastAPI REST API Server: Exposes endpoints for NL Query Engine, Ingestion, Database Telemetry, and Stats.
"""
from datetime import date
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.db.connection import get_db_connection, execute_query, execute_statement, init_db
from src.query_engine.pipeline import answer_question
from src.ingestion.sms_parser import parse_sms
from src.ingestion.normalizer import normalize_transaction

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes SQLite database schema on startup."""
    logger.info("Initializing SQLite database schema on server startup...")
    try:
        init_db()
        logger.info("Database schema initialization complete.")
    except Exception as e:
        logger.exception("Failed to initialize database schema during startup")
        raise e
    yield


app = FastAPI(
    title="Expense NL Query Engine API",
    description="Natural language query engine & RAG layer over personal transaction data",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str = Field(..., json_schema_extra={"example": "How much did I spend on food last month?"})
    ref_date: Optional[str] = Field(default=None, json_schema_extra={"example": "2026-08-11"})


class SMSIngestRequest(BaseModel):
    sms_text: str = Field(..., json_schema_extra={"example": "Spent Rs.450.00 at SWIGGY INDIA on HDFC Bank Card ending 1234 on 05-AUG-26."})


@app.get("/api/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/query")
def process_query(req: QueryRequest) -> Dict[str, Any]:
    """
    Executes a natural language query through the 3-stage pipeline.
    """
    logger.info(f"Received query request: '{req.question}' (ref_date: {req.ref_date})")
    if not req.question.strip():
        logger.warning("Empty query question received.")
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    ref_d = None
    if req.ref_date:
        try:
            ref_d = date.fromisoformat(req.ref_date)
        except ValueError:
            logger.warning(f"Invalid ref_date format received: '{req.ref_date}'")
            raise HTTPException(status_code=400, detail="Invalid ref_date format. Use YYYY-MM-DD.")

    try:
        result = answer_question(req.question, ref_date=ref_d)
        logger.info(
            f"Successfully processed query. is_grounded={result.get('is_grounded')}, "
            f"fallback_used={result.get('fallback_used')}, latency={result.get('latency_ms')}ms"
        )
        return result
    except Exception as e:
        logger.exception(f"Unhandled error processing query: '{req.question}'")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/sms")
def ingest_sms(req: SMSIngestRequest) -> Dict[str, Any]:
    """
    Parses a raw SMS string, normalizes merchant/category, and stores the transaction.
    """
    logger.info("Received SMS ingestion request.")
    parsed = parse_sms(req.sms_text)
    if not parsed:
        logger.warning(f"Failed to parse transaction from SMS body: '{req.sms_text}'")
        raise HTTPException(status_code=422, detail="Failed to parse transaction from SMS body.")

    logger.debug(f"Parsed SMS transaction: {parsed}")
    normalized = normalize_transaction(parsed)
    logger.debug(f"Normalized transaction: {normalized}")

    stmt = """
    INSERT INTO transactions (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source, account_id, currency, raw_text)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = [
        normalized["date"],
        normalized["amount"],
        normalized["transaction_type"],
        normalized["merchant_raw"],
        normalized["merchant_normalized"],
        normalized["category"],
        normalized["source"],
        normalized["account_id"],
        normalized["currency"],
        normalized["raw_text"]
    ]

    try:
        tx_id = execute_statement(stmt, params)
        logger.info(
            f"Successfully ingested SMS transaction ID {tx_id} "
            f"({normalized['merchant_normalized']} - ₹{normalized['amount']})"
        )
        return {
            "status": "success",
            "id": tx_id,
            "transaction": normalized
        }
    except Exception as e:
        logger.exception("Failed to insert parsed SMS transaction into database")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
def get_stats() -> Dict[str, Any]:
    """
    Returns summary metrics for the transaction database.
    """
    logger.info("Fetching summary transaction statistics.")
    total_tx = execute_query("SELECT COUNT(*) AS c FROM transactions")[0]["c"]
    
    dates = execute_query("SELECT MIN(date) AS min_d, MAX(date) AS max_d FROM transactions")[0]
    
    total_spent_res = execute_query(
        "SELECT SUM(amount) AS s FROM transactions WHERE transaction_type = 'debit' AND category != 'transfers'"
    )[0]["s"]
    total_spent = total_spent_res if total_spent_res is not None else 0.0

    category_breakdown = execute_query(
        """
        SELECT category, COUNT(*) AS count, SUM(amount) AS total_spent
        FROM transactions
        WHERE transaction_type = 'debit' AND category != 'transfers'
        GROUP BY category
        ORDER BY total_spent DESC
        """
    )

    logger.debug(f"Fetched stats: total_transactions={total_tx}, total_spent={total_spent}")
    return {
        "total_transactions": total_tx,
        "min_date": dates["min_d"],
        "max_date": dates["max_d"],
        "total_spent": total_spent,
        "category_breakdown": category_breakdown
    }


@app.get("/api/transactions")
def list_transactions(limit: int = 50, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns a list of transactions sorted newest first.
    """
    logger.info(f"Listing transactions (limit={limit}, category={category})")
    if category:
        query = "SELECT * FROM transactions WHERE category = ? ORDER BY date DESC, id DESC LIMIT ?"
        return execute_query(query, [category, limit])
    else:
        query = "SELECT * FROM transactions ORDER BY date DESC, id DESC LIMIT ?"
        return execute_query(query, [limit])
