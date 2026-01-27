"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ============== Property Schemas ==============

class PropertyCreate(BaseModel):
    """Schema for creating a property."""
    title: str = Field(..., min_length=1, max_length=255)
    location_name: str = Field(..., min_length=1, max_length=255)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    price: float = Field(..., gt=0)
    bedrooms: int = Field(..., ge=0)
    bathrooms: int = Field(..., ge=0)


class PropertyResponse(BaseModel):
    """Schema for property response."""
    id: int
    title: str
    location_name: str
    lat: float
    lng: float
    price: float
    bedrooms: int
    bathrooms: int
    geo_bucket_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PropertySearchResponse(BaseModel):
    """Schema for search results."""
    properties: list[PropertyResponse]
    count: int
    bucket_info: Optional[dict] = None


# ============== Geo-Bucket Schemas ==============

class GeoBucketResponse(BaseModel):
    """Schema for geo-bucket response."""
    id: int
    bucket_key: str
    canonical_name: str
    aliases: list[str]
    property_count: int
    centroid_lat: float
    centroid_lng: float
    
    model_config = ConfigDict(from_attributes=True)


class GeoBucketStatsResponse(BaseModel):
    """Schema for bucket statistics."""
    total_buckets: int
    total_properties: int
    avg_properties_per_bucket: float
    buckets: list[GeoBucketResponse]
