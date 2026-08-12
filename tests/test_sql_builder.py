import pytest
from datetime import date
from src.models.ir import QueryIR, DateRange, QueryFilters
from src.query_engine.sql_builder import build_query, build_single_query
from src.query_engine.db_executor import execute_ir, OUT_OF_DOMAIN_MESSAGE
from src.db.connection import get_db_connection, init_db
from src.ingestion.synthetic import generate_synthetic_transactions

def test_build_query_aggregate():
    """Verifies SQL generation for standard aggregate query."""
    ir = QueryIR(
        intent="aggregate",
        metric="sum",
        date_range=DateRange(start="2026-07-01", end="2026-07-31"),
        filters=QueryFilters(category=["dining"], exclude_transfers=True)
    )
    sql, params = build_query(ir)
    
    assert "SELECT SUM(amount) AS result FROM transactions" in sql
    assert "transaction_type = ?" in sql
    assert "date BETWEEN ? AND ?" in sql
    assert "category != ?" in sql
    assert "category IN (?)" in sql
    assert params == ["debit", "2026-07-01", "2026-07-31", "transfers", "dining"]

def test_build_query_list_with_merchant():
    """Verifies SQL generation for list query with normalized merchant search and limit."""
    ir = QueryIR(
        intent="list",
        metric="count",
        date_range=DateRange(start="2026-01-01", end="2026-08-11"),
        filters=QueryFilters(merchant=["swiggy", "zomato"], exclude_transfers=True),
        limit=5
    )
    sql, params = build_query(ir)
    
    assert "SELECT * FROM transactions" in sql
    assert "(merchant_normalized LIKE ? OR merchant_normalized LIKE ?)" in sql
    assert "ORDER BY date DESC, id DESC" in sql
    assert "LIMIT 5" in sql
    assert params == ["debit", "2026-01-01", "2026-08-11", "transfers", "%swiggy%", "%zomato%"]

def test_build_query_compare():
    """Verifies dual query structure for comparison intent."""
    ir = QueryIR(
        intent="compare",
        metric="sum",
        date_range=DateRange(start="2026-08-01", end="2026-08-11"),
        compare_date_range=DateRange(start="2026-07-01", end="2026-07-31"),
        filters=QueryFilters(exclude_transfers=True)
    )
    queries = build_query(ir)
    
    assert isinstance(queries, dict)
    assert "primary" in queries
    assert "compare" in queries
    
    primary_sql, primary_params = queries["primary"]
    compare_sql, compare_params = queries["compare"]
    
    assert "2026-08-01" in primary_params
    assert "2026-07-01" in compare_params

def test_build_query_unrelated():
    """Verifies that unrelated questions bypass query generation."""
    ir = QueryIR(intent="unrelated", filters=QueryFilters())
    sql, params = build_query(ir)
    assert sql == ""
    assert params == []

def test_execute_ir_unrelated():
    """Verifies refusal response for out-of-domain IR."""
    ir = QueryIR(intent="unrelated", filters=QueryFilters())
    res = execute_ir(ir)
    
    assert res["status"] == "unrelated"
    assert res["message"] == OUT_OF_DOMAIN_MESSAGE
    assert res["data"] is None

def test_execute_ir_in_memory_db():
    """Verifies execution of IR query against populated SQLite in-memory database."""
    conn = get_db_connection(":memory:")
    init_db(conn=conn)
    
    # Populate with synthetic transactions (seed 42)
    txs = generate_synthetic_transactions(count=50, start_date=date(2026, 1, 1), end_date=date(2026, 8, 11), seed=42)
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO transactions (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source, account_id, currency, raw_text)
        VALUES (:date, :amount, :transaction_type, :merchant_raw, :merchant_normalized, :category, :source, :account_id, :currency, :raw_text)
        """,
        txs
    )
    conn.commit()

    # Query 1: Aggregate dining spending
    ir_aggregate = QueryIR(
        intent="aggregate",
        metric="sum",
        date_range=DateRange(start="2026-01-01", end="2026-08-11"),
        filters=QueryFilters(category=["dining"], exclude_transfers=True)
    )
    res_aggregate = execute_ir(ir_aggregate, conn=conn)
    
    assert res_aggregate["status"] == "success"
    assert isinstance(res_aggregate["data"], (float, int))
    assert res_aggregate["data"] > 0

    # Query 2: List top 5 transactions
    ir_list = QueryIR(
        intent="list",
        date_range=DateRange(start="2026-01-01", end="2026-08-11"),
        filters=QueryFilters(exclude_transfers=True),
        limit=5
    )
    res_list = execute_ir(ir_list, conn=conn)
    
    assert res_list["status"] == "success"
    assert res_list["count"] == 5
    assert len(res_list["data"]) == 5

    conn.close()
