# Kumele AI/ML Backend API Documentation

## 📚 Complete API Reference for Client Presentation

> **Base URL**: `http://YOUR_SERVER_IP:8000`  
> **Last Updated**: 2025  
> **Total Endpoints**: ~100+

---

## 🚀 Quick Start

### Test Server Health
```bash
curl http://localhost:8000/health
```
**Expected Response**:
```json
{"status": "healthy", "timestamp": "2025-01-15T10:30:00Z"}
```

---

## 📋 Table of Contents

1. [Health & System](#1-health--system-endpoints)
2. [Location Matching](#2-location-matching-endpoints)
3. [Recommendations](#3-recommendation-endpoints)
4. [Ratings](#4-rating-endpoints)
5. [NLP Processing](#5-nlp-processing-endpoints)
6. [Content Moderation](#6-content-moderation-endpoints)
7. [Chatbot/RAG](#7-chatbot-rag-endpoints)
8. [Translation](#8-translation-endpoints)
9. [Support Email](#9-support-email-endpoints)
10. [Dynamic Pricing](#10-pricing-endpoints)
11. [Rewards](#11-rewards-endpoints)
12. [Predictions](#12-prediction-endpoints)
13. [Advertising](#13-advertising-endpoints)
14. [Taxonomy](#14-taxonomy-endpoints)
15. [Internationalization](#15-i18n-endpoints)
16. [Feedback Analysis](#16-feedback-analysis-endpoints)
17. [User Retention](#17-engagement-retention-endpoints)
18. [Testing Utilities](#18-testing-helper-endpoints)

---

## 1. Health & System Endpoints

### 1.1 Root Endpoint
```bash
curl http://localhost:8000/
```
**Response**:
```json
{
  "service": "Kumele AI/ML Backend",
  "version": "1.0.0",
  "status": "operational"
}
```

### 1.2 Readiness Probe
```bash
curl http://localhost:8000/ready
```

### 1.3 Liveness Probe
```bash
curl http://localhost:8000/health
```

### 1.4 Full AI Health Check
```bash
curl http://localhost:8000/ai/health
```
**Response**:
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "redis": "connected",
    "qdrant": "connected",
    "llm": "available"
  },
  "models_loaded": ["sentiment", "moderation", "embeddings"]
}
```

### 1.5 Database Health
```bash
curl http://localhost:8000/ai/health/db
```

### 1.6 Qdrant Vector DB Health
```bash
curl http://localhost:8000/ai/health/qdrant
```

### 1.7 LLM Health
```bash
curl http://localhost:8000/ai/health/llm
```

### 1.8 List AI Models
```bash
curl http://localhost:8000/ai/models
```
**Response**:
```json
{
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "sentiment_model": "cardiffnlp/twitter-roberta-base-sentiment-latest",
  "moderation_model": "unitary/toxic-bert",
  "nsfw_model": "Falconsai/nsfw_image_detection",
  "llm_mode": "openrouter"
}
```

### 1.9 AI Statistics
```bash
curl http://localhost:8000/ai/stats
```

### 1.10 Prometheus Metrics
```bash
curl http://localhost:8000/ai/metrics
```

---

## 2. Location Matching Endpoints

> Uses **OpenStreetMap Nominatim** (FREE, no API key required)

### 2.1 Geocode Address to Coordinates
```bash
curl -X POST "http://localhost:8000/match/geocode?address=Empire%20State%20Building,%20New%20York"
```
**Response**:
```json
{
  "success": true,
  "lat": 40.7484421,
  "lon": -73.9856589,
  "display_name": "Empire State Building, 350, 5th Avenue, Manhattan...",
  "source": "OpenStreetMap"
}
```

### 2.2 Match Events by Coordinates
```bash
curl "http://localhost:8000/match/events?user_id=1&lat=40.7484&lon=-73.9857&max_distance_km=50&limit=5"
```
**Response**:
```json
{
  "events": [
    {
      "event_id": 1,
      "title": "Central Park Yoga",
      "distance_km": 2.3,
      "match_score": 0.92,
      "date": "2025-02-01T09:00:00"
    }
  ],
  "total_matched": 15,
  "total_returned": 5,
  "processing_time_ms": 45
}
```

### 2.3 Match Events by Address
```bash
curl "http://localhost:8000/match/events?user_id=1&address=Central%20Park,%20New%20York&max_distance_km=25&limit=5"
```

### 2.4 Get Match Score Breakdown
```bash
curl "http://localhost:8000/match/score-breakdown/1?user_id=1"
```
**Response**:
```json
{
  "event_id": 1,
  "user_id": 1,
  "total_score": 0.87,
  "breakdown": {
    "relevance": {"weight": 0.35, "score": 0.92},
    "trust": {"weight": 0.25, "score": 0.88},
    "engagement": {"weight": 0.20, "score": 0.85},
    "freshness": {"weight": 0.10, "score": 0.80},
    "business": {"weight": 0.10, "score": 0.75}
  },
  "processing_time_ms": 12
}
```

---

## 3. Recommendation Endpoints

### 3.1 Hobby Recommendations
```bash
curl "http://localhost:8000/recommendations/hobbies/1?limit=5"
```
**Response**:
```json
{
  "user_id": 1,
  "recommendations": [
    {"hobby": "hiking", "score": 0.95, "reason": "Similar to your interest in outdoor activities"},
    {"hobby": "photography", "score": 0.88, "reason": "Popular among users like you"}
  ]
}
```

### 3.2 Event Recommendations
```bash
curl "http://localhost:8000/recommendations/events/1?limit=5"
```

### 3.3 Similar Users
```bash
curl "http://localhost:8000/recommendations/users/1?limit=5"
```

### 3.4 Two-Tower ML Recommendations
```bash
curl "http://localhost:8000/recommendations/tfrs/1?limit=5"
```

### 3.5 Generate User Embedding
```bash
curl -X POST "http://localhost:8000/recommendations/embed/user/1"
```

### 3.6 Generate Event Embedding
```bash
curl -X POST "http://localhost:8000/recommendations/embed/event/1"
```

---

## 4. Rating Endpoints

### 4.1 Get Host Rating
```bash
curl "http://localhost:8000/ratings/host/1"
```
**Response**:
```json
{
  "host_id": 1,
  "overall_rating": 4.7,
  "total_reviews": 156,
  "rating_distribution": {"5": 98, "4": 42, "3": 12, "2": 3, "1": 1},
  "dimensions": {
    "communication": 4.8,
    "respect": 4.9,
    "professionalism": 4.6,
    "atmosphere": 4.7,
    "value_for_money": 4.5
  }
}
```

### 4.2 Check Rating Eligibility
```bash
curl "http://localhost:8000/ratings/can-rate/1/5"
```
**Response**:
```json
{
  "can_rate": true,
  "reason": "User attended this event",
  "event_id": 1,
  "user_id": 5
}
```

### 4.3 Submit Event Rating
```bash
curl -X POST "http://localhost:8000/ratings/event/1/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "5",
    "communication": 4.5,
    "respect": 5.0,
    "professionalism": 4.0,
    "atmosphere": 4.5,
    "value_for_money": 4.0,
    "feedback": "Great event! Really enjoyed it."
  }'
```
**Response**:
```json
{
  "success": true,
  "rating_id": "abc123",
  "overall_score": 4.4,
  "message": "Rating submitted successfully"
}
```

### 4.4 Recalculate Host Rating
```bash
curl -X POST "http://localhost:8000/ratings/host/1/recalculate"
```

---

## 5. NLP Processing Endpoints

### 5.1 Sentiment Analysis
```bash
curl -X POST "http://localhost:8000/nlp/sentiment" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This event was absolutely amazing! Best experience ever.",
    "content_id": "review-123",
    "content_type": "review"
  }'
```
**Response**:
```json
{
  "sentiment": "POSITIVE",
  "confidence": 0.95,
  "scores": {
    "positive": 0.95,
    "neutral": 0.04,
    "negative": 0.01
  }
}
```

### 5.2 Keyword Extraction
```bash
curl -X POST "http://localhost:8000/nlp/keywords" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Join our outdoor hiking adventure in the mountains. Perfect for nature lovers and fitness enthusiasts.",
    "max_keywords": 5
  }'
```
**Response**:
```json
{
  "keywords": [
    {"keyword": "hiking", "score": 0.92},
    {"keyword": "outdoor", "score": 0.88},
    {"keyword": "mountains", "score": 0.85},
    {"keyword": "nature", "score": 0.80},
    {"keyword": "fitness", "score": 0.75}
  ]
}
```

### 5.3 Batch Sentiment Analysis
```bash
curl -X POST "http://localhost:8000/nlp/sentiment/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      "I loved this event!",
      "Terrible experience, never again.",
      "It was okay, nothing special."
    ]
  }'
```

### 5.4 Trending Topics
```bash
curl "http://localhost:8000/nlp/trending?period=7d&limit=10"
```

### 5.5 Text Summarization
```bash
curl -X POST "http://localhost:8000/nlp/summarize?text=Artificial%20intelligence%20is%20transforming%20how%20we%20live%20and%20work..."
```

---

## 6. Content Moderation Endpoints

### 6.1 Submit Text for Moderation
```bash
curl -X POST "http://localhost:8000/moderation/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "post-123",
    "content_type": "text",
    "text": "Hello everyone! Looking forward to the hiking meetup this weekend.",
    "user_id": "1"
  }'
```
**Response**:
```json
{
  "content_id": "post-123",
  "decision": "approved",
  "confidence": 0.98,
  "flags": [],
  "toxicity_score": 0.02,
  "processing_time_ms": 45
}
```

### 6.2 Submit Potentially Toxic Text
```bash
curl -X POST "http://localhost:8000/moderation/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "post-456",
    "content_type": "text",
    "text": "This is stupid and I hate everything about this terrible event.",
    "user_id": "2"
  }'
```
**Response**:
```json
{
  "content_id": "post-456",
  "decision": "flagged",
  "confidence": 0.75,
  "flags": ["toxicity"],
  "toxicity_score": 0.68,
  "requires_human_review": true
}
```

### 6.3 Submit Image for Moderation (URL)
```bash
curl -X POST "http://localhost:8000/moderation/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "img-789",
    "content_type": "image",
    "image_url": "https://example.com/image.jpg",
    "user_id": "1"
  }'
```

### 6.4 Get Moderation Queue
```bash
curl "http://localhost:8000/moderation/queue?limit=10"
```

### 6.5 Get Moderation Statistics
```bash
curl "http://localhost:8000/moderation/stats?days=7"
```
**Response**:
```json
{
  "period_days": 7,
  "total_processed": 1250,
  "approved": 1180,
  "flagged": 55,
  "rejected": 15,
  "average_processing_time_ms": 42,
  "by_content_type": {
    "text": 980,
    "image": 270
  }
}
```

---

## 7. Chatbot RAG Endpoints

### 7.1 Ask Chatbot
```bash
curl -X POST "http://localhost:8000/chatbot/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I create an event?",
    "user_id": "1",
    "language": "en"
  }'
```
**Response**:
```json
{
  "answer": "To create an event on Kumele, navigate to your dashboard and click the 'Create Event' button. Fill in the required details including title, description, date, time, location, and capacity. You can also set pricing and add images to make your event more attractive.",
  "confidence": 0.92,
  "sources": [
    {"doc_id": "faq-events", "title": "Event Creation Guide", "relevance": 0.95}
  ],
  "session_id": "sess-abc123"
}
```

### 7.2 Sync FAQ Document
```bash
curl -X POST "http://localhost:8000/chatbot/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "faq-booking",
    "title": "How to Book Events",
    "content": "To book an event, browse available events and click Book Now...",
    "category": "faq",
    "language": "en"
  }'
```

### 7.3 Get Chat History
```bash
curl "http://localhost:8000/chatbot/history/1?limit=10"
```

### 7.4 List Knowledge Documents
```bash
curl "http://localhost:8000/chatbot/documents?limit=10"
```

---

## 8. Translation Endpoints

### 8.1 Get Supported Languages
```bash
curl "http://localhost:8000/translate/languages"
```
**Response**:
```json
{
  "languages": [
    {"code": "en", "name": "English"},
    {"code": "fr", "name": "French"},
    {"code": "es", "name": "Spanish"},
    {"code": "ar", "name": "Arabic"},
    {"code": "de", "name": "German"}
  ]
}
```

### 8.2 Detect Language
```bash
curl -X POST "http://localhost:8000/translate/detect?text=Bonjour,%20comment%20allez-vous?"
```
**Response**:
```json
{
  "detected_language": "fr",
  "confidence": 0.98
}
```

### 8.3 Translate Text
```bash
curl -X POST "http://localhost:8000/translate/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how are you?",
    "source_language": "en",
    "target_language": "fr"
  }'
```
**Response**:
```json
{
  "original_text": "Hello, how are you?",
  "translated_text": "Bonjour, comment allez-vous?",
  "source_language": "en",
  "target_language": "fr"
}
```

---

## 9. Support Email Endpoints

### 9.1 Process Incoming Email
```bash
curl -X POST "http://localhost:8000/support/email/incoming" \
  -H "Content-Type: application/json" \
  -d '{
    "from_email": "customer@example.com",
    "subject": "Need help with booking",
    "body": "Hi, I'\''m having trouble completing my booking. The payment keeps failing.",
    "user_id": "1"
  }'
```
**Response**:
```json
{
  "email_id": "email-123",
  "status": "processing",
  "category": "payment",
  "priority": "high",
  "auto_response": "Thank you for contacting support. We've received your inquiry about payment issues and will respond within 24 hours.",
  "assigned_to": null,
  "sentiment": "frustrated"
}
```

### 9.2 Get Support Queue
```bash
curl "http://localhost:8000/support/email/queue?limit=10"
```

### 9.3 Get Support Statistics
```bash
curl "http://localhost:8000/support/email/stats?days=7"
```

---

## 10. Pricing Endpoints

### 10.1 Get Optimized Price
```bash
curl "http://localhost:8000/pricing/optimise?event_id=1&base_price=50&event_date=2025-02-15T09:00:00&category=outdoor&capacity=50"
```
**Response**:
```json
{
  "event_id": 1,
  "base_price": 50.0,
  "suggested_price": 62.50,
  "price_multiplier": 1.25,
  "factors": {
    "demand_surge": 1.15,
    "day_of_week": 1.05,
    "category_premium": 1.04
  },
  "confidence": 0.85
}
```

### 10.2 Get Pricing History
```bash
curl "http://localhost:8000/pricing/history/1?days=30"
```

### 10.3 Get Discount Suggestions
```bash
curl "http://localhost:8000/discount/suggestion?user_id=1&event_id=1"
```

### 10.4 Get Active Promotions
```bash
curl "http://localhost:8000/discount/active"
```

---

## 11. Rewards Endpoints

### 11.1 Get Reward Suggestions
```bash
curl "http://localhost:8000/rewards/suggest/1?include_analysis=true"
```
**Response**:
```json
{
  "user_id": 1,
  "suggested_rewards": [
    {
      "reward_type": "coupon",
      "value": 15,
      "reason": "Attended 10+ events this month",
      "expires_in_days": 30
    },
    {
      "reward_type": "badge",
      "badge_name": "Super Host",
      "reason": "Maintained 4.8+ rating for 3 months"
    }
  ],
  "user_tier": "gold",
  "points_balance": 2450
}
```

### 11.2 Get Reward Progress
```bash
curl "http://localhost:8000/rewards/progress/1"
```

### 11.3 Get User Coupons
```bash
curl "http://localhost:8000/rewards/coupons/1"
```

---

## 12. Prediction Endpoints

### 12.1 Predict Event Attendance
```bash
curl -X POST "http://localhost:8000/predict/attendance" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "1",
    "event_date": "2025-02-15T09:00:00",
    "category": "outdoor",
    "location": "New York",
    "capacity": 100,
    "host_id": "1"
  }'
```
**Response**:
```json
{
  "event_id": "1",
  "predicted_attendance": 78,
  "attendance_range": {"low": 65, "high": 92},
  "confidence": 0.82,
  "factors": {
    "host_rating": "positive",
    "category_trend": "growing",
    "weather_forecast": "favorable",
    "day_type": "weekend"
  }
}
```

### 12.2 Predict Trends
```bash
curl "http://localhost:8000/predict/trends?category=fitness&location=New%20York&days_ahead=30"
```

### 12.3 Predict Category Demand
```bash
curl "http://localhost:8000/predict/demand/outdoor?days_ahead=30"
```

### 12.4 Predict No-Show Rate
```bash
curl "http://localhost:8000/predict/no-show-rate?host_id=1&event_id=1"
```
**Response**:
```json
{
  "predicted_no_show_rate": 0.08,
  "confidence": 0.75,
  "historical_rate": 0.12,
  "factors": {
    "event_price": "low_risk",
    "host_communication": "high",
    "reminder_sent": true
  }
}
```

---

## 13. Advertising Endpoints

### 13.1 Match Ad to Audience
```bash
curl -X POST "http://localhost:8000/ads/match" \
  -H "Content-Type: application/json" \
  -d '{
    "ad_id": "1",
    "ad_content": "Join our fitness community! Special discount for new members.",
    "target_interests": ["fitness", "yoga", "running"],
    "target_locations": ["New York", "Los Angeles"],
    "target_age_min": 25,
    "target_age_max": 45
  }'
```
**Response**:
```json
{
  "ad_id": "1",
  "matched_users": 15420,
  "estimated_reach": 8500,
  "audience_quality_score": 0.78,
  "recommended_bid": 0.45
}
```

### 13.2 Predict Ad Performance
```bash
curl -X POST "http://localhost:8000/ads/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "ad_id": "1",
    "budget": 500,
    "duration_days": 7,
    "audience_segment_ids": ["fitness-enthusiasts"],
    "ad_content": "Limited time offer! 50% off all fitness events."
  }'
```
**Response**:
```json
{
  "ad_id": "1",
  "predicted_impressions": 45000,
  "predicted_clicks": 1800,
  "predicted_ctr": 0.04,
  "predicted_conversions": 90,
  "predicted_roi": 2.8,
  "confidence": 0.72
}
```

### 13.3 List Audience Segments
```bash
curl "http://localhost:8000/ads/segments?limit=10"
```

---

## 14. Taxonomy Endpoints

### 14.1 Get Interest Taxonomy (Hierarchical)
```bash
curl "http://localhost:8000/taxonomy/interests?language=en&active_only=true"
```
**Response**:
```json
{
  "taxonomy": [
    {
      "id": "sports",
      "name": "Sports & Fitness",
      "children": [
        {"id": "yoga", "name": "Yoga"},
        {"id": "running", "name": "Running"},
        {"id": "cycling", "name": "Cycling"}
      ]
    },
    {
      "id": "arts",
      "name": "Arts & Culture",
      "children": [
        {"id": "photography", "name": "Photography"},
        {"id": "painting", "name": "Painting"}
      ]
    }
  ]
}
```

### 14.2 Get Flat Interest List
```bash
curl "http://localhost:8000/taxonomy/interests/flat?language=en"
```

---

## 15. i18n Endpoints

### 15.1 Get UI Strings (English)
```bash
curl "http://localhost:8000/i18n/en?scope=common"
```

### 15.2 Get UI Strings (French)
```bash
curl "http://localhost:8000/i18n/fr?scope=common"
```

### 15.3 Get UI Strings (Arabic)
```bash
curl "http://localhost:8000/i18n/ar?scope=common"
```

---

## 16. Feedback Analysis Endpoints

### 16.1 Analyze Single Feedback
```bash
curl -X POST "http://localhost:8000/feedback/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The event was great but the venue was a bit crowded. Host was very friendly!",
    "feedback_id": "fb-123",
    "feedback_source": "event_review",
    "user_id": "1"
  }'
