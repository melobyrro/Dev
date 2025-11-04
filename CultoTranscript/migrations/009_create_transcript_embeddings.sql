-- Migration 009: Create transcript_embeddings table for RAG chatbot
-- This table stores vector embeddings of transcript segments for semantic search

CREATE TABLE IF NOT EXISTS transcript_embeddings (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    segment_text TEXT NOT NULL,
    segment_start INTEGER,  -- Start time in seconds
    segment_end INTEGER,    -- End time in seconds
    embedding vector(768),  -- Embedding vector (dimension 768 for sentence-transformers)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_transcript_embeddings_video_id ON transcript_embeddings(video_id);
CREATE INDEX IF NOT EXISTS idx_transcript_embeddings_embedding ON transcript_embeddings USING ivfflat (embedding vector_cosine_ops);

-- Comments for documentation
COMMENT ON TABLE transcript_embeddings IS 'Stores vector embeddings of transcript segments for RAG chatbot semantic search';
COMMENT ON COLUMN transcript_embeddings.embedding IS 'Vector embedding of the segment text (768 dimensions)';
COMMENT ON COLUMN transcript_embeddings.segment_text IS 'Text content of the transcript segment';

-- Trigger to update updated_at timestamp
CREATE TRIGGER update_transcript_embeddings_updated_at
    BEFORE UPDATE ON transcript_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DO $$
BEGIN
    RAISE NOTICE 'Migration 009 completed: Created transcript_embeddings table with vector support';
END $$;
