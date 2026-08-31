-- Initialize database with required extensions
-- This script runs automatically when the PostgreSQL container starts

-- Enable pgvector in the development and test databases.
CREATE EXTENSION IF NOT EXISTS vector;

SELECT 'CREATE DATABASE poliloom_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'poliloom_test') \gexec

\connect poliloom_test
CREATE EXTENSION IF NOT EXISTS vector;
