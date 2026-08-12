import random
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from src.config import VALID_CATEGORIES, DATABASE_PATH
from src.db.connection import execute_many, init_db, execute_statement

MERCHANT_POOL = {
    "groceries": [
        ("BIGBASKET IN", "Big Basket"),
        ("SWIGGY INSTAMART", "Swiggy Instamart"),
        ("BLINKIT GURGAON", "Blinkit"),
        ("NATURES BASKET BLR", "Nature's Basket")
    ],
    "dining": [
        ("SWIGGY BANGALORE IN", "Swiggy"),
        ("ZOMATO GURGAON IN", "Zomato"),
        ("STARBUCKS COFFEE BLR", "Starbucks"),
        ("MCDONALDS INDIA", "McDonald's")
    ],
    "transport": [
        ("UBER INDIA SYSTEMS", "Uber"),
        ("OLA CABS BENGALURU", "Ola"),
        ("HPCL PETROL PUMP", "HPCL Fuel"),
        ("NAMMA METRO RECHARGE", "Namma Metro")
    ],
    "shopping": [
        ("AMAZON PAY INDIA PVT", "Amazon"),
        ("FLIPKART INTERNET", "Flipkart"),
        ("MYNTRA DESIGNS", "Myntra"),
        ("UNIQLO INDIA", "Uniqlo")
    ],
    "subscriptions": [
        ("NETFLIX ENTERTAINMENT", "Netflix"),
        ("SPOTIFY INDIA PVT", "Spotify"),
        ("YOUTUBE PREMIUM", "YouTube Premium"),
        ("OPENAI CHATGPT PLUS", "ChatGPT Plus")
    ],
    "bills_utilities": [
        ("BESCOM ELECTRICITY", "BESCOM"),
        ("AIRTEL POSTPAID", "Airtel"),
        ("JIO FIBER RECHARGE", "Jio"),
        ("TATA PLAY DTH", "Tata Play")
    ],
    "entertainment": [
        ("PVR CINEMAS BLR", "PVR Cinemas"),
        ("BOOKMYSHOW MUMBAI", "BookMyShow"),
        ("STEAM GAMES", "Steam")
    ],
    "travel": [
        ("MAKEMYTRIP INDIA", "MakeMyTrip"),
        ("INDIGO AIRLINES", "IndiGo"),
        ("AIRBNB STAY", "Airbnb")
    ],
    "healthcare": [
        ("APOLLO PHARMACY BLR", "Apollo Pharmacy"),
        ("TATA 1MG GURGAON", "Tata 1mg"),
        ("PRACTO HEALTHCARE", "Practo")
    ],
    "transfers": [
        ("HDFC BANK SELF TRANSFER", "HDFC Self Transfer"),
        ("UPI TRANSFER TO FRIEND", "UPI Transfer")
    ],
    "fees_charges": [
        ("HDFC CARD ANNUAL FEE", "HDFC Bank"),
        ("ATM CASH WITHDRAWAL FEE", "ATM Fee")
    ],
    "other": [
        ("MISC LOCAL STORE", "Local Store"),
        ("CORNER STATIONERY", "Stationery Shop")
    ]
}

RECURRING_SUBSCRIPTIONS = [
    ("NETFLIX ENTERTAINMENT", "Netflix", 649.00, 5, "subscriptions"),
    ("SPOTIFY INDIA PVT", "Spotify", 119.00, 15, "subscriptions"),
    ("YOUTUBE PREMIUM", "YouTube Premium", 149.00, 20, "subscriptions"),
]

ACCOUNT_TAILS = ["HDFC_**4321", "ICICI_**8899", "SBI_**1204"]

