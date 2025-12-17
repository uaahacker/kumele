# Kumele AI/ML System Flows

## Overview

This document describes the end-to-end system flows for Kumele's AI/ML features.

---

## 1. CHECK-IN VALIDATION FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CHECK-IN VALIDATION FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

User Action                API Layer                    Service Layer                    Database
    │                          │                              │                              │
    │  POST /checkin/validate  │                              │                              │
    │─────────────────────────>│                              │                              │
    │  {event_id, user_id,     │                              │                              │
    │   mode: "self_check",    │                              │                              │
    │   lat, lon}              │                              │                              │
    │                          │                              │                              │
    │                          │  validate_checkin()          │                              │
    │                          │─────────────────────────────>│                              │
    │                          │                              │                              │
    │                          │                              │  Query: UserEvent            │
    │                          │                              │─────────────────────────────>│
    │                          │                              │  (check registration)        │
    │                          │                              │<─────────────────────────────│
    │                          │                              │                              │
    │                          │                              │  Query: existing CheckIn     │
    │                          │                              │─────────────────────────────>│
    │                          │                              │  (duplicate check)           │
    │                          │                              │<─────────────────────────────│
    │                          │                              │                              │
    │                          │                              │  ┌────────────────────────┐  │
    │                          │                              │  │ MODE: self_check       │  │
    │                          │                              │  │ • Calculate GPS dist   │  │
    │                          │                              │  │ • Check time window    │  │
    │                          │                              │  │ • Verify device trust  │  │
    │                          │                              │  │ • Calculate risk_score │  │
    │                          │                              │  └────────────────────────┘  │
    │                          │                              │                              │
    │                          │                              │  OR                          │
    │                          │                              │                              │
    │                          │                              │  ┌────────────────────────┐  │
    │                          │                              │  │ MODE: host_qr          │  │
    │                          │                              │  │ • Verify host auth     │  │
    │                          │                              │  │ • Hash QR code         │  │
    │                          │                              │  │ • Check replay attack  │  │
    │                          │                              │  │ • Log QR scan          │  │
    │                          │                              │  └────────────────────────┘  │
    │                          │                              │                              │
    │                          │                              │  INSERT: CheckIn record      │
    │                          │                              │─────────────────────────────>│
    │                          │                              │                              │
    │                          │                              │  UPDATE: UserMLFeatures      │
    │                          │                              │─────────────────────────────>│
    │                          │                              │  (if valid)                  │
    │                          │                              │                              │
    │                          │<─────────────────────────────│                              │
    │                          │  {is_valid, status,          │                              │
    │                          │   risk_score, reason_code}   │                              │
    │                          │                              │                              │
    │<─────────────────────────│                              │                              │
    │  CheckInResponse         │                              │                              │
    │                          │                              │                              │
```

### Decision Rules

```
GPS Distance Check:
  IF distance_km <= 2.0 → PASS
  IF distance_km > 2.0 → FAIL (reason: gps_mismatch)

Time Window Check:
  IF now < (event_start - 30min) → FAIL (reason: too_early)
  IF now > (event_start + 2h) → FAIL (reason: too_late)

QR Replay Check:
  IF same QR used in last 60s → FAIL (reason: qr_replay)
  ELSE → PASS
```

---

## 2. NO-SHOW PREDICTION FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NO-SHOW PREDICTION FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

Client Request             API Layer                    Service Layer                    Database
    │                          │                              │                              │
    │  GET /predict/noshow/123 │                              │                              │
    │─────────────────────────>│                              │                              │
    │                          │                              │                              │
    │                          │  predict_event_noshow()      │                              │
    │                          │─────────────────────────────>│                              │
    │                          │                              │                              │
    │                          │                              │  Query: Event                │
    │                          │                              │─────────────────────────────>│
    │                          │                              │<─────────────────────────────│
    │                          │                              │                              │
    │                          │                              │  Query: All UserEvent        │
    │                          │                              │─────────────────────────────>│
    │                          │                              │  (registrations)             │
    │                          │                              │<─────────────────────────────│
    │                          │                              │                              │
    │                          │                              │  FOR EACH registration:      │
    │                          │                              │  ┌────────────────────────┐  │
    │                          │                              │  │ Extract Features:      │  │
    │                          │                              │  │ • distance_km          │  │
    │                          │                              │  │ • hours_until_event    │  │
    │                          │                              │  │ • user_no_show_rate    │  │
    │                          │                              │  │ • is_paid              │  │
    │                          │                              │  │ • payment_confirmed    │  │
    │                          │                              │  │ • host_reliability     │  │
    │                          │                              │  │ • day_of_week          │  │
    │                          │                              │  │ • rsvp_timing          │  │
    │                          │                              │  │ • nft_badge_level      │  │
    │                          │                              │  └────────────────────────┘  │
    │                          │                              │                              │
    │                          │                              │  ┌────────────────────────┐  │
    │                          │                              │  │ Logistic Regression:   │  │
    │                          │                              │  │                        │  │
    │                          │                              │  │ z = INTERCEPT +        │  │
    │                          │                              │  │     Σ(weight * feature)│  │
    │                          │                              │  │                        │  │
    │                          │                              │  │ P = 1 / (1 + e^(-z))   │  │
    │                          │                              │  └────────────────────────┘  │
    │                          │                              │                              │
    │                          │                              │  Aggregate predictions       │
    │                          │                              │  Calculate avg probability   │
    │                          │                              │                              │
    │                          │<─────────────────────────────│                              │
    │                          │  {probability, risk_level,   │                              │
    │                          │   risk_factors, actions}     │                              │
    │                          │                              │                              │
    │<─────────────────────────│                              │                              │
    │  NoShowPredictionResponse│                              │                              │
    │                          │                              │                              │
```