```
**Response**:
```json
{
  "feedback_id": "fb-123",
  "sentiment": "positive",
  "themes": ["venue", "host"],
  "aspects": {
    "venue": {"sentiment": "negative", "mentions": ["crowded"]},
    "host": {"sentiment": "positive", "mentions": ["friendly"]}
  },
  "actionable_insights": ["Consider venue capacity limits"]
}
```

### 16.2 Batch Analyze Feedbacks
```bash
curl -X POST "http://localhost:8000/feedback/analyze/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "feedbacks": [
      {"text": "Loved it!", "feedback_id": "fb-1"},
      {"text": "Could be better", "feedback_id": "fb-2"}
    ]
  }'
```

### 16.3 Get Feedback Statistics
```bash
curl "http://localhost:8000/feedback/stats?days=30"
```

### 16.4 Get Theme Categories
```bash
curl "http://localhost:8000/feedback/themes"
```

---

## 17. Engagement/Retention Endpoints

### 17.1 Predict Churn Risk
```bash
curl "http://localhost:8000/engagement/retention/predict/1"
```
**Response**:
```json
{
  "user_id": 1,
  "churn_probability": 0.15,
  "risk_level": "low",
  "days_since_last_activity": 3,
  "engagement_score": 0.78,
  "recommended_actions": [
    "Send personalized event recommendation",
    "Offer loyalty reward"
  ]
}
```

### 17.2 Batch Churn Prediction
```bash
curl -X POST "http://localhost:8000/engagement/retention/predict/batch" \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["1", "2", "3", "4", "5"]}'
```

### 17.3 Get High-Risk Users
```bash
curl "http://localhost:8000/engagement/retention/high-risk?limit=10"
```

### 17.4 Get Feature Definitions
```bash
curl "http://localhost:8000/engagement/retention/features"
```

### 17.5 Get Model Information
```bash
curl "http://localhost:8000/engagement/retention/model-info"
```

---

## 18. Testing Helper Endpoints

### 18.1 Generate Test UUID
```bash
curl "http://localhost:8000/testing/uuid"
```

### 18.2 Generate Test User
```bash
curl "http://localhost:8000/testing/user"
```

### 18.3 Generate Test Event
```bash
curl "http://localhost:8000/testing/event"
```

### 18.4 Quick Moderation Test
```bash
curl -X POST "http://localhost:8000/testing/quick/moderation" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world, this is a friendly message."}'
```

### 18.5 Quick Sentiment Test
```bash
curl -X POST "http://localhost:8000/testing/quick/sentiment" \
  -H "Content-Type: application/json" \
  -d '{"text": "I absolutely love this amazing platform!"}'
