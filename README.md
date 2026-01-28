# Geo-Bucket Location Normalization System

A FastAPI backend that handles property searches using geo-buckets for consistent results.

## 🚀 Quick Start — PostgreSQL (Supabase, Neon, or Local)

This project uses **PostgreSQL** and works with:
- **Supabase**
- **Neon**
- **Local PostgreSQL**

---

## 1. Set Up the Database

Choose **one** of the options below.

---

### Option A: Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** → **New Query**
3. Paste and run the contents of:

```sql
migrations/001_initial_schema.sql
````

---

### Option B: Neon

1. Create a project at [neon.tech](https://neon.tech)
2. Create a database and copy the **connection string**
3. Run migrations locally:

```bash
psql "$DATABASE_URL" -f migrations/001_initial_schema.sql
```

> Neon does not provide a built-in SQL editor, so migrations are typically run locally or via CI.

---

### Option C: Local PostgreSQL

1. Install PostgreSQL (v14+ recommended)
2. Create a database:

```bash
createdb my_app
```

3. Run migrations:

```bash
psql postgresql://localhost/my_app -f migrations/001_initial_schema.sql
```

---

## 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
```

### Example Connection Strings

#### Supabase (Transaction Pooler)

```bash
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

#### Neon

```bash
DATABASE_URL=postgresql://USER:PASSWORD@ep-xxxxxx.us-east-1.aws.neon.tech/DATABASE?sslmode=require
```

#### Local PostgreSQL

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/my_app
```

---

## 3. Verify the Connection

Test the database connection:

```bash
psql "$DATABASE_URL"
```

If the connection succeeds, the database is ready 🎉

---


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


## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

> ⚠️ **Warning:** Tests run against the same PostgreSQL database and **DELETE all data** before each test. If you have seeded data, it will be removed.

**Recommended workflow:**
```bash
# 1. Run tests (this clears the database)
python -m pytest tests/ -v

# 2. Re-seed the database after tests
python seed.py

# 3. Start the application
uvicorn src.main:app --reload
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
