-- Migration 000: Create ALL required tables for Telegram Travel Assistant
-- Run this FIRST in Supabase SQL Editor before other migrations
-- Created: 2025-12-28

-- =============================================================================
-- 1. CREATE EXPENSES TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS expenses (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    trip_id BIGINT, -- Will be linked later

    -- Receipt information
    merchant_name TEXT,
    location TEXT,
    transaction_date DATE,
    transaction_time TIME,
    category TEXT DEFAULT 'other', -- food, transport, accommodation, entertainment, shopping, other

    -- Financial data
    subtotal NUMERIC(10, 2),
    tax_amount NUMERIC(10, 2),
    tip_amount NUMERIC(10, 2),
    total_amount NUMERIC(10, 2) NOT NULL,
    currency TEXT DEFAULT 'USD',

    -- Items (JSONB array of {name, price, quantity})
    items JSONB DEFAULT '[]',
    payment_method TEXT, -- cash, card, digital

    -- Splitting information
    paid_by TEXT, -- Name of person who paid
    split_between TEXT[], -- Array of participant names
    split_amounts JSONB, -- {participant: amount} mapping

    -- OCR metadata
    confidence_score NUMERIC(3, 2),
    raw_extracted_data JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_id ON expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(transaction_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);

-- =============================================================================
-- 2. CREATE TRAVEL_EVENTS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS travel_events (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    trip_id BIGINT, -- Will be linked later
    event_type TEXT NOT NULL, -- 'flight', 'hotel', 'activity'

    -- Common fields
    booking_reference TEXT,

    -- Flight-specific fields
    airline TEXT,
    flight_number TEXT,
    departure_city TEXT,
    departure_airport TEXT,
    arrival_city TEXT,
    arrival_airport TEXT,
    departure_time TIMESTAMPTZ,
    arrival_time TIMESTAMPTZ,
    gate TEXT,
    seat TEXT,
    passenger_name TEXT,

    -- Hotel-specific fields
    hotel_name TEXT,
    location TEXT,
    check_in_date DATE,
    check_in_time TIME,
    check_out_date DATE,
    check_out_time TIME,
    nights INTEGER,
    room_type TEXT,
    guests INTEGER,
    guest_name TEXT,

    -- Raw OCR data
    raw_extracted_data JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_travel_events_user_id ON travel_events(user_id);
CREATE INDEX IF NOT EXISTS idx_travel_events_type ON travel_events(event_type);
CREATE INDEX IF NOT EXISTS idx_travel_events_departure ON travel_events(departure_time);

-- =============================================================================
-- 3. CREATE DOCUMENTS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    trip_id BIGINT, -- Will be linked later
    file_id TEXT UNIQUE NOT NULL,
    original_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size_bytes BIGINT DEFAULT 0,
    mime_type TEXT,

    -- Content storage
    extracted_text TEXT,
    overarching_theme TEXT,
    keywords TEXT[], -- Array of keywords

    -- Processing info
    processing_status TEXT DEFAULT 'pending',
    processing_error TEXT,

    -- Metadata storage (JSONB for flexibility)
    metadata_json JSONB,

    -- Vector storage info (for future use)
    vector_stored BOOLEAN DEFAULT FALSE,
    vector_id TEXT,
    embedding_model TEXT,

    -- Processing metrics
    token_count INTEGER,
    processing_time_seconds NUMERIC,
    chunk_count INTEGER,

    -- Additional fields
    tags TEXT[],

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_file_id ON documents(file_id);
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(original_filename);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);

-- =============================================================================
-- 4. CREATE AUTO-UPDATE TIMESTAMP FUNCTION (if not exists)
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 5. CREATE TRIGGERS FOR AUTO-UPDATING TIMESTAMPS
-- =============================================================================
DROP TRIGGER IF EXISTS update_expenses_updated_at ON expenses;
CREATE TRIGGER update_expenses_updated_at
    BEFORE UPDATE ON expenses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_travel_events_updated_at ON travel_events;
CREATE TRIGGER update_travel_events_updated_at
    BEFORE UPDATE ON travel_events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SUCCESS MESSAGE
-- =============================================================================
SELECT 'Base tables created successfully!' as message;
