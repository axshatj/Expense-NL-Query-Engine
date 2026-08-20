import re
import json
import logging
from datetime import date
from typing import Optional, Dict, Any, List, Tuple
import sqlite3

from src.config import OPENAI_API_KEY, LLM_MODEL
from src.query_engine.llm_client import get_llm_client, call_llm_with_retry
from src.ingestion.normalizer import normalize_merchant_and_category, seed_default_aliases
from src.db.connection import execute_statement, execute_many

logger = logging.getLogger(__name__)

# Keywords for filtering non-transactional SMS messages
DENYLIST_KEYWORDS = [
    "OTP", "VERIFICATION CODE", "LOG IN", "OFFER", "CASHBACK EXPIRES",
    "DEAR CUSTOMER", "CONGRATS", "PROMO", "DISCOUNT", "APPLY NOW"
]

# Regex patterns for common bank/UPI debit & credit formats
PATTERNS = {
    "generic_debit": re.compile(
        r"(?:debited|spent|paid).*?(?:Rs\.?|INR)\s?([\d,]+\.?\d*).*?(?:at|to|vpa|info)\s+([A-Za-z0-9\s\.\@\_\-]+?)(?:\s+on|\s+ref|\.|$|\s+val|\s+avl)",
        re.IGNORECASE
    ),
    "upi_debit": re.compile(
        r"(?:sent|paid)\s+(?:Rs\.?|INR)\s?([\d,]+\.?\d*)\s+to\s+([A-Za-z0-9\s\.\@\_\-]+?)(?:\s+on|\.|$|\s+ref|\s+upi)",
        re.IGNORECASE
    ),
    "card_debit": re.compile(
        r"spent\s+(?:Rs\.?|INR)\s?([\d,]+\.?\d*)\s+(?:on|at)\s+(?:card|vpa)?\s*([A-Za-z0-9\s\.\_\-]+?)(?:\s+on|\.|$)",
        re.IGNORECASE
    ),
    "generic_credit": re.compile(
        r"(?:credited|received).*?(?:Rs\.?|INR)\s?([\d,]+\.?\d*).*?(?:from|by|at)?\s*([A-Za-z0-9\s\.\_\-]+?)(?:\s+on|\.|$|\s+ref)",
        re.IGNORECASE
    ),
}

def is_promotional_or_otp(text: str) -> bool:
    """
    Returns True if SMS body matches promotional or OTP denylist keywords.
    """
    text_upper = text.upper()
    return any(keyword in text_upper for keyword in DENYLIST_KEYWORDS)

