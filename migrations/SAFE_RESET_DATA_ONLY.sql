-- =============================================================================
-- SAFE DATABASE DATA RESET FOR TELEGRAM TRAVEL ASSISTANT
-- =============================================================================
-- This script will:
-- ✅ PRESERVE all table structures, indexes, triggers, and constraints
-- ✅ CLEAR all data from tables using TRUNCATE
-- ✅ Handle foreign key dependencies automatically with CASCADE
-- ✅ Show verification of reset
--
-- ⚠️ WARNING: This will DELETE ALL DATA but keep table structures intact
--
-- Tables affected:
--    - trips
--    - user_sessions
--    - expenses
--    - travel_events
--    - documents
--    - trip_itinerary
--    - trip_places
--
-- Run this in Supabase SQL Editor
-- Created: 2025-12-31
-- =============================================================================

-- =============================================================================
-- SAFETY CHECKS - Verify tables exist before attempting reset
-- =============================================================================
DO $$
DECLARE
    missing_tables TEXT[];
BEGIN
    -- Check for required tables
    SELECT ARRAY_AGG(table_name)
    INTO missing_tables
    FROM (VALUES
        ('trips'),
        ('user_sessions'),
        ('expenses'),
        ('travel_events'),
        ('documents'),
        ('trip_itinerary'),
        ('trip_places')
    ) AS required(table_name)
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = required.table_name
    );

    IF missing_tables IS NOT NULL THEN
        RAISE EXCEPTION 'Missing tables: %. Please run migrations first.',
            array_to_string(missing_tables, ', ');
    END IF;

    RAISE NOTICE '✅ All required tables exist. Proceeding with data reset...';
END $$;

-- =============================================================================
-- BEFORE RESET - Show current data counts
-- =============================================================================
SELECT '📊 BEFORE RESET - Current Data Counts:' as status;

SELECT 'trips' as table_name, COUNT(*) as row_count FROM trips
UNION ALL
SELECT 'user_sessions', COUNT(*) FROM user_sessions
UNION ALL
SELECT 'expenses', COUNT(*) FROM expenses
UNION ALL
SELECT 'travel_events', COUNT(*) FROM travel_events
UNION ALL
SELECT 'documents', COUNT(*) FROM documents
UNION ALL
SELECT 'trip_itinerary', COUNT(*) FROM trip_itinerary
UNION ALL
SELECT 'trip_places', COUNT(*) FROM trip_places
ORDER BY table_name;

-- =============================================================================
-- DATA RESET - Clear all data while preserving structure
-- =============================================================================
-- IMPORTANT: TRUNCATE with CASCADE will automatically handle foreign key dependencies
-- Order matters: Start with parent tables (trips) or use CASCADE to handle dependencies

-- Reset child tables first (safer, though CASCADE handles it)
TRUNCATE TABLE trip_itinerary CASCADE;
TRUNCATE TABLE trip_places CASCADE;
TRUNCATE TABLE expenses CASCADE;
TRUNCATE TABLE travel_events CASCADE;
TRUNCATE TABLE documents CASCADE;
TRUNCATE TABLE user_sessions CASCADE;

-- Reset parent table (trips)
TRUNCATE TABLE trips RESTART IDENTITY CASCADE;

-- RESTART IDENTITY resets auto-increment sequences (id will start from 1 again)

SELECT '🗑️  All data cleared successfully!' as status;

-- =============================================================================
-- AFTER RESET - Verify all tables are empty
-- =============================================================================
SELECT '✅ AFTER RESET - Verification (all should be 0):' as status;

SELECT 'trips' as table_name, COUNT(*) as row_count FROM trips
UNION ALL
SELECT 'user_sessions', COUNT(*) FROM user_sessions
UNION ALL
SELECT 'expenses', COUNT(*) FROM expenses
UNION ALL
SELECT 'travel_events', COUNT(*) FROM travel_events
UNION ALL
SELECT 'documents', COUNT(*) FROM documents
UNION ALL
SELECT 'trip_itinerary', COUNT(*) FROM trip_itinerary
UNION ALL
SELECT 'trip_places', COUNT(*) FROM trip_places
ORDER BY table_name;

-- =============================================================================
-- VERIFY TABLE STRUCTURES - Ensure all structures are preserved
-- =============================================================================
SELECT '🔍 STRUCTURE VERIFICATION - Tables still exist with correct structure:' as status;

SELECT
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('trips', 'user_sessions', 'expenses', 'travel_events', 'documents', 'trip_itinerary', 'trip_places')
ORDER BY tablename;

-- Verify indexes are intact
SELECT '🔍 INDEX VERIFICATION - Sample indexes still exist:' as status;

SELECT
    indexname,
    tablename
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN ('trips', 'user_sessions', 'expenses', 'travel_events', 'documents', 'trip_itinerary', 'trip_places')
ORDER BY tablename, indexname
LIMIT 10;

-- Verify triggers are intact
SELECT '🔍 TRIGGER VERIFICATION - Update triggers still exist:' as status;

SELECT
    trigger_name,
    event_object_table as table_name,
    action_statement
FROM information_schema.triggers
WHERE event_object_schema = 'public'
AND event_object_table IN ('trips', 'user_sessions', 'expenses', 'travel_events', 'documents', 'trip_itinerary', 'trip_places')
ORDER BY event_object_table, trigger_name;

-- =============================================================================
-- RESET COMPLETE
-- =============================================================================
SELECT
    '✅ RESET COMPLETE!' as status,
    'All data cleared, table structures preserved' as message,
    NOW() as completed_at;