def generate_synthetic_transactions(
    count: int = 300,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """
    Generates realistic synthetic transaction records spanning past 12 months.
    Includes recurring subscription patterns for testing subscription detection.
    """
    random.seed(seed)
    
    if end_date is None:
        end_date = date(2026, 8, 11)
    if start_date is None:
        start_date = end_date - timedelta(days=365)
        
    total_days = (end_date - start_date).days
    transactions: List[Dict[str, Any]] = []
    
    # 1. Generate monthly recurring subscriptions first (ensures recurrence signal)
    current_year_month = start_date.replace(day=1)
    while current_year_month <= end_date:
        for raw, norm, amount, target_day, cat in RECURRING_SUBSCRIPTIONS:
            # Construct exact date for monthly subscription
            sub_day = min(target_day, 28)
            try:
                sub_date = date(current_year_month.year, current_year_month.month, sub_day)
            except ValueError:
                sub_date = current_year_month
                
            if start_date <= sub_date <= end_date:
                transactions.append({
                    "date": sub_date.strftime("%Y-%m-%d"),
                    "amount": amount,
                    "transaction_type": "debit",
                    "merchant_raw": raw,
                    "merchant_normalized": norm,
                    "category": cat,
                    "source": "sms",
                    "account_id": random.choice(ACCOUNT_TAILS),
                    "currency": "INR",
                    "raw_text": f"Rs {amount} debited at {raw} on {sub_date}"
                })
        # Move to next month
        if current_year_month.month == 12:
            current_year_month = date(current_year_month.year + 1, 1, 1)
        else:
            current_year_month = date(current_year_month.year, current_year_month.month + 1, 1)
            
    # 2. Generate random transactions to fill up the target count
    remaining_count = max(0, count - len(transactions))
    categories = list(MERCHANT_POOL.keys())
    
    for _ in range(remaining_count):
        cat = random.choice(categories)
        raw_merchant, norm_merchant = random.choice(MERCHANT_POOL[cat])
        random_days = random.randint(0, total_days)
        tx_date = start_date + timedelta(days=random_days)
        
        # Decide transaction type (mostly debit, some salary/cashback credits)
        is_credit = random.random() < 0.05
        tx_type = "credit" if is_credit else "debit"
        
        if is_credit:
            amount = round(random.uniform(500, 55000), 2)
            cat = "transfers"
        else:
            if cat in ["dining", "transport", "groceries"]:
                amount = round(random.uniform(80, 1500), 2)
            elif cat in ["travel", "shopping"]:
                amount = round(random.uniform(800, 15000), 2)
            elif cat in ["bills_utilities"]:
                amount = round(random.uniform(500, 4500), 2)
            else:
                amount = round(random.uniform(100, 3000), 2)
                
        source = random.choice(["sms", "aa", "manual"])
        account_id = random.choice(ACCOUNT_TAILS)
        
        transactions.append({
            "date": tx_date.strftime("%Y-%m-%d"),
            "amount": amount,
            "transaction_type": tx_type,
            "merchant_raw": raw_merchant,
            "merchant_normalized": norm_merchant,
            "category": cat,
            "source": source,
            "account_id": account_id,
            "currency": "INR",
            "raw_text": f"Txn of Rs {amount} at {raw_merchant} via {source}"
        })
        
    # Sort transactions chronologically
    transactions.sort(key=lambda x: x["date"])
    return transactions

def seed_synthetic_database(db_path: Optional[str] = None, count: int = 300) -> int:
    """
    Seeds the SQLite database with synthetic transaction data.
    """
    target_path = db_path if db_path is not None else DATABASE_PATH
    init_db(target_path)
    
    # Clear existing transactions before seeding
    execute_statement("DELETE FROM transactions;", db_path=target_path)
    
    txs = generate_synthetic_transactions(count=count)
    params_list = [
        (
            t["date"],
            t["amount"],
            t["transaction_type"],
            t["merchant_raw"],
            t["merchant_normalized"],
            t["category"],
            t["source"],
            t["account_id"],
            t["currency"],
            t["raw_text"]
        )
        for t in txs
    ]
    
    inserted_count = execute_many(
        """
        INSERT INTO transactions 
        (date, amount, transaction_type, merchant_raw, merchant_normalized, category, source, account_id, currency, raw_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        params_list,
        db_path=target_path
    )
    return len(txs)

if __name__ == "__main__":
    count = seed_synthetic_database()
    print(f"Successfully seeded database with {count} synthetic transactions.")
