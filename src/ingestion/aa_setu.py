import uuid
import logging
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
import sqlite3

from src.ingestion.normalizer import normalize_merchant_and_category, seed_default_aliases
from src.db.connection import execute_many

logger = logging.getLogger(__name__)

class SetuAASandboxClient:
    """
    Mock / Sandbox client for Setu Account Aggregator (AA) FIU integration.
    Simulates consent creation, polling status, and fetching structured FI transaction JSON payloads.
    """
    def __init__(self, client_id: str = "sandbox_client_123", secret: str = "sandbox_secret"):
        self.client_id = client_id
        self.secret = secret
        self._consents: Dict[str, Dict[str, Any]] = {}

    def create_consent_request(self, phone_number: str, fip_id: str = "FIP_HDFC_MOCK") -> Dict[str, Any]:
        """
        Creates a new AA consent request handle.
        """
        logger.info(f"Creating mock AA consent request for phone: {phone_number}, fip: {fip_id}")
        handle_id = f"consent_handle_{uuid.uuid4().hex[:8]}"
        consent_obj = {
            "consentHandle": handle_id,
            "status": "PENDING",
            "phoneNumber": phone_number,
            "fipId": fip_id,
            "redirectUrl": f"https://setu.co/aa/sandbox/consent/{handle_id}"
        }
        self._consents[handle_id] = consent_obj
        return consent_obj

    def check_consent_status(self, consent_handle_id: str) -> str:
        """
        Polls or checks consent status. Automatically transitions PENDING -> ACTIVE for sandbox demo.
        """
        logger.debug(f"Checking consent status for handle: {consent_handle_id}")
        if consent_handle_id in self._consents:
            self._consents[consent_handle_id]["status"] = "ACTIVE"
            logger.info(f"Consent handle {consent_handle_id} transitioned to ACTIVE.")
            return "ACTIVE"
        logger.warning(f"Consent handle {consent_handle_id} not found/EXPIRED.")
        return "EXPIRED"

    def fetch_financial_data(self, consent_handle_id: str) -> List[Dict[str, Any]]:
        """
        Fetches structured financial transaction JSON payload from approved AA consent.
        """
        logger.info(f"Fetching financial data for consent handle: {consent_handle_id}")
        status = self.check_consent_status(consent_handle_id)
        if status != "ACTIVE":
            logger.error(f"Cannot fetch financial data. Consent handle {consent_handle_id} is not ACTIVE (status: {status})")
            raise ValueError(f"Consent handle {consent_handle_id} is not ACTIVE (current status: {status})")

        today = date.today()
        # Return mock structured Setu FI transaction payload
        return [
            {
                "txnId": f"aa_txn_{uuid.uuid4().hex[:6]}",
                "transactionTimestamp": (today - timedelta(days=2)).strftime("%Y-%m-%dT10:30:00Z"),
                "amount": 1499.00,
                "type": "DEBIT",
                "narration": "SWIGGY BANGALORE IN",
                "reference": "UPI/423156789012",
                "account_id": "ACC_HDFC_9912"
            },
            {
                "txnId": f"aa_txn_{uuid.uuid4().hex[:6]}",
                "transactionTimestamp": (today - timedelta(days=5)).strftime("%Y-%m-%dT14:15:00Z"),
                "amount": 4999.00,
                "type": "DEBIT",
                "narration": "AMAZON PAY INDIA PVT",
                "reference": "POS/1029384756",
                "account_id": "ACC_HDFC_9912"
            },
            {
                "txnId": f"aa_txn_{uuid.uuid4().hex[:6]}",
                "transactionTimestamp": (today - timedelta(days=10)).strftime("%Y-%m-%dT09:00:00Z"),
                "amount": 25000.00,
                "type": "CREDIT",
                "narration": "SALARY CREDIT ACME CORP",
                "reference": "NEFT/88997766",
                "account_id": "ACC_HDFC_9912"
            }
        ]

def map_aa_transaction(aa_txn: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maps a raw Setu AA JSON transaction object to the local database schema format.
    """
    raw_amount = abs(float(aa_txn.get("amount", 0.0)))
    raw_type = str(aa_txn.get("type", "DEBIT")).upper()
    tx_type = "credit" if raw_type == "CREDIT" else "debit"
    
    timestamp = aa_txn.get("transactionTimestamp", date.today().strftime("%Y-%m-%d"))
    tx_date = timestamp[:10] if len(timestamp) >= 10 else date.today().strftime("%Y-%m-%d")

    merchant_raw = aa_txn.get("narration", "AA Merchant")
    
    return {
        "date": tx_date,
        "amount": raw_amount,
        "transaction_type": tx_type,
        "merchant_raw": merchant_raw,
        "source": "aa",
        "account_id": aa_txn.get("account_id", "SETU_AA_ACC"),
        "currency": "INR",
        "raw_text": str(aa_txn)
    }

def ingest_aa_transactions(
    aa_txns: List[Dict[str, Any]],
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Maps AA transaction dicts, normalizes merchant/category via shared normalizer,
    and inserts records into the SQLite database.
    """
    if not aa_txns:
        logger.info("No AA transactions provided for ingestion.")
        return 0

    logger.info(f"Ingesting {len(aa_txns)} AA transactions...")
    seed_default_aliases(db_path=db_path, conn=conn)
    mapped_rows = []

    for item in aa_txns:
        mapped = map_aa_transaction(item)
        norm_merchant, category = normalize_merchant_and_category(
            mapped["merchant_raw"], db_path=db_path, conn=conn
        )
        mapped["merchant_normalized"] = norm_merchant
        mapped["category"] = category
        mapped_rows.append(mapped)

    params_list = [
        (
            m["date"], m["amount"], m["transaction_type"], m["merchant_raw"],
            m["merchant_normalized"], m["category"], m["source"], m["account_id"],
            m["currency"], m["raw_text"]
        )
        for m in mapped_rows
    ]
    
    execute_many(
        """
        INSERT INTO transactions 
        (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source, account_id, currency, raw_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        params_list,
        db_path=db_path,
        conn=conn
    )
    
    logger.info(f"Successfully normalized and ingested {len(mapped_rows)} AA transactions into database.")
    return len(mapped_rows)
