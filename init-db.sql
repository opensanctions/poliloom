-- Initialize database
-- This script runs automatically when the PostgreSQL container starts

-- Create the test database
SELECT 'CREATE DATABASE poliloom_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'poliloom_test') \gexec
