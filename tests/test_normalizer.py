import pytest
import tempfile
from pathlib import Path
from src.db.connection import init_db, execute_query, execute_statement, get_db_connection
from src.ingestion.normalizer import (
    seed_default_aliases,
    normalize_merchant_and_category,
    batch_normalize_unmapped_merchants,
    detect_recurring_subscriptions
)

@pytest.fixture(autouse=True)
def disable_api(monkeypatch):
    monkeypatch.setattr("src.ingestion.normalizer.OPENAI_API_KEY", "")

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    init_db(db_path)
    seed_default_aliases(db_path)
    yield db_path
    Path(db_path).unlink(missing_ok=True)

def test_seed_and_normalize(temp_db):
    """Tests matching raw merchant strings against seeded merchant aliases."""
    norm_name, cat = normalize_merchant_and_category("SWIGGY BANGALORE IN", db_path=temp_db)
    assert norm_name == "Swiggy"
    assert cat == "dining"

    norm_name, cat = normalize_merchant_and_category("AMAZON PAY INDIA PVT", db_path=temp_db)
    assert norm_name == "Amazon"
    assert cat == "shopping"

    norm_name, cat = normalize_merchant_and_category("NETFLIX ENTERTAINMENT", db_path=temp_db)
    assert norm_name == "Netflix"
    assert cat == "subscriptions"

def test_batch_normalize_unmapped(temp_db):
    """Tests adding new unmapped merchant rules into merchant_aliases table."""
    unmapped = ["CULT FIT GYM BLR", "DUNZO DIGITAL PVT"]
    results = batch_normalize_unmapped_merchants(unmapped, db_path=temp_db)
    
    assert len(results) == 2
    assert "CULT FIT GYM BLR" in results
    
    # Query database to confirm alias was persisted
    aliases = execute_query(
        "SELECT * FROM merchant_aliases WHERE raw_pattern LIKE ?",
        ("%CULT FIT GYM BLR%",),
        db_path=temp_db
    )
    assert len(aliases) == 1

def test_detect_recurring_subscriptions(temp_db):
    """Tests identifying transactions across distinct months and marking them as subscriptions."""
    # Insert transactions for Spotify across 3 distinct months
    txs = [
        ("2026-05-15", 119.00, "debit", "SPOTIFY INDIA", "Spotify", "other", "sms"),
        ("2026-06-15", 119.00, "debit", "SPOTIFY INDIA", "Spotify", "other", "sms"),
        ("2026-07-15", 119.00, "debit", "SPOTIFY INDIA", "Spotify", "other", "sms"),
    ]
    for date_str, amt, t_type, raw, norm, cat, src in txs:
        execute_statement(
            "INSERT INTO transactions (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (date_str, amt, t_type, raw, norm, cat, src),
            db_path=temp_db
        )
        
    subs = detect_recurring_subscriptions(db_path=temp_db)
    assert len(subs) >= 1
    assert subs[0]["merchant_normalized"] == "Spotify"
    
    # Verify category updated to 'subscriptions' in SQLite
    rows = execute_query("SELECT category FROM transactions WHERE merchant_normalized = 'Spotify'", db_path=temp_db)
    assert all(r["category"] == "subscriptions" for r in rows)
