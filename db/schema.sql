-- WorkLife Database Schema
-- Run this in your Supabase SQL editor

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Conversations table — one per WhatsApp thread
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    summary TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Messages table — every message in/out
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    agent_name TEXT,  -- which agent handled this (null for user messages)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at DESC);

-- Agent memory — long-term knowledge store with vector search
CREATE TABLE agent_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,  -- 'finance', 'logistics', 'research', 'travel', 'chief_of_staff'
    category TEXT NOT NULL,    -- 'fact', 'preference', 'research', 'alert_config'
    content TEXT NOT NULL,
    embedding VECTOR(1536),    -- for semantic search
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,    -- optional TTL for time-sensitive info
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_memory_agent ON agent_memory(agent_name, category);
CREATE INDEX idx_memory_embedding ON agent_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Scheduled tasks — recurring agent jobs
CREATE TABLE scheduled_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    task_name TEXT NOT NULL,
    cron_expression TEXT NOT NULL,  -- e.g. '0 9 * * *' for 9am daily
    task_config JSONB NOT NULL,     -- agent-specific config
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Function to match agent memory by semantic similarity
CREATE OR REPLACE FUNCTION match_memory(
    query_embedding VECTOR(1536),
    match_agent TEXT,
    match_count INT DEFAULT 5,
    match_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id UUID,
    agent_name TEXT,
    category TEXT,
    content TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        am.id,
        am.agent_name,
        am.category,
        am.content,
        1 - (am.embedding <=> query_embedding) AS similarity
    FROM agent_memory am
    WHERE am.agent_name = match_agent
        AND 1 - (am.embedding <=> query_embedding) > match_threshold
        AND (am.expires_at IS NULL OR am.expires_at > NOW())
    ORDER BY am.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
