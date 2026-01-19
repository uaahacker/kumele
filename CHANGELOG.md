# Changelog

All notable changes to the Kumele AI/ML Backend Service are documented in this file.

## [1.2.0] - 2026-01-08

### Added

#### No-Show Probability Prediction (Behavioral Forecasting)
- **New Service**: `kumele_ai/services/no_show_service.py`
  - Interpretable logistic regression model for no-show prediction
  - Feature extraction from user behavioral signals:
    - `user_no_show_rate` - Historical no-show rate (weight: 2.5)
    - `user_late_cancellation_rate` - Late cancel rate (weight: 1.2)
    - `event_is_free` - Free event indicator (weight: 0.7)
    - `user_booking_recency_days` - Days since last booking (weight: 0.3)
    - `event_distance_km` - Distance to event (weight: 0.15)
    - `host_avg_rating` - Host reputation (weight: -0.4)
    - `user_prepaid` - Prepayment indicator (weight: -1.0)
    - `event_start_hour_bin` - Time-of-day effect (weight: 0.1)
  - Confidence scoring based on data availability
  - Full audit logging with feature snapshots
  - Batch prediction for forecasting dashboards
  - User profile management for feedback loop

- **New API Endpoints** (in `ml.py`):
  - `POST /ml/no-show/predict` - Predict no-show probability
  - `POST /ml/no-show/outcome` - Record actual outcome (feedback)
  - `POST /ml/no-show/batch-predict` - Batch prediction
  - `POST /ml/no-show/update-profile/{user_id}` - Update user profile

- **New Database Tables** (in `schema.sql`):
  - `user_attendance_profile` - User behavioral signals (no-show rate, late cancel rate, total bookings)
  - `no_show_predictions` - Audit log with feature snapshots, outcomes, and model versions
  - `event_category_noshow_stats` - Aggregated no-show rates by category

- **New ORM Models** (in `models.py`):
  - `UserAttendanceProfile`
  - `NoShowPrediction`
  - `EventCategoryNoShowStats`

#### Attendance Verification (Trust & Fraud Detection)
- **New Service**: `kumele_ai/services/attendance_verification_service.py`
  - Rule-enhanced classifier (rules first, ML second)
  - 7 verification signals with configurable weights:
    - `qr_replay_detected` (0.60) - Same QR scanned multiple times
    - `gps_spoof_detected` (0.50) - Location mocking detected
    - `gps_mismatch` (0.35) - User too far from event venue
    - `device_untrusted` (0.25) - Unknown device fingerprint
    - `timing_anomaly` (0.15) - Check-in outside valid window
    - `host_no_confirmation` (0.20) - Host didn't confirm arrival
    - `low_trust_score` (0.20) - User has low trust profile
  - Risk score calculation (0.0-1.0 scale)
  - Status determination:
    - `Valid` (≤0.3) - Accept, unlock rewards/reviews/escrow
    - `Suspicious` (≤0.7) - Restrict access, escalate to support
    - `Fraudulent` (>0.7) - Block, escalate to support
  - Haversine GPS distance calculation
  - QR replay detection with time window
  - Device fingerprint registry
  - User trust profile management with recovery mechanism
  - Mandatory support decision feedback loop

- **New API Endpoints** (in `ml.py`):
  - `POST /ml/attendance/verify` - Verify check-in attempt
  - `POST /ml/attendance/support-decision` - Record support decision (feedback)
  - `GET /ml/attendance/history` - Get verification audit trail

- **New Database Tables** (in `schema.sql`):
  - `attendance_verifications` - Full audit trail with signals, support resolution
  - `device_fingerprints` - Device registry for fraud detection
  - `user_trust_profile` - Aggregated trust/fraud signals per user
  - `qr_scan_log` - QR replay detection log

- **New ORM Models** (in `models.py`):
  - `AttendanceVerification`
  - `DeviceFingerprint`
  - `UserTrustProfile`
  - `QRScanLog`

### Updated

#### Integration
- `kumele_ai/services/__init__.py` - Exported `no_show_service`, `attendance_verification_service`
- `kumele_ai/api/ml.py` - Added 7 new endpoints with Pydantic models
- `README.md` - Updated features, endpoints, and project structure

---

## [1.1.0] - 2026-01-07

### Added

#### Taxonomy Sync API (`GET /taxonomy/interests`)
- **New Service**: `kumele_ai/services/taxonomy_service.py`
  - Manages canonical ML-owned interest/hobby taxonomy
  - Interest IDs (not strings) drive the system
  - Supports hierarchical interests with `parent_id`
  - Generates embeddings for interests automatically
  - Includes sync helper to migrate from legacy hobbies table

- **New API Router**: `kumele_ai/api/taxonomy.py`
  - `GET /taxonomy/interests?updated_since=timestamp` - Incremental sync for clients
  - `GET /taxonomy/interests/{interest_id}` - Single interest lookup with translations
  - `POST /taxonomy/interests` - Create new interest with optional translations
  - `PATCH /taxonomy/interests/{interest_id}` - Update interest metadata
  - `DELETE /taxonomy/interests/{interest_id}` - Soft delete (deprecate)
  - `GET /taxonomy/categories` - List unique categories
  - `POST /taxonomy/sync-from-hobbies` - One-time migration from hobbies table

- **New Database Tables** (in `schema.sql`):
  - `interest_taxonomy` - Canonical interests with embeddings, icons, colors
  - `interest_translations` - Lazy-loaded translations by language