### Feature Weights (Logistic Regression)

```
FEATURE_WEIGHTS = {
    "distance_km":           0.08,   # Farther = higher no-show
    "hours_until_event":    -0.02,   # Less time = lower no-show
    "user_no_show_rate":     2.50,   # Historical rate is strong predictor
    "is_free_event":         0.30,   # Free events have higher no-shows
    "payment_confirmed":    -0.80,   # Payment reduces no-show
    "host_reliability":     -0.60,   # Good hosts have lower no-shows
    "is_weekend":           -0.15,   # Weekends slightly lower
    "rsvp_within_24h":       0.25,   # Last-minute RSVPs = higher
    "nft_badge_level":      -0.10,   # Per badge level
}
INTERCEPT = -1.5
```

### Risk Levels

```
IF probability < 0.10 → "low"      (Green)
IF probability < 0.25 → "medium"   (Yellow)
IF probability < 0.50 → "high"     (Orange)
IF probability >= 0.50 → "critical" (Red)
```

---

## 3. REWARD TIER CALCULATION FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REWARD TIER CALCULATION FLOW                          │
└─────────────────────────────────────────────────────────────────────────────┘

Trigger Event              Service Layer                    Database
    │                          │                              │
    │  on_successful_checkin() │                              │
    │─────────────────────────>│                              │
    │                          │                              │
    │                          │  Query: CheckIn (30d)        │
    │                          │─────────────────────────────>│
    │                          │  WHERE is_valid = TRUE       │
    │                          │<─────────────────────────────│
    │                          │                              │
    │                          │  ┌────────────────────────┐  │
    │                          │  │ Count Verified Events: │  │
    │                          │  │ • verified_attended    │  │
    │                          │  │ • verified_hosted      │  │
    │                          │  │ = total_verified       │  │
    │                          │  └────────────────────────┘  │
    │                          │                              │
    │                          │  ┌────────────────────────┐  │
    │                          │  │ Tier Calculation:      │  │
    │                          │  │                        │  │
    │                          │  │ IF total >= 4 → Gold   │  │
    │                          │  │ IF total >= 3 → Silver │  │
    │                          │  │ IF total >= 1 → Bronze │  │
    │                          │  │ ELSE → None            │  │
    │                          │  └────────────────────────┘  │
    │                          │                              │
    │                          │  Issue RewardCoupon          │
    │                          │─────────────────────────────>│
    │                          │                              │
    │                          │  ┌────────────────────────┐  │
    │                          │  │ NFT Badge Check:       │  │
    │                          │  │ (Lifetime Events)      │  │
    │                          │  │                        │  │
    │                          │  │ IF total >= 100 →      │  │
    │                          │  │     Legendary          │  │
    │                          │  │ IF total >= 50 →       │  │
    │                          │  │     Platinum           │  │
    │                          │  │ IF total >= 30 →       │  │
    │                          │  │     Gold               │  │
    │                          │  │ IF total >= 15 →       │  │
    │                          │  │     Silver             │  │
    │                          │  │ IF total >= 5 →        │  │
    │                          │  │     Bronze             │  │
    │                          │  └────────────────────────┘  │
    │                          │                              │
    │                          │  Issue/Upgrade NFTBadge      │
    │                          │─────────────────────────────>│
    │                          │                              │
    │                          │  Update UserMLFeatures       │
    │                          │─────────────────────────────>│
    │                          │                              │
    │                          │                              │
