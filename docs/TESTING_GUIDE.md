# Kumele AI/ML API - Complete Testing Guide

> **For Frontend Developers** - Complete reference for all API endpoints with request/response examples.

## Table of Contents

1. [Quick Start](#quick-start)
2. [API Base URL & Headers](#api-base-url--headers)
3. [Authentication](#authentication)
4. [Error Handling](#error-handling)
5. [Endpoints by Category](#endpoints-by-category)
   - [System & Health](#1-system--health)
   - [Check-in & QR Codes](#2-check-in--qr-codes)
   - [NFT Badges & Trust](#3-nft-badges--trust)
   - [Chat Rooms](#4-chat-rooms)
   - [Payment Windows](#5-payment-windows)
   - [Event Matching](#6-event-matching)
   - [Predictions & ML](#7-predictions--ml)
   - [Moderation](#8-moderation)
   - [Chatbot & Support](#9-chatbot--support)
   - [Host & Events](#10-host--events)
   - [Rewards](#11-rewards)
   - [i18n & Translations](#12-i18n--translations)
   - [Ads](#13-ads)
   - [NLP & Analytics](#14-nlp--analytics)
   - [AI Ops Monitoring](#15-ai-ops-monitoring)

---

## Quick Start

### Server Setup (For Testing)

```bash
# On server via SSH
cd /home/kumele
git pull origin main
docker-compose down
docker-compose up -d --build

# Run migrations
docker-compose exec api python scripts/migrate_add_columns.py

# Seed test data
docker-compose exec api python scripts/seed_database.py --clear

# Check logs
docker logs kumele_api -f
```

### Test All Endpoints Automatically

```bash
# From server
docker-compose exec api python scripts/test_endpoints.py

# From your machine
python scripts/test_endpoints.py --base-url http://your-server:8000
```

---

## API Base URL & Headers

### Base URL
```
Production: https://api.kumele.com
Development: http://localhost:8000
```

### Required Headers

```javascript
// All requests
{
  "Content-Type": "application/json"
}

// File uploads
{
  "Content-Type": "multipart/form-data"
}
```

### JavaScript/TypeScript Example

```typescript
const API_BASE = "http://localhost:8000";

async function apiRequest(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "API Error");
  }
  
  return response.json();
}
```

---

## Authentication

> **Note**: Current implementation does not require authentication tokens. Add `Authorization: Bearer <token>` header when auth is implemented.

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

### Common HTTP Status Codes

| Code | Meaning | When It Happens |
|------|---------|-----------------|
| `200` | Success | Request completed successfully |
| `400` | Bad Request | Invalid input data |
| `404` | Not Found | Resource doesn't exist |
| `422` | Validation Error | Request body validation failed |
| `500` | Server Error | Something went wrong on server |

### Validation Error Format (422)

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Endpoints by Category

---

# 1. System & Health

### `GET /` - Root
Returns API status.

**Response:**
```json
{
  "service": "Kumele AI/ML",
  "version": "1.0.0",
  "status": "running"
}
```

---

### `GET /health` - Health Check
Check if API is healthy.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

---

# 2. Check-in & QR Codes

> **Prefix**: `/checkin`

## QR Code Generation

### `POST /checkin/qr/generate` - Generate QR Code

Generate a QR code for a user to check into an event.

**Request Body:**
```json
{
  "user_id": 1,
  "event_id": 1,
  "validity_minutes": 30,
  "include_device_binding": false,
  "device_hash": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | integer | ✅ | User's ID |
| `event_id` | integer | ✅ | Event's ID |
| `validity_minutes` | integer | ❌ | How long QR is valid (5-1440, default: 30) |
| `include_device_binding` | boolean | ❌ | Bind QR to specific device |
| `device_hash` | string | ❌ | Device fingerprint (required if device binding enabled) |

**Response:**
```json
{
  "qr_token": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "qr_data": "{\"t\":\"a1b2c3...\",\"u\":1,\"e\":1,\"x\":1737500000,\"v\":1}",
  "qr_image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "expires_at": "2026-01-21T15:30:00",
  "user_id": 1,
  "event_id": 1,
  "is_device_bound": false,
  "scan_url": "/checkin/qr/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
}
```

**Frontend Usage:**
```javascript
// Generate QR
const qr = await apiRequest("/checkin/qr/generate", {
  method: "POST",
  body: JSON.stringify({
    user_id: currentUser.id,
    event_id: eventId,
    validity_minutes: 30
  })
});

// Display QR image
const img = document.getElementById("qr-code");
img.src = `data:image/png;base64,${qr.qr_image_base64}`;

// Or use the image endpoint directly
img.src = `${API_BASE}/checkin/qr/${qr.qr_token}/image`;
```

---

### `GET /checkin/qr/{qr_token}` - Validate QR Token

Check if a QR token is valid (for hosts scanning attendees).

**URL Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `qr_token` | string | The QR token to validate |

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scanner_id` | integer | ❌ | Host ID who is scanning |
| `device_hash` | string | ❌ | Device fingerprint |

**Response (Valid):**
```json
{
  "is_valid": true,
  "user_id": 1,
  "event_id": 1,
  "user_name": "john_doe",
  "event_title": "Weekend Yoga Session",
  "expires_at": "2026-01-21T15:30:00",
  "status": "valid",
  "message": "QR code is valid. Ready for check-in.",
  "can_check_in": true
}
```

**Response (Expired):**
```json
{
  "is_valid": false,
  "user_id": 1,
  "event_id": 1,
  "status": "expired",
  "message": "QR code has expired. Please generate a new one.",
  "can_check_in": false
}
```

**Possible `status` Values:**
| Status | Description |
|--------|-------------|
| `valid` | QR is valid and ready for check-in |
| `expired` | QR has expired |
| `already_used` | QR was already used |
| `invalid` | QR token doesn't exist |
| `device_mismatch` | QR is bound to different device |

---

### `POST /checkin/qr/{qr_token}/use` - Complete Check-in with QR

Actually perform the check-in (mark QR as used).

**URL Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `qr_token` | string | The QR token |

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scanner_id` | integer | ✅ | Host ID performing the check-in |

**Response:**
```json
{
  "success": true,
  "message": "Check-in successful",
  "user_id": 1,
  "event_id": 1,
  "check_in_time": "2026-01-21T14:05:00"
}
```

---

### `GET /checkin/qr/{qr_token}/image` - Get QR as Image

Get QR code as PNG image directly.

**URL Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `qr_token` | string | The QR token |

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `size` | integer | ❌ | Image size in pixels (100-1000, default: 300) |

**Response:** PNG image file

**Frontend Usage:**
```html
<img src="http://localhost:8000/checkin/qr/TOKEN_HERE/image?size=400" alt="QR Code" />
```

---

### `POST /checkin/qr/refresh` - Refresh Expired QR

Generate a new QR code (invalidates old one if provided).

**Request Body:**
```json
{
  "user_id": 1,
  "event_id": 1,
  "old_token": "old_qr_token_here",
  "validity_minutes": 60
}
```

**Response:** Same as `POST /checkin/qr/generate`

---

### `POST /checkin/qr/batch` - Batch Generate QR Codes

Generate QR codes for multiple users at once (for hosts).

**Request Body:**
```json
{
  "event_id": 1,
  "user_ids": [1, 2, 3, 4, 5],
  "validity_minutes": 60
}
```

**Response:**
```json
{
  "event_id": 1,
  "generated_count": 5,
  "failed_count": 0,
  "qr_codes": [
    {
      "qr_token": "token1...",
      "user_id": 1,
      "event_id": 1,
      "qr_image_base64": "...",
      "expires_at": "2026-01-21T15:30:00"
    }
  ],
  "failed_user_ids": []
}
```

---

### `GET /checkin/qr/user/{user_id}/active` - Get User's Active QR Codes

Get all valid (non-expired, non-used) QR codes for a user.

**URL Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | integer | User's ID |

**Response:**
```json
{
  "user_id": 1,
  "active_count": 2,
  "qr_codes": [
    {
      "qr_token": "abc123...",
      "event_id": 1,
      "event_title": "Yoga Session",
      "expires_at": "2026-01-21T15:30:00",
      "is_device_bound": false
    }
  ]
}
```

---

### `DELETE /checkin/qr/{qr_token}` - Revoke QR Token

Invalidate a QR code (user lost phone, etc.).

**URL Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `qr_token` | string | The QR token to revoke |

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | integer | ✅ | User ID (must match token owner) |

**Response:**
```json
{
  "success": true,
  "message": "QR token revoked successfully"
}
```

---

## Check-in Validation

### `POST /checkin/validate` - Validate Check-in

Validate a user's check-in (GPS or QR mode).

**Request Body:**
```json
{
  "event_id": 1,
  "user_id": 1,
  "mode": "self_check",
  "user_latitude": 40.7128,
  "user_longitude": -74.0060,
  "device_hash": "device_fingerprint_here"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | integer | ✅ | Event ID |
| `user_id` | integer | ✅ | User ID |
| `mode` | string | ✅ | `"self_check"` or `"host_qr"` |
| `user_latitude` | float | For self_check | User's GPS latitude |
| `user_longitude` | float | For self_check | User's GPS longitude |
| `qr_code` | string | For host_qr | QR code scanned |
| `host_id` | integer | For host_qr | Host performing scan |
| `device_hash` | string | ❌ | Device fingerprint |

**Response:**
```json
{
  "is_valid": true,
  "status": "Valid",
  "risk_score": 0.05,
  "reason_code": "gps_verified",
  "message": "Check-in validated successfully",
  "check_in_id": 123,
  "verification_id": 456,
  "checks_passed": {
    "gps_distance": true,
    "time_window": true,
    "device_trust": true
  },
  "warnings": []
}
```

**`status` Values:**
| Status | Description |
|--------|-------------|
| `Valid` | Check-in accepted |
| `Suspicious` | Check-in accepted but flagged |
| `Fraudulent` | Check-in rejected |

---

### `POST /checkin/verify` - Verify Check-in (Enhanced)

Enhanced verification with more signals.

**Request Body:**
```json
{
  "event_id": 1,
  "user_id": 1,
  "latitude": 40.7128,
  "longitude": -74.0060,
  "device_hash": "abc123",
  "qr_code": null,
  "qr_timestamp": null
}
```

**Response:**
```json
{
  "verified": true,
  "status": "verified",
  "confidence": 0.95,
  "geo_distance_km": 0.5,
  "device_trusted": true,
  "message": "Check-in verified"
}
```

---

### `POST /checkin/fraud-detect` - Fraud Detection

Check for fraudulent check-in attempts.

**Request Body:**
```json
{
  "event_id": 1,
  "user_id": 1,
  "device_hash": "abc123",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "qr_code": null
}
```

**Response:**
```json
{
  "score": 0.15,
  "decision": "clean",
  "reason": "No significant risk factors detected",
  "risk_factors": [],
  "recommendations": ["Allow check-in"]
}
```

**`decision` Values:**
| Decision | Score Range | Action |
|----------|-------------|--------|
| `clean` | 0.0 - 0.3 | Allow |
| `suspicious` | 0.3 - 0.7 | Allow with review |
| `fraudulent` | 0.7 - 1.0 | Block |

---

### `GET /checkin/event/{event_id}/status` - Event Check-in Status

Get check-in statistics for an event.

**Response:**
```json
{
  "event_id": 1,
  "total_rsvps": 50,
  "total_checked_in": 35,
  "valid_check_ins": 33,
  "suspicious_check_ins": 2,
  "check_in_rate": 0.70,
  "by_mode": {
    "self_check": 20,
    "host_qr": 15
  }
}
```

---

### `GET /checkin/user/{user_id}/history` - User Check-in History

Get user's past check-ins.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | ❌ | Max results (default: 20) |
| `offset` | integer | ❌ | Skip results for pagination |

**Response:**
```json
{
  "user_id": 1,
  "total_check_ins": 15,
  "check_ins": [
    {
      "id": 123,
      "event_id": 1,
      "event_title": "Yoga Session",
      "check_in_time": "2026-01-20T14:05:00",
      "mode": "self_check",
      "is_valid": true
    }
  ]
}
```

---

### `GET /checkin/host/{host_id}/compliance` - Host Compliance Rate

Get host's check-in compliance statistics.

**Response:**
```json
{
  "host_id": 1,
  "total_events": 25,
  "events_with_checkins": 20,
  "total_expected_checkins": 500,
  "total_actual_checkins": 425,
  "compliance_rate": 0.85,
  "avg_checkin_rate_per_event": 0.80,
  "host_tier": "Gold",
  "event_completion_rate": 0.92,
  "cancellation_rate": 0.08,
  "refund_penalty_count": 2
}
```

---

# 3. NFT Badges & Trust

> **Prefix**: `/nft`

### `GET /nft/badge/eligibility/{user_id}` - Check Badge Eligibility

Check if user is eligible for an NFT badge.

**Response:**
```json
{
  "user_id": 1,
  "is_eligible": true,
  "verified_events": 15,
  "current_badge": "Bronze",
  "eligible_for": "Silver",
  "next_tier": "Gold",
  "events_until_next": 10,
  "trust_boost": 0.05,
  "discount_percent": 5.0,
  "priority_matching": false
}
```

**Badge Tiers:**
| Tier | Verified Events | Trust Boost | Discount |
|------|-----------------|-------------|----------|
| Bronze | 5+ | 2% | 2% |
| Silver | 15+ | 5% | 5% |
| Gold | 30+ | 10% | 10% |
| Platinum | 50+ | 15% | 15% |
| Legendary | 100+ | 20% | 20% |

---

### `POST /nft/badge/issue` - Issue NFT Badge

Issue a badge to eligible user.

**Request Body:**
```json
{
  "user_id": 1
}
```

**Response:**
```json
{
  "id": 123,
  "user_id": 1,
  "badge_type": "Silver",
  "token_id": "0x1a2b3c",
  "contract_address": "0xabc123...",
  "chain": "polygon",
  "earned_reason": "attendance_milestone",
  "experience_points": 1500,
  "level": 3,
  "trust_boost": 0.05,
  "price_discount_percent": 5.0,
  "priority_matching": false,
  "is_active": true,
  "created_at": "2026-01-21T14:00:00"
}
```

---

### `GET /nft/badge/user/{user_id}` - Get User's Badge

Get user's current NFT badge.

**Response:** Same as issue response, or `null` if no badge.

---

### `GET /nft/badge/history/{user_id}` - Badge History

Get badge upgrade/activity history.

**Response:**
```json
{
  "user_id": 1,
  "history": [
    {
      "id": 1,
      "action": "minted",
      "old_level": null,
      "new_level": 1,
      "reason": "Initial badge issuance",
      "created_at": "2026-01-01T10:00:00"
    },
    {
      "id": 2,
      "action": "upgraded",
      "old_level": 1,
      "new_level": 2,
      "reason": "Level milestone reached",
      "created_at": "2026-01-15T10:00:00"
    }
  ]
}
```

---

### `GET /nft/trust-score/{user_id}` - Get Trust Score

Get user's overall trust score.

**Response:**
```json
{
  "user_id": 1,
  "trust_score": 0.92,
  "components": {
    "attendance_rate": 0.95,
    "no_show_rate": 0.05,
    "payment_reliability": 0.98,
    "fraud_flags": 0,
    "badge_bonus": 0.05
  },
  "risk_level": "low",
  "recommendations": []
}
```

---

### `GET /nft/host-priority/{host_id}` - Host Priority Score

Get host's priority ranking.

**Response:**
```json
{
  "host_id": 1,
  "priority_score": 0.88,
  "tier": "Gold",
  "boost_percentage": 15,
  "factors": {
    "avg_rating": 4.7,
    "total_events": 35,
    "completion_rate": 0.95,
    "badge_type": "Gold"
  }
}
```

---

### `GET /nft/discount-eligibility/{user_id}` - Discount Eligibility

Check what discounts user is eligible for.

**Response:**
```json
{
  "user_id": 1,
  "eligible": true,
  "discount_percent": 10.0,
  "max_discount_amount": 50.0,
  "sources": {
    "badge": 5.0,
    "loyalty": 3.0,
    "promotional": 2.0
  },
  "stackable": true,
  "expires_at": null
}
```

---

### `GET /nft/payment-reliability/{user_id}` - Payment Reliability

Get user's payment history reliability.

**Response:**
```json
{
  "user_id": 1,
  "reliability_score": 0.95,
  "total_payments": 20,
  "successful_payments": 19,
  "failed_payments": 1,
  "timeout_payments": 0,
  "avg_payment_time_minutes": 5.2,
  "risk_level": "low"
}
```

---

### `GET /nft/event-ranking-boost/{event_id}` - Event Ranking Boost

Get ranking boost for an event based on host's NFT.

**Response:**
```json
{
  "event_id": 1,
  "host_id": 5,
  "boost_percentage": 15,
  "host_badge": "Gold",
  "host_trust_score": 0.92
}
```

---

# 4. Chat Rooms

> **Prefix**: `/chat`

### `POST /chat/rooms` - Create Chat Room

Create a temporary chat room for an event.

**Request Body:**
```json
{
  "event_id": 1,
  "chat_type": "event"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | integer | ✅ | Event ID |
| `chat_type` | string | ❌ | `"event"` or `"group"` (default: event) |

**Response:**
```json
{
  "id": 1,
  "event_id": 1,
  "chat_type": "event",
  "status": "active",
  "expires_at": "2026-01-22T14:00:00",
  "message_count": 0,
  "active_participants": 0,
  "created_at": "2026-01-21T14:00:00"
}
```

---

### `GET /chat/rooms/{chat_id}` - Get Chat Room

Get chat room details.

**Response:** Same as create response.

---

### `GET /chat/rooms/event/{event_id}` - Get Chat by Event

Find chat room for a specific event.

**Response:** Same as create response, or 404 if not found.

---

### `POST /chat/rooms/{chat_id}/join` - Join Chat

Join a chat room as participant.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | integer | ✅ | User joining |

**Response:**
```json
{
  "success": true,
  "message": "Joined chat successfully",
  "participant_id": 123
}
```

---

### `POST /chat/rooms/{chat_id}/leave` - Leave Chat

Leave a chat room.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | integer | ✅ | User leaving |

**Response:**
```json
{
  "success": true,
  "message": "Left chat successfully"
}
```

---

### `GET /chat/rooms/{chat_id}/messages` - Get Messages

Get messages in a chat room.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | ❌ | Max messages (default: 50) |
| `before_id` | integer | ❌ | Get messages before this ID |

**Response:**
```json
[
  {
    "id": 1,
    "chat_id": 1,
    "user_id": 5,
    "username": "john_doe",
    "content": "Hello everyone!",
    "is_moderated": false,
    "moderation_status": "approved",
    "created_at": "2026-01-21T14:05:00"
  }
]
```

---

### `POST /chat/rooms/{chat_id}/messages` - Send Message

Send a message to chat room.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | integer | ✅ | User sending |

**Request Body:**
```json
{
  "content": "Hello everyone!"
}
```

**Response:**
```json
{
  "id": 123,
  "chat_id": 1,
  "user_id": 5,
  "content": "Hello everyone!",
  "is_moderated": false,
  "moderation_status": "approved",
  "toxicity_score": 0.02,
  "created_at": "2026-01-21T14:10:00"
}
```

---

### `DELETE /chat/rooms/{chat_id}/messages/{message_id}` - Delete Message

Delete a message (soft delete).

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | integer | ✅ | User deleting (must be owner) |

**Response:**
```json
{
  "success": true,
  "message": "Message deleted"
}
```

---

### `GET /chat/rooms/{chat_id}/participants` - Get Participants

List chat room participants.

**Response:**
```json
[
  {
    "id": 1,
    "user_id": 5,
    "username": "john_doe",
    "role": "host",
    "is_active": true,
    "message_count": 15,
    "joined_at": "2026-01-21T14:00:00"
  }
]
```

---

### `POST /chat/rooms/{chat_id}/close` - Close Chat Room

Close a chat room.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `reason` | string | ❌ | Close reason |

**Response:**
```json
{
  "success": true,
  "message": "Chat closed",
  "closed_at": "2026-01-21T16:00:00"
}
```

---

### `POST /chat/rooms/{chat_id}/messages/{message_id}/moderate` - Moderate Message

Manually moderate a specific message.

**Request Body:**
```json
{
  "message_id": 123,
  "action": "approve"
}
```

| Action | Description |
|--------|-------------|
| `approve` | Mark as approved |
| `reject` | Mark as rejected |
| `flag` | Flag for review |

**Response:**
```json
{
  "message_id": 123,
  "action": "approve",
  "previous_status": "pending",
  "new_status": "approved",
  "moderated_at": "2026-01-21T14:15:00"
}
```

---

### `POST /chat/rooms/{chat_id}/auto-moderate` - Auto-Moderate Chat

Run AI moderation on all unmoderated messages.

**Response:**
```json
{
  "processed": 10,
  "approved": 8,
  "flagged": 2,
  "rejected": 0
}
```

---

### `GET /chat/rooms/{chat_id}/moderation-stats` - Moderation Stats

Get moderation statistics for a chat.

**Response:**
```json
{
  "chat_id": 1,
  "total_messages": 150,
  "moderated_count": 10,
  "approved_count": 140,
  "flagged_count": 8,
  "rejected_count": 2,
  "avg_toxicity_score": 0.05,
  "toxic_message_count": 5
}
```

---

### `GET /chat/rooms/{chat_id}/popularity` - Chat Popularity

Predict chat popularity score.

**Response:**
```json
{
  "chat_id": 1,
  "popularity_score": 0.75,
  "activity_level": "high",
  "messages_per_hour": 12.5,
  "active_users": 8,
  "peak_time": "14:00-16:00",
  "trend": "growing"
}
```

---

### `GET /chat/rooms/{chat_id}/sentiment` - Chat Sentiment

Analyze overall chat sentiment.

**Response:**
```json
{
  "chat_id": 1,
  "overall_sentiment": "positive",
  "sentiment_score": 0.72,
  "breakdown": {
    "positive": 0.65,
    "neutral": 0.25,
    "negative": 0.10
  },
  "trending_topics": ["event", "excited", "thanks"]
}
```

---

### `POST /chat/rooms/{chat_id}/auto-close-check` - Check Auto-Close

Check if chat should be auto-closed (dead chat).

**Response:**
```json
{
  "should_close": false,
  "reason": null,
  "last_activity": "2026-01-21T14:30:00",
  "hours_inactive": 0.5
}
```

---

# 5. Payment Windows

> **Prefix**: `/payment`

### `POST /payment/window/create` - Create Payment Window

Create a time-limited payment window.

**Request Body:**
```json
{
  "user_id": 1,
  "event_id": 1,
  "amount": 25.00,
  "currency": "USD",
  "window_minutes": 15
}
```

**Response:**
```json
{
  "id": 123,
  "user_id": 1,
  "event_id": 1,
  "amount": 25.00,
  "currency": "USD",
  "status": "pending",
  "expires_at": "2026-01-21T14:30:00",
  "created_at": "2026-01-21T14:15:00",
  "remaining_seconds": 900
}
```

---

### `GET /payment/window/{window_id}` - Get Payment Window

Get payment window status.

**Response:** Same as create response.

---

### `POST /payment/window/{window_id}/extend` - Extend Window

Extend payment window time.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `minutes` | integer | ❌ | Additional minutes (default: 5) |

**Response:**
```json
{
  "success": true,
  "new_expires_at": "2026-01-21T14:35:00",
  "remaining_seconds": 1200
}
```

---

### `POST /payment/window/{window_id}/complete` - Complete Payment

Mark payment as completed.

**Response:**
```json
{
  "success": true,
  "status": "completed",
  "completed_at": "2026-01-21T14:20:00"
}
```

---

### `POST /payment/window/{window_id}/cancel` - Cancel Payment

Cancel a payment window.

**Response:**
```json
{
  "success": true,
  "status": "cancelled",
  "cancelled_at": "2026-01-21T14:18:00"
}
```

---

### `GET /payment/window/user/{user_id}/active` - User's Active Windows

Get all active payment windows for a user.

**Response:**
```json
{
  "user_id": 1,
  "active_windows": [
    {
      "id": 123,
      "event_id": 1,
      "amount": 25.00,
      "expires_at": "2026-01-21T14:30:00",
      "remaining_seconds": 600
    }
  ]
}
```

---

### `GET /payment/urgency/event/{event_id}` - Payment Urgency

Get urgency level for event payment.

**Response:**
```json
{
  "event_id": 1,
  "urgency_level": "high",
  "urgency_score": 0.85,
  "factors": {
    "spots_remaining": 3,
    "capacity": 20,
    "time_until_event_hours": 2,
    "demand_score": 0.9
  },
  "recommended_window_minutes": 10,
  "message": "Only 3 spots left! Pay quickly to secure your spot."
}
```

---

### `GET /payment/urgency/batch` - Batch Urgency

Get urgency for multiple events.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_ids` | string | ✅ | Comma-separated event IDs |

**Example:** `/payment/urgency/batch?event_ids=1,2,3,4,5`

**Response:**
```json
{
  "urgencies": [
    {"event_id": 1, "urgency_level": "high", "urgency_score": 0.85},
    {"event_id": 2, "urgency_level": "medium", "urgency_score": 0.55}
  ]
}
```

---

### `GET /payment/analytics/timeouts` - Timeout Analytics

Get payment timeout statistics.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `days` | integer | ❌ | Look back days (default: 30) |

**Response:**
```json
{
  "period_days": 30,
  "total_windows": 500,
  "completed": 420,
  "timed_out": 60,
  "cancelled": 20,
  "timeout_rate": 0.12,
  "avg_completion_time_minutes": 8.5
}
```

---

# 6. Event Matching

> **Prefix**: `/match`

### `GET /match/events` - Match Events to User

Get personalized event recommendations.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | integer | ✅ | User ID |
| `limit` | integer | ❌ | Max results (default: 10) |
| `min_age` | integer | ❌ | Filter by min age |
| `max_age` | integer | ❌ | Filter by max age |
| `gender` | string | ❌ | Filter by gender |
| `host_tier_min` | string | ❌ | Min host tier (Bronze/Silver/Gold) |
| `verified_hosts_only` | boolean | ❌ | Only verified hosts |

**Example:** `/match/events?user_id=1&limit=20&verified_hosts_only=true`

**Response:**
```json
{
  "user_id": 1,
  "matches": [
    {
      "event_id": 1,
      "title": "Weekend Yoga Session",
      "match_score": 0.92,
      "host_id": 5,
      "host_name": "Jane Doe",
      "host_tier": "Gold",
      "date": "2026-01-25T10:00:00",
      "location": "Central Park",
      "price": 15.00,
      "capacity": 20,
      "spots_remaining": 5
    }
  ],
  "total_matches": 15
}
```

---

### `GET /match/events/with-capacity` - Events with Capacity Info

Get matched events with capacity countdown.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | integer | ✅ | User ID |

**Response:**
```json
{
  "user_id": 1,
  "events": [
    {
      "event_id": 1,
      "title": "Yoga Session",
      "capacity": 20,
      "current_rsvps": 15,
      "spots_remaining": 5,
      "fill_percentage": 75,
      "urgency": "high",
      "estimated_fill_time_hours": 4
    }
  ]
}
```

---

### `GET /match/events/by-host-reputation` - Events by Host Reputation

Get events sorted by host reputation.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | integer | ✅ | User ID |
| `min_rating` | float | ❌ | Minimum host rating (1-5) |

**Response:**
```json
{
  "user_id": 1,
  "events": [
    {
      "event_id": 1,
      "title": "Yoga Session",
      "host_id": 5,
      "host_rating": 4.8,
      "host_tier": "Gold",
      "host_total_events": 45,
      "host_completion_rate": 0.97,
      "reputation_score": 0.92
    }
  ]
}
```

---

# 7. Predictions & ML

> **Prefix**: `/predict` and `/ml`

### `POST /predict/attendance` - Predict Attendance

Predict attendance for a new event.

**Request Body:**
```json
{
  "hobby": "yoga",
  "location": "New York",
  "date": "2026-02-15T14:00:00",
  "is_paid": true,
  "price": 20.00,
  "host_experience": 10,
  "host_rating": 4.5,
  "capacity": 30
}
```

**Response:**
```json
{
  "predicted_attendance": 22,
  "confidence": 0.85,
  "fill_rate_prediction": 0.73,
  "factors": {
    "hobby_popularity": 0.8,
    "location_demand": 0.9,
    "price_sensitivity": -0.1,
    "host_reputation": 0.85
  }
}
```

---

### `GET /predict/noshow/{event_id}` - Predict No-Shows

Predict no-show rate for an event.

**Response:**
```json
{
  "event_id": 1,
  "predicted_no_show_rate": 0.15,
  "predicted_no_shows": 3,
  "total_rsvps": 20,
  "confidence": 0.82,
  "risk_level": "medium",
  "recommendations": [
    "Send reminder 2 hours before",
    "Consider overbooking by 2 spots"
  ]
}
```

---

### `GET /predict/trends` - Predict Trends

Get trending hobbies/activities.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `location` | string | ❌ | Filter by location |
| `days` | integer | ❌ | Forecast days ahead |

**Response:**
```json
{
  "trending_up": [
    {"hobby": "yoga", "growth_rate": 0.25},
    {"hobby": "hiking", "growth_rate": 0.18}
  ],
  "trending_down": [
    {"hobby": "indoor_gaming", "growth_rate": -0.10}
  ],
  "forecast": {
    "next_7_days": ["yoga", "outdoor_sports"],
    "next_30_days": ["fitness", "wellness"]
  }
}
```

---

### `POST /ml/no-show/predict` - ML No-Show Prediction

Detailed no-show prediction for a user.

**Request Body:**
```json
{
  "user_id": 1,
  "event_id": 1,
  "event_date": "2026-01-25T14:00:00",
  "is_paid": true,
  "distance_km": 5.0
}
```

**Response:**
```json
{
  "user_id": 1,
  "event_id": 1,
  "no_show_probability": 0.12,
  "risk_category": "low",
  "features_used": {
    "historical_no_show_rate": 0.08,
    "payment_reliability": 0.95,
    "distance_factor": 0.1,
    "days_until_event": 4
  }
}
```

---

### `POST /ml/attendance/verify` - ML Attendance Verification

Verify attendance using ML signals.

**Request Body:**
```json
{
  "event_id": 1,
  "user_id": 1,
  "gps_latitude": 40.7128,
  "gps_longitude": -74.0060,
  "device_hash": "abc123",
  "qr_code": null,
  "qr_scan_timestamp": null
}
```

**Response:**
```json
{
  "verification_status": "verified",
  "confidence": 0.92,
  "signals": {
    "gps_match": true,
    "device_trust": true,
    "timing_valid": true,
    "qr_valid": null
  }
}
```

---

### `GET /ml/models` - List ML Models

Get list of available ML models.

**Response:**
```json
{
  "models": [
    {
      "name": "no_show_predictor",
      "version": "1.2.0",
      "status": "active",
      "last_trained": "2026-01-15T10:00:00"
    },
    {
      "name": "fraud_detector",
      "version": "2.0.1",
      "status": "active",
      "last_trained": "2026-01-10T08:00:00"
    }
  ]
}
```

---

# 8. Moderation

> **Prefix**: `/moderation`

### `POST /moderation/text` - Moderate Text

Check text content for policy violations.

**Request Body:**
```json
{
  "text": "This is a message to check",
  "context": "chat_message"
}
```

| Context | Description |
|---------|-------------|
| `chat_message` | Chat room message |
| `event_description` | Event description |
| `profile_bio` | User profile bio |
| `comment` | Comment/review |

**Response:**
```json
{
  "is_safe": true,
  "toxicity_score": 0.05,
  "categories": {
    "hate_speech": 0.01,
    "harassment": 0.02,
    "spam": 0.03,
    "adult_content": 0.00
  },
  "flagged_categories": [],
  "action": "approve"
}
```

---

### `POST /moderation/image` - Moderate Image

Check image for policy violations.

**Request Body:**
```json
{
  "image_url": "https://example.com/image.jpg",
  "context": "profile_photo"
}
```

**Response:**
```json
{
  "is_safe": true,
  "categories": {
    "adult": 0.02,
    "violence": 0.01,
    "gore": 0.00,
    "hate_symbols": 0.00
  },
  "flagged_categories": [],
  "action": "approve"
}
```

---

### `POST /moderation/video` - Moderate Video

Check video for policy violations.

**Request Body:**
```json
{
  "video_url": "https://example.com/video.mp4",
  "context": "event_promo"
}
```

**Response:**
```json
{
  "is_safe": true,
  "job_id": "mod_123",
  "status": "processing",
  "estimated_time_seconds": 30
}
```

---

### `GET /moderation/{content_id}` - Get Moderation Status

Check status of moderation job.

**Response:**
```json
{
  "content_id": "mod_123",
  "status": "completed",
  "is_safe": true,
  "results": {
    "frames_analyzed": 150,
    "flagged_frames": 0
  }
}
```

---

# 9. Chatbot & Support

> **Prefix**: `/chatbot` and `/support`

### `POST /chatbot/ask` - Ask Chatbot

Ask the AI chatbot a question.

**Request Body:**
```json
{
  "user_id": 1,
  "query": "How do I create an event?",
  "language": "en",
  "session_id": "session_123"
}
```

**Response:**
```json
{
  "answer": "To create an event, go to the Events tab and click 'Create Event'. Fill in the details like title, date, location, and capacity. You can also set a price for paid events.",
  "confidence": 0.92,
  "sources": [
    {"title": "How to Create an Event", "relevance": 0.95}
  ],
  "suggested_actions": ["View tutorial", "Go to Events"],
  "session_id": "session_123"
}
```

---

### `POST /chatbot/feedback` - Submit Feedback

Submit feedback on chatbot response.

**Request Body:**
```json
{
  "session_id": "session_123",
  "query": "How do I create an event?",
  "answer": "To create an event...",
  "helpful": true,
  "rating": 5,
  "comment": "Very helpful!"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Thank you for your feedback!"
}
```

---

### `GET /chatbot/knowledge` - List Knowledge Docs

List knowledge base documents.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | ❌ | Filter by category |
| `language` | string | ❌ | Filter by language |

**Response:**
```json
{
  "documents": [
    {
      "id": 1,
      "title": "Getting Started",
      "category": "faq",
      "language": "en",
      "created_at": "2026-01-01T10:00:00"
    }
  ]
}
```

---

### `POST /chatbot/knowledge` - Create Knowledge Doc

Add a new knowledge document.

**Request Body:**
```json
{
  "title": "How to Cancel an Event",
  "content": "To cancel an event, go to your Events...",
  "category": "faq",
  "language": "en"
}
```

**Response:**
```json
{
  "id": 5,
  "title": "How to Cancel an Event",
  "category": "faq",
  "language": "en",
  "created_at": "2026-01-21T14:00:00"
}
```

---

# 10. Host & Events

> **Prefix**: `/host` and `/event`

### `GET /host/{host_id}/rating` - Get Host Rating

Get aggregated host rating.

**Response:**
```json
{
  "host_id": 1,
  "overall_rating": 4.7,
  "total_ratings": 150,
  "breakdown": {
    "communication": 4.8,
    "respect": 4.9,
    "professionalism": 4.6,
    "atmosphere": 4.7,
    "value": 4.5
  },
  "total_events": 45,
  "total_attendees": 890
}
```

---

### `POST /event/{event_id}/rating` - Submit Event Rating

Submit a rating for an event.

**Request Body:**
```json
{
  "user_id": 1,
  "rating": 4.5,
  "communication_score": 5.0,
  "respect_score": 5.0,
  "professionalism_score": 4.5,
  "atmosphere_score": 4.5,
  "value_score": 4.0,
  "comment": "Great event! Really enjoyed it."
}
```

**Response:**
```json
{
  "id": 123,
  "event_id": 1,
  "user_id": 1,
  "rating": 4.5,
  "created_at": "2026-01-21T16:00:00"
}
```

---

### `GET /event/{event_id}/ratings` - Get Event Ratings

Get all ratings for an event.

**Response:**
```json
{
  "event_id": 1,
  "average_rating": 4.6,
  "total_ratings": 15,
  "ratings": [
    {
      "user_id": 1,
      "rating": 4.5,
      "comment": "Great event!",
      "created_at": "2026-01-21T16:00:00"
    }
  ]
}
```

---

# 11. Rewards

> **Prefix**: `/rewards`

### `GET /rewards/user/{user_id}` - Get User Rewards

Get user's rewards status.

**Response:**
```json
{
  "user_id": 1,
  "tier": "Gold",
  "total_points": 1500,
  "points_until_next_tier": 500,
  "coupons_available": 3,
  "lifetime_savings": 125.00
}
```

---

### `GET /rewards/coupons/{user_id}` - Get User Coupons

Get user's available coupons.

**Response:**
```json
{
  "user_id": 1,
  "coupons": [
    {
      "id": 1,
      "code": "GOLD10",
      "discount_value": 10.0,
      "discount_type": "percentage",
      "expires_at": "2026-02-21T00:00:00",
      "is_redeemed": false
    }
  ]
}
```

---

# 12. i18n & Translations

> **Prefix**: `/i18n`

### `GET /i18n/{language}` - Get All Strings

Get all translation strings for a language.

**Response:**
```json
{
  "language": "es",
  "strings": {
    "common": {
      "welcome": "Bienvenido",
      "search": "Buscar",
      "home": "Inicio"
    },
    "events": {
      "create_event": "Crear Evento",
      "join_event": "Unirse"
    }
  }
}
```

---

### `GET /i18n/{language}/{scope}/{key}` - Get Single String

Get a specific translation string.

**Example:** `/i18n/es/common/welcome`

**Response:**
```json
{
  "key": "welcome",
  "scope": "common",
  "language": "es",
  "value": "Bienvenido"
}
```

---

### `GET /i18n/scopes/list` - List Scopes

Get available translation scopes.

**Response:**
```json
{
  "scopes": ["common", "events", "auth", "profile", "chat", "settings"]
}
```

---

# 13. Ads

> **Prefix**: `/ads`

### `GET /ads/audience-match` - Match Ads to Audience

Get ads matched to audience criteria.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `hobby` | string | ❌ | Target hobby |
| `location` | string | ❌ | Target location |
| `age_min` | integer | ❌ | Minimum age |
| `age_max` | integer | ❌ | Maximum age |

**Response:**
```json
{
  "ads": [
    {
      "id": 1,
      "title": "Premium Yoga Gear",
      "image_url": "https://...",
      "match_score": 0.85
    }
  ]
}
```

---

### `GET /ads/performance-predict` - Predict Ad Performance

Predict performance of an ad.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ad_id` | integer | ✅ | Ad ID |

**Response:**
```json
{
  "ad_id": 1,
  "predicted_ctr": 0.025,
  "predicted_conversions": 15,
  "confidence": 0.8
}
```

---

# 14. NLP & Analytics

> **Prefix**: `/nlp`

### `POST /nlp/sentiment` - Analyze Sentiment

Analyze text sentiment.

**Request Body:**
```json
{
  "text": "I had an amazing time at the event!",
  "language": "en"
}
```

**Response:**
```json
{
  "sentiment": "positive",
  "score": 0.92,
  "emotions": {
    "joy": 0.85,
    "excitement": 0.75,
    "gratitude": 0.60
  }
}
```

---

### `POST /nlp/keywords` - Extract Keywords

Extract keywords from text.

**Request Body:**
```json
{
  "text": "We're hosting a yoga session in Central Park this Saturday morning."
}
```

**Response:**
```json
{
  "keywords": [
    {"word": "yoga", "score": 0.95},
    {"word": "Central Park", "score": 0.90},
    {"word": "Saturday", "score": 0.85}
  ]
}
```

---

### `GET /nlp/trends` - Get Trending Topics

Get trending topics from user content.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `days` | integer | ❌ | Look back days |
| `category` | string | ❌ | Content category |

**Response:**
```json
{
  "trends": [
    {"topic": "outdoor activities", "mentions": 150, "growth": 0.25},
    {"topic": "wellness", "mentions": 120, "growth": 0.18}
  ]
}
```

---

# 15. AI Ops Monitoring

> **Prefix**: `/ai-ops`

### `GET /ai-ops/health` - System Health

Get AI system health status.

**Response:**
```json
{
  "status": "healthy",
  "models_loaded": 5,
  "avg_inference_time_ms": 45,
  "error_rate": 0.001,
  "uptime_hours": 720
}
```

---

### `GET /ai-ops/metrics/checkins` - Check-in Metrics

Get check-in system metrics.

**Response:**
```json
{
  "total_checkins_24h": 1500,
  "valid_rate": 0.95,
  "suspicious_rate": 0.04,
  "fraudulent_rate": 0.01,
  "avg_validation_time_ms": 120
}
```

---

### `GET /ai-ops/metrics/models/{model_name}` - Model Metrics

Get metrics for a specific model.

**Response:**
```json
{
  "model_name": "no_show_predictor",
  "version": "1.2.0",
  "predictions_24h": 5000,
  "avg_latency_ms": 25,
  "accuracy": 0.87,
  "last_drift_check": "2026-01-21T10:00:00"
}
```

---

### `GET /ai-ops/drift/check/{model_name}` - Check Model Drift

Check if model is experiencing drift.

**Response:**
```json
{
  "model_name": "no_show_predictor",
  "drift_detected": false,
  "feature_drift_score": 0.08,
  "prediction_drift_score": 0.05,
  "accuracy_current": 0.87,
  "accuracy_baseline": 0.88,
  "alert_level": "none"
}
```

---

## Quick Reference Card

### Most Used Endpoints

| Action | Method | Endpoint |
|--------|--------|----------|
| Generate QR | POST | `/checkin/qr/generate` |
| Validate QR | GET | `/checkin/qr/{token}` |
| Use QR for check-in | POST | `/checkin/qr/{token}/use` |
| Get QR image | GET | `/checkin/qr/{token}/image` |
| Check badge eligibility | GET | `/nft/badge/eligibility/{user_id}` |
| Get trust score | GET | `/nft/trust-score/{user_id}` |
| Create chat room | POST | `/chat/rooms` |
| Send message | POST | `/chat/rooms/{id}/messages` |
| Get messages | GET | `/chat/rooms/{id}/messages` |
| Create payment window | POST | `/payment/window/create` |
| Get matched events | GET | `/match/events?user_id=X` |
| Predict no-shows | GET | `/predict/noshow/{event_id}` |
| Moderate text | POST | `/moderation/text` |
| Ask chatbot | POST | `/chatbot/ask` |

---

## Frontend Integration Tips

### 1. QR Code Display
```javascript
// Generate and display QR
const response = await fetch("/checkin/qr/generate", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({user_id: 1, event_id: 1})
});
const data = await response.json();

// Option 1: Use base64 data
document.getElementById("qr").src = `data:image/png;base64,${data.qr_image_base64}`;

// Option 2: Use image endpoint (better for caching)
document.getElementById("qr").src = `/checkin/qr/${data.qr_token}/image`;
```

### 2. Real-time Chat Updates
```javascript
// Poll for new messages every 3 seconds
setInterval(async () => {
  const messages = await fetch(`/chat/rooms/${chatId}/messages?limit=50`);
  updateChatUI(await messages.json());
}, 3000);
```

### 3. Payment Countdown
```javascript
// Show countdown timer
function startCountdown(expiresAt) {
  setInterval(() => {
    const remaining = new Date(expiresAt) - new Date();
    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);
    document.getElementById("timer").textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    
    if (remaining <= 0) {
      alert("Payment window expired!");
    }
  }, 1000);
}
```

### 4. Error Handling
```javascript
async function apiCall(endpoint, options) {
  try {
    const response = await fetch(endpoint, options);
    
    if (!response.ok) {
      const error = await response.json();
      
      if (response.status === 404) {
        showError("Resource not found");
      } else if (response.status === 422) {
        showValidationErrors(error.detail);
      } else {
        showError(error.detail || "An error occurred");
      }
      return null;
    }
    
    return await response.json();
  } catch (e) {
    showError("Network error. Please try again.");
    return null;
  }
}
```

---

## Swagger UI

For interactive API documentation, open: `http://localhost:8000/docs`

All endpoints are available with "Try it out" functionality.
