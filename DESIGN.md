# Geo-Bucket Location Normalization System

> **Design Document for ExpertListing Property Search**

---

## Table of Contents
1. [Problem Overview](#1-problem-overview)
2. [Geo-Bucket Strategy](#2-geo-bucket-strategy)
3. [Database Schema](#3-database-schema)
4. [Location Matching Logic](#4-location-matching-logic)
5. [Request Flow](#5-request-flow)
6. [Scaling & Performance Considerations](#6-scaling--performance-considerations)
7. [Tradeoffs & Alternatives](#7-tradeoffs--alternatives)

---

## 1. Problem Overview

### The Inconsistency Problem

On the ExpertListing platform, users searching for properties in the same physical area often receive inconsistent results. This occurs due to:

| Issue | Example |
|-------|---------|
| **Naming variations** | "Sangotedo" vs "Sangotedo, Ajah" vs "sangotedo lagos" |
| **Case sensitivity** | "SANGOTEDO" vs "sangotedo" |
| **Coordinate drift** | Properties at `(6.4698, 3.6285)` vs `(6.4720, 3.6301)` |
| **Data entry inconsistencies** | Manual input without standardization |

**Result:** A search for "Sangotedo" might return 0 properties in one case and 47 in another, despite referring to the same physical neighborhood.

### Goal

Implement a **location normalization system using geo-buckets** that:

- Groups nearby properties into logical spatial buckets
- Ensures consistent search results regardless of naming/capitalization variations
- Enables efficient lookups without full-table scans
- Scales to 500,000+ properties

### Assumptions

1. **Geographic scope**: Nigeria-focused (Lagos specifically), but the system should work globally
2. **Bucket precision**: Neighborhood-level granularity (~500m–1km radius)
3. **Primary lookup**: Location name search is the primary use case (not lat/lng coordinates)
4. **Data quality**: Properties always have valid lat/lng coordinates
5. **No real-time geocoding**: Location names are stored as-is; geocoding is done at property creation

---

## 2. Geo-Bucket Strategy

### What is a Geo-Bucket?

A **geo-bucket** is a discrete geographic cell that groups properties within a defined spatial boundary. Each bucket:

- Has a **canonical location name** (e.g., "sangotedo")
- Contains a **representative centroid** (lat/lng)
- Holds **aliases** for variant location names
- References all properties within its boundary

### Bucket Computation: Grid-Based Rounding

We use a **fixed-grid approach** where lat/lng coordinates are rounded to create bucket identifiers.

```
Bucket ID Formula:
  bucket_lat = ROUND(lat / GRID_SIZE) * GRID_SIZE
  bucket_lng = ROUND(lng / GRID_SIZE) * GRID_SIZE
  bucket_id  = f"{bucket_lat}_{bucket_lng}"
```

**Grid Size Selection:**

| Grid Size | Distance (~at equator) | Use Case |
|-----------|------------------------|----------|
| 0.001°    | ~111 meters            | Too granular, too many buckets |
| **0.005°** | **~500 meters** | ✅ **Recommended** - neighborhood level |
| 0.01°     | ~1.1 km                | Larger areas, fewer buckets |
| 0.1°      | ~11 km                 | City-level, too coarse |

**Why 0.005° (~500m)?**

1. **Neighborhood appropriate**: Captures a typical Lagos neighborhood block
2. **Handles coordinate drift**: Properties 200-300m apart land in the same bucket
3. **Manageable bucket count**: ~4 buckets per km² vs. 100 for 0.001°
4. **Aligns with user expectations**: "Sangotedo" as a search term implies ~500m radius

### Bucket Assignment Example

```python
# Property coordinates
lat, lng = 6.4698, 3.6285
GRID_SIZE = 0.005

# Compute bucket center
bucket_lat = round(lat / GRID_SIZE) * GRID_SIZE  # 6.470
bucket_lng = round(lng / GRID_SIZE) * GRID_SIZE  # 3.630

# Bucket ID
bucket_id = f"{bucket_lat}_{bucket_lng}"  # "6.470_3.630"
```

### Multi-Bucket Edge Cases

Properties near bucket boundaries may conceptually belong to adjacent buckets. We handle this by:

1. **Soft boundaries**: Searching in adjacent buckets is possible for edge cases
2. **Alias linking**: If "Sangotedo" spans two buckets, both are linked via aliases

---

## 3. Database Schema

### Tables Overview

```
┌─────────────────────┐         ┌─────────────────────┐
│    geo_buckets      │         │    properties       │
├─────────────────────┤         ├─────────────────────┤
│ id (PK)             │◄────────│ geo_bucket_id (FK)  │
│ bucket_key          │         │ id (PK)             │
│ canonical_name      │         │ title               │
│ centroid (POINT)    │         │ location_name       │
│ aliases[]           │         │ coordinates (POINT) │
│ created_at          │         │ price               │
│ updated_at          │         │ bedrooms            │
└─────────────────────┘         │ bathrooms           │
                                │ created_at          │
                                └─────────────────────┘
```

### Detailed Schema (PostgreSQL + PostGIS)

```sql
-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy text search

-- Geo-Buckets Table
CREATE TABLE geo_buckets (
    id              SERIAL PRIMARY KEY,
    bucket_key      VARCHAR(50) UNIQUE NOT NULL,  -- e.g., "6.470_3.630"
    canonical_name  VARCHAR(255) NOT NULL,        -- e.g., "sangotedo"
    centroid        GEOMETRY(POINT, 4326) NOT NULL,
    aliases         TEXT[] DEFAULT '{}',          -- e.g., {"sangotedo, ajah", "sangotedo lagos"}
    property_count  INTEGER DEFAULT 0,            -- Denormalized for stats
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Properties Table
CREATE TABLE properties (
    id              SERIAL PRIMARY KEY,
    geo_bucket_id   INTEGER NOT NULL REFERENCES geo_buckets(id),
    title           VARCHAR(255) NOT NULL,
    location_name   VARCHAR(255) NOT NULL,        -- Original user input
    coordinates     GEOMETRY(POINT, 4326) NOT NULL,
    price           DECIMAL(15, 2) NOT NULL,
    bedrooms        INTEGER NOT NULL,
    bathrooms       INTEGER NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============
-- INDEXES
-- =============

-- Bucket lookup by key (O(1) bucket assignment)
CREATE UNIQUE INDEX idx_bucket_key ON geo_buckets(bucket_key);

-- Canonical name search (case-insensitive)
CREATE INDEX idx_bucket_canonical ON geo_buckets(LOWER(canonical_name));

-- Trigram index for fuzzy/typo-tolerant search on aliases
CREATE INDEX idx_bucket_aliases_gin ON geo_buckets USING GIN (aliases gin_trgm_ops);

-- Spatial index for proximity queries
CREATE INDEX idx_bucket_centroid ON geo_buckets USING GIST(centroid);

-- Properties by bucket (fast join)
CREATE INDEX idx_property_bucket ON properties(geo_bucket_id);

-- Spatial index for coordinate-based property queries
CREATE INDEX idx_property_coords ON properties USING GIST(coordinates);
```

### Property-to-Bucket Assignment Logic

When a property is created:

```python
def assign_to_bucket(lat: float, lng: float, location_name: str) -> int:
    """Assign property to a geo-bucket, creating one if necessary."""
    
    GRID_SIZE = 0.005
    bucket_lat = round(lat / GRID_SIZE) * GRID_SIZE
    bucket_lng = round(lng / GRID_SIZE) * GRID_SIZE
    bucket_key = f"{bucket_lat:.3f}_{bucket_lng:.3f}"
    
    # Normalize location name
    normalized_name = normalize_location(location_name)
    
    # Try to find existing bucket
    bucket = db.query("""
        SELECT id, aliases FROM geo_buckets 
        WHERE bucket_key = %s
    """, bucket_key)
    
    if bucket:
        # Add alias if new
        if normalized_name not in bucket.aliases:
            update_aliases(bucket.id, normalized_name)
        return bucket.id
    else:
        # Create new bucket
        return create_bucket(
            bucket_key=bucket_key,
            canonical_name=normalized_name,
            centroid=Point(lng, lat),
            aliases=[normalized_name]
        )
```

---

## 4. Location Matching Logic

### Location Name Normalization

All location names undergo a standardized normalization pipeline:

```python
import re

STOP_WORDS = {'lagos', 'nigeria', 'state', 'lga', 'area', 'estate'}

def normalize_location(name: str) -> str:
    """
    Normalize location name for consistent matching.
    
    Examples:
        "Sangotedo, Ajah"    → "sangotedo ajah"
        "SANGOTEDO LAGOS"    → "sangotedo"
        "  Sangotedo  "      → "sangotedo"
    """
    # 1. Lowercase
    name = name.lower().strip()
    
    # 2. Remove special characters (keep spaces)
    name = re.sub(r'[^\w\s]', ' ', name)
    
    # 3. Split into tokens
    tokens = name.split()
    
    # 4. Remove stop words
    tokens = [t for t in tokens if t not in STOP_WORDS]
    
    # 5. Sort and deduplicate for canonical form
    tokens = sorted(set(tokens))
    
    return ' '.join(tokens)
```

### Matching Strategy: Multi-Step Lookup

When a user searches for a location, we use a **cascade matching strategy**:

```
Step 1: Exact canonical match     → Fast, O(1) via index
Step 2: Alias array containment   → Uses GIN index
Step 3: Fuzzy trigram similarity  → For typos, uses pg_trgm
Step 4: Coordinate proximity      → Fallback if name fails
```

```sql
-- Example: Search for "sangotedo"
WITH normalized_input AS (
    SELECT 'sangotedo' AS search_term  -- Pre-normalized in Python
),
matched_buckets AS (
    -- Step 1: Exact canonical match
    SELECT id FROM geo_buckets 
    WHERE LOWER(canonical_name) = (SELECT search_term FROM normalized_input)
    
    UNION
    
    -- Step 2: Alias containment
    SELECT id FROM geo_buckets
    WHERE (SELECT search_term FROM normalized_input) = ANY(aliases)
    
    UNION
    
    -- Step 3: Fuzzy match (similarity > 0.3)
    SELECT id FROM geo_buckets
    WHERE canonical_name % (SELECT search_term FROM normalized_input)
       OR EXISTS (
           SELECT 1 FROM unnest(aliases) AS alias 
           WHERE alias % (SELECT search_term FROM normalized_input)
       )
)
SELECT DISTINCT id FROM matched_buckets;
```

### Coordinate Proximity Matching

For cases where name matching fails or for validation:

```sql
-- Find bucket within 500m of given coordinates
SELECT id FROM geo_buckets
WHERE ST_DWithin(
    centroid::geography,
    ST_SetSRID(ST_MakePoint(3.6285, 6.4698), 4326)::geography,
    500  -- meters
)
ORDER BY ST_Distance(centroid::geography, 
                     ST_SetSRID(ST_MakePoint(3.6285, 6.4698), 4326)::geography)
LIMIT 1;
```

---

## 5. Request Flow

### End-to-End Search Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           USER SEARCH FLOW                                   │
└──────────────────────────────────────────────────────────────────────────────┘

    User Input                API Layer              Database Layer
    ──────────                ─────────              ──────────────
         │
         │  GET /api/properties/search?location=Sangotedo
         ▼
    ┌─────────┐
    │ Client  │
    └────┬────┘
         │
         ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        FASTAPI ENDPOINT                             │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │  1. NORMALIZE INPUT                                                 │
    │     ┌──────────────────────────────────────────────────────────┐   │
    │     │ "Sangotedo" → lowercase → remove punctuation → "sangotedo"│   │
    │     └──────────────────────────────────────────────────────────┘   │
    │                              │                                      │
    │  2. BUCKET LOOKUP            ▼                                      │
    │     ┌───────────────────────────────────────────────────┐          │
    │     │ Query geo_buckets WHERE:                          │          │
    │     │   - canonical_name = 'sangotedo' OR               │          │
    │     │   - 'sangotedo' = ANY(aliases) OR                 │          │
    │     │   - canonical_name % 'sangotedo' (fuzzy)          │          │
    │     └───────────────────────────────────────────────────┘          │
    │                              │                                      │
    │                              ▼                                      │
    │     ┌───────────────────────────────────────────────────┐          │
    │     │        RESULT: bucket_id = 42                     │          │
    │     └───────────────────────────────────────────────────┘          │
    │                              │                                      │
    │  3. PROPERTY FETCH           ▼                                      │
    │     ┌───────────────────────────────────────────────────┐          │
    │     │ SELECT * FROM properties                          │          │
    │     │ WHERE geo_bucket_id = 42                          │          │
    │     │ ORDER BY created_at DESC                          │          │
    │     └───────────────────────────────────────────────────┘          │
    │                              │                                      │
    │  4. RETURN RESPONSE          ▼                                      │
    │     ┌───────────────────────────────────────────────────┐          │
    │     │ { "properties": [...], "count": 47, "bucket": ...}│          │
    │     └───────────────────────────────────────────────────┘          │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
         │
         ▼
    ┌─────────┐
    │ Client  │  ← Receives 47 properties for "Sangotedo"
    └─────────┘
```

### Property Creation Flow

```
    ┌─────────────────────────────────────────────────────────────────────┐
    │                    PROPERTY CREATION FLOW                           │
    └─────────────────────────────────────────────────────────────────────┘

    POST /api/properties
    {
      "title": "3 Bed Apartment",
      "location_name": "Sangotedo, Ajah",
      "lat": 6.4720,
      "lng": 3.6301,
      "price": 2500000,
      "bedrooms": 3,
      "bathrooms": 2
    }
                            │
                            ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │  1. COMPUTE BUCKET KEY                                          │
    │     bucket_lat = round(6.4720 / 0.005) * 0.005 = 6.470          │
    │     bucket_lng = round(3.6301 / 0.005) * 0.005 = 3.630          │
    │     bucket_key = "6.470_3.630"                                   │
    └─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │  2. LOOKUP/CREATE BUCKET                                        │
    │     IF bucket exists:                                           │
    │        → Add "sangotedo ajah" to aliases if new                 │
    │        → Return bucket.id                                       │
    │     ELSE:                                                       │
    │        → CREATE geo_bucket(                                     │
    │            bucket_key="6.470_3.630",                            │
    │            canonical_name="sangotedo ajah",                     │
    │            centroid=POINT(3.630, 6.470)                         │
    │          )                                                      │
    │        → Return new bucket.id                                   │
    └─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │  3. INSERT PROPERTY                                             │
    │     INSERT INTO properties (                                    │
    │       geo_bucket_id, title, location_name, coordinates, ...    │
    │     )                                                           │
    └─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │  4. UPDATE BUCKET STATS                                         │
    │     UPDATE geo_buckets SET property_count = property_count + 1  │
    │     WHERE id = bucket.id                                        │
    └─────────────────────────────────────────────────────────────────┘
```

---

## 6. Scaling & Performance Considerations

### How This Design Avoids Full-Table Scans

| Operation | Without Geo-Buckets | With Geo-Buckets |
|-----------|---------------------|------------------|
| Search by location | `O(n)` - scan all properties, compare names | `O(1)` - index lookup on bucket, then fetch |
| Property creation | `O(n)` - check all for duplicates | `O(1)` - hash-based bucket assignment |
| Proximity search | `O(n)` - compare all coordinates | `O(log n)` - spatial index on buckets |

### Index Strategy Summary

```sql
-- Query: Search for "sangotedo"
-- Path: idx_bucket_canonical → geo_buckets.id → idx_property_bucket → properties
-- Cost: O(1) + O(k) where k = properties in bucket

EXPLAIN ANALYZE
SELECT p.* FROM properties p
JOIN geo_buckets g ON p.geo_bucket_id = g.id
WHERE LOWER(g.canonical_name) = 'sangotedo';

-- Expected: Index Scan on idx_bucket_canonical + Index Scan on idx_property_bucket
```

### Scaling Projections

| Properties | Buckets (est.) | Avg Properties/Bucket | Search Latency |
|------------|----------------|----------------------|----------------|
| 10,000     | ~500           | 20                   | < 5ms          |
| 100,000    | ~2,000         | 50                   | < 10ms         |
| 500,000    | ~5,000         | 100                  | < 20ms         |

### Caching Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CACHING LAYERS                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 1: Application Cache (Redis)                                 │
│  ├── Bucket lookup cache: location_name → bucket_id                 │
│  │   TTL: 1 hour                                                    │
│  │   Key: "bucket:lookup:{normalized_name}"                         │
│  │                                                                  │
│  └── Search results cache: query → property_ids                     │
│      TTL: 5 minutes (invalidate on property creation)               │
│      Key: "search:{hash(query_params)}"                             │
│                                                                     │
│  Layer 2: Database Query Cache (PostgreSQL)                         │
│  └── Prepared statements for bucket lookup and property fetch       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Future Improvements

1. **Read replicas**: Separate read/write traffic for search-heavy workloads
2. **Materialized views**: Pre-computed bucket statistics
3. **Async alias updates**: Queue-based alias management for high-throughput
4. **Bucket merging**: Periodic job to merge low-property buckets
5. **ML-based name matching**: Use embeddings for semantic location matching

---

## 7. Tradeoffs & Alternatives

### Why Grid-Based Rounding?

1. **Simplicity**: No external dependencies (vs H3)
2. **Determinism**: Same coordinates always yield the same bucket
3. **Transparency**: Easy to debug and understand
4. **Efficiency**: O(1) bucket computation
5. **PostgreSQL-native**: Works with PostGIS out of the box

### Known Limitations & Mitigations

| Limitation | Mitigation |
|------------|------------|
| **Bucket edge effects**: Properties near bucket boundaries may be "far" from bucket center | Use 500m grid which is smaller than typical search radius; optionally query adjacent buckets |
| **Name ambiguity**: "Victoria Island" could match multiple cities globally | Scope by context (Nigeria-only), add parent location to aliases |
| **Alias explosion**: Popular areas may have many aliases | Implement alias normalization and periodic cleanup job |
| **Grid too coarse/fine**: Fixed 500m may not suit all areas | Make `GRID_SIZE` configurable per-region if needed |

### Design Decisions Summary

| Decision | Rationale |
|----------|-----------|
| Grid size = 0.005° | ~500m balances granularity and bucket count |
| Aliases stored in bucket | Enables O(1) name→bucket mapping |
| Denormalized property_count | Avoids COUNT(*) for stats endpoint |
| pg_trgm for fuzzy search | PostgreSQL-native, handles typos |
| PostGIS for spatial | Industry standard, battle-tested |

---

## Appendix: Quick Reference

### API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/properties` | POST | Create property (auto-assigns bucket) |
| `/api/properties/search` | GET | Search by location name |
| `/api/geo-buckets/stats` | GET | Bucket statistics |

### Key Configuration

```python
# config.py
GEO_BUCKET_GRID_SIZE = 0.005  # ~500 meters
FUZZY_MATCH_THRESHOLD = 0.3   # pg_trgm similarity threshold
LOCATION_STOP_WORDS = {'lagos', 'nigeria', 'state', 'lga', 'area', 'estate'}
```

### Test Case Verification

```python
# Expected behavior for required test case
properties = [
    {"location": "Sangotedo", "lat": 6.4698, "lng": 3.6285},
    {"location": "Sangotedo, Ajah", "lat": 6.4720, "lng": 3.6301},
    {"location": "sangotedo lagos", "lat": 6.4705, "lng": 3.6290},
]

# All three should:
# 1. Be assigned to the same bucket (key: "6.470_3.630")
# 2. Be returned when searching for "sangotedo"
```