```

### Reward Tiers (30-Day Rolling Window)

```
┌─────────────────────────────────────────────────────────────┐
│ TIER      │ THRESHOLD │ DISCOUNT │ STACKABLE │ NFT BOOST  │
├───────────┼───────────┼──────────┼───────────┼────────────┤
│ Bronze    │ 1 event   │ 0%       │ No        │ 0.02       │
│ Silver    │ 3 events  │ 4%       │ No        │ 0.05       │
│ Gold      │ 4 events  │ 8%       │ Yes       │ 0.08       │
└─────────────────────────────────────────────────────────────┘
```

### NFT Badge Tiers (Lifetime Verified Events)

```
┌─────────────────────────────────────────────────────────────┐
│ BADGE     │ THRESHOLD │ DISCOUNT │ TRUST     │ PRIORITY   │
├───────────┼───────────┼──────────┼───────────┼────────────┤
│ Bronze    │ 5         │ 2%       │ +0.02     │ No         │
│ Silver    │ 15        │ 5%       │ +0.05     │ No         │
│ Gold      │ 30        │ 8%       │ +0.08     │ No         │
│ Platinum  │ 50        │ 12%      │ +0.12     │ Yes        │
│ Legendary │ 100       │ 15%      │ +0.20     │ Yes        │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. DYNAMIC PRICING FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DYNAMIC PRICING FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Host Request               API Layer                    Service Layer                    Database
    │                          │                              │                              │
    │  POST /pricing/optimize  │                              │                              │
    │  {event_id, host_id,     │                              │                              │
    │   category, city,        │                              │                              │
    │   capacity}              │                              │                              │
    │─────────────────────────>│                              │                              │
    │                          │                              │                              │
    │                          │  optimize_pricing_enhanced() │                              │
    │                          │─────────────────────────────>│                              │
    │                          │                              │                              │
    │                          │                              │  Query: PricingHistory       │
    │                          │                              │─────────────────────────────>│
    │                          │                              │  (similar events)            │
    │                          │                              │<─────────────────────────────│
    │                          │                              │                              │
    │                          │                              │  ┌────────────────────────┐  │
    │                          │                              │  │ Base Price Analysis:   │  │
    │                          │                              │  │ • Regression model     │  │
    │                          │                              │  │ • Historical avg       │  │
    │                          │                              │  │ • Price elasticity     │  │
    │                          │                              │  └────────────────────────┘  │
    │                          │                              │                              │
    │                          │                              │  Query: UserMLFeatures       │
    │                          │                              │─────────────────────────────>│
    │                          │                              │  (host tier)                 │
    │                          │                              │<─────────────────────────────│
    │                          │                              │                              │
    │                          │                              │  ┌────────────────────────┐  │
    │                          │                              │  │ Host Tier Multiplier:  │  │
    │                          │                              │  │ • Bronze: 1.00x        │  │
    │                          │                              │  │ • Silver: 1.10x        │  │
    │                          │                              │  │ • Gold:   1.25x        │  │
    │                          │                              │  └────────────────────────┘  │
    │                          │                              │                              │
    │                          │                              │  ┌────────────────────────┐  │
    │                          │                              │  │ No-Show Adjustment:    │  │
    │                          │                              │  │ IF no_show >= 30%:     │  │
    │                          │                              │  │   price *= 0.95        │  │
    │                          │                              │  │ IF no_show >= 20%:     │  │
    │                          │                              │  │   price *= 0.97        │  │
    │                          │                              │  └────────────────────────┘  │
    │                          │                              │                              │
    │                          │                              │  ┌────────────────────────┐  │
    │                          │                              │  │ Overbooking Factor:    │  │
    │                          │                              │  │ IF no_show >= 40%:     │  │
    │                          │                              │  │   overbook 20%         │  │
    │                          │                              │  │ IF no_show >= 30%:     │  │
    │                          │                              │  │   overbook 15%         │  │
    │                          │                              │  │ IF no_show >= 20%:     │  │
    │                          │                              │  │   overbook 10%         │  │
    │                          │                              │  │ IF no_show >= 10%:     │  │
    │                          │                              │  │   overbook 5%          │  │
    │                          │                              │  └────────────────────────┘  │
    │                          │                              │                              │
    │                          │                              │  INSERT: PricingHistory      │
    │                          │                              │─────────────────────────────>│
    │                          │                              │                              │
    │                          │<─────────────────────────────│                              │
    │                          │  {recommended_price,         │                              │
    │                          │   pricing_breakdown,         │                              │
    │                          │   overbooking_recommendation}│                              │
    │                          │                              │                              │
    │<─────────────────────────│                              │                              │
    │  PricingResponse         │                              │                              │
    │                          │                              │                              │
