import pytest
from datetime import date
from src.query_engine.pipeline import QueryPipeline, answer_question
from src.db.connection import get_db_connection, init_db
from src.ingestion.synthetic import generate_synthetic_transactions

@pytest.fixture
def test_db_path(tmp_path):
    db_file = str(tmp_path / "test_pipeline.db")
    conn = get_db_connection(db_file)
    init_db(conn=conn)
    
    txs = generate_synthetic_transactions(count=60, start_date=date(2026, 1, 1), end_date=date(2026, 8, 11), seed=100)
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO transactions (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source, account_id, currency, raw_text)
        VALUES (:date, :amount, :transaction_type, :merchant_raw, :merchant_normalized, :category, :source, :account_id, :currency, :raw_text)
        """,
        txs
    )
    conn.commit()
    conn.close()
    return db_file

def test_pipeline_aggregate_question(test_db_path):
    """Verifies end-to-end pipeline execution for aggregate food spending question."""
    ref = date(2026, 8, 11)
    res = answer_question("How much did I spend on food last month?", ref_date=ref, db_path=test_db_path)
    
    assert "answer" in res
    assert res["ir"]["intent"] == "aggregate"
    assert "dining" in res["ir"]["filters"]["category"]
    assert res["db_result"]["status"] == "success"
    assert res["latency_ms"] > 0

def test_pipeline_unrelated_question(test_db_path):
    """Verifies end-to-end pipeline refusal for out-of-domain question."""
    ref = date(2026, 8, 11)
    res = answer_question("Write a python script to calculate fibonacci", ref_date=ref, db_path=test_db_path)
    
    assert res["ir"]["intent"] == "unrelated"
    assert res["db_result"]["status"] == "unrelated"
    assert "expense tracking assistant" in res["answer"]

def test_pipeline_list_question(test_db_path):
    """Verifies end-to-end pipeline execution for transaction list question."""
    ref = date(2026, 8, 11)
    res = answer_question("Show me my last 5 Swiggy orders", ref_date=ref, db_path=test_db_path)
    
    assert res["ir"]["intent"] == "list"
    assert res["ir"]["limit"] == 5
    assert res["db_result"]["status"] == "success"
