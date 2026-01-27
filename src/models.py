"""SQLAlchemy models for geo-buckets and properties."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship

from src.database import Base


class GeoBucket(Base):
    """Geo-bucket model representing a geographic area."""
    
    __tablename__ = "geo_buckets"
    
    id = Column(Integer, primary_key=True, index=True)
    bucket_key = Column(String(50), unique=True, nullable=False, index=True)
    canonical_name = Column(String(255), nullable=False)
    # Store centroid as separate lat/lng for SQLite compatibility
    centroid_lat = Column(Float, nullable=False)
    centroid_lng = Column(Float, nullable=False)
    # Store aliases as JSON for SQLite compatibility (PostgreSQL would use ARRAY)
    aliases = Column(JSON, default=list)
    property_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    # Store coordinates as separate lat/lng for SQLite compatibility
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    bedrooms = Column(Integer, nullable=False)
    bathrooms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    geo_bucket = relationship("GeoBucket", back_populates="properties")
    
    def __repr__(self):
        return f"<Property {self.id}: {self.title}>"
