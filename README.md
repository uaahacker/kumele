# Kumele AI/ML Backend

A comprehensive AI/ML backend API built with FastAPI for the Kumele platform. This system provides intelligent services including rating systems, personalized recommendations, advertising intelligence, NLP processing, content moderation, AI chatbot, translation services, support automation, and dynamic pricing.

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [DigitalOcean Droplet Requirements](#-digitalocean-droplet-requirements)
- [Quick Start](#-quick-start)
- [Environment Configuration](#-environment-configuration)
- [Running the Application](#-running-the-application)
- [API Documentation](#-api-documentation)
- [Testing](#-testing)
- [API Endpoints Reference](#-api-endpoints-reference)
- [Monitoring](#-monitoring)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Features

### 🌟 Rating System
- Weighted 5-star host rating model
- Formula: `Host Score = (0.7 × Attendee Rating %) + (0.3 × System Reliability %)`
- Badge system for top performers (Top Rated, Rising Star, Veteran Host)

### 🎯 Personalized Recommendations
- Hobby recommendations based on user preferences
- Event recommendations using collaborative filtering
- Hybrid recommendation engine (content-based + collaborative)

### 📢 Advertising & Targeting Intelligence
- Audience segment matching with ML
- Ad performance prediction (CTR, CPC, engagement)
- Smart targeting recommendations

### 📝 NLP for User-Generated Content
- Sentiment analysis (positive/neutral/negative)
- Keyword extraction
- Trending topics detection
- Entity recognition

### 🛡️ Unified Moderation Service
- Text moderation (toxicity, hate speech, spam)
- Image moderation (nudity, violence detection)
- Video moderation with keyframe analysis
- Async processing with Celery

### 🤖 Chatbot & Knowledge Base
- RAG-based Q&A system using Qdrant vector DB
- Multi-language support
- Knowledge base document sync
- User feedback collection

### 🌐 Translation & i18n
- Real-time text translation via LibreTranslate
- 6 supported languages: English, French, Spanish, Chinese, Arabic, German
- UI string management with approval workflow

### 📧 AI Support Operations
- Intelligent email routing and categorization
- Sentiment-based priority calculation
- Auto-generated reply drafts
- Escalation workflow

### 💰 Dynamic Pricing & Discounts
- Price optimization based on demand, time, seasonality
- Discount suggestions (loyalty, new user, last-minute)
- Confidence scoring for pricing recommendations

### ❤️ System Health & Monitoring
- Comprehensive health checks for all AI/ML components
- System metrics (CPU, Memory, Disk)
- Component-level monitoring (DB, Redis, Qdrant, LLM, Translate)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kumele AI/ML Backend                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   FastAPI   │  │   Celery    │  │   Flower    │             │
│  │    API      │  │   Worker    │  │  Dashboard  │             │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘             │
│         │                │                                       │
│  ┌──────┴────────────────┴──────┐                               │
│  │          Services Layer       │                               │
│  │  ┌─────────┐ ┌─────────────┐ │                               │
│  │  │ Rating  │ │Recommendation│ │                               │
│  │  ├─────────┤ ├─────────────┤ │                               │
│  │  │   NLP   │ │  Moderation │ │                               │
│  │  ├─────────┤ ├─────────────┤ │                               │
│  │  │ Chatbot │ │ Translation │ │                               │
│  │  ├─────────┤ ├─────────────┤ │                               │
│  │  │ Support │ │   Pricing   │ │                               │
│  │  ├─────────┤ ├─────────────┤ │                               │
│  │  │   Ads   │ │   System    │ │                               │
│  │  └─────────┘ └─────────────┘ │                               │
│  └──────────────────────────────┘                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────┐ │
│  │PostgreSQL │ │   Redis   │ │  Qdrant   │ │ LibreTranslate  │ │
│  │    DB     │ │   Cache   │ │  Vector   │ │   Translation   │ │
│  └───────────┘ └───────────┘ └───────────┘ └─────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              TGI (Text Generation Inference)                 ││
│  │                    Mistral 7B LLM                            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI 0.109.0 |
| Database | PostgreSQL 15 + SQLAlchemy Async |
| Cache/Queue | Redis 7 |
| Vector DB | Qdrant |
| Task Queue | Celery 5.3.4 |
| LLM | Mistral 7B via TGI |
| Translation | LibreTranslate |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Sentiment | cardiffnlp/twitter-roberta-base-sentiment |
| Moderation | unitary/toxic-bert |
| Container | Docker + Docker Compose |

---

## 📋 Prerequisites

- **Docker** (v20.10 or higher)
- **Docker Compose** (v2.0 or higher)
- **Git** (for cloning repository)
- **4GB+ RAM minimum** (8GB+ recommended for TGI/LLM)

### Install Docker on Ubuntu

```bash
# Update packages
sudo apt update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

---

## 💧 DigitalOcean Droplet Requirements

### Minimum for Testing (Without LLM/TGI)

| Specification | Requirement |
|--------------|-------------|
| **Droplet Type** | Basic |
| **Plan** | Regular with SSD |
| **vCPUs** | 2 |
| **RAM** | 4 GB |
| **Storage** | 80 GB SSD |
| **Monthly Cost** | ~$24/month |
| **Droplet Name** | Basic Droplet - 4GB RAM |

> ⚠️ **Note**: This configuration runs WITHOUT the TGI/LLM service. The chatbot will use fallback responses.

### Recommended for Full Testing (With LLM)

| Specification | Requirement |
|--------------|-------------|
| **Droplet Type** | CPU-Optimized |
| **vCPUs** | 4 |
| **RAM** | 8 GB |
| **Storage** | 160 GB SSD |
| **Monthly Cost** | ~$48/month |
| **Droplet Name** | CPU-Optimized - 8GB RAM |

### Production Ready (With GPU for LLM)

| Specification | Requirement |
|--------------|-------------|
| **Droplet Type** | GPU Droplet |
| **GPU** | 1x NVIDIA GPU |
| **vCPUs** | 8 |
| **RAM** | 32 GB |
| **Storage** | 320 GB SSD |
| **Monthly Cost** | ~$500+/month |

### DigitalOcean Setup Steps

1. **Create Droplet**:
   ```
   - Go to https://cloud.digitalocean.com/droplets/new
   - Choose Ubuntu 22.04 LTS
   - Select droplet size based on requirements above
   - Choose datacenter region closest to your users
   - Add SSH key for authentication
   - Create Droplet
   ```

2. **Initial Server Setup**:
   ```bash
   # SSH into your droplet
   ssh root@your_droplet_ip
   
   # Create non-root user
   adduser kumele
   usermod -aG sudo kumele
   
   # Setup firewall
   ufw allow OpenSSH
   ufw allow 8000  # API
   ufw allow 5555  # Flower (optional)
   ufw enable
   
   # Switch to new user
   su - kumele
   ```

---

## ⚡ Quick Start

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/your-repo/kumele-backend.git
cd kumele-backend

# Or if you already have the files, navigate to the directory
cd /path/to/newapi
```

### Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit the environment file (optional for testing)
nano .env
```

### Step 3: Start All Services

```bash
# Start all services in detached mode
docker compose up -d

# Wait for services to be healthy (about 1-2 minutes)
docker compose ps
```

### Step 4: Verify Installation

```bash
# Check if API is running
curl http://localhost:8000/

# Check health status
curl http://localhost:8000/ready

# Open API documentation
# Visit: http://localhost:8000/docs
```

---

## ⚙️ Environment Configuration

### Key Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `true` |
| `SECRET_KEY` | JWT secret key | Change in production |
| `DATABASE_URL` | PostgreSQL connection | Auto-configured |
| `REDIS_HOST` | Redis hostname | `localhost` |
| `QDRANT_URL` | Qdrant vector DB URL | `http://localhost:6333` |
| `LLM_API_URL` | TGI/LLM service URL | `http://localhost:8080` |
| `TRANSLATE_URL` | LibreTranslate URL | `http://localhost:5000` |

### Production Configuration

```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Update .env file
SECRET_KEY=your-generated-secret-key
DEBUG=false
CORS_ORIGINS=https://your-domain.com
```

---

## 🏃 Running the Application

### Using Docker Compose (Recommended)

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f api

# Stop all services
docker compose down

# Stop and remove volumes (clean start)
docker compose down -v
```

### Running Without TGI/LLM (For Testing on Low-Memory Droplets)

Create a `docker-compose.override.yml` file:

```yaml
# docker-compose.override.yml
version: '3.8'
services:
  tgi:
    deploy:
      replicas: 0  # Disable TGI service
```

Then run:
```bash
docker compose up -d
```

### Running Individual Services

```bash
# Only start essential services (DB, Redis, API)
docker compose up -d postgres redis api

# Add more services as needed
docker compose up -d qdrant libretranslate
```

### Manual Run (Development)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (required)
docker compose up -d postgres redis qdrant

# Run database migrations (if any)
# alembic upgrade head

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, start Celery worker
celery -A worker.celery_app worker --loglevel=info
```

---

## 📚 API Documentation

Once the application is running, access the interactive API documentation:

| Documentation | URL |
|--------------|-----|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **OpenAPI JSON** | http://localhost:8000/openapi.json |

---

## 🧪 Testing

### Quick API Tests with cURL

#### 1. Test Root Endpoint
```bash
curl http://localhost:8000/
```
Expected response:
```json
{
  "name": "Kumele AI/ML Backend",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs",
  "health": "/ai/health"
}
```

#### 2. Test Health Check
```bash
curl http://localhost:8000/ai/health
```

#### 3. Test Sentiment Analysis
```bash
curl -X POST http://localhost:8000/nlp/sentiment \
  -H "Content-Type: application/json" \
  -d '{"text": "I love this event! It was absolutely amazing!"}'
```
Expected response:
```json
{
  "sentiment": "positive",
  "score": 0.92,
  "confidence": 0.89
}
```

#### 4. Test Keyword Extraction
```bash
curl -X POST http://localhost:8000/nlp/keywords \
  -H "Content-Type: application/json" \
  -d '{"text": "Learn Python programming and machine learning in this workshop", "max_keywords": 5}'
```

#### 5. Test Translation
```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "source_language": "en", "target_language": "es"}'
```
Expected response:
```json
{
  "translated_text": "Hola mundo",
  "source_language": "en",
  "target_language": "es",
  "confidence": 1.0
}
```

#### 6. Test Content Moderation
```bash
curl -X POST http://localhost:8000/moderation/check \
  -H "Content-Type: application/json" \
  -d '{"content_id": "test-123", "content_type": "text", "text": "This is a friendly message about our community event."}'
```

#### 7. Test Chatbot
```bash
curl -X POST http://localhost:8000/chatbot/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I create an event?", "user_id": "user-123"}'
```

#### 8. Test Price Optimization
```bash
curl "http://localhost:8000/pricing/optimize/event-123?base_price=50.0"
```

#### 9. Test Discount Suggestions
```bash
curl "http://localhost:8000/discount/suggest?user_id=user-123&event_id=event-456"
```

#### 10. Test Taxonomy
```bash
curl http://localhost:8000/taxonomy/categories
```

### Running Automated Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run with coverage
pip install pytest-cov
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_nlp.py -v
```

### Sample Test File

Create `tests/test_api.py`:

```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"

@pytest.mark.asyncio
async def test_health_ready():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

@pytest.mark.asyncio
async def test_sentiment_positive():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/nlp/sentiment", json={
            "text": "I absolutely love this product!"
        })
    assert response.status_code == 200
    data = response.json()
    assert data["sentiment"] == "positive"
    assert data["score"] > 0.5
```

### Load Testing with hey

```bash
# Install hey (Go-based load testing tool)
# Mac: brew install hey
# Linux: Download from https://github.com/rakyll/hey

# Run load test - 1000 requests, 50 concurrent
hey -n 1000 -c 50 http://localhost:8000/ready

# Test POST endpoint
hey -n 100 -c 10 -m POST \
  -H "Content-Type: application/json" \
  -d '{"text": "Testing sentiment analysis"}' \
  http://localhost:8000/nlp/sentiment
```

---

## 📡 API Endpoints Reference

### Rating System (`/rating`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rating/event/{event_id}/submit` | Submit event rating |
| GET | `/rating/host/{host_id}` | Get host rating summary |
| POST | `/rating/host/{host_id}/system-reliability` | Record system reliability |
| GET | `/rating/event/{event_id}/ratings` | Get event ratings list |

### Recommendations (`/recommendations`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/recommendations/hobbies/{user_id}` | Get hobby recommendations |
| GET | `/recommendations/events/{user_id}` | Get event recommendations |
| POST | `/recommendations/user/{user_id}/interaction` | Record user interaction |
| GET | `/recommendations/similar/{hobby_id}` | Get similar hobbies |

### Advertising (`/ads`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ads/audience-match` | Match audience segments |
| POST | `/ads/predict-performance` | Predict ad performance |
| GET | `/ads/{ad_id}/analytics` | Get ad analytics |
| GET | `/ads/segments` | List audience segments |
| GET | `/ads/top-performing` | Get top performing ads |

### NLP Services (`/nlp`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/nlp/sentiment` | Analyze text sentiment |
| POST | `/nlp/keywords` | Extract keywords |
| GET | `/nlp/trending-topics` | Get trending topics |
| POST | `/nlp/entities` | Extract named entities |
| POST | `/nlp/summarize` | Summarize text |

### Moderation (`/moderation`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/moderation/check` | Check content for violations |
| GET | `/moderation/status/{content_id}` | Get moderation status |
| POST | `/moderation/review/{content_id}` | Submit manual review |
| GET | `/moderation/queue` | Get moderation queue |
| GET | `/moderation/stats` | Get moderation statistics |

### Chatbot (`/chatbot`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chatbot/ask` | Ask the chatbot |
| POST | `/chatbot/knowledge/sync` | Sync knowledge document |
| POST | `/chatbot/feedback` | Submit feedback |
| GET | `/chatbot/knowledge` | List knowledge docs |
| GET | `/chatbot/stats` | Get chatbot statistics |

### Translation (`/translate`, `/i18n`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/translate` | Translate text |
| POST | `/translate/detect` | Detect language |
| GET | `/translate/languages` | List supported languages |
| GET | `/i18n/strings/{language}` | Get UI strings |
| POST | `/admin/i18n/string` | Add UI string |
| GET | `/admin/i18n/pending` | Get pending translations |
| POST | `/admin/i18n/approve/{translation_id}` | Approve translation |

### Support (`/support`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/support/email/incoming` | Process incoming email |
| POST | `/support/email/{email_id}/reply` | Reply to email |
| POST | `/support/email/{email_id}/escalate` | Escalate email |
| GET | `/support/email/{email_id}` | Get email details |
| GET | `/support/emails` | List support emails |
| GET | `/support/stats` | Get support statistics |

### Pricing (`/pricing`, `/discount`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/pricing/optimize/{event_id}` | Optimize event price |
| GET | `/pricing/history/{event_id}` | Get pricing history |
| GET | `/discount/suggest` | Get discount suggestions |

### System Health (`/ai`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ai/health` | Full system health check |
| GET | `/ai/health/db` | Database health |
| GET | `/ai/health/redis` | Redis health |
| GET | `/ai/health/qdrant` | Qdrant health |
| GET | `/ai/health/llm` | LLM service health |
| GET | `/ai/health/translate` | Translation service health |

### Taxonomy (`/taxonomy`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/taxonomy/categories` | Get all categories |
| GET | `/taxonomy/categories/{category_id}` | Get category details |
| GET | `/taxonomy/categories/{category_id}/hobbies` | Get hobbies in category |
| POST | `/taxonomy/categories` | Create category (admin) |

---

## 📊 Monitoring

### Flower Dashboard (Celery Monitoring)

Access at: `http://localhost:5555`

Features:
- Real-time task monitoring
- Worker status
- Task history and results
- Task rate graphs

### Health Check Endpoints

```bash
# Readiness probe
curl http://localhost:8000/ready

# Liveness probe  
curl http://localhost:8000/live

# Full system health
curl http://localhost:8000/ai/health
```

### Docker Container Logs

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f postgres

# View last 100 lines
docker compose logs --tail=100 api
```

### System Metrics

The `/ai/health` endpoint returns system metrics:

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "components": {
    "database": {"status": "healthy", "latency_ms": 5.2},
    "redis": {"status": "healthy", "latency_ms": 1.1},
    "qdrant": {"status": "healthy", "latency_ms": 8.3},
    "llm": {"status": "healthy", "latency_ms": 150.5},
    "translate": {"status": "healthy", "latency_ms": 45.2}
  },
  "system": {
    "cpu": {"percent": 25.5, "count": 4},
    "memory": {"percent": 62.3, "total_gb": 8.0},
    "disk": {"percent": 45.0, "total_gb": 160.0}
  }
}
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Container Won't Start

```bash
# Check container status
docker compose ps

# View detailed logs
docker compose logs api

# Restart specific service
docker compose restart api
```

#### 2. Database Connection Error

```bash
# Check if PostgreSQL is running
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres

# Manually test connection
docker compose exec postgres psql -U kumele -d kumele_db -c "SELECT 1;"
```

#### 3. Redis Connection Error

```bash
# Check Redis status
docker compose exec redis redis-cli ping
# Should return: PONG
```

#### 4. Out of Memory (OOM)

If TGI/LLM service causes OOM:

```bash
# Disable TGI service
# Edit docker-compose.yml and comment out tgi service
# Or create docker-compose.override.yml as shown above

# Restart without TGI
docker compose up -d
```

#### 5. Port Already in Use

```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>

# Or change the port in docker-compose.yml
```

#### 6. Slow Response Times

```bash
# Check system resources
docker stats

# Scale workers if needed
docker compose up -d --scale worker=3
```

### Reset Everything

```bash
# Stop all containers and remove volumes
docker compose down -v

# Remove all images (optional)
docker compose down --rmi all

# Clean Docker system
docker system prune -a

# Start fresh
docker compose up -d
```

---

## 📁 Project Structure

```
newapi/
├── app/
│   ├── __init__.py
│   ├── config.py              # Application settings
│   ├── database.py            # Database connection
│   ├── main.py                # FastAPI application
│   ├── api/                   # API route handlers
│   │   ├── __init__.py
│   │   ├── ratings.py
│   │   ├── recommendations.py
│   │   ├── ads.py
│   │   ├── nlp.py
│   │   ├── moderation.py
│   │   ├── chatbot.py
│   │   ├── translate.py
│   │   ├── support.py
│   │   ├── pricing.py
│   │   ├── system.py
│   │   └── taxonomy.py
│   ├── models/                # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── database_models.py
│   ├── schemas/               # Pydantic schemas
│   │   ├── __init__.py
│   │   └── schemas.py
│   └── services/              # Business logic
│       ├── __init__.py
│       ├── rating_service.py
│       ├── recommendation_service.py
│       ├── nlp_service.py
│       ├── ads_service.py
│       ├── moderation_service.py
│       ├── chatbot_service.py
│       ├── translation_service.py
│       ├── support_service.py
│       ├── pricing_service.py
│       └── system_service.py
├── worker/
│   ├── __init__.py
│   ├── celery_app.py          # Celery configuration
│   └── tasks/                 # Background tasks
│       ├── __init__.py
│       ├── moderation_tasks.py
│       ├── recommendation_tasks.py
│       ├── nlp_tasks.py
│       └── email_tasks.py
├── tests/                     # Test files (create as needed)
├── .env.example               # Environment template
├── docker-compose.yml         # Docker services
├── Dockerfile                 # Container image
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## 📜 License

[Add your license here]

---

## 🤝 Contributing

[Add contribution guidelines here]

---

## 📞 Support

For issues and questions:
- Create an issue in the repository
- Contact: [your-email@example.com]

---

**Built with ❤️ for Kumele Platform**
