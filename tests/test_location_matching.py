"""
Tests for location matching and geo-bucket functionality.

Run tests with: python -m pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.database import Base, get_db
from src.services.location_service import (
    normalize_location,
    compute_bucket_key
)


# =====================================================
# TEST DATABASE SETUP
# =====================================================

# Use SQLite in-memory for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the dependency
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    """Create test client with fresh database."""
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


# =====================================================
# UNIT TESTS: Location Normalization
# =====================================================

class TestLocationNormalization:
    """Tests for location name normalization."""
    
    def test_lowercase_conversion(self):
        """Test that names are converted to lowercase."""
        assert "sangotedo" in normalize_location("SANGOTEDO")
        assert "sangotedo" in normalize_location("Sangotedo")
    
    def test_punctuation_removal(self):
        """Test that punctuation is removed."""
        result = normalize_location("Sangotedo, Ajah")
        assert "," not in result
        assert "ajah" in result
        assert "sangotedo" in result
    
    def test_stop_word_removal(self):
        """Test that stop words are removed."""
        result = normalize_location("Sangotedo Lagos Nigeria")
        assert "lagos" not in result
        assert "nigeria" not in result
        assert "sangotedo" in result
    
    def test_whitespace_handling(self):
        """Test that extra whitespace is handled."""
        assert normalize_location("  Sangotedo  ") == "sangotedo"
        assert normalize_location("Sangotedo   Ajah") == "ajah sangotedo"
    
    def test_sorted_tokens(self):
        """Test that tokens are sorted for canonical form."""
        result1 = normalize_location("Ajah Sangotedo")
        result2 = normalize_location("Sangotedo Ajah")
        assert result1 == result2  # Both should produce same canonical form


# =====================================================
# UNIT TESTS: Bucket Key Computation
# =====================================================

class TestBucketKeyComputation:
    """Tests for geo-bucket key computation."""
    
    def test_basic_bucket_key(self):
        """Test basic bucket key computation."""
        key, lat, lng = compute_bucket_key(6.4698, 3.6285)
        assert key == "6.470_3.630"
    
    def test_same_bucket_nearby_coords(self):
        """Test that nearby coordinates fall in the same bucket."""
        key1, _, _ = compute_bucket_key(6.4698, 3.6285)
        key2, _, _ = compute_bucket_key(6.4720, 3.6301)
        key3, _, _ = compute_bucket_key(6.4705, 3.6290)
        
        # All Sangotedo coordinates should be in the same bucket
        assert key1 == key2 == key3
    
    def test_different_buckets_far_coords(self):
        """Test that distant coordinates fall in different buckets."""
        sangotedo_key, _, _ = compute_bucket_key(6.4698, 3.6285)
        lekki_key, _, _ = compute_bucket_key(6.4371, 3.4698)
        
        # Sangotedo and Lekki should be in different buckets
        assert sangotedo_key != lekki_key


# =====================================================
# INTEGRATION TESTS: Required Test Case
# =====================================================

class TestRequiredTestCase:
    """
    Tests for the required test case:
    - POST 3 properties with different Sangotedo location names
    - GET search should return all 3
    """
    
    def test_sangotedo_properties_via_api(self, client):
        """Test the required Sangotedo test case via API."""
        # Create 3 properties with different location name variations
        properties = [
            {
                "title": "Property 1",
                "location_name": "Sangotedo",
                "lat": 6.4698,
                "lng": 3.6285,
                "price": 2500000,
                "bedrooms": 3,
                "bathrooms": 2
            },
            {
                "title": "Property 2",
                "location_name": "Sangotedo, Ajah",
                "lat": 6.4720,
                "lng": 3.6301,
                "price": 4500000,
                "bedrooms": 4,
                "bathrooms": 3
            },
            {
                "title": "Property 3",
                "location_name": "sangotedo lagos",
                "lat": 6.4705,
                "lng": 3.6290,
                "price": 1800000,
                "bedrooms": 2,
                "bathrooms": 2
            }
        ]
        
        # POST all properties
        for prop in properties:
            response = client.post("/api/properties", json=prop)
            assert response.status_code == 200, f"Failed to create property: {response.text}"
        
        # Search for "sangotedo" - should return all 3
        response = client.get("/api/properties/search?location=sangotedo")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] == 3, f"Expected 3 properties, got {data['count']}"
    
    def test_case_insensitive_search(self, client):
        """Test that search is case-insensitive."""
        # Create a property
        client.post("/api/properties", json={
            "title": "Test Property",
            "location_name": "Sangotedo",
            "lat": 6.4698,
            "lng": 3.6285,
            "price": 1000000,
            "bedrooms": 2,
            "bathrooms": 1
        })
        
        # Search with different cases
        for query in ["sangotedo", "SANGOTEDO", "SanGoTeDo"]:
            response = client.get(f"/api/properties/search?location={query}")
            assert response.status_code == 200
            assert response.json()["count"] >= 1
    
    def test_location_variation_matching(self, client):
        """Test that location name variations match."""
        # Create property with location variation
        client.post("/api/properties", json={
            "title": "Test Property",
            "location_name": "Sangotedo, Ajah, Lagos",
            "lat": 6.4698,
            "lng": 3.6285,
            "price": 1000000,
            "bedrooms": 2,
            "bathrooms": 1
        })
        
        # Should be found with just "sangotedo"
        response = client.get("/api/properties/search?location=sangotedo")
        assert response.status_code == 200
        assert response.json()["count"] >= 1


# =====================================================
# API ENDPOINT TESTS
# =====================================================

class TestAPIEndpoints:
    """Tests for API endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_create_property(self, client):
        """Test property creation endpoint."""
        response = client.post("/api/properties", json={
            "title": "New Property",
            "location_name": "Test Location",
            "lat": 6.5,
            "lng": 3.5,
            "price": 1000000,
            "bedrooms": 2,
            "bathrooms": 1
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Property"
        assert "geo_bucket_id" in data
    
    def test_create_property_validation(self, client):
        """Test property creation validation."""
        # Missing required field
        response = client.post("/api/properties", json={
            "title": "Test",
            "lat": 6.5,
            "lng": 3.5
        })
        assert response.status_code == 422  # Validation error
    
    def test_search_empty_result(self, client):
        """Test search with no matching properties."""
        response = client.get("/api/properties/search?location=nonexistent")
        assert response.status_code == 200
        assert response.json()["count"] == 0
    
    def test_bucket_stats(self, client):
        """Test bucket stats endpoint."""
        # Create a property first
        client.post("/api/properties", json={
            "title": "Test Property",
            "location_name": "Test Location",
            "lat": 6.5,
            "lng": 3.5,
            "price": 1000000,
            "bedrooms": 2,
            "bathrooms": 1
        })
        
        response = client.get("/api/geo-buckets/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_buckets" in data
        assert "total_properties" in data
        assert data["total_buckets"] >= 1
