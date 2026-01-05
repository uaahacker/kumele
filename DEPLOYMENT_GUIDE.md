# Kumele AI/ML Backend - Deployment & Testing Guide

## 🚀 Quick Reference Commands

```bash
# Navigate to project
cd /home/kumele

# Stop all containers
docker-compose down

# Rebuild and start (detached)
docker-compose up -d --build

# View logs
docker-compose logs -f api
docker-compose logs -f worker

# Access Swagger UI
# http://YOUR_IP:8000/docs
```

---

## 📋 Complete Deployment Steps

### Step 1: Update Code (If needed)

```bash
cd /home/kumele
git pull  # If using git
# Or upload files via SFTP/SCP
```

### Step 2: Stop Running Containers

```bash
docker-compose down
```

### Step 3: Rebuild and Start

```bash
# Full rebuild (recommended after code changes)
docker-compose up -d --build

# Quick restart (no rebuild)
docker-compose up -d
```

### Step 4: Wait for Services to Start

```bash
# Check container status
docker ps

# Wait until all containers show "healthy" or "Up"
# API should show "healthy" after ~30 seconds
```

### Step 5: Initialize Database Schema

The schema is auto-created by SQLAlchemy on first run. To manually load test data:

```bash
# Copy SQL file to container
docker cp scripts/load_data.sql kumele-postgres:/tmp/load_data.sql

# Load data into PostgreSQL
docker exec -it kumele-postgres psql -U kumele -d kumele_db -f /tmp/load_data.sql
```

---

## 📊 Load Test Data into PostgreSQL

### Option A: Use Existing SQL File

```bash
# Copy and execute load_data.sql
docker cp scripts/load_data.sql kumele-postgres:/tmp/load_data.sql
docker exec -it kumele-postgres psql -U kumele -d kumele_db -f /tmp/load_data.sql
```

### Option B: Generate Fresh Synthetic Data

```bash
# Run the Python generator (inside container or host)
docker exec -it kumele-api python scripts/generate_synthetic_data.py

# Or from host with venv
source /home/venv/bin/activate
python scripts/generate_synthetic_data.py
```

### Option C: Manual Data via psql

```bash
# Connect to PostgreSQL
docker exec -it kumele-postgres psql -U kumele -d kumele_db

# Inside psql:
\dt              -- List all tables
SELECT * FROM users LIMIT 5;
SELECT COUNT(*) FROM events;
\q               -- Exit
```

---

## 🧪 Testing APIs via Swagger UI

### Access Swagger
Open in browser: `http://YOUR_SERVER_IP:8000/docs`

### Test Order (Recommended)

#### 1️⃣ Health Check (First!)
```
GET /ai/health
```
Expected: All components should show "healthy" or "degraded" (TGI may take time)

#### 2️⃣ System APIs
```
GET /ready
GET /health
GET /ai/models
GET /ai/stats
```

#### 3️⃣ Rating System
```
POST /ratings/submit
{
  "host_id": "1",
  "event_id": "1", 
  "attendee_id": "2",
  "rating": 4.5,
  "comment": "Great event!"
}

GET /ratings/host/1
```

#### 4️⃣ Recommendations
```
GET /recommendations/events?user_id=1&limit=5
GET /recommendations/hobbies?user_id=1
GET /recommendations/content/1?content_type=event
```

#### 5️⃣ NLP & Sentiment
```
POST /nlp/sentiment
{
  "text": "This event was absolutely amazing! Best experience ever.",
  "content_id": "test-1",
  "content_type": "review"
}

POST /nlp/keywords
{
  "text": "Join our outdoor hiking adventure in the mountains. Perfect for nature lovers and fitness enthusiasts.",
  "max_keywords": 5
}
```

#### 6️⃣ Content Moderation
```
POST /moderation/text
{
  "text": "Hello everyone! Looking forward to the meetup.",
  "content_id": "test-mod-1",
  "content_type": "message"
}
```

#### 7️⃣ Chatbot
```
POST /chatbot/ask
{
  "question": "How do I create an event?",
  "user_id": "user-1",
  "language": "en"
}

POST /chatbot/sync
{
  "document_id": "faq-1",
  "title": "How to Create Events",
  "content": "To create an event, go to the Events page and click Create New Event...",
  "category": "faq"
}
```

#### 8️⃣ Translation
```
POST /translate/text
{
  "text": "Hello, how are you?",
  "source_language": "en",
  "target_language": "fr"
}

POST /translate/detect?text=Bonjour comment allez-vous

GET /translate/languages
```

