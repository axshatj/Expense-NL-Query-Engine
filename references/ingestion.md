# Ingestion (Built From Scratch)

This is the part of the project that doesn't exist yet and has to be built before there's any real data for the AI layer to query. Two independent sources feed the same `transactions` table: SMS parsing and Account Aggregator (AA) integration. Build and test them separately — they fail in different ways and debugging is much easier when they're not tangled together.

Do this work first, even though it's less exciting than the LLM layer. An eval benchmark and a grounded-answer pipeline are worthless without real (or realistic) transactions to run them against.

## Start with synthetic data, not real SMS/AA access

Real AA integration requires FIU sandbox approval and a real bank account consent flow — that's setup time that shouldn't block everything downstream of it. Same with SMS: testing needs actual bank/UPI message history, which takes time to accumulate or export.

Instead, build a small synthetic data generator first:

```python
import random
from datetime import date, timedelta

MERCHANTS = ["Swiggy", "Amazon", "Zomato", "Uber", "Netflix", "BESCOM", "Big Basket"]
CATEGORIES = {"Swiggy": "dining", "Zomato": "dining", "Amazon": "shopping",
              "Uber": "transport", "Netflix": "subscriptions",
              "BESCOM": "bills_utilities", "Big Basket": "groceries"}

def generate_synthetic_transactions(n=300, start=date(2026, 1, 1)):
    rows = []
    for _ in range(n):
        merchant = random.choice(MERCHANTS)
        rows.append({
            "date": start + timedelta(days=random.randint(0, 220)),
            "amount": round(random.uniform(50, 3000), 2),
            "merchant_raw": merchant.upper() + random.choice(["", " INDIA", " PVT LTD"]),
            "category": CATEGORIES[merchant],
            "source": "manual",
        })
    return rows
```

This unblocks weeks 3+ (the query engine, prompts, eval harness) from ever being stalled on sandbox approval or SMS export logistics. Real ingestion gets built in parallel and swapped in once ready — the `transactions` table doesn't care which source populated it.

## SMS parsing, scoped small

**Don't try to parse every bank's SMS format.** That's a genuinely hard problem at scale (dozens of banks, inconsistent templates, frequent format changes) and isn't necessary to prove the concept. Scope it to:

- 2-3 bank/UPI senders you actually have real SMS history from (your own phone is the test data)
- The common shape: debit/credit alert with amount, merchant/reference, and account tail

A workable approach — regex first, LLM fallback for anything that doesn't match:

```python
import re

# One pattern per known sender format. Add more as you encounter them —
# don't try to write a universal parser upfront.
PATTERNS = {
    "generic_debit": re.compile(
        r"debited.*?(?:Rs\.?|INR)\s?([\d,]+\.?\d*).*?"
        r"(?:at|to)\s+([A-Za-z0-9\s]+?)(?:\s+on|\.|$)",
        re.IGNORECASE
    ),
    "generic_credit": re.compile(
        r"credited.*?(?:Rs\.?|INR)\s?([\d,]+\.?\d*)",
        re.IGNORECASE
    ),
}

def parse_sms(text: str) -> dict | None:
    for name, pattern in PATTERNS.items():
        match = pattern.search(text)
        if match:
            amount = float(match.group(1).replace(",", ""))
            merchant = match.group(2).strip() if match.lastindex and match.lastindex >= 2 else None
            return {
                "amount": amount,
                "merchant_raw": merchant,
                "transaction_type": "credit" if "credit" in name else "debit",
                "raw_text": text,
            }
    return None  # falls through to the LLM-fallback batch, not handled per-message
```

For messages that don't match any known pattern, **batch them and send to an LLM periodically** (e.g., once you've accumulated 20-30 unparsed messages) rather than calling an LLM per SMS as it arrives — same reasoning as the merchant-alias fallback in `architecture-and-schema.md`: memoize the expensive path, keep the cheap path doing most of the work. Ask the model to extract `{amount, merchant, transaction_type}` from the batch, and treat its output as lower-confidence than a regex match — worth flagging in the UI or logs as "parsed via fallback" so mistakes are traceable back to their source.

**What to explicitly leave out of a from-scratch solo build:**
- Multi-currency SMS parsing
- OTP/promotional message filtering at scale (a simple keyword denylist — "OTP", "offer", "cashback expires" — is enough)
- Every possible bank template — 2-3 real ones you can test against is a legitimate, defensible scope for a portfolio project

## Account Aggregator (AA) integration, scoped small

The full AA framework (via Setu or another AA) involves becoming a registered FIU, an app-to-app consent flow, and encrypted data fetch. For a from-scratch personal project, the realistic scope is the **sandbox environment**, not production FIU registration:

1. **Sign up for Setu's AA sandbox** — this gives test FIP (bank) data without needing real regulatory approval, which is the right call for a portfolio project (production FIU registration is a business process, not a weekend of coding).
2. **Implement the consent flow**: create consent request → redirect user to approve → receive consent handle → poll/webhook for consent status.
3. **Fetch financial information**: once consent is `ACTIVE`, request FI data for the approved account, decrypt the response (Setu's SDK/library handles the ECDH key exchange — don't hand-roll the crypto), and parse the returned transaction list into the same `transactions` schema SMS parsing feeds.
4. **Map AA's transaction format to the local schema** — AA data arrives more structured than SMS (proper JSON, not free text), so this direction is more "field mapping" than "parsing":

```python
def map_aa_transaction(aa_txn: dict) -> dict:
    return {
        "date": aa_txn["transactionTimestamp"][:10],
        "amount": abs(float(aa_txn["amount"])),
        "transaction_type": "credit" if aa_txn["type"] == "CREDIT" else "debit",
        "merchant_raw": aa_txn.get("narration", ""),
        "source": "aa",
        "raw_text": str(aa_txn),
    }
```

**What to explicitly leave out of a from-scratch solo build:**
- Multiple AA provider support (Setu sandbox alone is enough to demonstrate the integration)
- Production FIU registration/compliance — sandbox is the right and expected scope for a resume project; say so plainly rather than implying production-grade compliance work that didn't happen
- Handling every FIP (bank) — the sandbox typically ships a small set of mock FIPs, which is sufficient

## Both paths converge on the same normalizer

Whichever source a transaction came from, it should pass through one shared normalization step before landing in `transactions` — see `architecture-and-schema.md` for the merchant-alias and category-assignment logic. Keeping SMS parsing and AA mapping as thin adapters that both feed one normalizer (rather than each doing their own categorization) is what keeps the downstream query layer source-agnostic — a question like "how much did I spend on food" shouldn't need to know or care whether a transaction came from SMS or AA.