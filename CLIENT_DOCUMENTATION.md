# Kumele AI/ML Backend - Client Documentation

## 📋 Table of Contents
1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [API Endpoints](#api-endpoints)
4. [Configuration](#configuration)
5. [Database Schema](#database-schema)
6. [Integration Guide](#integration-guide)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This is the **AI/ML Backend** for the Kumele platform. It provides intelligent services via REST APIs:

| Service | What It Does |
|---------|--------------|
| **Recommendations** | Suggests events & hobbies based on user preferences |
| **Event Matching** | Finds nearby relevant events using location + interests |
| **Rewards System** | Rules-based gamification (Bronze/Silver/Gold tiers) |
| **Predictions** | Forecasts attendance, best times, demand |
| **Host Ratings** | 70% attendee rating + 30% system reliability |
| **Ads Intelligence** | Audience matching + CTR prediction |
| **NLP Analysis** | Sentiment, keywords, trending topics |
| **Content Moderation** | Text toxicity + image NSFW detection |
| **AI Chatbot** | RAG-based Q&A using your knowledge base |
| **Translation** | Multi-language support (6 languages) |
| **Support Automation** | Email classification + auto-routing |

---

## Quick Start

### Step 1: Prerequisites
- Docker & Docker Compose installed
- 4GB+ RAM (8GB recommended)

### Step 2: Clone & Configure
```bash
# Clone the repository
git clone <your-repo-url>
cd newapi

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### Step 3: Set Required API Keys
Edit `.env` file:
```env
# Required for AI Chatbot (FREE)
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Optional for image moderation
HUGGINGFACE_API_KEY=hf_your-key-here
```

Get free OpenRouter key: https://openrouter.ai/keys

### Step 4: Start Services
```bash
docker-compose up -d
```

### Step 5: Verify Installation
```bash
# Check all services are running
docker-compose ps

# Test API
curl http://localhost:8000/

# Open documentation
# Visit: http://localhost:8000/docs
```

---

## API Endpoints

### 🎯 Recommendations & Matching

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/recommendations/hobbies` | GET | Get hobby suggestions for user |
| `/recommendations/events` | GET | Get personalized event recommendations |
| `/match/events` | GET | Find nearby relevant events |
| `/match/geocode` | POST | Convert address to coordinates |

**Example - Get Event Recommendations:**
```bash
curl "http://localhost:8000/recommendations/events?user_id=user-123&limit=10"
```

**Example - Match Events by Location:**
```bash
curl "http://localhost:8000/match/events?user_id=user-123&lat=51.5074&lon=-0.1278&max_distance_km=50"
```

---

### 🏆 Rewards & Gamification

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/rewards/suggestion` | GET | Get user's tier status & available rewards |
| `/rewards/progress/{user_id}` | GET | Full progress history |
| `/rewards/coupons/{user_id}` | GET | List available coupons |
| `/rewards/redeem/{coupon_id}` | POST | Redeem a coupon |

**Tier Rules:**
| Tier | Events in 30 Days | Discount |
|------|-------------------|----------|
| Bronze | 1+ | 0% |
| Silver | 3+ | 4% |
| Gold | 4+ | 8% per Gold (stacks!) |

**Example:**
```bash
curl "http://localhost:8000/rewards/suggestion?user_id=user-123"
```

---

### 📊 Predictions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict/attendance` | POST | Predict event attendance |
| `/predict/trends` | GET | Best day/time to host |
| `/predict/demand/{category}` | GET | Category demand forecast |
| `/predict/no-show-rate` | GET | No-show probability |

**Example - Predict Attendance:**
```bash
curl -X POST "http://localhost:8000/predict/attendance" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "event-123",
    "category": "cooking",
    "location": "london",
    "capacity": 50,
    "is_free": false,
    "days_until_event": 7
  }'
```

---

### ⭐ Ratings

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ratings/host/{host_id}` | GET | Get host rating summary |
| `/ratings/submit` | POST | Submit event rating |
| `/ratings/event/{event_id}` | GET | Get event ratings |

**Rating Formula:**
```
Host Score = (0.7 × Attendee Rating) + (0.3 × System Reliability)
```

---

### 📢 Advertising

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ads/audience-match` | POST | Match audience segments |
| `/ads/performance-predict` | POST | Predict CTR & engagement |
| `/ads/segments` | GET | List audience segments |
| `/ads/target` | POST | Get target audience for ad |

---

### 📝 NLP Analysis

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/nlp/sentiment` | POST | Analyze text sentiment |
| `/nlp/keywords` | POST | Extract keywords |
| `/nlp/entities` | POST | Extract named entities |
| `/nlp/trends` | GET | Get trending topics |

**Example - Sentiment Analysis:**
```bash
curl -X POST "http://localhost:8000/nlp/sentiment" \
  -H "Content-Type: application/json" \
  -d '{"text": "I loved this event! It was amazing!"}'
```

Response:
```json
{
  "sentiment": "positive",
  "score": 0.92,
  "confidence": 0.89
}
```

---

### 🛡️ Content Moderation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/moderation` | POST | Check content for violations |
| `/moderation/{content_id}` | GET | Get moderation status |
| `/moderation/queue/pending` | GET | Get items needing review |
| `/moderation/{content_id}/review` | POST | Submit manual review |

**Example - Moderate Text:**
```bash
curl -X POST "http://localhost:8000/moderation" \
  -H "Content-Type: application/json" \
  -d '{
    "content_type": "text",
    "text": "This is a great community event!"
  }'
```

**Example - Moderate Image:**
```bash
curl -X POST "http://localhost:8000/moderation" \
  -H "Content-Type: application/json" \
  -d '{
    "content_type": "image",
    "image_url": "https://example.com/image.jpg"
  }'
```

---

### 🤖 AI Chatbot

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chatbot/ask` | POST | Ask the chatbot a question |
| `/chatbot/sync` | POST | Add document to knowledge base |
| `/chatbot/feedback` | POST | Submit feedback on response |
| `/chatbot/documents` | GET | List knowledge documents |
| `/chatbot/history/{user_id}` | GET | Get chat history |

**Example - Ask Chatbot:**
```bash
curl -X POST "http://localhost:8000/chatbot/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I create an event?",
    "user_id": "user-123"
  }'
```

**Example - Add Knowledge Document:**
```bash
curl -X POST "http://localhost:8000/chatbot/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "faq-001",
    "title": "How to Create Events",
    "content": "To create an event: 1. Go to Events tab 2. Click Create 3. Fill in details 4. Publish",
    "category": "faq"
  }'
```

---

### 🌐 Translation & i18n

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/translate` | POST | Translate text |
| `/translate/detect` | POST | Detect language |
| `/translate/languages` | GET | List supported languages |
| `/i18n/{language}` | GET | Get UI strings for language |
| `/admin/i18n/strings` | POST | Add UI string |
| `/admin/i18n/submit` | POST | Submit translation |
| `/admin/i18n/approve` | POST | Approve translation |

**Supported Languages:** English, French, Spanish, Chinese, Arabic, German

**Example - Translate:**
```bash
curl -X POST "http://localhost:8000/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "source_language": "en",
    "target_language": "es"
  }'
```

---

### 💰 Pricing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/pricing/optimise` | GET | Get optimized price suggestion |
| `/pricing/history/{event_id}` | GET | Get pricing history |
| `/discount/suggest` | GET | Get discount suggestions |

---

### 📧 Support

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/support/email/incoming` | POST | Process incoming email |
| `/support/email/reply/{id}` | POST | Send reply |
| `/support/email/escalate/{id}` | POST | Escalate to tier 2 |
| `/support/email/queue` | GET | Get email queue |
| `/support/email/stats` | GET | Get support statistics |

---

### 📂 Taxonomy

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/taxonomy/interests` | GET | Get interest hierarchy |
| `/taxonomy/interests/flat` | GET | Get flat list |
| `/taxonomy/interests/{id}` | GET | Get interest details |

---

### ❤️ Health & Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ai/health` | GET | Full system health check |
| `/ready` | GET | Readiness probe |
| `/live` | GET | Liveness probe |

---

## Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection | `postgresql+asyncpg://user:pass@host/db` |
| `REDIS_URL` | Yes | Redis connection | `redis://localhost:6379` |
| `QDRANT_URL` | Yes | Qdrant vector DB | `http://localhost:6333` |
| `OPENROUTER_API_KEY` | Yes* | LLM access (free) | `sk-or-v1-xxx` |
| `TRANSLATE_URL` | No | LibreTranslate URL | `http://localhost:5000` |
| `HUGGINGFACE_API_KEY` | No | Image moderation | `hf_xxx` |

*Required for AI chatbot to work properly

---

## Database Schema

The API uses these main tables:

| Table | Purpose |
|-------|---------|
| `users` | User profiles |
| `events` | Event data |
| `user_hobbies` | User interests |
| `event_ratings` | Event ratings |
| `user_activities` | Activity log (for rewards) |
| `reward_coupons` | Issued coupons |
| `moderation_jobs` | Moderation queue |
| `chatbot_logs` | Chat history |
| `knowledge_documents` | Chatbot knowledge |
| `ui_strings` | i18n strings |
| `ui_translations` | Translations |
| `interest_taxonomy` | Hobby categories |

Tables are **auto-created** on first startup.

---

## Integration Guide

### How to Connect Your App

**1. Your Main Backend → This AI API**
```
Your Backend writes to PostgreSQL (users, events, interactions)
     ↓
This AI API reads from same PostgreSQL
     ↓
Your Frontend calls AI API endpoints
```

**2. Example Flow - Get Recommendations:**
```
1. User opens app
2. Frontend calls: GET /recommendations/events?user_id=xxx
3. AI API reads user's hobbies + interactions from DB
4. AI API computes personalized recommendations
5. Returns ranked event list to frontend
```

**3. Example Flow - Chatbot:**
```
1. Admin syncs FAQ docs via POST /chatbot/sync
2. User asks question via POST /chatbot/ask
3. AI finds relevant docs + generates answer
4. User submits feedback via POST /chatbot/feedback
```

---

## Testing

### Using Swagger UI
1. Open `http://localhost:8000/docs`
2. Click on any endpoint
3. Click "Try it out"
4. Fill in parameters
5. Click "Execute"

### Using Testing Helpers
The API includes testing endpoints at `/testing/*`:

| Endpoint | Purpose |
|----------|---------|
| `/testing/generate-uuid` | Generate test UUID |
| `/testing/generate-test-user` | Generate sample user data |
| `/testing/generate-test-event` | Generate sample event data |
| `/testing/test-sentiment` | Quick sentiment test |
| `/testing/test-chatbot` | Quick chatbot test |

### Load Synthetic Data
```bash
# Run the data generator
python scripts/generate_synthetic_data.py

# This creates test data in the database
```

---

## Troubleshooting

### Common Issues

**1. "Connection refused" errors**
```bash
# Check if services are running
docker-compose ps

# Restart services
docker-compose restart
```

**2. Chatbot returns generic responses**
```bash
# Check if OpenRouter key is set
grep OPENROUTER .env

# Sync some knowledge documents first
curl -X POST http://localhost:8000/chatbot/sync -d '...'
```

**3. Empty recommendations**
- Database has no data yet
- Load synthetic data or connect your main backend

**4. LLM health shows "unhealthy"**
- Add `OPENROUTER_API_KEY` to `.env`
- Get free key at: https://openrouter.ai/keys

### Logs
```bash
# View API logs
docker-compose logs -f api

# View all logs
docker-compose logs -f
```

### Reset Everything
```bash
docker-compose down -v
docker-compose up -d
```

---

## Support

For technical issues:
- Check `/ai/health` endpoint first
- Review logs: `docker-compose logs api`
- Contact: [your-email]

---

**Version:** 1.0.0  
**Last Updated:** December 2024
