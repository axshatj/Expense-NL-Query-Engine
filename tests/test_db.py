import pytest
import sqlite3
import tempfile
from pathlib import Path
from src.db.connection import (
    init_db,
    get_db_connection,
    execute_query,
    execute_statement,
    execute_many
)

@pytest.fixture
def temp_db_file():
    """Provides a temporary SQLite database file initialized with schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    init_db(db_path)
    yield db_path
    
    # Cleanup temp file
    Path(db_path).unlink(missing_ok=True)

@pytest.fixture
def mem_conn():
    """Provides an open in-memory database connection initialized with schema."""
    conn = get_db_connection(":memory:")
    init_db(conn=conn)
    yield conn
    conn.close()

def test_init_db(temp_db_file):
    """Verifies tables transactions and merchant_aliases exist."""
    conn = get_db_connection(temp_db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row["name"] for row in cursor.fetchall()]
    conn.close()
    
    assert "transactions" in tables
    assert "merchant_aliases" in tables

def test_insert_transaction(mem_conn):
    """Tests inserting and fetching a single transaction using in-memory connection."""
    tx_id = execute_statement(
        """
        INSERT INTO transactions 
        (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source, account_id, currency, raw_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-08-10", 450.50, "debit", "SWIGGY BANGALORE IN", "Swiggy", "dining", "sms", "XX1234", "INR", "Debited Rs 450.50 at Swiggy"),
        conn=mem_conn
    )
    
    assert tx_id == 1
    
    rows = execute_query("SELECT * FROM transactions WHERE id = ?", (tx_id,), conn=mem_conn)
    assert len(rows) == 1
    row = rows[0]
    assert row["date"] == "2026-08-10"
    assert row["amount"] == 450.50
    assert row["transaction_type"] == "debit"
    assert row["merchant_normalized"] == "Swiggy"
    assert row["category"] == "dining"
    assert row["source"] == "sms"

def test_check_constraints(mem_conn):
    """Verifies CHECK constraints on transaction_type and source."""
    with pytest.raises(sqlite3.IntegrityError):
        execute_statement(
            "INSERT INTO transactions (date, amount, transaction_type, source) VALUES ('2026-08-10', 100, 'invalid_type', 'sms')",
            conn=mem_conn
        )

    with pytest.raises(sqlite3.IntegrityError):
        execute_statement(
            "INSERT INTO transactions (date, amount, transaction_type, source) VALUES ('2026-08-10', 100, 'debit', 'invalid_source')",
            conn=mem_conn
        )

def test_merchant_aliases(mem_conn):
    """Tests merchant aliases insertion and lookup."""
    execute_statement(
        "INSERT INTO merchant_aliases (raw_pattern, normalized_name, default_category) VALUES (?, ?, ?)",
        ("%AMAZON%", "Amazon", "shopping"),
        conn=mem_conn
    )
    
    aliases = execute_query("SELECT * FROM merchant_aliases WHERE raw_pattern LIKE ?", ("%AMAZON%",), conn=mem_conn)
    assert len(aliases) == 1
    assert aliases[0]["normalized_name"] == "Amazon"
    assert aliases[0]["default_category"] == "shopping"

def test_execute_many(mem_conn):
    """Tests batch execution for multiple transactions."""
    txs = [
        ("2026-08-01", 120.00, "debit", "UBER TRIP", "Uber", "transport", "sms"),
        ("2026-08-02", 999.00, "debit", "NETFLIX IN", "Netflix", "subscriptions", "sms"),
    ]
    
    count = execute_many(
        "INSERT INTO transactions (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
        txs,
        conn=mem_conn
    )
    assert count == 2
    
    rows = execute_query("SELECT * FROM transactions", conn=mem_conn)
    assert len(rows) == 2