```

### 18.6 Quick Keyword Test
```bash
curl -X POST "http://localhost:8000/testing/quick/keywords" \
  -H "Content-Type: application/json" \
  -d '{"text": "Machine learning and AI are transforming technology.", "max_keywords": 3}'
```

### 18.7 Quick Chatbot Test
```bash
curl -X POST "http://localhost:8000/testing/quick/chatbot" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Kumele?", "language": "en"}'
```

### 18.8 HuggingFace Status
```bash
curl "http://localhost:8000/testing/huggingface-status"
```

### 18.9 Get Sample Requests
```bash
curl "http://localhost:8000/testing/samples"
```

---

## 🔐 Authentication

Currently, the API uses simple user_id parameters for identification. For production, JWT authentication should be implemented.

---

## 📊 Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Server Error |

---

## 🛠️ Technology Stack

| Component | Technology | Cost |
|-----------|------------|------|
| Geocoding | OpenStreetMap Nominatim | FREE |
| Embeddings | HuggingFace (all-MiniLM-L6-v2) | FREE |
| Sentiment | HuggingFace (twitter-roberta) | FREE |
| Moderation | HuggingFace (toxic-bert) | FREE |
| NSFW Detection | HuggingFace (Falconsai) | FREE |
| Vector DB | Qdrant | FREE (self-hosted) |
| LLM | OpenRouter / Mistral | Pay-per-use |
| Translation | LibreTranslate | FREE (self-hosted) |
| Database | PostgreSQL | FREE |
| Cache | Redis | FREE |

---

## 🚀 Running the Test Script

```bash
# Install dependencies
pip install requests colorama tabulate

# Run against local server
python scripts/test_all_endpoints.py --host http://localhost:8000

# Run against production server
python scripts/test_all_endpoints.py --host http://YOUR_SERVER_IP:8000

# Export results to JSON
python scripts/test_all_endpoints.py --host http://localhost:8000 --export results.json
```

---

## 📞 Support

For questions or issues, contact the development team.

---

*Document generated for Kumele AI/ML Backend v1.0*
