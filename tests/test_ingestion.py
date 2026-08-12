import pytest
import tempfile
from pathlib import Path

from src.db.connection import init_db, execute_query
from src.ingestion.sms_parser import parse_sms, is_promotional_or_otp, ingest_sms_batch
from src.ingestion.aa_setu import SetuAASandboxClient, map_aa_transaction, ingest_aa_transactions

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    init_db(db_path)
    yield db_path
    Path(db_path).unlink(missing_ok=True)

def test_sms_promotional_and_otp_filter():
    """Verifies that OTP and promotional messages are identified and filtered out."""
    assert is_promotional_or_otp("Your OTP for HDFC Bank login is 482910. Do not share.") is True
    assert is_promotional_or_otp("Congrats! You got 20% discount on Myntra. Use PROMO20.") is True
    assert is_promotional_or_otp("Rs 450.00 debited from A/C XX1234 at Swiggy on 10-Aug-26.") is False

def test_parse_sms_regex():
    """Tests regex parsing of debit and credit SMS messages."""
    # Test HDFC Debit SMS
    parsed = parse_sms("Rs 450.50 debited from A/C XX1234 to Swiggy Bangalore on 10-Aug-26")
    assert parsed is not None
    assert parsed["amount"] == 450.50
    assert parsed["transaction_type"] == "debit"
    assert "Swiggy" in parsed["merchant_raw"]

    # Test UPI Sent SMS
    parsed_upi = parse_sms("Sent Rs 120.00 to Uber India Systems on 08-Aug-26 ref 492810")
    assert parsed_upi is not None
    assert parsed_upi["amount"] == 120.00
    assert parsed_upi["transaction_type"] == "debit"

    # Test Credit SMS
    parsed_credit = parse_sms("Rs 5000.00 credited to A/C XX1234 from Acme Corp on 01-Aug-26")
    assert parsed_credit is not None
    assert parsed_credit["amount"] == 5000.00
    assert parsed_credit["transaction_type"] == "credit"

def test_ingest_sms_batch(temp_db):
    """Tests ingesting a batch of SMS messages into SQLite database."""
    sms_batch = [
        {"text": "Rs 850.00 debited from A/C XX1234 at Zomato Gurgaon on 05-Aug-26", "date": "2026-08-05"},
        {"text": "Your OTP is 123456 for logging into netbanking.", "date": "2026-08-05"},
        {"text": "Spent Rs 2499.00 on card XX8899 at Amazon Pay India on 06-Aug-26", "date": "2026-08-06"},
    ]
    
    parsed_count, unparsed = ingest_sms_batch(sms_batch, db_path=temp_db)
    assert parsed_count == 2
    assert len(unparsed) == 0  # OTP was filtered out, 2 transactions parsed
    
    rows = execute_query("SELECT * FROM transactions WHERE source = 'sms'", db_path=temp_db)
    assert len(rows) == 2
    merchants = [r["merchant_normalized"] for r in rows]
    assert "Zomato" in merchants
    assert "Amazon" in merchants

def test_setu_aa_sandbox_ingestion(temp_db):
    """Tests Setu AA sandbox consent flow, payload mapping, and database ingestion."""
    client = SetuAASandboxClient()
    consent = client.create_consent_request("9999988888")
    assert consent["status"] == "PENDING"
    
    handle = consent["consentHandle"]
    status = client.check_consent_status(handle)
    assert status == "ACTIVE"
    
    fi_data = client.fetch_financial_data(handle)
    assert len(fi_data) == 3
    
    ingested_count = ingest_aa_transactions(fi_data, db_path=temp_db)
    assert ingested_count == 3
    
    rows = execute_query("SELECT * FROM transactions WHERE source = 'aa'", db_path=temp_db)
    assert len(rows) == 3
    
    sources = {r["source"] for r in rows}
    assert "aa" in sources
