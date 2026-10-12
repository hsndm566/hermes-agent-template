CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY,
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    phone TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('inbound','outbound')),
    body TEXT NOT NULL,
    provider_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE ("businessId", direction, provider_id)
);
CREATE INDEX IF NOT EXISTS messages_business_phone_time ON messages("businessId", phone, created_at DESC);
