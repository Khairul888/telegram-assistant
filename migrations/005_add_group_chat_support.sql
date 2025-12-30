-- Migration 005: Add group chat support with backward compatibility
-- Run this in Supabase SQL Editor AFTER running 001-004
-- Created: 2025-12-30
-- This migration enables collaborative trip management in Telegram group chats

-- Step 1: Add chat_id and chat_type columns to trips table
ALTER TABLE trips
    ADD COLUMN IF NOT EXISTS chat_id TEXT;

ALTER TABLE trips
    ADD COLUMN IF NOT EXISTS chat_type TEXT DEFAULT 'private';

-- Add check constraint for chat_type
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'trips_chat_type_check'
    ) THEN
        ALTER TABLE trips
            ADD CONSTRAINT trips_chat_type_check
            CHECK (chat_type IN ('private', 'group', 'supergroup'));
    END IF;
END $$;

-- Step 2: Create indexes for chat-based queries
CREATE INDEX IF NOT EXISTS idx_trips_chat_id ON trips(chat_id);
CREATE INDEX IF NOT EXISTS idx_trips_chat_status ON trips(chat_id, status);

-- Step 3: Modify user_sessions to support per-chat-per-user state
-- Drop unique constraint on user_id (to allow composite key)
ALTER TABLE user_sessions
    DROP CONSTRAINT IF EXISTS user_sessions_user_id_key;

-- Add chat_id column to sessions
ALTER TABLE user_sessions
    ADD COLUMN IF NOT EXISTS chat_id TEXT;

-- Step 4: Backfill existing data (all current trips are DM trips)
-- Set chat_id = user_id for all existing trips (they're all private DMs)
UPDATE trips
SET chat_id = user_id,
    chat_type = 'private'
WHERE chat_id IS NULL;

-- Backfill user_sessions with chat_id = user_id (DM sessions)
UPDATE user_sessions
SET chat_id = user_id
WHERE chat_id IS NULL;

-- Step 5: Make chat_id NOT NULL after backfill
ALTER TABLE trips
    ALTER COLUMN chat_id SET NOT NULL;

ALTER TABLE user_sessions
    ALTER COLUMN chat_id SET NOT NULL;

-- Step 6: Create composite unique constraint on user_sessions
-- This allows same user to have different sessions in different chats
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'user_sessions_user_chat_unique'
    ) THEN
        ALTER TABLE user_sessions
            ADD CONSTRAINT user_sessions_user_chat_unique
            UNIQUE (user_id, chat_id);
    END IF;
END $$;

-- Create index for chat-based session queries
CREATE INDEX IF NOT EXISTS idx_user_sessions_chat_id ON user_sessions(chat_id);

-- Step 7: Add comments for documentation
COMMENT ON COLUMN trips.chat_id IS 'Telegram chat ID - for group chats this is the group ID; for DMs this is the user ID';
COMMENT ON COLUMN trips.chat_type IS 'Type of chat where trip was created: private (DM), group, or supergroup';
COMMENT ON COLUMN user_sessions.chat_id IS 'Chat ID for session scoping - enables per-chat state for users in multiple groups';

-- Validation queries (run these to verify migration success)
-- 1. Verify all trips have chat_id
-- SELECT COUNT(*) FROM trips WHERE chat_id IS NULL;  -- Should return 0

-- 2. Verify backfill correctness (all existing trips should be private DMs)
-- SELECT COUNT(*) FROM trips WHERE chat_type = 'private' AND chat_id = user_id;  -- Should equal total pre-migration trip count

-- 3. Verify session uniqueness (no duplicate user_id+chat_id combinations)
-- SELECT user_id, chat_id, COUNT(*) FROM user_sessions GROUP BY user_id, chat_id HAVING COUNT(*) > 1;  -- Should return empty

-- 4. Verify no orphaned sessions
-- SELECT s.* FROM user_sessions s LEFT JOIN trips t ON s.current_trip_id = t.id WHERE s.current_trip_id IS NOT NULL AND t.id IS NULL;  -- Should return empty
