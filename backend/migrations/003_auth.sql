CREATE TABLE staff_accounts (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('admin', 'staff'))
);
CREATE TABLE staff_sessions (
 token_hash TEXT PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES staff_accounts(id) ON DELETE CASCADE,
 expires_at INTEGER NOT NULL
);
