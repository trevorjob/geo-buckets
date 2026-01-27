-- Geo-Bucket Location Normalization System
-- Supabase/PostgreSQL Migration
-- 
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)

-- =====================================================
-- GEO_BUCKETS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS geo_buckets (
    id              SERIAL PRIMARY KEY,
    bucket_key      VARCHAR(50) UNIQUE NOT NULL,
    canonical_name  VARCHAR(255) NOT NULL,
    centroid_lat    DOUBLE PRECISION NOT NULL,
    centroid_lng    DOUBLE PRECISION NOT NULL,
    aliases         JSONB DEFAULT '[]',
    property_count  INTEGER DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_bucket_key ON geo_buckets(bucket_key);
CREATE INDEX IF NOT EXISTS idx_bucket_canonical ON geo_buckets(LOWER(canonical_name));
CREATE INDEX IF NOT EXISTS idx_bucket_aliases ON geo_buckets USING GIN (aliases);


-- =====================================================
-- PROPERTIES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS properties (
    id              SERIAL PRIMARY KEY,
    geo_bucket_id   INTEGER NOT NULL REFERENCES geo_buckets(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    location_name   VARCHAR(255) NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    lng             DOUBLE PRECISION NOT NULL,
    price           DECIMAL(15, 2) NOT NULL,
    bedrooms        INTEGER NOT NULL,
    bathrooms       INTEGER NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for bucket lookups
CREATE INDEX IF NOT EXISTS idx_property_bucket ON properties(geo_bucket_id);


-- =====================================================
-- AUTO-UPDATE TRIGGER FOR updated_at
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_geo_buckets_updated_at ON geo_buckets;
CREATE TRIGGER update_geo_buckets_updated_at
    BEFORE UPDATE ON geo_buckets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- =====================================================
-- VERIFY TABLES CREATED
-- =====================================================
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name IN ('geo_buckets', 'properties')
ORDER BY table_name, ordinal_position;
