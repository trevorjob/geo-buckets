# Geo-Bucket Location Normalization System

A FastAPI backend that handles property searches using geo-buckets for consistent results.

---

## 🚀 Quick Start with Supabase

### 1. Set Up Supabase Database

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** → **New Query**
3. Paste and run the contents of `migrations/001_initial_schema.sql`

### 2. Get Connection String

1. Go to **Project Settings** → **Database**
2. Copy the **URI** connection string (Transaction Pooler recommended)
3. Create `.env` file:

```bash
# .env
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

### 3. Install & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Seed database
python seed.py

# Start server
uvicorn src.main:app --reload
```

API available at: `http://localhost:8000`

---

## 📡 API Endpoints

### Create Property
```http
POST /api/properties
Content-Type: application/json

{
  "title": "Modern 3 Bedroom Apartment",
  "location_name": "Sangotedo",
  "lat": 6.4698,
  "lng": 3.6285,
  "price": 2500000,
  "bedrooms": 3,
  "bathrooms": 2
}
```

### Search Properties
```http
GET /api/properties/search?location=sangotedo
```

### Bucket Statistics
```http
GET /api/geo-buckets/stats
```

---

## ✅ Required Test Case

```javascript
POST /api/properties → { location_name: "Sangotedo", lat: 6.4698, lng: 3.6285 }
POST /api/properties → { location_name: "Sangotedo, Ajah", lat: 6.4720, lng: 3.6301 }
POST /api/properties → { location_name: "sangotedo lagos", lat: 6.4705, lng: 3.6290 }

GET /api/properties/search?location=sangotedo
// ✓ Returns all 3 properties
```

---

## 🧪 Running Tests

```bash
# Uses SQLite in-memory - no database needed
python -m pytest tests/ -v
```

---

## 📁 Project Structure

```
assessment/
├── DESIGN.md                    # Architecture doc
├── README.md
├── requirements.txt
├── seed.py
├── .env.example
├── migrations/
│   └── 001_initial_schema.sql   # Run in Supabase SQL Editor
├── src/
│   ├── main.py                  # FastAPI app
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── services/
│       └── location_service.py
└── tests/
    └── test_location_matching.py
```

---

## 🔧 How It Works

1. **Grid-based bucketing**: Coordinates rounded to 0.005° grid (~500m)
2. **Bucket assignment**: `(6.4698, 3.6285)` → bucket key `6.470_3.630`
3. **Alias tracking**: Each bucket stores all location name variations
4. **Search**: Normalized input matched against bucket names/aliases

---

## 📖 Documentation

See [DESIGN.md](./DESIGN.md) for full architecture documentation.
