-- Migration 003: Add user_sessions table for conversation state management
-- Run this in Supabase SQL Editor AFTER running 001 and 002
-- Created: 2025-12-20

-- Create user_sessions table for tracking current trip and conversation state
CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    current_trip_id BIGINT REFERENCES trips(id) ON DELETE SET NULL,
    conversation_state TEXT, -- 'awaiting_location', 'awaiting_participants', 'awaiting_split_type', etc.
    conversation_context JSONB, -- Store temporary data during multi-step conversations
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_current_trip ON user_sessions(current_trip_id);

-- Create trigger to auto-update timestamp
CREATE TRIGGER update_user_sessions_updated_at
    BEFORE UPDATE ON user_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE user_sessions IS 'Stores user session data including current trip and conversation state';
COMMENT ON COLUMN user_sessions.current_trip_id IS 'Reference to the active trip for this user (auto-use latest)';
COMMENT ON COLUMN user_sessions.conversation_state IS 'Current state in multi-step conversation flow';
COMMENT ON COLUMN user_sessions.conversation_context IS 'JSONB storage for temporary conversation data (e.g., trip_name during creation)';
