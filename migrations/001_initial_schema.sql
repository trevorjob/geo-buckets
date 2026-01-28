-- ============================================
-- Geo-Bucket Location Normalization System
-- PostgreSQL + PostGIS Schema
-- ============================================

-- Enable PostGIS extension (required for spatial types)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable pg_trgm for fuzzy text matching (optional enhancement)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================
-- GEO_BUCKETS TABLE
-- ============================================
-- Represents a geographic area (~500m grid cell)
-- Properties are grouped into buckets for efficient search

CREATE TABLE IF NOT EXISTS geo_buckets (
    id              SERIAL PRIMARY KEY,
    bucket_key      VARCHAR(50) UNIQUE NOT NULL,
    canonical_name  VARCHAR(255) NOT NULL,
    
    -- PostGIS POINT for bucket centroid (SRID 4326 = WGS84/GPS)
    centroid        GEOMETRY(POINT, 4326) NOT NULL,
    
    -- Also store as floats for simpler queries when spatial ops not needed
    centroid_lat    DOUBLE PRECISION NOT NULL,
    centroid_lng    DOUBLE PRECISION NOT NULL,
    
    -- Location name variations (for text-based search)
    aliases         JSONB DEFAULT '[]',
    
    -- Denormalized count for stats endpoint
    property_count  INTEGER DEFAULT 0,
    
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- PROPERTIES TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS properties (
    id              SERIAL PRIMARY KEY,
    geo_bucket_id   INTEGER NOT NULL REFERENCES geo_buckets(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    location_name   VARCHAR(255) NOT NULL,
    
    -- PostGIS POINT for property location
    coordinates     GEOMETRY(POINT, 4326) NOT NULL,
    
    -- Also store as floats for simpler access
    lat             DOUBLE PRECISION NOT NULL,
    lng             DOUBLE PRECISION NOT NULL,
    
    price           DECIMAL(15, 2) NOT NULL,
    bedrooms        INTEGER NOT NULL CHECK (bedrooms >= 0),
    bathrooms       INTEGER NOT NULL CHECK (bathrooms >= 0),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================

-- GIST spatial indexes (PostGIS feature for proximity queries)
CREATE INDEX IF NOT EXISTS idx_bucket_centroid_gist 
    ON geo_buckets USING GIST(centroid);

CREATE INDEX IF NOT EXISTS idx_property_coords_gist 
    ON properties USING GIST(coordinates);

-- B-tree indexes for standard lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_bucket_key 
    ON geo_buckets(bucket_key);

CREATE INDEX IF NOT EXISTS idx_bucket_canonical 
    ON geo_buckets(LOWER(canonical_name));

CREATE INDEX IF NOT EXISTS idx_property_bucket 
    ON properties(geo_bucket_id);

-- GIN index for JSONB alias search
CREATE INDEX IF NOT EXISTS idx_bucket_aliases_gin 
    ON geo_buckets USING GIN(aliases);

-- Optional: Trigram index for fuzzy name matching
CREATE INDEX IF NOT EXISTS idx_bucket_canonical_trgm 
    ON geo_buckets USING GIN(canonical_name gin_trgm_ops);

-- ============================================
-- HELPER FUNCTION: Update timestamp trigger
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_geo_buckets_updated_at
    BEFORE UPDATE ON geo_buckets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
