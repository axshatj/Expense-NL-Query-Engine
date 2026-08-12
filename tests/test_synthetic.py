import pytest
import tempfile
from pathlib import Path
from src.ingestion.synthetic import generate_synthetic_transactions, seed_synthetic_database
from src.db.connection import execute_query, init_db

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    init_db(db_path)
    yield db_path
    Path(db_path).unlink(missing_ok=True)

def test_generate_synthetic_transactions():
    """Verifies generated transaction count, categories, and subscription patterns."""
    txs = generate_synthetic_transactions(count=300)
    assert len(txs) >= 300
    
    # Check that all categories are covered
    categories = {t["category"] for t in txs}
    assert "dining" in categories
    assert "groceries" in categories
    assert "subscriptions" in categories
    assert "transport" in categories

    # Verify recurring Netflix subscriptions exist
    netflix_txs = [t for t in txs if t["merchant_normalized"] == "Netflix"]
    assert len(netflix_txs) >= 10, "Expected at least 10 monthly Netflix subscription transactions"

def test_seed_synthetic_database(temp_db):
    """Verifies seeding synthetic transactions into SQLite database."""
    count = seed_synthetic_database(db_path=temp_db, count=250)
    assert count >= 250
    
    rows = execute_query("SELECT COUNT(*) as cnt FROM transactions", db_path=temp_db)
    assert rows[0]["cnt"] == count
    
    # Verify aggregate SQL queries work as expected against seeded data
    dining_sum = execute_query(
        "SELECT SUM(amount) as total FROM transactions WHERE category = 'dining' AND transaction_type = 'debit'",
        db_path=temp_db
    )
    assert dining_sum[0]["total"] is not None and dining_sum[0]["total"] > 0
