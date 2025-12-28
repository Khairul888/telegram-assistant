-- Migration 004: Add itinerary and places tables for conversational memory
-- This adds support for:
-- 1. Trip itinerary (scheduled activities with dates/times)
-- 2. Trip places wishlist (restaurants, attractions, etc. with Google Maps data)

-- Create trip_itinerary table (scheduled activities)
CREATE TABLE IF NOT EXISTS trip_itinerary (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    trip_id BIGINT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,

    -- Core fields
    date DATE NOT NULL,
    time TIME,
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    category TEXT DEFAULT 'activity', -- activity, dining, transport, other

    -- Optional enrichment
    duration_minutes INTEGER,
    confirmation_number TEXT,
    cost NUMERIC(10, 2),
    currency TEXT DEFAULT 'USD',
    notes TEXT,

    -- Metadata
    source TEXT DEFAULT 'manual', -- manual, detected, google_maps
    raw_extracted_data JSONB,
    day_order INTEGER,  -- Day 1, Day 2, etc.
    time_order INTEGER, -- Ordering within same day

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_itinerary_trip_id ON trip_itinerary(trip_id);
CREATE INDEX idx_itinerary_date ON trip_itinerary(date);
CREATE INDEX idx_itinerary_ordering ON trip_itinerary(trip_id, date, time_order);

-- Trigger for updated_at
CREATE TRIGGER update_itinerary_updated_at
    BEFORE UPDATE ON trip_itinerary
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create trip_places table (wishlist with Google Maps data)
CREATE TABLE IF NOT EXISTS trip_places (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    trip_id BIGINT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,

    -- Core fields
    name TEXT NOT NULL,
    category TEXT NOT NULL, -- restaurant, attraction, shopping, nightlife, other
    address TEXT,

    -- Google Maps integration
    google_place_id TEXT UNIQUE,
    google_maps_url TEXT,
    latitude NUMERIC(10, 8),
    longitude NUMERIC(11, 8),

    -- Rich data from Places API
    rating NUMERIC(2, 1),
    user_ratings_total INTEGER,
    price_level INTEGER,
    phone_number TEXT,
    website TEXT,
    opening_hours JSONB,
    photos JSONB,

    -- User metadata
    notes TEXT,
    priority TEXT DEFAULT 'medium',
    visited BOOLEAN DEFAULT FALSE,
    visited_date DATE,

    -- Tracking
    source TEXT DEFAULT 'manual',
    raw_api_data JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_places_trip_id ON trip_places(trip_id);
CREATE INDEX idx_places_category ON trip_places(category);
CREATE INDEX idx_places_visited ON trip_places(visited);
CREATE INDEX idx_places_google_place_id ON trip_places(google_place_id);

-- Trigger for updated_at
CREATE TRIGGER update_places_updated_at
    BEFORE UPDATE ON trip_places
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