```

---

## 5. MATCHING SCORE CALCULATION

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MATCHING SCORE CALCULATION                            │
└─────────────────────────────────────────────────────────────────────────────┘

User Request               API Layer                    Service Layer
    │                          │                              │
    │  GET /match/events       │                              │
    │  ?user_id=123            │                              │
    │─────────────────────────>│                              │
    │                          │                              │
    │                          │  match_events()              │
    │                          │─────────────────────────────>│
    │                          │                              │
    │                          │                              │
    │                          │  ┌────────────────────────────────────────────┐
    │                          │  │                                            │
    │                          │  │  MATCHING SCORE FORMULA:                   │
    │                          │  │                                            │
    │                          │  │  score = distance_score     * 0.25         │
    │                          │  │        + hobby_similarity   * 0.35         │
    │                          │  │        + engagement_score   * 0.10         │
    │                          │  │        + verified_attendance* 0.10         │
    │                          │  │        + nft_badge_score    * 0.08         │
    │                          │  │        + payment_urgency    * 0.05         │
    │                          │  │        + host_reputation    * 0.07         │
    │                          │  │                                            │
    │                          │  │  IF user has NFT badge:                    │
    │                          │  │    score *= badge_multiplier               │
    │                          │  │                                            │
    │                          │  │  Badge Multipliers:                        │
    │                          │  │    Bronze:    1.02x                        │
    │                          │  │    Silver:    1.05x                        │
    │                          │  │    Gold:      1.10x                        │
    │                          │  │    Platinum:  1.15x                        │
    │                          │  │    Legendary: 1.25x                        │
    │                          │  │                                            │
    │                          │  └────────────────────────────────────────────┘
    │                          │                              │
    │                          │<─────────────────────────────│
    │                          │  [{event, match_score,       │
    │                          │    score_breakdown}]         │
    │                          │                              │
    │<─────────────────────────│                              │
    │  MatchingResponse        │                              │
    │                          │                              │
```

---

## 6. TEMPORARY CHAT LIFECYCLE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TEMPORARY CHAT LIFECYCLE                              │
└─────────────────────────────────────────────────────────────────────────────┘

Timeline:
────────────────────────────────────────────────────────────────────────────────

    Event Created          Event Start           Event End           +24h
         │                      │                     │                │
         ▼                      ▼                     ▼                ▼
    ┌─────────┐            ┌─────────┐           ┌─────────┐      ┌─────────┐
    │ CREATED │            │ ACTIVE  │           │ ACTIVE  │      │ EXPIRED │
    │         │───────────>│  CHAT   │──────────>│  CHAT   │─────>│         │
    │ Chat    │            │         │           │ (wind-  │      │ Chat    │
    │ Room    │            │ Users   │           │  down)  │      │ Closed  │
    │         │            │ join    │           │         │      │         │
    └─────────┘            └─────────┘           └─────────┘      └─────────┘
         │                      │                     │                │
         │                      │                     │                │
    Host added             Participants         24h countdown      All data
    as first               can chat             begins             archived
    participant                                                    

State Transitions:
─────────────────
    ACTIVE ──────> EXPIRED     (after expires_at)
    ACTIVE ──────> SUSPENDED   (if toxic_message_count >= 3)
    ACTIVE ──────> CLOSED      (manual close or inactivity)

Message Moderation:
──────────────────
    IF toxicity_score >= 0.7:
        message.status = "flagged"
        chat.toxic_message_count += 1
        
    IF chat.toxic_message_count >= 3:
        chat.status = "suspended"