#### 9️⃣ Pricing
```
GET /pricing/optimise?event_id=1&base_price=50&event_date=2026-02-15T10:00:00

GET /discount/suggestion?user_id=1&event_id=1
```

#### 🔟 Support Email
```
POST /support/email/incoming
{
  "from_email": "customer@example.com",
  "subject": "Need help with booking",
  "body": "Hi, I'm having trouble completing my booking for the hiking event. The payment keeps failing.",
  "user_id": "user-1"
}

GET /support/email/list
```

#### 1️⃣1️⃣ Advertising
```
POST /ads/predict
{
  "ad_id": "ad-123",
  "campaign_id": "camp-1",
  "ad_type": "banner",
  "target_audience": {
    "age_range": [25, 45],
    "interests": ["outdoor", "fitness"],
    "location": "New York"
  },
  "budget": 500
}

GET /ads/segments?event_id=1
```

#### 1️⃣2️⃣ Rewards
```
GET /rewards/user/1
POST /rewards/action
{
  "user_id": "1",
  "action_type": "event_attendance",
  "metadata": {"event_id": "1"}
}
```

#### 1️⃣3️⃣ Taxonomy
```
GET /taxonomy/interests?language=en
GET /taxonomy/interests?updated_since=2025-01-01T00:00:00
```

#### 1️⃣4️⃣ i18n
```
GET /i18n/en?scope=common
GET /i18n/ar?scope=common
```

---

## 🔍 Troubleshooting

### Container Not Starting
```bash
# Check logs
docker-compose logs api
docker-compose logs worker

# Common issues:
# - Port already in use: Change ports in docker-compose.yml
# - Database connection: Check POSTGRES_* env vars
```

### Database Connection Error
```bash
# Check PostgreSQL is running
docker exec -it kumele-postgres pg_isready

# Verify connection
docker exec -it kumele-postgres psql -U kumele -d kumele_db -c "SELECT 1"
```

### Redis Connection Error
```bash
# Check Redis
docker exec -it kumele-redis redis-cli ping
# Should return: PONG
```

### API Returns 500 Error
```bash
# Check API logs
docker-compose logs -f api

# Common causes:
# - Missing environment variables
# - Database schema not created
# - External service (Qdrant, Redis) not ready
```

### Worker Not Processing Tasks
```bash
# Check worker logs
docker-compose logs -f worker

# Check Flower dashboard
# http://YOUR_IP:5555

# Verify Redis queue
docker exec -it kumele-redis redis-cli LLEN celery
```

### TGI/LLM Not Working
```bash
# TGI needs GPU or takes time to load models
# Check logs:
docker-compose logs tgi

# The API will fallback to mock responses if TGI is unavailable
```

### LibreTranslate Not Working
```bash
# First startup downloads language models (takes 5-10 minutes)
docker-compose logs libretranslate

# Check status
curl http://localhost:5000/languages
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Container orchestration |
| `.env` | Environment variables |
| `scripts/load_data.sql` | Test data SQL |
| `app/main.py` | FastAPI entry point |
| `app/models/database_models.py` | Database schemas |
| `worker/celery_app.py` | Celery configuration |

---

## 🔄 Full Reset (Nuclear Option)

If something is broken and you need a clean start:

```bash
# Stop everything
docker-compose down

# Remove ALL data volumes (WARNING: deletes all data!)
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Full rebuild
docker-compose up -d --build

# Reload test data
docker cp scripts/load_data.sql kumele-postgres:/tmp/load_data.sql
docker exec -it kumele-postgres psql -U kumele -d kumele_db -f /tmp/load_data.sql
```

---

## 📊 Monitoring

### Flower (Celery Dashboard)
```
http://YOUR_IP:5555
```

### Qdrant Dashboard
```
http://YOUR_IP:6333/dashboard
```

### API Health
```
http://YOUR_IP:8000/ai/health
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] `GET /ai/health` returns status
- [ ] `GET /docs` loads Swagger UI
- [ ] Database has test data: `SELECT COUNT(*) FROM users`
- [ ] Redis responds: `docker exec kumele-redis redis-cli ping`
- [ ] Worker is processing: Check Flower at :5555
- [ ] Translation works: `POST /translate/text`
- [ ] Recommendations work: `GET /recommendations/events?user_id=1`

---

## 🆘 Getting Help

If you encounter errors:
1. Copy the exact error message
2. Check which API endpoint failed
3. Check container logs: `docker-compose logs api`
4. Share the output for debugging
