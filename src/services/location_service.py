"""Location normalization and geo-bucket services."""
import re
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config import settings
from src.models import GeoBucket, Property


def normalize_location(name: str) -> str:
    """
    Normalize location name for consistent matching.
    
    Examples:
        "Sangotedo, Ajah"    → "ajah sangotedo"
        "SANGOTEDO LAGOS"    → "sangotedo"
        "  Sangotedo  "      → "sangotedo"
    """
    # 1. Lowercase and strip
    name = name.lower().strip()
    
    # 2. Remove special characters (keep spaces)
    name = re.sub(r'[^\w\s]', ' ', name)
    
    # 3. Split into tokens
    tokens = name.split()
    
    # 4. Remove stop words
    tokens = [t for t in tokens if t not in settings.LOCATION_STOP_WORDS]
    
    # 5. Sort and deduplicate for canonical form
    tokens = sorted(set(tokens))
    
    return ' '.join(tokens)


def compute_bucket_key(lat: float, lng: float) -> tuple[str, float, float]:
    """
    Compute bucket key from coordinates using grid-based rounding.
    
    Returns:
        Tuple of (bucket_key, bucket_lat, bucket_lng)
    """
    grid_size = settings.GEO_BUCKET_GRID_SIZE
    
    bucket_lat = round(lat / grid_size) * grid_size
    bucket_lng = round(lng / grid_size) * grid_size
    
    # Format to 3 decimal places for consistency
    bucket_key = f"{bucket_lat:.3f}_{bucket_lng:.3f}"
    
    return bucket_key, bucket_lat, bucket_lng


def get_or_create_bucket(
    db: Session, 
    lat: float, 
    lng: float, 
    location_name: str
) -> GeoBucket:
    """
    Get existing bucket or create a new one for the given coordinates.
    Also updates bucket aliases if the location name is new.
    """
    bucket_key, bucket_lat, bucket_lng = compute_bucket_key(lat, lng)
    normalized_name = normalize_location(location_name)
    
    # Try to find existing bucket
    bucket = db.query(GeoBucket).filter(GeoBucket.bucket_key == bucket_key).first()
    
    if bucket:
        # Add alias if it's new
        current_aliases = bucket.aliases if bucket.aliases else []
        if normalized_name and normalized_name not in current_aliases:
            updated_aliases = list(current_aliases) + [normalized_name]
            bucket.aliases = updated_aliases
            db.commit()
            db.refresh(bucket)
        return bucket
    
    # Create new bucket
    bucket = GeoBucket(
        bucket_key=bucket_key,
        canonical_name=normalized_name or "unknown",
        centroid_lat=bucket_lat,
        centroid_lng=bucket_lng,
        aliases=[normalized_name] if normalized_name else [],
        property_count=0
    )
    db.add(bucket)
    db.commit()
    db.refresh(bucket)
    
    return bucket


def find_buckets_by_location(db: Session, location_query: str) -> list[GeoBucket]:
    """
    Find geo-buckets matching a location query using multi-step matching.
    
    Steps:
        1. Exact canonical name match
        2. Alias array containment
        3. Partial match (LIKE)
    """
    normalized_query = normalize_location(location_query)
    
    if not normalized_query:
        return []
    
    all_buckets = db.query(GeoBucket).all()
    
    matched_buckets = []
    for bucket in all_buckets:
        # Step 1: Exact canonical name match
        if bucket.canonical_name.lower() == normalized_query:
            matched_buckets.append(bucket)
            continue
            
        # Step 2: Check aliases
        aliases = bucket.aliases if bucket.aliases else []
        if normalized_query in aliases:
            matched_buckets.append(bucket)
            continue
            
        # Step 3: Partial match in canonical name or aliases
        if normalized_query in bucket.canonical_name.lower():
            matched_buckets.append(bucket)
            continue
            
        for alias in aliases:
            if normalized_query in alias:
                matched_buckets.append(bucket)
                break
    
    return matched_buckets


def search_properties_by_location(
    db: Session, 
    location_query: str
) -> tuple[list[Property], Optional[GeoBucket]]:
    """
    Search properties by location name.
    
    Returns:
        Tuple of (properties list, matched bucket or None)
    """
    # Find matching buckets
    buckets = find_buckets_by_location(db, location_query)
    
    if not buckets:
        return [], None
    
    # Get all bucket IDs
    bucket_ids = [b.id for b in buckets]
    
    # Fetch properties from all matching buckets
    properties = db.query(Property).filter(
        Property.geo_bucket_id.in_(bucket_ids)
    ).order_by(Property.created_at.desc()).all()
    
    return properties, buckets[0] if buckets else None


def create_property(
    db: Session,
    title: str,
    location_name: str,
    lat: float,
    lng: float,
    price: float,
    bedrooms: int,
    bathrooms: int
) -> Property:
    """
    Create a new property and assign it to a geo-bucket.
    """
    # Get or create bucket
    bucket = get_or_create_bucket(db, lat, lng, location_name)
    
    # Create property
    property_obj = Property(
        geo_bucket_id=bucket.id,
        title=title,
        location_name=location_name,
        lat=lat,
        lng=lng,
        price=price,
        bedrooms=bedrooms,
        bathrooms=bathrooms
    )
    db.add(property_obj)
    
    # Update bucket property count
    bucket.property_count = (bucket.property_count or 0) + 1
    
    db.commit()
    db.refresh(property_obj)
    
    return property_obj


def get_bucket_stats(db: Session) -> dict:
    """Get statistics about all geo-buckets."""
    buckets = db.query(GeoBucket).all()
    
    total_buckets = len(buckets)
    total_properties = sum(b.property_count or 0 for b in buckets)
    avg_properties = total_properties / total_buckets if total_buckets > 0 else 0
    
    bucket_list = []
    for bucket in buckets:
        bucket_list.append({
            "id": bucket.id,
            "bucket_key": bucket.bucket_key,
            "canonical_name": bucket.canonical_name,
            "aliases": bucket.aliases or [],
            "property_count": bucket.property_count or 0,
            "centroid_lat": bucket.centroid_lat,
            "centroid_lng": bucket.centroid_lng,
        })
    
    return {
        "total_buckets": total_buckets,
        "total_properties": total_properties,
        "avg_properties_per_bucket": round(avg_properties, 2),
        "buckets": bucket_list
    }
