-- Migration 001: Add terminal fields to travel_events table
-- Run this in Supabase SQL Editor to add departure and arrival terminal fields
-- Created: 2025-12-28

-- Add terminal fields for flight information
ALTER TABLE travel_events
ADD COLUMN IF NOT EXISTS departure_terminal TEXT,
ADD COLUMN IF NOT EXISTS arrival_terminal TEXT;

-- Add comment
COMMENT ON COLUMN travel_events.departure_terminal IS 'Departure terminal (e.g., Terminal 1, Terminal A)';
COMMENT ON COLUMN travel_events.arrival_terminal IS 'Arrival terminal (e.g., Terminal 2, Terminal B)';

-- Verification
SELECT 'Terminal fields added successfully!' as message;
