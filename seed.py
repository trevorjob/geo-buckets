"""
Seed script to populate the database with test data.

Run this script after setting up the database:
    python seed.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import SessionLocal, engine, Base
from src.services.location_service import create_property


# Test data - includes the required Sangotedo test case
SEED_DATA = [
    # Required test case: 3 Sangotedo properties
    {
        "title": "Modern 3 Bedroom Apartment in Sangotedo",
        "location_name": "Sangotedo",
        "lat": 6.4698,
        "lng": 3.6285,
        "price": 2500000,
        "bedrooms": 3,
        "bathrooms": 2
    },
    {
        "title": "Luxury 4 Bedroom Duplex",
        "location_name": "Sangotedo, Ajah",
        "lat": 6.4720,
        "lng": 3.6301,
        "price": 4500000,
        "bedrooms": 4,
        "bathrooms": 3
    },
    {
        "title": "Cozy 2 Bedroom Flat",
        "location_name": "sangotedo lagos",
        "lat": 6.4705,
        "lng": 3.6290,
        "price": 1800000,
        "bedrooms": 2,
        "bathrooms": 2
    },
    
    # Additional test data for other areas
    {
        "title": "Spacious 5 Bedroom Mansion",
        "location_name": "Lekki Phase 1",
        "lat": 6.4371,
        "lng": 3.4698,
        "price": 15000000,
        "bedrooms": 5,
        "bathrooms": 5
    },
    {
        "title": "Studio Apartment in Victoria Island",
        "location_name": "Victoria Island, Lagos",
        "lat": 6.4281,
        "lng": 3.4219,
        "price": 1200000,
        "bedrooms": 1,
        "bathrooms": 1
    },
    {
        "title": "3 Bed Flat in Ikeja",
        "location_name": "Ikeja GRA",
        "lat": 6.5833,
        "lng": 3.3500,
        "price": 2200000,
        "bedrooms": 3,
        "bathrooms": 2
    },
    {
        "title": "Executive 4 Bedroom in Ajah",
        "location_name": "Ajah, Lagos",
        "lat": 6.4667,
        "lng": 3.5833,
        "price": 3500000,
        "bedrooms": 4,
        "bathrooms": 3
    },
    {
        "title": "Beach House in Lekki",
        "location_name": "lekki",
        "lat": 6.4375,
        "lng": 3.4700,
        "price": 8000000,
        "bedrooms": 4,
        "bathrooms": 4
    },
]


def seed_database():
    """Seed the database with test data."""
    print("🌱 Seeding database...")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        from src.models import Property
        existing_count = db.query(Property).count()
        
        if existing_count > 0:
            print(f"⚠️  Database already has {existing_count} properties. Skipping seed.")
            print("   To re-seed, clear the database first.")
            return
        
        # Insert seed data
        for i, data in enumerate(SEED_DATA, 1):
            property_obj = create_property(
                db=db,
                title=data["title"],
                location_name=data["location_name"],
                lat=data["lat"],
                lng=data["lng"],
                price=data["price"],
                bedrooms=data["bedrooms"],
                bathrooms=data["bathrooms"]
            )
            print(f"   ✓ Created property {i}: {property_obj.title[:40]}...")
        
        print(f"\n✅ Seeded {len(SEED_DATA)} properties successfully!")
        
        # Verify Sangotedo test case
        from src.services.location_service import search_properties_by_location
        sangotedo_results, _ = search_properties_by_location(db, "sangotedo")
        print(f"\n📍 Sangotedo test: Found {len(sangotedo_results)} properties (expected: 3)")
        
        if len(sangotedo_results) == 3:
            print("✅ Required test case PASSED!")
        else:
            print("❌ Required test case FAILED!")
        
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
