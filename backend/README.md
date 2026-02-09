# Virtual Try-On Backend API

Backend API for Shopify Virtual Try-On App built with FastAPI, PostgreSQL, Redis, MediaPipe, and Google Gemini.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Virtual environment (already created)

### 1. Install Dependencies

```bash
# Activate virtual environment
cd d:\Work\OptimoSolutions\VirtualTryOn
.venv\Scripts\activate

# Install backend dependencies
cd backend
pip install -r requirements.txt
```

### 2. Start Docker Services

```bash
# From project root
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 3. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API keys
# For now, the defaults work for local development
```

### 4. Run the Application

```bash
# From backend directory
cd backend
python -m app.main

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Test the API

Open your browser and visit:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Root:** http://localhost:8000/
- **Health Check:** http://localhost:8000/health

## 📁 Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry
│   ├── config.py            # Configuration management
│   ├── api/
│   │   └── v1/              # API version 1 endpoints
│   ├── models/              # SQLAlchemy models
│   ├── services/            # Business logic
│   ├── core/                # Core functionality
│   │   ├── database.py      # PostgreSQL connection
│   │   └── redis.py         # Redis connection
│   ├── utils/               # Utility functions
│   └── data/                # Static data (size charts, etc.)
├── tests/                   # Test files
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🧪 Testing with Swagger

1. Go to http://localhost:8000/docs
2. Try the `/health` endpoint:
   - Click "GET /health"
   - Click "Try it out"
   - Click "Execute"
   - You should see a 200 response with database and Redis status

## 🔧 Development Commands

```bash
# Start Docker services
docker-compose up -d

# Stop Docker services
docker-compose down

# View logs
docker-compose logs -f

# Access PostgreSQL
docker exec -it virtual_tryon_postgres psql -U dev -d virtual_tryon_dev

# Access Redis CLI
docker exec -it virtual_tryon_redis redis-cli

# Run tests (when available)
pytest

# Check code style
flake8 app/
```

## 📊 Database & Redis

### PostgreSQL
- Host: localhost:5432
- Database: virtual_tryon_dev
- User: dev
- Password: dev123

### Redis
- Host: localhost:6379
- Max Memory: 256MB
- Eviction Policy: allkeys-lru (Least Recently Used)

## 🎯 Next Steps

- [ ] Segment 2: Database Models & Migrations
- [ ] Segment 3: Shopify Integration
- [ ] Segment 4: Measurement Extraction
- [ ] Segment 5: Size Recommendation & Heatmap
- [ ] Segment 6: Virtual Try-On
- [ ] Segment 7: Analytics & Dashboard

## 📝 Environment Variables

See `.env.example` for all available configuration options.

## 🐛 Troubleshooting

### Docker services won't start
```bash
docker-compose down
docker-compose up -d
```

### Database connection error
Check if PostgreSQL container is running:
```bash
docker ps | grep postgres
```

### Redis connection error
Check if Redis container is running:
```bash
docker ps | grep redis
```

## 📚 API Documentation

Full API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🔐 Security Notes

- Never commit `.env` file
- Change default database credentials in production
- Use strong SECRET_KEY in production
- Enable HTTPS in production

---

**Version:** 1.0.0
**Last Updated:** 2026-02-09
