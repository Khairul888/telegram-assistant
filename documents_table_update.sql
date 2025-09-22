-- Updated Documents Table Schema for Telegram Assistant
-- This updates the existing documents table to support the new bot functionality
-- Run this in your Supabase SQL Editor

-- Drop existing documents table if it exists (this will lose existing data!)
-- DROP TABLE IF EXISTS documents CASCADE;

-- Create enhanced documents table
CREATE TABLE IF NOT EXISTS documents (
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

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_documents_file_id ON documents(file_id);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(original_filename);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_documents_telegram_user_id ON documents USING GIN ((metadata_json->'telegram_user_id'));
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);

-- Update function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions for API access
-- GRANT ALL ON documents TO authenticated;
-- GRANT ALL ON documents TO anon;

-- Sample insert to test the table structure
-- INSERT INTO documents (
--     file_id,
--     original_filename,
--     file_type,
--     extracted_text,
--     overarching_theme,
--     metadata_json
-- ) VALUES (
--     'test_file_123',
--     'test_document.pdf',
--     'pdf',
--     'This is sample extracted text from a PDF document.',
--     'Sample document for testing',
--     '{"telegram_user_id": "123456789", "document_type": "itinerary"}'
-- );

-- Query to check if the table was created successfully
-- SELECT * FROM documents;