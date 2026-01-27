"""FastAPI application for Geo-Bucket Location Normalization System."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db, engine, Base
from src.schemas import (
    PropertyCreate, 
    PropertyResponse, 
    PropertySearchResponse,
    GeoBucketStatsResponse
)
from src.services.location_service import (
    create_property,
    search_properties_by_location,
    get_bucket_stats
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup."""
    Base.metadata.create_all(bind=engine)
    yield


# Create FastAPI app
app = FastAPI(
    title="Geo-Bucket Property Search API",
    description="Location normalization system using geo-buckets for consistent property search",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Geo-Bucket Property Search API"}


# ============== Property Endpoints ==============

@app.post("/api/properties", response_model=PropertyResponse)
async def create_property_endpoint(
    property_data: PropertyCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new property.
    
    The property is automatically assigned to a geo-bucket based on its coordinates.
    If a bucket doesn't exist for the area, one is created.
    """
    try:
        property_obj = create_property(
            db=db,
            title=property_data.title,
            location_name=property_data.location_name,
            lat=property_data.lat,
            lng=property_data.lng,
            price=property_data.price,
            bedrooms=property_data.bedrooms,
            bathrooms=property_data.bathrooms
        )
        
        return PropertyResponse(
            id=property_obj.id,
            title=property_obj.title,
            location_name=property_obj.location_name,
            lat=property_obj.lat,
            lng=property_obj.lng,
            price=property_obj.price,
            bedrooms=property_obj.bedrooms,
            bathrooms=property_obj.bathrooms,
            geo_bucket_id=property_obj.geo_bucket_id,
            created_at=property_obj.created_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/properties/search", response_model=PropertySearchResponse)
async def search_properties(
    location: str = Query(..., min_length=1, description="Location name to search for"),
    db: Session = Depends(get_db)
):
    """
    Search for properties by location name.
    
    Handles case-insensitive matching and location name variations.
    Uses geo-buckets for efficient lookup.
    """
    properties, bucket = search_properties_by_location(db, location)
    
    # Build response
    property_responses = [
        PropertyResponse(
            id=prop.id,
            title=prop.title,
            location_name=prop.location_name,
            lat=prop.lat,
            lng=prop.lng,
            price=prop.price,
            bedrooms=prop.bedrooms,
            bathrooms=prop.bathrooms,
            geo_bucket_id=prop.geo_bucket_id,
            created_at=prop.created_at
        )
        for prop in properties
    ]
    
    bucket_info = None
    if bucket:
        bucket_info = {
            "id": bucket.id,
            "bucket_key": bucket.bucket_key,
            "canonical_name": bucket.canonical_name
        }
    
    return PropertySearchResponse(
        properties=property_responses,
        count=len(property_responses),
        bucket_info=bucket_info
    )


# ============== Geo-Bucket Endpoints ==============

@app.get("/api/geo-buckets/stats", response_model=GeoBucketStatsResponse)
async def get_geo_bucket_stats(db: Session = Depends(get_db)):
    """
    Get statistics about all geo-buckets.
    
    Returns total buckets, properties per bucket, and coverage information.
    """
    stats = get_bucket_stats(db)
    
    return GeoBucketStatsResponse(
        total_buckets=stats["total_buckets"],
        total_properties=stats["total_properties"],
        avg_properties_per_bucket=stats["avg_properties_per_bucket"],
        buckets=[
            {
                "id": b["id"],
                "bucket_key": b["bucket_key"],
                "canonical_name": b["canonical_name"],
                "aliases": b["aliases"],
                "property_count": b["property_count"],
                "centroid_lat": b["centroid_lat"],
                "centroid_lng": b["centroid_lng"]
            }
            for b in stats["buckets"]
        ]
    )
