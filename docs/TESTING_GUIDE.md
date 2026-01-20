# Kumele AI/ML API Testing Guide

This guide explains how to test all the API endpoints after deployment.

## Prerequisites

1. Server running with Docker containers up
2. Database migrated and seeded
3. API accessible at `http://your-server:8000`

---

## Quick Setup Commands

### On the Server (SSH)

```bash
# Navigate to project
cd /home/kumele

# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Run migrations
docker-compose exec api python scripts/migrate_add_columns.py

# Seed database (with clear for fresh start)
docker-compose exec api python scripts/seed_database.py --clear

# Check logs
docker logs kumele_api -f
```

---

## Testing with cURL

### 1. Health Check
```bash
curl http://localhost:8000/
curl http://localhost:8000/health
```

### 2. Check-in API

#### Validate Check-in (GPS mode)
```bash
curl -X POST http://localhost:8000/checkin/validate \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": 1,
    "user_id": 1,
    "mode": "self_check",
    "user_latitude": 40.7128,
    "user_longitude": -74.0060
  }'
```

#### Verify Check-in
```bash
curl -X POST http://localhost:8000/checkin/verify \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": 1,
    "user_id": 1,
    "latitude": 40.7128,
    "longitude": -74.0060,
    "device_hash": "abc123"
  }'
```

#### Fraud Detection
```bash
curl -X POST http://localhost:8000/checkin/fraud-detect \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": 1,
    "user_id": 1,
    "device_hash": "abc123",
    "latitude": 40.7128,
    "longitude": -74.0060
  }'
```

#### Host Compliance
```bash
curl http://localhost:8000/checkin/host/1/compliance
```

### 3. NFT Badge API

#### Check Eligibility
```bash
curl http://localhost:8000/nft/badge/eligibility/1
```

#### Issue Badge
```bash
curl -X POST http://localhost:8000/nft/badge/issue \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1}'
```

#### Get Trust Score
```bash
curl http://localhost:8000/nft/trust-score/1
```

#### Host Priority
```bash
curl http://localhost:8000/nft/host-priority/1
```

#### Discount Eligibility
```bash
curl http://localhost:8000/nft/discount-eligibility/1
```

#### Payment Reliability
```bash
curl http://localhost:8000/nft/payment-reliability/1
```

### 4. Chat Room API

#### Create Chat Room
```bash
curl -X POST http://localhost:8000/chat/rooms \
  -H "Content-Type: application/json" \
  -d '{"event_id": 1, "chat_type": "event"}'
```

#### Join Chat
```bash
curl -X POST "http://localhost:8000/chat/rooms/1/join?user_id=1"
```

#### Send Message
```bash
curl -X POST "http://localhost:8000/chat/rooms/1/messages?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello everyone!"}'
```

#### Get Messages
```bash
curl http://localhost:8000/chat/rooms/1/messages
```

#### Moderate Message
```bash
curl -X POST http://localhost:8000/chat/rooms/1/messages/1/moderate \
  -H "Content-Type: application/json" \
  -d '{"message_id": 1, "action": "approve"}'
```

#### Auto-Moderate Chat
```bash
curl -X POST http://localhost:8000/chat/rooms/1/auto-moderate
```

#### Get Chat Popularity
```bash
curl http://localhost:8000/chat/rooms/1/popularity
```

#### Get Chat Sentiment
```bash
curl http://localhost:8000/chat/rooms/1/sentiment
```

### 5. Payment Window API

#### Create Payment Window
```bash
curl -X POST http://localhost:8000/payment/window/create \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "event_id": 1,
    "amount": 25.00,
    "window_minutes": 15
  }'
```

#### Get Window Status
```bash
curl http://localhost:8000/payment/window/1
```

#### Complete Payment
```bash
curl -X POST http://localhost:8000/payment/window/1/complete
```

#### Get Urgency
```bash
curl http://localhost:8000/payment/urgency/event/1
```

### 6. Matching API (with Filters)

#### Match Events with Filters
```bash
curl "http://localhost:8000/match/events?user_id=1&limit=10&min_age=18&max_age=40&verified_hosts_only=true"
```

#### Events with Capacity
```bash
curl "http://localhost:8000/match/events/with-capacity?user_id=1"
```

#### Events by Host Reputation
```bash
curl "http://localhost:8000/match/events/by-host-reputation?user_id=1"
```

### 7. Moderation API

#### Moderate Image
```bash
curl -X POST http://localhost:8000/moderation/image \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg",
    "context": "profile_photo"
  }'
```

#### Moderate Text
```bash
curl -X POST http://localhost:8000/moderation/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world!",
    "context": "chat_message"
  }'
```

### 8. Predictions API

