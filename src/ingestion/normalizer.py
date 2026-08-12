import re
import json
import logging
from typing import Tuple, List, Dict, Any, Optional
import sqlite3
from src.config import VALID_CATEGORIES, DATABASE_PATH, OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from src.db.connection import execute_query, execute_statement, execute_many, get_db_connection

logger = logging.getLogger(__name__)

# Default merchant alias patterns to seed
DEFAULT_MERCHANT_ALIASES = [
    ("%AMAZON%", "Amazon", "shopping"),
    ("%FLIPKART%", "Flipkart", "shopping"),
    ("%MYNTRA%", "Myntra", "shopping"),
    ("%UNIQLO%", "Uniqlo", "shopping"),
    ("%SWIGGY%", "Swiggy", "dining"),
    ("%ZOMATO%", "Zomato", "dining"),
    ("%STARBUCKS%", "Starbucks", "dining"),
    ("%MCDONALD%", "McDonald's", "dining"),
    ("%UBER%", "Uber", "transport"),
    ("%OLA%", "Ola", "transport"),
    ("%HPCL%", "HPCL Fuel", "transport"),
    ("%METRO%", "Namma Metro", "transport"),
    ("%BIGBASKET%", "Big Basket", "groceries"),
    ("%INSTAMART%", "Swiggy Instamart", "groceries"),
    ("%BLINKIT%", "Blinkit", "groceries"),
    ("%NETFLIX%", "Netflix", "subscriptions"),
    ("%SPOTIFY%", "Spotify", "subscriptions"),
    ("%YOUTUBE%", "YouTube Premium", "subscriptions"),
    ("%OPENAI%", "ChatGPT Plus", "subscriptions"),
    ("%BESCOM%", "BESCOM", "bills_utilities"),
    ("%AIRTEL%", "Airtel", "bills_utilities"),
    ("%JIO%", "Jio", "bills_utilities"),
    ("%TATA PLAY%", "Tata Play", "bills_utilities"),
    ("%PVR%", "PVR Cinemas", "entertainment"),
    ("%BOOKMYSHOW%", "BookMyShow", "entertainment"),
    ("%STEAM%", "Steam", "entertainment"),
    ("%MAKEMYTRIP%", "MakeMyTrip", "travel"),
    ("%INDIGO%", "IndiGo", "travel"),
    ("%AIRBNB%", "Airbnb", "travel"),
    ("%APOLLO%", "Apollo Pharmacy", "healthcare"),
    ("%1MG%", "Tata 1mg", "healthcare"),
    ("%PRACTO%", "Practo", "healthcare"),
    ("%TRANSFER%", "Transfer", "transfers"),
    ("%ATM%", "ATM Fee", "fees_charges"),
]

