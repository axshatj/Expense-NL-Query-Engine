# Architecture & Schema

## Data flow (this whole thing is built here, in order)

```
SMS inbox ─┐
           ├─► parser (built in ingestion.md) ─► normalizer (this file) ─► transactions table ─┐
AA / Setu ─┘                                                                                     │
                                                                                                  ▼
                                                                    NL query engine (see nl-query-and-grounding.md)
```

`ingestion.md` covers building the SMS regex parser and the AA/Setu Bridge sandbox consent-and-fetch flow from zero — that has to exist and be producing real (or synthetic, early on) rows before anything in this file matters. What this file covers is the shape those rows land in: the schema, the normalization step both ingestion paths feed into, and why a text-to-query system is only as good as the structure it's querying against — so normalization isn't a nice-to-have, it's a prerequisite the query engine assumes is already true of every row it sees.

## Core schema

```sql
CREATE TABLE transactions (
    id                   INTEGER PRIMARY KEY,
    date                 DATE NOT NULL,
    amount               DECIMAL(12,2) NOT NULL,      -- always positive; sign lives in transaction_type
    transaction_type     TEXT NOT NULL CHECK (transaction_type IN ('debit', 'credit')),
    merchant_raw         TEXT,                         -- exactly as it came off SMS/AA, e.g. "AMAZON PAY INDIA PVT"
    merchant_normalized  TEXT,                         -- e.g. "Amazon" — see merchant_aliases below
    category             TEXT,                         -- from the fixed taxonomy below
    source               TEXT NOT NULL CHECK (source IN ('sms', 'aa', 'manual')),
    account_id           TEXT,                         -- which card/account this came from
    currency             TEXT NOT NULL DEFAULT 'INR',
    raw_text             TEXT                          -- original SMS body / AA payload snippet, kept for debugging and re-parsing
);

CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_merchant ON transactions(merchant_normalized);
```

Why both `merchant_raw` and `merchant_normalized`: SMS/AA merchant strings are inconsistent for the same real-world merchant — "AMAZON PAY INDIA", "Amazon.in", "AMZN Mktp" might all be the same merchant. Keep the raw string for audit/debugging; always query against the normalized one.

## Merchant normalization

```sql
CREATE TABLE merchant_aliases (
    raw_pattern        TEXT PRIMARY KEY,   -- substring or regex to match against merchant_raw
    normalized_name    TEXT NOT NULL,
    default_category   TEXT                -- category to assign when this alias first creates a transaction
);
```

Approach, cheapest-to-most-thorough:

1. **Exact/substring match first** — most SMS senders are consistent enough (`LIKE '%AMAZON%'` catches the bulk of it). Cheap, deterministic, zero LLM cost.
2. **Fall back to an LLM call only for unmatched merchants** — batch the unknowns (not one call per transaction), ask the model to propose a normalized name + category, and *write the result back into `merchant_aliases`* so the same raw string never needs another LLM call again. This is the pattern that keeps ongoing cost near-zero: the alias table gets more complete over time and the LLM only ever does genuinely new work.
3. Never call an LLM per-transaction at ingestion time for something this memoizable — that's the kind of design choice worth calling out in an interview as evidence you think about cost and latency, not just correctness.

## Category taxonomy

Keep this fixed and small — an open-ended category set makes both the IR schema and the eval harness much harder to get right. A reasonable starting set:

`groceries, dining, transport, shopping, subscriptions, bills_utilities, entertainment, travel, healthcare, transfers, fees_charges, other`

Two categories deserve special handling because they're what people actually ask about most:

- **`subscriptions`** — anything recurring (same normalized merchant, same-ish amount, monthly cadence). Worth detecting explicitly with a lightweight recurrence check — same merchant + amount within a small tolerance appearing in ≥2 consecutive months — since "what subscriptions am I paying for" is one of the highest-value questions this whole project can answer, and a plain category tag alone doesn't get you there; it needs the recurrence signal too.
- **`transfers`** — self-transfers (moving money between your own accounts) should generally be *excluded* from spending aggregates by default, or spend numbers will be wrong. This is why the IR schema (see next file) has an explicit `exclude_transfers` field rather than a hardcoded backend rule — "how much did I spend" and "how much money moved out of my account" need different defaults, and only the model reading the question can tell which one applies.