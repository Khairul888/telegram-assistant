-- Migration 001: Add trips table for trip-based memory system
-- Run this in Supabase SQL Editor
-- Created: 2025-12-20

-- Create trips table
CREATE TABLE IF NOT EXISTS trips (
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

-- Create indexes for efficient queries
CREATE INDEX idx_trips_user_id ON trips(user_id);
CREATE INDEX idx_trips_status ON trips(status);
CREATE INDEX idx_trips_last_activity ON trips(last_activity_at DESC);

-- Create function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update timestamp
CREATE TRIGGER update_trips_updated_at
    BEFORE UPDATE ON trips
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comment for documentation
COMMENT ON TABLE trips IS 'Stores trip information with participants for trip-based memory system';
COMMENT ON COLUMN trips.participants IS 'JSONB array of participant names (e.g., ["Alice", "Bob", "Carol"])';
COMMENT ON COLUMN trips.status IS 'Trip status: active, completed, or archived';
COMMENT ON COLUMN trips.last_activity_at IS 'Timestamp of last activity (used for auto-selecting current trip)';
