"""SQLAlchemy models for geo-buckets and properties.

Uses PostgreSQL with PostGIS for spatial indexing.
Float columns are kept alongside GEOMETRY columns for simpler queries.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship

from src.database import Base


def get_current_time():
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class GeoBucket(Base):
    """Geo-bucket model representing a geographic area."""
    
    __tablename__ = "geo_buckets"
    
    id = Column(Integer, primary_key=True, index=True)
    bucket_key = Column(String(50), unique=True, nullable=False, index=True)
    canonical_name = Column(String(255), nullable=False)
    # Float columns for ORM operations and simple queries
    centroid_lat = Column(Float, nullable=False)
    centroid_lng = Column(Float, nullable=False) 
    # Location name variations for text-based search
    aliases = Column(JSON, default=list)
    
    # Denormalized property count for stats endpoint
    property_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), default=get_current_time)
    updated_at = Column(DateTime(timezone=True), default=get_current_time, onupdate=get_current_time)
    
    # Relationship
    properties = relationship("Property", back_populates="geo_bucket")
    
    def __repr__(self):
        return f"<GeoBucket {self.bucket_key}: {self.canonical_name}>"


class Property(Base):
    """Property model."""
    
    __tablename__ = "properties"
    
    id = Column(Integer, primary_key=True, index=True)
    geo_bucket_id = Column(Integer, ForeignKey("geo_buckets.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    location_name = Column(String(255), nullable=False)  # Original user input
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    bedrooms = Column(Integer, nullable=False)
    bathrooms = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_current_time)
    
    # Relationship
    geo_bucket = relationship("GeoBucket", back_populates="properties")
    
    def __repr__(self):
        return f"<Property {self.id}: {self.title}>"
