CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY,
    "businessId" UUID NOT NULL UNIQUE,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    phone TEXT NOT NULL,
    whatsapp_session_id TEXT NOT NULL UNIQUE,
    maps_url TEXT NOT NULL,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    vat_number TEXT,
    cr_number TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT businesses_tenant_identity CHECK (id = "businessId")
);

CREATE TABLE IF NOT EXISTS services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    duration_min INTEGER NOT NULL CHECK (duration_min > 0 AND duration_min <= 1440),
    price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    buffer_min INTEGER NOT NULL DEFAULT 0 CHECK (buffer_min >= 0 AND buffer_min <= 240)
);

CREATE TABLE IF NOT EXISTS working_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    open_time TIME,
    close_time TIME,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    is_ramadan BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT working_hours_times CHECK (
        is_closed OR (open_time IS NOT NULL AND close_time IS NOT NULL AND close_time > open_time)
    ),
    UNIQUE ("businessId", day_of_week, is_ramadan)
);

CREATE TABLE IF NOT EXISTS staff (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    customer_phone TEXT NOT NULL,
    service_id UUID NOT NULL REFERENCES services(id),
    staff_id UUID NOT NULL REFERENCES staff(id),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('confirmed','rescheduled','cancelled','completed','no_show')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reminder_24_sent BOOLEAN NOT NULL DEFAULT FALSE,
    reminder_2_sent BOOLEAN NOT NULL DEFAULT FALSE,
    followup_sent BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT appointment_time_order CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    phone TEXT NOT NULL,
    name TEXT,
    no_show_count INTEGER NOT NULL DEFAULT 0 CHECK (no_show_count >= 0),
    last_visit TIMESTAMPTZ,
    UNIQUE ("businessId", phone)
);

CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE ("businessId", key)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'appointments_no_overlap'
    ) THEN
        ALTER TABLE appointments
        ADD CONSTRAINT appointments_no_overlap
        EXCLUDE USING gist (
            "businessId" WITH =,
            staff_id WITH =,
            tstzrange(start_time, end_time, '[)') WITH &&
        ) WHERE (status IN ('confirmed','rescheduled'));
    END IF;
END $$;
