CREATE INDEX IF NOT EXISTS idx_services_business ON services("businessId");
CREATE INDEX IF NOT EXISTS idx_hours_business_day ON working_hours("businessId", day_of_week, is_ramadan);
CREATE INDEX IF NOT EXISTS idx_staff_business_active ON staff("businessId", is_active);
CREATE INDEX IF NOT EXISTS idx_appointments_business_start ON appointments("businessId", start_time);
CREATE INDEX IF NOT EXISTS idx_appointments_business_phone ON appointments("businessId", customer_phone, start_time);
CREATE INDEX IF NOT EXISTS idx_customers_business_phone ON customers("businessId", phone);
CREATE INDEX IF NOT EXISTS idx_settings_business_key ON settings("businessId", key);
