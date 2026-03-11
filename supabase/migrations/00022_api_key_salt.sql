-- SEC-04: Add per-key salt column for API key hashing.
-- New keys get a random salt; existing keys have NULL (use unsalted hash path).
ALTER TABLE api_keys ADD COLUMN salt VARCHAR(64) DEFAULT NULL;

COMMENT ON COLUMN api_keys.salt IS 'Per-key random salt for SHA-256 hashing. NULL = legacy unsalted key.';
