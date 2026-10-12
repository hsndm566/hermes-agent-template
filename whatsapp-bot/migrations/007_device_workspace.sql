ALTER TABLE businesses ADD COLUMN IF NOT EXISTS owner_session TEXT;
CREATE INDEX IF NOT EXISTS businesses_owner_session ON businesses(owner_session);