#### Predict Attendance
```bash
curl -X POST http://localhost:8000/predict/attendance \
  -H "Content-Type: application/json" \
  -d '{
    "hobby": "hiking",
    "location": "New York",
    "date": "2026-02-15T14:00:00",
    "is_paid": false,
    "host_experience": 5,
    "host_rating": 4.5,
    "capacity": 20
  }'
```

#### Predict No-Show
```bash
curl http://localhost:8000/predict/noshow/1
```

---

## Testing with Python

```python
import requests

BASE_URL = "http://localhost:8000"

# Health check
r = requests.get(f"{BASE_URL}/health")
print(r.json())

# Check-in verify
r = requests.post(f"{BASE_URL}/checkin/verify", json={
    "event_id": 1,
    "user_id": 1,
    "latitude": 40.7128,
    "longitude": -74.0060
})
print(r.json())

# NFT badge eligibility
r = requests.get(f"{BASE_URL}/nft/badge/eligibility/1")
print(r.json())

# Fraud detection
r = requests.post(f"{BASE_URL}/checkin/fraud-detect", json={
    "event_id": 1,
    "user_id": 1,
    "device_hash": "test123",
    "latitude": 40.7128,
    "longitude": -74.0060
})
print(r.json())
```

---

## Swagger UI Testing

Open in browser: `http://your-server:8000/docs`

All endpoints are documented with request/response examples.

---

## Expected Responses

### Successful Check-in Verify
```json
{
  "verified": true,
  "status": "verified",
  "confidence": 0.75,
  "geo_distance_km": 0.5,
  "device_trusted": true,
  "message": "Check-in verified"
}
```

### Fraud Detection (Clean)
```json
{
  "score": 0.05,
  "decision": "clean",
  "reason": "No significant risk factors detected",
  "risk_factors": [],
  "recommendations": ["Allow check-in"]
}
```

### Fraud Detection (Suspicious)
```json
{
  "score": 0.65,
  "decision": "suspicious",
  "reason": "Device has 2 previous fraud flags",
  "risk_factors": ["Device has 2 previous fraud flags"],
  "recommendations": ["Allow with manual review", "Monitor user activity"]
}
```

### NFT Badge Eligibility
```json
{
  "user_id": 1,
  "verified_events": 12,
  "current_badge": "Bronze",
  "eligible_for": "Bronze",
  "next_tier": "Silver",
  "events_until_next": 3,
  "trust_boost": 0.02,
  "discount_percent": 2.0,
  "priority_matching": false
}
```

---

## Troubleshooting

### API Not Starting
```bash
# Check container logs
docker logs kumele_api

# Common issues:
# - Missing environment variables
# - Database connection failed
# - Import errors (missing files)
```

### Database Errors
```bash
# Check PostgreSQL
docker logs kumele_db

# Connect to database
docker-compose exec db psql -U kumele -d kumele

# Check tables exist
\dt
```

### Migration Errors
```bash
# Run migration manually
docker-compose exec api python scripts/migrate_add_columns.py

# If tables missing, recreate
docker-compose exec api python -c "from kumele_ai.db.database import engine; from kumele_ai.db.models import Base; Base.metadata.create_all(bind=engine)"
```

### Seed Errors
```bash
# Run with verbose output
docker-compose exec api python scripts/seed_database.py --clear 2>&1 | tee seed.log
```

---

## Endpoint Summary

| Category | Endpoint | Method | Description |
|----------|----------|--------|-------------|
| **Check-in** | /checkin/validate | POST | Validate check-in |
| | /checkin/verify | POST | Verify with geo/device |
| | /checkin/fraud-detect | POST | Fraud detection |
| | /checkin/host/{id}/compliance | GET | Host compliance rate |
| **NFT** | /nft/badge/eligibility/{id} | GET | Badge eligibility |
| | /nft/badge/issue | POST | Issue badge |
| | /nft/trust-score/{id} | GET | Trust score |
| | /nft/host-priority/{id} | GET | Host priority |
| | /nft/discount-eligibility/{id} | GET | Discount eligibility |
| **Chat** | /chat/rooms | POST | Create chat room |
| | /chat/rooms/{id}/messages | GET/POST | Messages |
| | /chat/rooms/{id}/auto-moderate | POST | Auto-moderate |
| | /chat/rooms/{id}/popularity | GET | Popularity score |
| | /chat/rooms/{id}/sentiment | GET | Sentiment analysis |
| **Payment** | /payment/window/create | POST | Create window |
| | /payment/window/{id}/complete | POST | Complete payment |
| | /payment/urgency/event/{id} | GET | Urgency level |
| **Matching** | /match/events | GET | Match with filters |
| | /match/events/with-capacity | GET | With capacity info |
| | /match/events/by-host-reputation | GET | By host reputation |
| **Moderation** | /moderation/image | POST | Moderate image |
| | /moderation/text | POST | Moderate text |
