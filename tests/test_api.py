import pytest
from fastapi.testclient import TestClient
from datetime import date
from src.api.server import app
from src.db.connection import get_db_connection, init_db
from src.ingestion.synthetic import generate_synthetic_transactions

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Sets up an isolated test database for API tests."""
    db_file = str(tmp_path / "test_api.db")
    monkeypatch.setattr("src.api.server.get_db_connection", lambda db_path=None: get_db_connection(db_file))
    
    conn = get_db_connection(db_file)
    init_db(conn=conn)
    
    txs = generate_synthetic_transactions(count=30, start_date=date(2026, 1, 1), end_date=date(2026, 8, 11), seed=200)
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

client = TestClient(app)

def test_api_health():
    """Verifies health check endpoint."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "1.0.0"}

def test_api_stats():
    """Verifies database statistics endpoint."""
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_transactions" in data
    assert data["total_transactions"] >= 30
    assert "total_spent" in data
    assert "category_breakdown" in data

def test_api_transactions():
    """Verifies transactions list endpoint."""
    res = client.get("/api/transactions?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 10

def test_api_query():
    """Verifies query processing endpoint."""
    res = client.post("/api/query", json={"question": "How much did I spend on food last month?"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert data["ir"]["intent"] == "aggregate"

def test_api_ingest_sms():
    """Verifies SMS ingestion endpoint."""
    sms = "Spent Rs.450.00 at SWIGGY INDIA on HDFC Bank Card ending 1234 on 05-AUG-26."
    res = client.post("/api/ingest/sms", json={"sms_text": sms})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["transaction"]["merchant_normalized"] == "Swiggy"
