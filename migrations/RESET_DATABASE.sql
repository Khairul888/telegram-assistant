-- =============================================================================
-- COMPLETE DATABASE RESET FOR TELEGRAM TRAVEL ASSISTANT
-- =============================================================================
-- This script will:
-- 1. Drop all existing tables (with CASCADE to handle dependencies)
-- 2. Recreate all tables from scratch
-- 3. Create all indexes and triggers
--
-- ⚠️ WARNING: This will DELETE ALL DATA in these tables:
--    - trips, expenses, travel_events, documents, user_sessions
--
-- Run this in Supabase SQL Editor
-- Created: 2025-12-28
-- =============================================================================

-- =============================================================================
-- STEP 1: DROP ALL EXISTING TABLES
-- =============================================================================
DROP TABLE IF EXISTS user_sessions CASCADE;
DROP TABLE IF EXISTS expenses CASCADE;
DROP TABLE IF EXISTS travel_events CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS trips CASCADE;

-- Drop the update function if it exists (we'll recreate it)
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- =============================================================================
-- STEP 2: CREATE UPDATE TIMESTAMP FUNCTION
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- STEP 3: CREATE TRIPS TABLE (Main table - must be created first)
-- =============================================================================
CREATE TABLE trips (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    trip_name TEXT NOT NULL,
    location TEXT,
    participants JSONB NOT NULL DEFAULT '[]', -- Array of simple names: ["Alice", "Bob", "Carol"]
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'completed', 'archived'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for trips
CREATE INDEX idx_trips_user_id ON trips(user_id);
CREATE INDEX idx_trips_status ON trips(status);
CREATE INDEX idx_trips_last_activity ON trips(last_activity_at DESC);

-- Create trigger for trips
CREATE TRIGGER update_trips_updated_at
    BEFORE UPDATE ON trips
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE trips IS 'Stores trip information with participants for trip-based memory system';
COMMENT ON COLUMN trips.participants IS 'JSONB array of participant names (e.g., ["Alice", "Bob", "Carol"])';
COMMENT ON COLUMN trips.status IS 'Trip status: active, completed, or archived';
COMMENT ON COLUMN trips.last_activity_at IS 'Timestamp of last activity (used for auto-selecting current trip)';

-- =============================================================================
-- STEP 4: CREATE USER_SESSIONS TABLE (For conversation state)
-- =============================================================================
CREATE TABLE user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    current_trip_id BIGINT REFERENCES trips(id) ON DELETE SET NULL,
    conversation_state TEXT, -- 'awaiting_location', 'awaiting_participants', etc.
    conversation_context JSONB, -- Store temporary data during multi-step conversations
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for user_sessions
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_current_trip ON user_sessions(current_trip_id);

-- Create trigger for user_sessions
CREATE TRIGGER update_user_sessions_updated_at
    BEFORE UPDATE ON user_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE user_sessions IS 'Stores user session data including current trip and conversation state';
COMMENT ON COLUMN user_sessions.current_trip_id IS 'Reference to the active trip for this user';
COMMENT ON COLUMN user_sessions.conversation_state IS 'Current state in multi-step conversation flow';
COMMENT ON COLUMN user_sessions.conversation_context IS 'JSONB storage for temporary conversation data';

-- =============================================================================
-- STEP 5: CREATE EXPENSES TABLE (Receipts and expense tracking)
-- =============================================================================
CREATE TABLE expenses (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE,

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
    split_between TEXT[], -- PostgreSQL array of participant names
    split_amounts JSONB, -- {participant: amount} mapping

    -- OCR metadata
    confidence_score NUMERIC(3, 2),
    raw_extracted_data JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for expenses
CREATE INDEX idx_expenses_user_id ON expenses(user_id);
CREATE INDEX idx_expenses_trip_id ON expenses(trip_id);
CREATE INDEX idx_expenses_date ON expenses(transaction_date DESC);
CREATE INDEX idx_expenses_category ON expenses(category);

-- Create trigger for expenses
CREATE TRIGGER update_expenses_updated_at
    BEFORE UPDATE ON expenses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE expenses IS 'Stores expense data from receipts with splitting information';
COMMENT ON COLUMN expenses.trip_id IS 'Foreign key to trips table - isolates expenses per trip';

-- =============================================================================
-- STEP 6: CREATE TRAVEL_EVENTS TABLE (Flights, hotels, etc.)
-- =============================================================================
CREATE TABLE travel_events (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE,
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

-- Create indexes for travel_events
CREATE INDEX idx_travel_events_user_id ON travel_events(user_id);
CREATE INDEX idx_travel_events_trip_id ON travel_events(trip_id);
CREATE INDEX idx_travel_events_type ON travel_events(event_type);
CREATE INDEX idx_travel_events_departure ON travel_events(departure_time);

-- Create trigger for travel_events
CREATE TRIGGER update_travel_events_updated_at
    BEFORE UPDATE ON travel_events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE travel_events IS 'Stores flight tickets, hotel bookings, and other travel events';
COMMENT ON COLUMN travel_events.trip_id IS 'Foreign key to trips table - isolates events per trip';

-- =============================================================================
-- STEP 7: CREATE DOCUMENTS TABLE (Generic document storage)
-- =============================================================================
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE,
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

-- Create indexes for documents
CREATE INDEX idx_documents_file_id ON documents(file_id);
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_trip_id ON documents(trip_id);
CREATE INDEX idx_documents_filename ON documents(original_filename);
CREATE INDEX idx_documents_status ON documents(processing_status);

-- Create trigger for documents
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE documents IS 'Stores generic documents and files uploaded by users';
COMMENT ON COLUMN documents.trip_id IS 'Foreign key to trips table - isolates documents per trip';

-- =============================================================================
-- STEP 8: VERIFICATION - List all created tables
-- =============================================================================
SELECT
    '✅ Database reset complete!' as status,
    'Tables created: trips, user_sessions, expenses, travel_events, documents' as message;

-- Show table counts
SELECT 'trips' as table_name, COUNT(*) as row_count FROM trips
UNION ALL
SELECT 'user_sessions', COUNT(*) FROM user_sessions
UNION ALL
SELECT 'expenses', COUNT(*) FROM expenses
UNION ALL
SELECT 'travel_events', COUNT(*) FROM travel_events
UNION ALL
SELECT 'documents', COUNT(*) FROM documents;
