ALTER TABLE customers
  ADD COLUMN IF NOT EXISTS preferred_language TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='customers_preferred_language_check'
  ) THEN
    ALTER TABLE customers
      ADD CONSTRAINT customers_preferred_language_check
      CHECK (preferred_language IS NULL OR preferred_language IN ('ar','en'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_customers_business_language
  ON customers("businessId", preferred_language);
