-- Phase 2B Database Schema
-- Enhanced tables for travel context and expense tracking
-- Run this in your Supabase SQL Editor after the existing schema

-- Travel events (flights, hotels, activities)
CREATE TABLE IF NOT EXISTS travel_events (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    processing_job_id BIGINT REFERENCES processing_jobs(id),
    event_type TEXT NOT NULL, -- 'flight', 'hotel', 'activity'

    -- Common fields
    title TEXT,
    location TEXT,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,

    -- Flight specific fields
    airline TEXT,
    flight_number TEXT,
    departure_airport TEXT,
    arrival_airport TEXT,
    departure_time TIMESTAMPTZ,
    arrival_time TIMESTAMPTZ,
    gate TEXT,
    seat TEXT,
    departure_city TEXT,
    arrival_city TEXT,

    -- Hotel specific fields
    hotel_name TEXT,
    check_in_date DATE,
    check_out_date DATE,
    room_type TEXT,
    nights INTEGER,
    guests INTEGER,

    -- Common metadata
    booking_reference TEXT,
    passenger_name TEXT,
    guest_name TEXT,
    confidence_score DECIMAL(3,2),
    raw_extracted_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Expenses and receipts
CREATE TABLE IF NOT EXISTS expenses (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    processing_job_id BIGINT REFERENCES processing_jobs(id),

    -- Basic transaction info
    merchant_name TEXT,
    location TEXT,
    transaction_date DATE,
    transaction_time TIME,
    category TEXT, -- 'food', 'transport', 'accommodation', 'entertainment', 'shopping'

    -- Financial details
    subtotal DECIMAL(10,2),
    tax_amount DECIMAL(10,2),
    tip_amount DECIMAL(10,2),
    total_amount DECIMAL(10,2),
    currency TEXT DEFAULT 'USD',

    -- Itemized breakdown
    items JSONB, -- [{"name": "Coffee", "price": 4.50, "quantity": 1}, ...]

    -- Group expense tracking
    paid_by TEXT, -- user who paid
    split_between TEXT[], -- array of user IDs to split among
    split_amounts JSONB, -- {"user1": 25.50, "user2": 30.00}

    -- Payment metadata
    payment_method TEXT, -- 'cash', 'card', 'digital'
    confidence_score DECIMAL(3,2),
    raw_extracted_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document processing results
CREATE TABLE IF NOT EXISTS document_processing_results (
    id BIGSERIAL PRIMARY KEY,
    processing_job_id BIGINT REFERENCES processing_jobs(id),
    document_type TEXT, -- 'flight_ticket', 'receipt', 'hotel_booking', 'itinerary'
    processing_status TEXT DEFAULT 'pending', -- 'pending', 'completed', 'failed', 'needs_review'

    -- Processing metadata
    extraction_confidence DECIMAL(3,2),
    processing_time_ms INTEGER,
    ai_model_used TEXT DEFAULT 'gemini-2.5-flash',

    -- Results
    structured_data JSONB,
    extracted_text TEXT,
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Link to created records
    travel_event_id BIGINT REFERENCES travel_events(id),
    expense_id BIGINT REFERENCES expenses(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_travel_events_user_id ON travel_events(user_id);
CREATE INDEX IF NOT EXISTS idx_travel_events_date ON travel_events(start_date);
CREATE INDEX IF NOT EXISTS idx_travel_events_type ON travel_events(event_type);

CREATE INDEX IF NOT EXISTS idx_expenses_user_id ON expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(transaction_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);

CREATE INDEX IF NOT EXISTS idx_document_results_job_id ON document_processing_results(processing_job_id);
CREATE INDEX IF NOT EXISTS idx_document_results_status ON document_processing_results(processing_status);

-- Update trigger for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_travel_events_updated_at BEFORE UPDATE ON travel_events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_expenses_updated_at BEFORE UPDATE ON expenses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add some sample data for testing
INSERT INTO travel_events (id, user_id, event_type, title, airline, flight_number, departure_airport, arrival_airport, departure_time, arrival_time, confidence_score, raw_extracted_data)
VALUES (0, 'sample_user', 'flight', 'Sample Flight', 'Sample Airlines', 'SA123', 'JFK', 'LHR', NOW() + INTERVAL '7 days', NOW() + INTERVAL '7 days 8 hours', 0.95, '{"sample": true}')
ON CONFLICT (id) DO NOTHING;

INSERT INTO expenses (id, user_id, merchant_name, category, total_amount, transaction_date, confidence_score, raw_extracted_data)
VALUES (0, 'sample_user', 'Sample Coffee Shop', 'food', 12.50, CURRENT_DATE, 0.90, '{"sample": true}')
ON CONFLICT (id) DO NOTHING;

-- Phase 2B schema setup complete!
-- You can now process travel documents and store structured data.