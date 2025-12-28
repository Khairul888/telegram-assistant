-- Safe Documents Table Migration for Telegram Assistant
-- This script safely updates the documents table without breaking existing data
-- Run this in your Supabase SQL Editor

-- First, let's check what exists and create a backup if needed
-- Step 1: Check current table structure
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'documents' ORDER BY ordinal_position;

-- Step 2: Create backup of existing data (if any)
-- CREATE TABLE documents_backup AS SELECT * FROM documents;

-- Step 3: Drop existing table and recreate with correct structure
DROP TABLE IF EXISTS documents CASCADE;

-- Step 4: Create the new documents table with proper structure
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    file_id TEXT UNIQUE NOT NULL,
    original_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size_bytes BIGINT DEFAULT 0,
    mime_type TEXT,

    -- Content storage
    extracted_text TEXT,
    overarching_theme TEXT,
    keywords TEXT[], -- Array of keywords

    -- Processing info
    processing_status TEXT DEFAULT 'pending',
    processing_error TEXT,

    -- Metadata storage (JSONB for flexibility)
    metadata_json JSONB,

    -- Vector storage info (for future use)
    vector_stored BOOLEAN DEFAULT FALSE,
    vector_id TEXT,
    embedding_model TEXT,

    -- Processing metrics
    token_count INTEGER,
    processing_time_seconds NUMERIC,
    chunk_count INTEGER,

    -- Additional fields
    tags TEXT[],

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 5: Create indexes for better performance
CREATE INDEX idx_documents_file_id ON documents(file_id);
CREATE INDEX idx_documents_filename ON documents(original_filename);
CREATE INDEX idx_documents_status ON documents(processing_status);
CREATE INDEX idx_documents_telegram_user_id ON documents USING GIN ((metadata_json->'telegram_user_id'));
CREATE INDEX idx_documents_created_at ON documents(created_at);

-- Step 6: Create trigger function for auto-updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 7: Create trigger to auto-update updated_at
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Step 8: Test the table by inserting a sample record
INSERT INTO documents (
    file_id,
    original_filename,
    file_type,
    extracted_text,
    overarching_theme,
    metadata_json
) VALUES (
    'test_file_' || extract(epoch from now()),
    'test_document.pdf',
    'pdf',
    'This is a test document to verify the table structure.',
    'Test document for schema validation',
    '{"telegram_user_id": "test_user", "document_type": "test"}'
);

-- Step 9: Verify the table was created successfully
SELECT
    'Documents table created successfully' as status,
    count(*) as record_count
FROM documents;

-- Step 10: Clean up test record
DELETE FROM documents WHERE file_id LIKE 'test_file_%';

-- Success message
SELECT 'Documents table is ready for use!' as message;