-- Migration 006: Add start_date and end_date to trips table
-- This allows proper date calculation for itinerary items
-- Created: 2026-01-01

-- Add start_date and end_date columns
ALTER TABLE trips
ADD COLUMN IF NOT EXISTS start_date DATE,
ADD COLUMN IF NOT EXISTS end_date DATE;

-- Add indexes for date queries
CREATE INDEX IF NOT EXISTS idx_trips_start_date ON trips(start_date);

-- Add comment for documentation
COMMENT ON COLUMN trips.start_date IS 'Trip start date (YYYY-MM-DD format)';
COMMENT ON COLUMN trips.end_date IS 'Trip end date (YYYY-MM-DD format)';