- **New ORM Models** (in `models.py`):
  - `InterestTaxonomy`
  - `InterestTranslation`

#### i18n Lazy Loading API (`GET /i18n/{language}?scope=common`)
- **New Service**: `kumele_ai/services/i18n_service.py`
  - Scope-based translation loading (common, events, profile, auth, settings, chat, ads, moderation)
  - Only approved translations served to production
  - Supports bulk import and approval workflow
  - Reduces frontend bundle size via lazy loading

- **New API Router**: `kumele_ai/api/i18n.py`
  - `GET /i18n/{language}?scope=common` - Load translations by scope
  - `GET /i18n/{language}/multiple?scopes=common,events` - Load multiple scopes at once
  - `GET /i18n/{language}/{scope}/{key}` - Get single translation string
  - `POST /i18n/{language}/string` - Set/update translation string
  - `POST /i18n/{language}/bulk` - Bulk import translations
  - `POST /i18n/{language}/{scope}/{key}/approve` - Approve for production
  - `GET /i18n/` - List available languages
  - `GET /i18n/scopes/list` - List available scopes

- **New Database Tables** (in `schema.sql`):
  - `i18n_scopes` - Translation scope definitions
  - `i18n_strings` - Translation strings with approval workflow

- **New ORM Models** (in `models.py`):
  - `I18nScope`
  - `I18nString`

#### Redis Streams Scaffolding
- **New Service**: `kumele_ai/services/stream_service.py`
  - Near-real-time event processing infrastructure
  - 4 dedicated streams:
    - `kumele:stream:nlp` - Sentiment analysis, keyword extraction events
    - `kumele:stream:ads` - Ad impressions, clicks, conversions
    - `kumele:stream:activity` - User activities, ratings, searches
    - `kumele:stream:moderation` - Content moderation events
  - MAXLEN=10000 retention policy
  - Publish methods for all event types
  - Consumer read methods for workers
  - Stream info utilities

#### Timeseries Tables for Analytics
- **New Database Tables** (in `schema.sql`):
  - `timeseries_daily` - Daily aggregated metrics:
    - `date` (unique, indexed)
    - `total_visits`, `unique_visitors`, `registrations`
    - `events_created`, `events_completed`
    - `total_revenue`, `active_users`, `new_users`
  - `timeseries_hourly` - Hourly metrics for monitoring:
    - `timestamp` (indexed)
    - `visits`, `api_calls`, `errors`
    - `avg_response_time_ms`

- **New ORM Models** (in `models.py`):
  - `TimeseriesDaily`
  - `TimeseriesHourly`

### Updated

#### Integration
- `kumele_ai/main.py` - Added taxonomy and i18n routers
- `kumele_ai/api/__init__.py` - Exported taxonomy and i18n modules
- `kumele_ai/services/__init__.py` - Exported stream_service, taxonomy_service, i18n_service
- `README.md` - Updated documentation with new features, endpoints, and project structure

---

## [1.0.1] - 2026-01-07 (Earlier Session)

### Added

#### Nominatim Geocoding Integration
- **New Service**: `kumele_ai/services/geocode_service.py`
  - OpenStreetMap Nominatim geocoding with Redis caching
  - Rate limiting (1 req/sec per Nominatim policy)
  - Automatic retries with exponential backoff
  - Batch geocoding support
  - 24-hour cache TTL (configurable)

#### Updated Matching Service
- `kumele_ai/services/matching_service.py`
  - Integrated geocode_service for location-based matching
  - `GET /match/events?location=Paris,France` geocodes to coordinates
  - Falls back to user's stored lat/lon if geocoding fails

#### Endpoint Path Fixes
- **Split Pricing and Discount**:
  - `GET /pricing/optimise` - Price optimization endpoint
  - `GET /discount/suggestion` - Discount suggestions endpoint (new router)

- **New Router**: `kumele_ai/api/discount.py`
  - Separated from pricing router for correct path structure

### Configuration
- `.env.example` - Added Nominatim environment variables
- `kumele_ai/config.py` - Added Nominatim configuration settings

---

## [1.0.0] - Initial Release

### Features
- RAG Chatbot with Qdrant vector store
- Smart Matching with ML clustering
- Personalized Recommendations (TFRS-style)
- Content Moderation (text, image, video)
- NLP Analysis (sentiment, keywords, trends)
- Dynamic Pricing optimization
- Attendance Prediction (Prophet)
- Support Email Processing
- Multi-language Translation (LibreTranslate/Argos)
- Rewards System with tier-based coupons
- Host Quality Scoring

### API Endpoints (15 routers)
- `/ai/health` - System health
- `/chatbot/*` - RAG chatbot
- `/support/email/*` - Support processing
- `/translate/*` - Translation
- `/ml/*` - Model management
- `/match/*` - Event matching
- `/recommendations/*` - Personalized recommendations
- `/rewards/*` - Rewards system
- `/predict/*` - Forecasting
- `/host/*` - Host ratings
- `/event/*` - Event ratings
- `/ads/*` - Ad intelligence
- `/nlp/*` - NLP analysis
- `/moderation/*` - Content moderation
- `/pricing/*` - Price optimization

### Infrastructure
- Docker Compose setup
- PostgreSQL database schema
- Redis for caching and Celery
- Qdrant for vector embeddings
- Mistral via TGI for LLM
- Celery worker for async tasks
- Synthetic data generator script
