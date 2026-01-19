# Kumele AI/ML Backend Service

A comprehensive AI/ML backend service providing intelligent features for the Kumele events platform.

## Features

- **RAG Chatbot** - Retrieval-Augmented Generation chatbot with Qdrant vector store
- **Smart Matching** - ML-based event matching using clustering + Nominatim geocoding
- **Personalized Recommendations** - TFRS-style collaborative filtering
- **Content Moderation** - Text, image, and video moderation
- **NLP Analysis** - Sentiment analysis, keyword extraction, trending topics
- **Dynamic Pricing** - Demand-based price optimization
- **Attendance Prediction** - Prophet-based forecasting
- **Support Email Processing** - AI-assisted customer support
- **Translation** - Multi-language support via LibreTranslate/Argos
- **Rewards System** - Tier-based rewards and coupon generation
- **Geocoding** - OpenStreetMap Nominatim integration for location-based matching
- **Interest Taxonomy** - ML-owned canonical interest/hobby taxonomy with translations
- **i18n Lazy Loading** - Scope-based translation lazy loading for frontend optimization
- **Redis Streams** - Near-real-time event processing for NLP, ads, activities, and moderation
- **Timeseries Analytics** - Daily and hourly metrics for forecasting and dashboards
- **No-Show Prediction** - Behavioral forecasting for attendance probability and dynamic pricing
- **Attendance Verification** - Trust & fraud detection for check-in validation with GPS, QR, and device signals

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        API Layer                              │
│  FastAPI endpoints at /ai/* and /chatbot/* and /support/*    │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                      Service Layer                            │
│  All ML/AI logic, no direct HTTP calls from routers          │
└───────────────────────────┬──────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  PostgreSQL   │   │    Qdrant     │   │  Mistral LLM  │
│   (Data)      │   │  (Vectors)    │   │   (via TGI)   │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- 16GB+ RAM recommended
- GPU recommended for LLM inference

## Quick Start

### 1. Clone and Configure

```bash
cd aliproject
cp .env.example .env
# Edit .env with your configuration
```

### 2. Start with Docker Compose

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Qdrant (ports 6333, 6334)
- LibreTranslate/Argos (port 5000)
- Mistral via TGI (port 8080)
- Kumele API (port 8000)
- Celery Worker

### 3. Initialize Database

```bash
# Run database migrations
docker-compose exec api python -c "
from kumele_ai.db.database import engine
from kumele_ai.db.models import Base
Base.metadata.create_all(bind=engine)
"

# Or use the schema file directly
docker-compose exec postgres psql -U postgres -d kumele -f /docker-entrypoint-initdb.d/schema.sql
```

### 4. Generate and Import Synthetic Data

```bash
# Generate data
python scripts/generate_data.py --output-dir ./synthetic_data

# Push to database (optional)
python scripts/generate_data.py --push-to-db
```

### 5. Sync Knowledge Base

```bash
curl -X POST http://localhost:8000/chatbot/sync
```

### 6. Health Check

```bash
curl http://localhost:8000/ai/health
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://kumele:kumele@postgres:5432/kumele_ai` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `QDRANT_URL` | Qdrant server URL | `http://qdrant:6333` |
| `LLM_API_URL` | TGI/Mistral API URL | `http://mistral:8080` |
| `TRANSLATE_URL` | LibreTranslate URL | `http://argos:5000` |
| `SMTP_HOST` | SMTP server for emails | `localhost` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username | - |
| `SMTP_PASS` | SMTP password | - |
| `API_KEY` | Internal API key for /chatbot/sync | - |
| `NOMINATIM_URL` | Nominatim geocoding API URL | `https://nominatim.openstreetmap.org` |
| `NOMINATIM_USER_AGENT` | User-Agent for Nominatim (required) | `KumeleAI/1.0` |
| `NOMINATIM_TIMEOUT_SEC` | Nominatim request timeout | `10` |
| `NOMINATIM_CACHE_TTL_SEC` | Geocoding cache TTL | `86400` |
| `MODERATION_TEXT_TOXICITY_THRESHOLD` | Text toxicity rejection threshold | `0.60` |
| `MODERATION_TEXT_HATE_THRESHOLD` | Text hate speech threshold | `0.30` |
| `MODERATION_TEXT_SPAM_THRESHOLD` | Text spam threshold | `0.70` |
| `MODERATION_IMAGE_NUDITY_THRESHOLD` | Image nudity threshold | `0.60` |
| `MODERATION_IMAGE_VIOLENCE_THRESHOLD` | Image violence threshold | `0.50` |
| `MODERATION_IMAGE_HATE_THRESHOLD` | Image hate symbols threshold | `0.40` |

## API Endpoints

### System
- `GET /ai/health` - Health check returning machine-readable component statuses

### Chatbot
- `POST /chatbot/ask` - Ask the RAG chatbot
- `POST /chatbot/sync` - Sync knowledge documents to Qdrant (internal, API key protected)
- `POST /chatbot/feedback` - Submit feedback on chatbot response

### Support
- `POST /support/email/incoming` - Process incoming support email
- `POST /support/email/reply/{email_id}` - Send reply to support email
- `POST /support/email/escalate/{email_id}` - Escalate to human support

### Translation
- `POST /translate/text` - Translate text between languages

### ML/AI
- `GET /ml/models` - List loaded ML models

### Matching
- `GET /match/events` - Get event matches for user (supports Nominatim geocoding via `location` query param)

### Recommendations
- `GET /recommendations/events` - Get personalized event recommendations
- `GET /recommendations/hobbies` - Get hobby recommendations

### Rewards
- `GET /rewards/suggestion` - Get reward/coupon suggestion for user

### Predictions
- `POST /predict/attendance` - Predict event attendance (Prophet + sklearn)
- `GET /predict/trends` - Get trending predictions

### Host/Event Rating
- `GET /host/{host_id}/rating` - Get host quality score (weighted formula)
- `POST /event/{event_id}/rating` - Submit event rating

### Ads Intelligence
- `GET /ads/audience-match` - Get matching audience for ad
- `GET /ads/performance-predict` - Predict ad performance

### NLP
- `POST /nlp/sentiment` - Analyze text sentiment
- `POST /nlp/keywords` - Extract keywords from text
- `GET /nlp/trends` - Get trending topics

### Moderation
- `POST /moderation` - Submit content for moderation
- `GET /moderation/{content_id}` - Get moderation status

### Pricing
- `GET /pricing/optimise` - Get optimized pricing for event

### Discount
- `GET /discount/suggestion` - Get discount suggestions

### Taxonomy
- `GET /taxonomy/interests` - Get canonical interest taxonomy (supports `updated_since` for incremental sync)
- `GET /taxonomy/interests/{interest_id}` - Get single interest by ID
- `POST /taxonomy/interests` - Create new interest
- `PATCH /taxonomy/interests/{interest_id}` - Update interest
- `DELETE /taxonomy/interests/{interest_id}` - Deprecate interest (soft delete)
- `GET /taxonomy/categories` - List all interest categories

### i18n (Internationalization)
- `GET /i18n/{language}?scope=common` - Lazy load translations by scope
- `GET /i18n/{language}/multiple?scopes=common,events` - Load multiple scopes
- `GET /i18n/{language}/{scope}/{key}` - Get single translation string
- `POST /i18n/{language}/string` - Set translation string
- `POST /i18n/{language}/bulk` - Bulk import translations
- `POST /i18n/{language}/{scope}/{key}/approve` - Approve translation for production

### No-Show Prediction (Behavioral Forecasting)
- `POST /ml/no-show/predict` - Predict no-show probability for a booking
- `POST /ml/no-show/outcome` - Record actual attendance outcome (feedback loop)
- `POST /ml/no-show/batch-predict` - Batch prediction for forecasting dashboards
- `POST /ml/no-show/update-profile/{user_id}` - Update user attendance profile

### Attendance Verification (Trust & Fraud Detection)
- `POST /ml/attendance/verify` - Verify check-in attempt with multi-signal analysis
- `POST /ml/attendance/support-decision` - Record support team decision (feedback loop)
- `GET /ml/attendance/history` - Get verification audit trail

## Development

### Local Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Start services (PostgreSQL, Redis, Qdrant)
docker-compose up -d postgres redis qdrant

# Run API locally
uvicorn kumele_ai.main:app --reload --host 0.0.0.0 --port 8000

# Run worker locally
celery -A kumele_ai.worker.celery_app worker --loglevel=info
```

### Project Structure

```
kumele_ai/
├── __init__.py
├── config.py           # Configuration management
├── main.py             # FastAPI application
├── dependencies.py     # Dependency injection
├── api/                # API routers
│   ├── system.py
│   ├── chatbot.py
│   ├── support.py
│   ├── translate.py
│   ├── ml.py
│   ├── matching.py
│   ├── recommendations.py
│   ├── rewards.py
│   ├── predictions.py
│   ├── host.py
│   ├── events.py
│   ├── ads.py
│   ├── nlp.py
│   ├── moderation.py
│   ├── pricing.py
│   ├── discount.py
│   ├── taxonomy.py     # Interest taxonomy API
│   └── i18n.py         # Internationalization API
├── services/           # Business logic
│   ├── llm_service.py
│   ├── embed_service.py
│   ├── classify_service.py
│   ├── translate_service.py
│   ├── email_service.py
│   ├── rewards_service.py
│   ├── matching_service.py
│   ├── recommendation_service.py
│   ├── forecast_service.py
│   ├── pricing_service.py
│   ├── ads_service.py
│   ├── moderation_service.py
│   ├── chatbot_service.py
│   ├── support_service.py
│   ├── nlp_service.py
│   ├── host_service.py
│   ├── event_service.py
│   ├── geocode_service.py
│   ├── stream_service.py      # Redis Streams for near-real-time events
│   ├── taxonomy_service.py    # Interest taxonomy management
│   ├── i18n_service.py        # Internationalization service
│   ├── no_show_service.py     # No-show probability prediction
│   └── attendance_verification_service.py  # Check-in fraud detection
├── models/             # ML model registry
│   └── registry.py
├── db/                 # Database layer
│   ├── database.py
│   ├── models.py
│   └── schema.sql
└── worker/             # Async task processing
    ├── celery_app.py
    └── tasks.py

docker/
├── Dockerfile.api
├── Dockerfile.worker
└── docker-compose.yml

scripts/
└── generate_data.py    # Synthetic data generator
```

## Troubleshooting

### LLM Not Responding
- Ensure Mistral container is running: `docker-compose logs mistral`
- Check GPU availability if using GPU inference
- Verify `LLM_API_URL` is correct

### Qdrant Connection Issues
- Verify Qdrant is running: `docker-compose logs qdrant`
- Check collection exists: `curl http://localhost:6333/collections`

### Translation Errors
- Ensure Argos/LibreTranslate is running: `docker-compose logs argos`
- Language models are downloaded on first use

### Database Errors
- Run migrations: `docker-compose exec api alembic upgrade head`
- Check connection: `docker-compose exec postgres psql -U postgres -d kumele`

## License

Proprietary - Kumele Platform
