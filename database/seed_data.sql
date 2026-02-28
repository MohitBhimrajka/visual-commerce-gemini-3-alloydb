-- ============================================================
-- Autonomous Supply Chain - Database Schema & Seed Data
-- Run these statements in AlloyDB Studio (one block at a time)
-- ============================================================

-- ============================================================
-- STEP 1: Enable Required Extensions
-- ============================================================
-- pgvector: Stores and queries vector embeddings
-- google_ml_integration: Enables ai.embedding() for in-database ML
-- alloydb_scann: Google's ScaNN index for ultra-fast vector search

CREATE EXTENSION IF NOT EXISTS google_ml_integration CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS alloydb_scann CASCADE;

-- ============================================================
-- STEP 2: Create Inventory Table
-- ============================================================
-- part_embedding: 768-dimensional vector from text-embedding-005
-- This column will power our ScaNN vector search

DROP TABLE IF EXISTS inventory;

CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    part_name TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    description TEXT,
    stock_level INT DEFAULT 0,
    part_embedding vector(768)
);

-- ============================================================
-- STEP 3: Insert Sample Inventory Data (20 items)
-- ============================================================
-- These represent a realistic warehouse inventory covering
-- packaging, hardware, fasteners, and industrial parts.

INSERT INTO inventory (part_name, supplier_name, description, stock_level) VALUES
('Cardboard Shipping Box Large', 'Packaging Solutions Inc', 'Heavy-duty corrugated cardboard shipping container, 24x18x12 inches', 250),
('Warehouse Storage Container', 'Industrial Supply Co', 'Stackable plastic storage bin with snap-lock lid, blue', 180),
('Product Shipping Boxes', 'Acme Packaging', 'Medium corrugated boxes for warehouse storage, 18x14x10 inches', 320),
('Industrial Widget X-9', 'Acme Corp', 'Heavy-duty industrial coupling for pneumatic systems', 50),
('Precision Bolt M4', 'Global Fasteners Inc', 'Stainless steel M4 allen bolt, 20mm length, grade A2-70', 200),
('Hexagonal Nut M6', 'Metro Supply Co', 'Galvanized steel hex nut M6, DIN 934 standard', 150),
('Phillips Head Screw 3x20', 'Acme Corp', 'Zinc-plated Phillips head wood screw, 3mm x 20mm', 500),
('Wooden Dowel 10mm', 'Craft Materials Ltd', 'Hardwood birch dowel rod, 10mm diameter x 300mm length', 80),
('Rubber Gasket Small', 'SealTech Industries', 'Buna-N rubber gasket, 25mm OD x 15mm ID, oil resistant', 120),
('Spring Tension 5kg', 'Mechanical Parts Co', 'Stainless steel compression spring, 5kg load capacity', 60),
('Bearing 6204', 'Bearings Direct', 'Deep groove ball bearing 6204-2RS, 20x47x14mm sealed', 45),
('Warehouse Shelf Boxes', 'Storage Systems Ltd', 'Standardized warehouse inventory boxes, corrugated, bulk pack', 400),
('Inventory Container Units', 'Supply Chain Pros', 'Modular stackable storage units for warehouse racking', 95),
('Aluminum Extrusion Bar', 'MetalWorks International', 'T-slot aluminum extrusion 20x20mm profile, 1 meter length', 110),
('Cable Tie Pack 200mm', 'ElectroParts Depot', 'Nylon cable ties, 200mm x 4.8mm, UV resistant black, pack of 100', 600),
('Hydraulic Hose 1/2 inch', 'FluidPower Systems', 'High-pressure hydraulic hose, 1/2 inch ID, 3000 PSI rated', 35),
('Safety Goggles Clear', 'WorkSafe Equipment Co', 'ANSI Z87.1 rated clear safety goggles, anti-fog coating', 275),
('Packing Tape Industrial', 'Packaging Solutions Inc', 'Heavy-duty polypropylene packing tape, 48mm x 100m, clear', 450),
('Stainless Steel Sheet 1mm', 'MetalWorks International', '304 stainless steel sheet, 1mm thickness, 300x300mm', 70),
('Silicone Sealant Tube', 'SealTech Industries', 'Industrial-grade RTV silicone sealant, 300ml cartridge, grey', 190);

-- ============================================================
-- STEP 4: Grant Embedding Function Permission
-- ============================================================

GRANT EXECUTE ON FUNCTION embedding TO postgres;

-- ============================================================
-- STEP 5: Generate Vector Embeddings
-- ============================================================
-- Uses AlloyDB's built-in ai.embedding() to call Vertex AI
-- text-embedding-005 model directly from SQL.
-- This generates 768-dimensional vectors for semantic search.

UPDATE inventory
SET part_embedding = ai.embedding(
    'text-embedding-005',
    part_name || '. ' || description
)::vector
WHERE part_embedding IS NULL;

-- ============================================================
-- STEP 6: Create ScaNN Index
-- ============================================================
-- ScaNN (Scalable Nearest Neighbors) uses vector quantization
-- to compress vectors, making the index fit in CPU L2 cache.
-- Up to 10x faster than standard HNSW for filtered queries.

SET scann.allow_blocked_operations = true;

CREATE INDEX IF NOT EXISTS idx_inventory_scann
ON inventory USING scann (part_embedding cosine)
WITH (num_leaves=5, quantizer='sq8');

-- ============================================================
-- VERIFY: Check that everything worked
-- ============================================================
-- You should see 20 rows, all with non-null embeddings.

SELECT part_name, supplier_name, stock_level,
       (part_embedding IS NOT NULL) as has_embedding
FROM inventory
ORDER BY id;