```

---

## 7. AI OPS MONITORING FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AI OPS MONITORING                                     │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
                    │         MONITORING DASHBOARD        │
                    │                                     │
                    │  ┌──────────────────────────────┐   │
                    │  │ CHECK-IN METRICS             │   │
                    │  │ • Total check-ins (24h)      │   │
                    │  │ • Validation rate            │   │
                    │  │ • Avg risk score             │   │
                    │  │ • By mode breakdown          │   │
                    │  └──────────────────────────────┘   │
                    │                                     │
                    │  ┌──────────────────────────────┐   │
                    │  │ MODEL PERFORMANCE            │   │
                    │  │ • No-show accuracy           │   │
                    │  │ • Precision / Recall         │   │
                    │  │ • F1 Score                   │   │
                    │  │ • Prediction volume          │   │
                    │  └──────────────────────────────┘   │
                    │                                     │
                    │  ┌──────────────────────────────┐   │
                    │  │ DRIFT DETECTION              │   │
                    │  │ • Feature drift score        │   │
                    │  │ • Prediction drift score     │   │
                    │  │ • Alert status               │   │
                    │  └──────────────────────────────┘   │
                    │                                     │
                    └─────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │         ALERT TRIGGERS              │
                    │                                     │
                    │  • Drift score > 2.0 std dev        │
                    │  • Accuracy drop > 10%              │
                    │  • Fraud rate > 20%                 │
                    │  • Service degradation              │
                    │                                     │
                    └─────────────────────────────────────┘

API Endpoints:
─────────────
GET  /ai-ops/metrics/checkins?period=24h
GET  /ai-ops/metrics/models/no_show
GET  /ai-ops/drift/check/no_show
GET  /ai-ops/health
POST /ai-ops/metrics/record
```

---

## 8. END-TO-END EVENT ATTENDANCE FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    END-TO-END EVENT ATTENDANCE FLOW                          │
└─────────────────────────────────────────────────────────────────────────────┘

1. EVENT CREATION
   Host creates event
        │
        ▼
   ┌─────────────────┐
   │ Dynamic Pricing │ ──────> Recommended price based on:
   │                 │         • Historical data
   └─────────────────┘         • Host tier (Bronze/Silver/Gold)
        │                      • Predicted no-show rate
        ▼
   ┌─────────────────┐
   │ TempChat Created│ ──────> Chat room ready for participants
   └─────────────────┘

2. USER DISCOVERY & RSVP
   User searches for events
        │
        ▼
   ┌─────────────────┐
   │ Matching Engine │ ──────> Score based on:
   │                 │         • Distance (25%)
   └─────────────────┘         • Hobby similarity (35%)
        │                      • Verified attendance (10%)
        │                      • NFT badge bonus (8%)
        ▼
   ┌─────────────────┐
   │ No-Show Predict │ ──────> Flag high-risk RSVPs
   └─────────────────┘

3. EVENT DAY - CHECK-IN
   User arrives at venue
        │
        ▼
   ┌─────────────────┐
   │ Check-in API    │ ──────> Mode: host_qr OR self_check
   │                 │
   │ POST /checkin/  │         Validations:
   │     validate    │         • GPS within 2km
   └─────────────────┘         • Time window ±30min
        │                      • QR replay detection
        ▼                      • Device trust score
   ┌─────────────────┐
   │ Risk Scoring    │ ──────> risk_score: 0.0-1.0
   │                 │         status: Valid/Suspicious/Fraudulent
   └─────────────────┘

4. POST-EVENT - REWARDS
   Event completed
        │
        ▼
   ┌─────────────────┐
   │ Reward Check    │ ──────> ONLY verified check-ins count
   │                 │
   │ count_verified_ │         Tier calculation:
   │     events()    │         • Bronze: 1 verified
   └─────────────────┘         • Silver: 3 verified
        │                      • Gold: 4 verified (stackable)
        ▼
   ┌─────────────────┐
   │ NFT Badge Check │ ──────> Lifetime verified events
   │                 │         • Bronze: 5 events
   │ check_and_issue_│         • Silver: 15 events
   │     badge()     │         • Gold: 30 events
   └─────────────────┘         • Platinum: 50 events
        │                      • Legendary: 100 events
        ▼
   ┌─────────────────┐
   │ Update ML       │ ──────> UserMLFeatures updated
   │ Features        │         • verified_attendance_30d
   └─────────────────┘         • reward_tier
                               • nft_badge_type
                               • trust_score
```

---

## API Reference Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/checkin/validate` | POST | Validate check-in (host_qr/self_check) |
| `/checkin/event/{id}/status` | GET | Get event check-in statistics |
| `/predict/noshow/{event_id}` | GET | Predict no-show for event |
| `/predict/noshow/user` | POST | Predict no-show for user |
| `/rewards/suggestion/{user_id}` | GET | Get reward tier and coupons |
| `/pricing/optimize` | POST | Get optimized pricing |
| `/match/events` | GET | Get matched events for user |
| `/ai-ops/metrics/checkins` | GET | Get check-in metrics |
| `/ai-ops/health` | GET | Get system health |

---

*Last Updated: January 2025*
*Version: 1.0.0*
