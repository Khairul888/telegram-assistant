-- Supabase Setup for Telegram Assistant
-- Phase 1: Job Queue and Basic Tables
-- Run this in your Supabase SQL Editor

-- Enable Row Level Security (RLS) for better security
-- You can adjust these policies based on your needs

-- 1. Create processing_jobs table for job queue
CREATE TABLE IF NOT EXISTS processing_jobs (
    id BIGSERIAL PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    result_data JSONB,
    file_size BIGINT,
    file_type TEXT,
    processing_time_seconds NUMERIC
);

-- 2. Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_user_id ON processing_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_created_at ON processing_jobs(created_at);

-- 3. Create users table for user management (Phase 2+)
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_user_id TEXT UNIQUE NOT NULL,
    first_name TEXT,
    username TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    total_files_processed INTEGER DEFAULT 0
);

-- 4. Create documents table for processed files (Phase 2+)
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    job_id BIGINT REFERENCES processing_jobs(id),
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size BIGINT,
    content_text TEXT,
    summary TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Enable pgvector extension for Phase 3 (vector search)
-- Note: This may need to be enabled in your Supabase project settings first
CREATE EXTENSION IF NOT EXISTS vector;

-- 6. Create document_embeddings table for vector search (Phase 3)
CREATE TABLE IF NOT EXISTS document_embeddings (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT REFERENCES documents(id),
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding vector(1536), -- OpenAI embedding size
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Create index for vector similarity search (Phase 3)
CREATE INDEX IF NOT EXISTS idx_document_embeddings_vector ON document_embeddings
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 8. Create conversation_history table for chat memory
CREATE TABLE IF NOT EXISTS conversation_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    message_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    message_type TEXT DEFAULT 'chat', -- 'chat', 'command', 'file_upload'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. Insert some sample statuses for reference
INSERT INTO processing_jobs (id, file_name, file_id, user_id, status, created_at, completed_at, result_data)
VALUES (0, 'sample_document.pdf', 'sample_file_id', 'sample_user', 'completed', NOW() - INTERVAL '1 day', NOW() - INTERVAL '23 hours', '{"sample": true}')
ON CONFLICT (id) DO NOTHING;

-- 10. Enable Row Level Security (optional, for multi-user setups)
-- ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- 11. Create RLS policies (uncomment for multi-user setup)
-- CREATE POLICY "Users can see their own jobs" ON processing_jobs
--   FOR ALL USING (user_id = current_setting('app.current_user_id'));

-- CREATE POLICY "Users can see their own documents" ON documents
--   FOR ALL USING (user_id IN (SELECT id FROM users WHERE telegram_user_id = current_setting('app.current_user_id')));

-- 12. Create a function to clean up old jobs (optional)
CREATE OR REPLACE FUNCTION cleanup_old_jobs()
RETURNS void AS $$
BEGIN
    -- Delete completed jobs older than 30 days
    DELETE FROM processing_jobs
    WHERE status = 'completed'
    AND completed_at < NOW() - INTERVAL '30 days';

    -- Delete failed jobs older than 7 days
    DELETE FROM processing_jobs
    WHERE status = 'failed'
    AND created_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- 13. Grant necessary permissions (adjust based on your security needs)
-- GRANT ALL ON processing_jobs TO authenticated;
-- GRANT ALL ON users TO authenticated;
-- GRANT ALL ON documents TO authenticated;

-- Setup complete!
-- Your Telegram Assistant database is ready for Phase 1 deployment.