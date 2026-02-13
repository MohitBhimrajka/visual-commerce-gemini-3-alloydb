-- Seed script for AlloyDB inventory with ScaNN vector search
-- Run via: python run_seed.py
-- Prerequisites: Auth Proxy connected to AlloyDB, DB_PASS set

-- 1. Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS alloydb_scann CASCADE;

-- 2. Create inventory table
CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    part_name TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    description TEXT,
    stock_level INT DEFAULT 0,
    part_embedding vector(768)
);

-- 3. Allow ScaNN index on small tables (for codelab demo)
-- Without this, AlloyDB may reject index creation on < ~1000 rows
SET scann.allow_blocked_operations = true;