def parse_sms(text: str, tx_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Parses a single SMS text string.
    Extracts amount, merchant, and transaction_type flexibly.
    Returns None if text is promotional/OTP or no transaction amount is found.
    """
    if not text:
        return None
    if is_promotional_or_otp(text):
        logger.debug("Filtered out non-transactional/OTP SMS message.")
        return None

    text_lower = text.lower()
    
    # Check if text contains transactional keywords
    is_debit = any(w in text_lower for w in ["debited", "spent", "paid", "sent", "dr"])
    is_credit = any(w in text_lower for w in ["credited", "received", "added", "cr"])
    
    if not (is_debit or is_credit):
        logger.debug("SMS does not contain transaction keywords (spent/credited/etc.).")
        return None
        
    # Extract amount
    amt_match = re.search(r"(?:Rs\.?|INR)\s?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if not amt_match:
        logger.debug("Could not find transaction amount in SMS.")
        return None
        
    try:
        amount = float(amt_match.group(1).replace(",", ""))
    except ValueError:
        logger.debug("Failed parsing float from amount match.")
        return None
        
    if amount <= 0:
        logger.debug("Transaction amount is zero or negative.")
        return None

    # Extract merchant (looking for 'at', 'to', 'from', 'by', 'vpa')
    merchant_match = re.search(
        r"(?:at|to|from|by|vpa|info)\s+([A-Za-z0-9\s\.\@\_\-]+?)(?:\s+on|\s+ref|\s+vpa|\s+card|\.|$|\s+val|\s+avl|\s+via|\s+bal)",
        text,
        re.IGNORECASE
    )
    
    merchant_raw = merchant_match.group(1).strip() if merchant_match else "Unknown Merchant"
    
    # Filter out spurious merchant names if regex matched account keywords
    if re.match(r"^(a/c|account|card|vpa|rs|inr|xx\d+)", merchant_raw, re.IGNORECASE):
        # Try second attempt skipping initial account word
        alt_match = re.search(r"(?:at|to|from|by)\s+(?:a/c\s+[x\d]+\s+)?([A-Za-z0-9\s\.\@\_\-]+?)(?:\s+on|\.|$)", text, re.IGNORECASE)
        if alt_match:
            merchant_raw = alt_match.group(1).strip()

    if len(merchant_raw) > 50:
        merchant_raw = merchant_raw[:50].strip()

    tx_type = "credit" if is_credit and not is_debit else "debit"
    
    if tx_date is None:
        tx_date = date.today().strftime("%Y-%m-%d")

    # Extract card / account tail if present
    acc_match = re.search(r"(?:A/C|card|acct|account)\s*(?:no\.?)?\s*([X\*\d]{4,})", text, re.IGNORECASE)
    account_id = acc_match.group(1) if acc_match else "SMS_ACCOUNT"

    logger.debug(f"Regex successfully parsed SMS: {tx_type} ₹{amount} at raw merchant: '{merchant_raw}'")
    return {
        "date": tx_date,
        "amount": amount,
        "transaction_type": tx_type,
        "merchant_raw": merchant_raw,
        "source": "sms",
        "account_id": account_id,
        "currency": "INR",
        "raw_text": text
    }

def ingest_sms_batch(
    sms_list: List[Dict[str, str]],
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Tuple[int, List[str]]:
    """
    Ingests a batch of SMS dicts `[{"text": "...", "date": "YYYY-MM-DD"}]`.
    Parses regex first, normalizes merchants/categories, inserts valid rows into SQLite.
    Returns `(parsed_count, unparsed_sms_texts)`.
    """
    logger.info(f"Ingesting batch of {len(sms_list)} SMS messages...")
    seed_default_aliases(db_path=db_path, conn=conn)
    
    parsed_rows = []
    unparsed_texts = []
    
    for item in sms_list:
        text = item.get("text", "")
        tx_date = item.get("date", date.today().strftime("%Y-%m-%d"))
        
        parsed = parse_sms(text, tx_date=tx_date)
        if parsed:
            # Pass merchant_raw through shared normalizer
            norm_merchant, category = normalize_merchant_and_category(
                parsed["merchant_raw"], db_path=db_path, conn=conn
            )
            parsed["merchant_normalized"] = norm_merchant
            parsed["category"] = category
            parsed_rows.append(parsed)
        else:
            if not is_promotional_or_otp(text):
                unparsed_texts.append(text)

    if parsed_rows:
        params_list = [
            (
                p["date"], p["amount"], p["transaction_type"], p["merchant_raw"],
                p["merchant_normalized"], p["category"], p["source"], p["account_id"],
                p["currency"], p["raw_text"]
            )
            for p in parsed_rows
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

    logger.info(f"SMS batch ingestion complete: parsed={len(parsed_rows)}, unparsed={len(unparsed_texts)}.")
    return len(parsed_rows), unparsed_texts

def parse_unparsed_sms_with_llm(
    unparsed_texts: List[str],
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Batches unparsed SMS texts and sends them to LLM to extract {amount, merchant_raw, transaction_type}.
    Inserts lower-confidence fallback parsed records into SQLite.
    """
    if not unparsed_texts or not OPENAI_API_KEY:
        return 0
        
    logger.info(f"Attempting LLM fallback parsing on {len(unparsed_texts)} unparsed SMS messages.")
    try:
        client = get_llm_client()
        
        prompt = f"""
Extract transaction details from the following unparsed SMS messages.
For each message that is a financial transaction, extract:
- amount (float)
- merchant_raw (string)
- transaction_type ("debit" or "credit")

Messages:
{json.dumps(unparsed_texts)}

Output ONLY a JSON array of objects:
[
  {{"text": "original sms text", "amount": 100.0, "merchant_raw": "Merchant Name", "transaction_type": "debit"}}
]
If a message is not a transaction, omit it.
"""
        response = call_llm_with_retry(
            client,
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        items = json.loads(content).get("items", json.loads(content))
        
        if not isinstance(items, list):
            items = [items]
            
        parsed_rows = []
        today_str = date.today().strftime("%Y-%m-%d")
        
        for item in items:
            raw_merchant = item.get("merchant_raw", "Unknown")
            norm_merchant, category = normalize_merchant_and_category(raw_merchant, db_path=db_path, conn=conn)
            parsed_rows.append((
                today_str,
                float(item.get("amount", 0.0)),
                item.get("transaction_type", "debit"),
                raw_merchant,
                norm_merchant,
                category,
                "sms",
                "SMS_LLM_FALLBACK",
                "INR",
                item.get("text", "")
            ))
            
        if parsed_rows:
            execute_many(
                """
                INSERT INTO transactions 
                (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source, account_id, currency, raw_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                parsed_rows,
                db_path=db_path,
                conn=conn
            )
            logger.info(f"LLM fallback parsing successfully extracted {len(parsed_rows)} transaction(s).")
            return len(parsed_rows)
    except Exception as e:
        logger.warning(f"LLM fallback SMS parsing failed: {e}")
        
    return 0
