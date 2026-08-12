-- SQLite Database Schema for Expense NL Query Engine

CREATE TABLE IF NOT EXISTS transactions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    date                 DATE NOT NULL,
    amount               DECIMAL(12,2) NOT NULL,      -- positive value; debit/credit in transaction_type
    transaction_type     TEXT NOT NULL CHECK (transaction_type IN ('debit', 'credit')),
    merchant_raw         TEXT,                         -- raw string from SMS/AA (e.g. "AMAZON PAY INDIA PVT")
    merchant_normalized  TEXT,                         -- clean name (e.g. "Amazon")
    category             TEXT,                         -- category from taxonomy
    source               TEXT NOT NULL CHECK (source IN ('sms', 'aa', 'manual')),
    account_id           TEXT,                         -- card/account tail identifier
    currency             TEXT NOT NULL DEFAULT 'INR',
    raw_text             TEXT                          -- original SMS payload / AA snippet
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant ON transactions(merchant_normalized);

CREATE TABLE IF NOT EXISTS merchant_aliases (
    raw_pattern        TEXT PRIMARY KEY,   -- pattern (or uppercase substring) to match against merchant_raw
    normalized_name    TEXT NOT NULL,
    default_category   TEXT                -- default category taxonomy string
);