def seed_default_aliases(db_path: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Seeds default merchant_aliases into SQLite database if table is empty.
    """
    logger.info("Seeding default merchant aliases into database...")
    params_list = [(pat, norm, cat) for pat, norm, cat in DEFAULT_MERCHANT_ALIASES]
    inserted = execute_many(
        "INSERT OR IGNORE INTO merchant_aliases (raw_pattern, normalized_name, default_category) VALUES (?, ?, ?);",
        params_list,
        db_path=db_path,
        conn=conn
    )
    logger.info(f"Default merchant aliases seed complete (inserted or ignored: {inserted}).")

def normalize_merchant_and_category(
    merchant_raw: str,
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Tuple[str, str]:
    """
    Normalizes raw merchant string against merchant_aliases table via SQL LIKE matching.
    Returns (normalized_merchant, category).
    """
    if not merchant_raw:
        return ("Unknown Merchant", "other")
        
    raw_upper = merchant_raw.strip().upper()
    
    # Query database for matching pattern
    aliases = execute_query(
        "SELECT normalized_name, default_category FROM merchant_aliases WHERE ? LIKE raw_pattern LIMIT 1",
        (raw_upper,),
        db_path=db_path,
        conn=conn
    )
    
    if aliases:
        norm_name = aliases[0]["normalized_name"]
        category = aliases[0]["default_category"] or "other"
        logger.debug(f"Normalized raw merchant '{merchant_raw}' -> '{norm_name}' ({category}) via db pattern.")
        return (norm_name, category)
        
    # Heuristic fallback if not found in aliases table
    clean_name = re.sub(r"\b(PVT|LTD|INDIA|PAY|INC|CORP|BLR|GURGAON|SYSTEMS)\b", "", raw_upper).strip()
    clean_name = clean_name.title() if clean_name else merchant_raw.title()
    logger.debug(f"Normalized raw merchant '{merchant_raw}' -> '{clean_name}' (other) via heuristic fallback.")
    return (clean_name, "other")

def normalize_transaction(
    parsed_tx: Dict[str, Any],
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Takes a parsed transaction dictionary (from SMS or AA) and normalizes merchant & category.
    """
    merchant_raw = parsed_tx.get("merchant_raw", "")
    norm_name, category = normalize_merchant_and_category(merchant_raw, db_path=db_path, conn=conn)
    
    tx = dict(parsed_tx)
    tx["merchant_normalized"] = norm_name
    tx["category"] = parsed_tx.get("category") or category
    return tx

def batch_normalize_unmapped_merchants(
    unmapped_merchants: List[str],
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Tuple[str, str]]:
    """
    Batches unknown raw merchant strings and uses LLM (or heuristic fallback) to propose
    normalized names and categories. Writes new mappings to merchant_aliases SQLite table.
    """
    if not unmapped_merchants:
        return {}

    unique_unmapped = list(set([m.strip() for m in unmapped_merchants if m and m.strip()]))
    logger.info(f"Batch normalising {len(unique_unmapped)} unique unmapped merchants.")
    results: Dict[str, Tuple[str, str]] = {}
    
    # Attempt LLM batch normalization if API key is present
    if OPENAI_API_KEY:
        try:
            logger.info("Using LLM batch normalization for unknown merchants...")
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)
            
            prompt = f"""
Given the following list of raw merchant strings from SMS/bank statements:
{json.dumps(unique_unmapped)}

Valid categories: {json.dumps(VALID_CATEGORIES)}

For each raw merchant string, provide a clean normalized merchant name and assign the single best category.
Output ONLY a JSON object mapping each raw string to {{"normalized_name": "...", "category": "..."}}:
"""
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            llm_content = response.choices[0].message.content
            parsed = json.loads(llm_content)
            
            for raw in unique_unmapped:
                if raw in parsed:
                    norm = parsed[raw].get("normalized_name", raw.title())
                    cat = parsed[raw].get("category", "other")
                    if cat not in VALID_CATEGORIES:
                        cat = "other"
                    results[raw] = (norm, cat)
                    logger.debug(f"LLM normalized '{raw}' -> '{norm}' ({cat})")
        except Exception as e:
            logger.warning(f"LLM batch normalization failed, falling back to heuristic: {e}")

    # Heuristic fallback for any unmapped merchants not answered by LLM
    for raw in unique_unmapped:
        if raw not in results:
            norm, cat = normalize_merchant_and_category(raw, db_path=db_path, conn=conn)
            results[raw] = (norm, cat)

    # Write new rules back to merchant_aliases table so LLM is never called twice for same pattern
    new_aliases = [
        (f"%{raw.upper()}%", norm, cat)
        for raw, (norm, cat) in results.items()
    ]
    execute_many(
        "INSERT OR IGNORE INTO merchant_aliases (raw_pattern, normalized_name, default_category) VALUES (?, ?, ?);",
        new_aliases,
        db_path=db_path,
        conn=conn
    )
    
    logger.info(f"Batch normalization complete. Learned {len(results)} new merchant mappings.")
    return results

def detect_recurring_subscriptions(
    db_path: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Identifies recurring transactions (same normalized merchant + similar amount appearing in >= 2 distinct months).
    Updates their category to 'subscriptions' in the database.
    Returns list of detected subscription merchants.
    """
    logger.info("Running recurring subscriptions detection...")
    query = """
    SELECT 
        merchant_normalized,
        ROUND(amount, 0) as rounded_amount,
        COUNT(DISTINCT strftime('%Y-%m', date)) as distinct_months,
        COUNT(*) as total_occurrences
    FROM transactions
    WHERE transaction_type = 'debit'
    GROUP BY merchant_normalized, rounded_amount
    HAVING distinct_months >= 2;
    """
    detected_subscriptions = execute_query(query, db_path=db_path, conn=conn)
    logger.info(f"Subscription detector found {len(detected_subscriptions)} candidate subscriptions.")
    
    updated_count = 0
    for sub in detected_subscriptions:
        merchant = sub["merchant_normalized"]
        amount = sub["rounded_amount"]
        
        # Update matching transactions category to 'subscriptions'
        rows_updated = execute_statement(
            """
            UPDATE transactions 
            SET category = 'subscriptions'
            WHERE merchant_normalized = ? 
              AND ABS(amount - ?) < 5.0 
              AND transaction_type = 'debit'
            """,
            (merchant, amount),
            db_path=db_path,
            conn=conn
        )
        updated_count += rows_updated
        logger.debug(f"Updated {rows_updated} transaction(s) for subscription: '{merchant}' (₹{amount})")
        
    logger.info(f"Subscription detection complete. Categorised {updated_count} total transactions as subscriptions.")
    return detected_subscriptions
