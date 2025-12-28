-- Migration 002: Add trip_id foreign keys to existing tables
-- Run this in Supabase SQL Editor AFTER running 001_add_trips_table.sql
-- Created: 2025-12-20

-- Add trip_id to expenses table
ALTER TABLE expenses
ADD COLUMN IF NOT EXISTS trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE;

-- Create index for efficient trip-based queries
CREATE INDEX IF NOT EXISTS idx_expenses_trip_id ON expenses(trip_id);

-- Add trip_id to travel_events table
ALTER TABLE travel_events
ADD COLUMN IF NOT EXISTS trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE;

-- Create index for efficient trip-based queries
CREATE INDEX IF NOT EXISTS idx_travel_events_trip_id ON travel_events(trip_id);

-- Add trip_id to documents table
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS trip_id BIGINT REFERENCES trips(id) ON DELETE CASCADE;

-- Create index for efficient trip-based queries
CREATE INDEX IF NOT EXISTS idx_documents_trip_id ON documents(trip_id);

-- Add comments for documentation
COMMENT ON COLUMN expenses.trip_id IS 'Foreign key to trips table - isolates expenses per trip';
COMMENT ON COLUMN travel_events.trip_id IS 'Foreign key to trips table - isolates travel events per trip';
COMMENT ON COLUMN documents.trip_id IS 'Foreign key to trips table - isolates documents per trip';
