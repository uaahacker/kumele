-- Kumele AI/ML Database Schema
-- Version: 1.0.0
-- Run this script to create all required tables

-- =====================================================
-- 3.1 Synthetic Base Schema
-- =====================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    age INTEGER,
    gender VARCHAR(20),
    address TEXT,
    latitude FLOAT,
    longitude FLOAT,
    city VARCHAR(100),
    country VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_users_city ON users(city);
CREATE INDEX idx_users_location ON users(latitude, longitude);

-- Hobbies table
CREATE TABLE IF NOT EXISTS hobbies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_hobbies_category ON hobbies(category);

-- User Hobbies (many-to-many)
CREATE TABLE IF NOT EXISTS user_hobbies (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hobby_id INTEGER NOT NULL REFERENCES hobbies(id) ON DELETE CASCADE,
    skill_level VARCHAR(50),
    interest_level INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, hobby_id)
);

CREATE INDEX idx_user_hobbies_user ON user_hobbies(user_id);
CREATE INDEX idx_user_hobbies_hobby ON user_hobbies(hobby_id);

-- Events table
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    hobby_id INTEGER REFERENCES hobbies(id),
    hobby_tags JSONB,
    event_date TIMESTAMP NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    location TEXT,
    latitude FLOAT,
    longitude FLOAT,
    city VARCHAR(100),
    country VARCHAR(100),
    capacity INTEGER,
    is_paid BOOLEAN DEFAULT FALSE,
    price NUMERIC(10, 2) DEFAULT 0,
    currency VARCHAR(10) DEFAULT 'USD',
    status VARCHAR(50) DEFAULT 'upcoming',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_events_host ON events(host_id);
CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_hobby ON events(hobby_id);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_location ON events(latitude, longitude);
CREATE INDEX idx_events_city ON events(city);

-- User Events (RSVPs/Attendance)
CREATE TABLE IF NOT EXISTS user_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    rsvp_status VARCHAR(50) DEFAULT 'registered',
    checked_in BOOLEAN DEFAULT FALSE,
    check_in_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(user_id, event_id)
);

CREATE INDEX idx_user_events_user ON user_events(user_id);
CREATE INDEX idx_user_events_event ON user_events(event_id);
CREATE INDEX idx_user_events_status ON user_events(rsvp_status);

-- Event Ratings
CREATE TABLE IF NOT EXISTS event_ratings (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating FLOAT NOT NULL,
    communication_score FLOAT,
    respect_score FLOAT,
    professionalism_score FLOAT,
    atmosphere_score FLOAT,
    value_score FLOAT,
    comment TEXT,
    moderation_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, event_id)
);

CREATE INDEX idx_event_ratings_event ON event_ratings(event_id);

-- Blogs table
CREATE TABLE IF NOT EXISTS blogs (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    hobby_tags JSONB,
    status VARCHAR(50) DEFAULT 'published',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_blogs_author ON blogs(author_id);
CREATE INDEX idx_blogs_status ON blogs(status);

-- Blog Interactions
CREATE TABLE IF NOT EXISTS blog_interactions (
    id SERIAL PRIMARY KEY,
    blog_id INTEGER NOT NULL REFERENCES blogs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_blog_interactions_blog ON blog_interactions(blog_id);
CREATE INDEX idx_blog_interactions_user ON blog_interactions(user_id);
CREATE INDEX idx_blog_interactions_type ON blog_interactions(interaction_type);

-- Ads table
CREATE TABLE IF NOT EXISTS ads (
    id SERIAL PRIMARY KEY,
    advertiser_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    image_url TEXT,
    image_tags JSONB,
    target_hobbies JSONB,
    target_locations JSONB,
    target_age_min INTEGER,
    target_age_max INTEGER,
    budget NUMERIC(10, 2),
    cpc NUMERIC(10, 4),
    status VARCHAR(50) DEFAULT 'draft',
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_ads_advertiser ON ads(advertiser_id);
CREATE INDEX idx_ads_status ON ads(status);

-- Ad Interactions
CREATE TABLE IF NOT EXISTS ad_interactions (
    id SERIAL PRIMARY KEY,
    ad_id INTEGER NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id),
    interaction_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ad_interactions_ad ON ad_interactions(ad_id);
CREATE INDEX idx_ad_interactions_type ON ad_interactions(interaction_type);
CREATE INDEX idx_ad_interactions_date ON ad_interactions(created_at);

-- Referrals table
CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_id INTEGER NOT NULL REFERENCES users(id),
    referred_id INTEGER NOT NULL REFERENCES users(id),
    referral_code VARCHAR(50) UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX idx_referrals_code ON referrals(referral_code);

-- =====================================================
-- 3.2 Rewards Tables
-- =====================================================

-- User Activities (source of truth for rewards)
CREATE TABLE IF NOT EXISTS user_activities (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL, -- event_created, event_attended
    event_id INTEGER REFERENCES events(id),
    activity_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_activities_user ON user_activities(user_id);
CREATE INDEX idx_user_activities_date ON user_activities(user_id, activity_date);
CREATE INDEX idx_user_activities_type ON user_activities(activity_type);

-- Reward Coupons
CREATE TABLE IF NOT EXISTS reward_coupons (
    coupon_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status_level VARCHAR(20) NOT NULL, -- Bronze, Silver, Gold
    discount_value FLOAT NOT NULL,
    stackable BOOLEAN DEFAULT FALSE,
    is_redeemed BOOLEAN DEFAULT FALSE,
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    redeemed_at TIMESTAMP
);

CREATE INDEX idx_reward_coupons_user ON reward_coupons(user_id);
CREATE INDEX idx_reward_coupons_status ON reward_coupons(status_level);
CREATE INDEX idx_reward_coupons_redeemed ON reward_coupons(is_redeemed);

-- =====================================================
-- 3.3 Moderation Tables
-- =====================================================

CREATE TABLE IF NOT EXISTS moderation_jobs (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(255) NOT NULL,
    content_type VARCHAR(50) NOT NULL, -- text, image, video
    subtype VARCHAR(100),
    content_data TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed
    decision VARCHAR(50), -- approve, reject, needs_review
    labels JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);

CREATE INDEX idx_moderation_jobs_content ON moderation_jobs(content_id);
CREATE INDEX idx_moderation_jobs_status ON moderation_jobs(status);
CREATE INDEX idx_moderation_jobs_type ON moderation_jobs(content_type);

-- =====================================================
-- 3.4 Chatbot Knowledge & Logs
-- =====================================================

-- Knowledge Documents
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL, -- faq, blog, event, policy
    language VARCHAR(10) DEFAULT 'en',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_docs_category ON knowledge_documents(category);
CREATE INDEX idx_knowledge_docs_language ON knowledge_documents(language);

-- Knowledge Embeddings
CREATE TABLE IF NOT EXISTS knowledge_embeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT,
    embedding_model VARCHAR(255),
    vector_id VARCHAR(255), -- Qdrant point ID
    last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_embeddings_doc ON knowledge_embeddings(document_id);
CREATE INDEX idx_knowledge_embeddings_vector ON knowledge_embeddings(vector_id);

-- Chatbot Logs
CREATE TABLE IF NOT EXISTS chatbot_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    query TEXT NOT NULL,
    response TEXT,
    language VARCHAR(10),
    confidence FLOAT,
    source_docs JSONB,
    feedback VARCHAR(50), -- helpful, not_helpful
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chatbot_logs_user ON chatbot_logs(user_id);
CREATE INDEX idx_chatbot_logs_date ON chatbot_logs(created_at);

-- =====================================================
-- 3.5 Support Email Tables
-- =====================================================

-- Support Emails
CREATE TABLE IF NOT EXISTS support_emails (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR(255),
    from_email VARCHAR(255) NOT NULL,
    to_email VARCHAR(255),
    subject VARCHAR(500),
    raw_body TEXT,
    cleaned_text TEXT,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'new' -- new, analyzed, replied, escalated, closed
);

CREATE INDEX idx_support_emails_thread ON support_emails(thread_id);
CREATE INDEX idx_support_emails_status ON support_emails(status);
CREATE INDEX idx_support_emails_date ON support_emails(received_at);

-- Support Email Analysis
CREATE TABLE IF NOT EXISTS support_email_analysis (
    id SERIAL PRIMARY KEY,
    email_id INTEGER NOT NULL REFERENCES support_emails(id) ON DELETE CASCADE,
    category VARCHAR(100),
    sentiment VARCHAR(50),
    sentiment_score FLOAT,
    urgency VARCHAR(50),
    keywords JSONB,
    suggested_response TEXT,
    confidence FLOAT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_analysis_email ON support_email_analysis(email_id);

-- Support Email Replies
CREATE TABLE IF NOT EXISTS support_email_replies (
    id SERIAL PRIMARY KEY,
    email_id INTEGER NOT NULL REFERENCES support_emails(id) ON DELETE CASCADE,
    draft_response TEXT,
    final_response TEXT,
    response_type VARCHAR(50), -- ai_generated, human_edited, human_written
    sent_status VARCHAR(50) DEFAULT 'draft', -- draft, sent, failed
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_replies_email ON support_email_replies(email_id);

-- Support Email Escalations
CREATE TABLE IF NOT EXISTS support_email_escalations (
    id SERIAL PRIMARY KEY,
    email_id INTEGER NOT NULL REFERENCES support_emails(id) ON DELETE CASCADE,
    escalation_reason TEXT,
    escalation_level VARCHAR(50),
    assigned_to VARCHAR(255),
    escalated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);

CREATE INDEX idx_email_escalations_email ON support_email_escalations(email_id);

-- =====================================================
-- 3.6 Global Action Logs
-- =====================================================

CREATE TABLE IF NOT EXISTS ai_action_logs (
    id SERIAL PRIMARY KEY,
    action_type VARCHAR(100) NOT NULL,
    endpoint VARCHAR(255),
    user_id INTEGER,
    input_data JSONB,
    output_data JSONB,
    model_used VARCHAR(255),
    processing_time_ms INTEGER,
    status VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_logs_type ON ai_action_logs(action_type);
CREATE INDEX idx_ai_logs_date ON ai_action_logs(created_at);
CREATE INDEX idx_ai_logs_user ON ai_action_logs(user_id);

-- =====================================================
-- 3.7 AI Model Registry
-- =====================================================

CREATE TABLE IF NOT EXISTS ai_model_registry (
    name VARCHAR(255) PRIMARY KEY,
    version VARCHAR(100),
    type VARCHAR(50), -- llm, embedder, classifier, translator
    status VARCHAR(50) DEFAULT 'inactive', -- active, inactive, loading
    loaded_at TIMESTAMP,
    config JSONB
);

-- =====================================================
-- 3.8 Dynamic Pricing/Discount Tables
-- =====================================================

-- Pricing History
CREATE TABLE IF NOT EXISTS pricing_history (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    price NUMERIC(10, 2) NOT NULL,
    turnout INTEGER,
    host_score FLOAT,
    city VARCHAR(100),
    date DATE,
    revenue NUMERIC(12, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pricing_history_event ON pricing_history(event_id);
CREATE INDEX idx_pricing_history_city ON pricing_history(city);
CREATE INDEX idx_pricing_history_date ON pricing_history(date);

-- Discount Suggestions
CREATE TABLE IF NOT EXISTS discount_suggestions (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    discount_type VARCHAR(50),
    value_percent FLOAT,
    segment VARCHAR(100),
    expected_uplift FLOAT,
    expected_roi FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_discount_suggestions_event ON discount_suggestions(event_id);

-- =====================================================
-- Additional Tables
-- =====================================================

-- NLP Sentiment Results
CREATE TABLE IF NOT EXISTS nlp_sentiment (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(255),
    content_hash VARCHAR(64),
    text TEXT,
    sentiment VARCHAR(50),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_nlp_sentiment_content ON nlp_sentiment(content_id);
CREATE INDEX idx_nlp_sentiment_hash ON nlp_sentiment(content_hash);

-- NLP Keywords
CREATE TABLE IF NOT EXISTS nlp_keywords (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(255),
    keyword VARCHAR(255),
    keyword_type VARCHAR(50), -- topic, entity, hobby
    score FLOAT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_nlp_keywords_content ON nlp_keywords(content_id);
CREATE INDEX idx_nlp_keywords_keyword ON nlp_keywords(keyword);
CREATE INDEX idx_nlp_keywords_date ON nlp_keywords(keyword, extracted_at);

-- Host Ratings (aggregated)
CREATE TABLE IF NOT EXISTS host_ratings (
    id SERIAL PRIMARY KEY,
    host_id INTEGER NOT NULL REFERENCES users(id) UNIQUE,
    total_events INTEGER DEFAULT 0,
    completed_events INTEGER DEFAULT 0,
    total_attendees INTEGER DEFAULT 0,
    repeat_attendees INTEGER DEFAULT 0,
    avg_communication FLOAT,
    avg_respect FLOAT,
    avg_professionalism FLOAT,
    avg_atmosphere FLOAT,
    avg_value FLOAT,
    overall_score FLOAT,
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_host_ratings_host ON host_ratings(host_id);
CREATE INDEX idx_host_ratings_score ON host_ratings(overall_score);

-- =====================================================
-- 3.9 Timeseries Tables (for Prophet forecasting)
-- =====================================================

-- Daily Timeseries Data
CREATE TABLE IF NOT EXISTS timeseries_daily (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_visits INTEGER DEFAULT 0,
    unique_visitors INTEGER DEFAULT 0,
    registrations INTEGER DEFAULT 0,
    events_created INTEGER DEFAULT 0,
    events_completed INTEGER DEFAULT 0,
    total_revenue NUMERIC(12, 2) DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timeseries_daily_date ON timeseries_daily(date);

-- Hourly Timeseries Data
CREATE TABLE IF NOT EXISTS timeseries_hourly (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL UNIQUE,
    visits INTEGER DEFAULT 0,
    api_calls INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timeseries_hourly_timestamp ON timeseries_hourly(timestamp);

-- =====================================================
-- 3.10 Interest/Hobby Taxonomy (ML-owned)
-- =====================================================

-- Interest Taxonomy (canonical source for ML)
CREATE TABLE IF NOT EXISTS interest_taxonomy (
    interest_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(100),
    parent_id INTEGER REFERENCES interest_taxonomy(interest_id),
    icon_key VARCHAR(100),
    color_token VARCHAR(50),
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    embedding_vector JSONB,  -- Store precomputed embedding
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_interest_taxonomy_category ON interest_taxonomy(category);
CREATE INDEX idx_interest_taxonomy_active ON interest_taxonomy(is_active);
CREATE INDEX idx_interest_taxonomy_updated ON interest_taxonomy(updated_at);

-- Interest Translations (lazy-loaded by scope)
CREATE TABLE IF NOT EXISTS interest_translations (
    id SERIAL PRIMARY KEY,
    interest_id INTEGER NOT NULL REFERENCES interest_taxonomy(interest_id) ON DELETE CASCADE,
    language VARCHAR(10) NOT NULL,
    label VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(interest_id, language)
);

CREATE INDEX idx_interest_translations_lang ON interest_translations(language);

-- =====================================================
-- 3.11 i18n Translation Tables (lazy-loading)
-- =====================================================

-- Translation Scopes
CREATE TABLE IF NOT EXISTS i18n_scopes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,  -- common, auth, home, events, hobbies, profile
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Translation Strings
CREATE TABLE IF NOT EXISTS i18n_strings (
    id SERIAL PRIMARY KEY,
    scope_id INTEGER NOT NULL REFERENCES i18n_scopes(id) ON DELETE CASCADE,
    key VARCHAR(255) NOT NULL,
    language VARCHAR(10) NOT NULL,
    value TEXT NOT NULL,
    is_approved BOOLEAN DEFAULT FALSE,
    is_locked BOOLEAN DEFAULT FALSE,  -- Prevent overwrite
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scope_id, key, language)
);

CREATE INDEX idx_i18n_strings_scope ON i18n_strings(scope_id);
CREATE INDEX idx_i18n_strings_lang ON i18n_strings(language);
CREATE INDEX idx_i18n_strings_key ON i18n_strings(key);
CREATE INDEX idx_i18n_strings_approved ON i18n_strings(is_approved);


-- =====================================================
-- 3.12 No-Show Prediction System (Behavioral Forecasting)
-- =====================================================

-- User Behavioral Profile for No-Show Prediction
CREATE TABLE IF NOT EXISTS user_attendance_profile (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_rsvps INTEGER DEFAULT 0,
    total_check_ins INTEGER DEFAULT 0,
    total_no_shows INTEGER DEFAULT 0,
    late_cancellations INTEGER DEFAULT 0,
    payment_timeouts INTEGER DEFAULT 0,
    failed_payments INTEGER DEFAULT 0,
    avg_rsvp_to_event_hours FLOAT,  -- Average time between RSVP and event start
    last_minute_rsvp_count INTEGER DEFAULT 0,  -- RSVPs < 24h before event
    avg_distance_km FLOAT,  -- Average travel distance to events
    max_distance_km FLOAT,  -- Maximum travel distance ever
    check_in_rate FLOAT,  -- total_check_ins / total_rsvps
    no_show_rate FLOAT,  -- total_no_shows / total_rsvps
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

CREATE INDEX idx_user_attendance_profile_user ON user_attendance_profile(user_id);
CREATE INDEX idx_user_attendance_profile_noshow ON user_attendance_profile(no_show_rate);

-- No-Show Prediction Log (Audit Trail)
CREATE TABLE IF NOT EXISTS no_show_predictions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    event_id INTEGER NOT NULL REFERENCES events(id),
    no_show_probability FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    -- Feature snapshot for explainability
    features JSONB NOT NULL,
    -- Context at prediction time
    price_mode VARCHAR(20),  -- 'paid', 'free', 'pay_in_person'
    distance_km FLOAT,
    rsvp_timestamp TIMESTAMP,
    event_start_timestamp TIMESTAMP,
    hours_until_event FLOAT,
    -- Model metadata
    model_version VARCHAR(50),
    -- Outcome tracking (filled after event)
    actual_outcome VARCHAR(20),  -- 'attended', 'no_show', 'cancelled', NULL
    outcome_recorded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_noshow_pred_user ON no_show_predictions(user_id);
CREATE INDEX idx_noshow_pred_event ON no_show_predictions(event_id);
CREATE INDEX idx_noshow_pred_created ON no_show_predictions(created_at);
CREATE INDEX idx_noshow_pred_outcome ON no_show_predictions(actual_outcome);

-- Event Category No-Show Rates (Aggregated)
CREATE TABLE IF NOT EXISTS event_category_noshow_stats (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    price_mode VARCHAR(20) NOT NULL,
    day_of_week INTEGER,  -- 0=Monday, 6=Sunday
    hour_of_day INTEGER,  -- 0-23
    total_rsvps INTEGER DEFAULT 0,
    total_no_shows INTEGER DEFAULT 0,
    avg_no_show_rate FLOAT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, price_mode, day_of_week, hour_of_day)
);

CREATE INDEX idx_category_noshow_stats ON event_category_noshow_stats(category, price_mode);


-- =====================================================
-- 3.13 Attendance Verification AI (Trust & Fraud Detection)
-- =====================================================

-- Check-In Verification Log (Audit Trail - MANDATORY)
CREATE TABLE IF NOT EXISTS attendance_verifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    event_id INTEGER NOT NULL REFERENCES events(id),
    -- Verification Result
    check_in_status VARCHAR(20) NOT NULL,  -- 'Valid', 'Suspicious', 'Fraudulent'
    risk_score FLOAT NOT NULL,
    action VARCHAR(30) NOT NULL,  -- 'accept', 'restrict', 'escalate_to_support'
    signals JSONB NOT NULL,  -- Array of triggered signals
    -- Input Signals Snapshot
    user_latitude FLOAT,
    user_longitude FLOAT,
    event_latitude FLOAT,
    event_longitude FLOAT,
    distance_km FLOAT,
    qr_scan_timestamp TIMESTAMP,
    event_start_timestamp TIMESTAMP,
    event_end_timestamp TIMESTAMP,
    minutes_from_start FLOAT,  -- Negative = early, positive = late
    device_hash VARCHAR(255),
    device_os VARCHAR(50),
    app_instance_id VARCHAR(255),
    host_confirmed BOOLEAN,
    -- Model metadata
    model_version VARCHAR(50),
    rules_triggered JSONB,  -- Which rules fired
    ml_score FLOAT,  -- ML model contribution
    -- Support Resolution (if escalated)
    support_decision VARCHAR(30),  -- 'confirmed_valid', 'confirmed_fraud', 'inconclusive'
    support_decision_at TIMESTAMP,
    support_notes TEXT,
    -- Outcome
    rewards_unlocked BOOLEAN DEFAULT FALSE,
    reviews_unlocked BOOLEAN DEFAULT FALSE,
    escrow_released BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attendance_verify_user ON attendance_verifications(user_id);
CREATE INDEX idx_attendance_verify_event ON attendance_verifications(event_id);
CREATE INDEX idx_attendance_verify_status ON attendance_verifications(check_in_status);
CREATE INDEX idx_attendance_verify_action ON attendance_verifications(action);
CREATE INDEX idx_attendance_verify_created ON attendance_verifications(created_at);

-- Device Fingerprint Registry (Fraud Detection)
CREATE TABLE IF NOT EXISTS device_fingerprints (
    id SERIAL PRIMARY KEY,
    device_hash VARCHAR(255) NOT NULL,
    device_os VARCHAR(50),
    app_instance_id VARCHAR(255),
    user_id INTEGER NOT NULL REFERENCES users(id),
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    check_in_count INTEGER DEFAULT 0,
    is_flagged BOOLEAN DEFAULT FALSE,
    flag_reason TEXT,
    UNIQUE(device_hash, user_id)
);

CREATE INDEX idx_device_fp_hash ON device_fingerprints(device_hash);
CREATE INDEX idx_device_fp_user ON device_fingerprints(user_id);
CREATE INDEX idx_device_fp_flagged ON device_fingerprints(is_flagged);

-- User Trust Profile (Aggregated Fraud Signals)
CREATE TABLE IF NOT EXISTS user_trust_profile (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trust_score FLOAT DEFAULT 1.0,  -- 0.0 (untrusted) to 1.0 (fully trusted)
    total_verifications INTEGER DEFAULT 0,
    valid_count INTEGER DEFAULT 0,
    suspicious_count INTEGER DEFAULT 0,
    fraudulent_count INTEGER DEFAULT 0,
    gps_mismatch_count INTEGER DEFAULT 0,
    qr_replay_count INTEGER DEFAULT 0,
    device_anomaly_count INTEGER DEFAULT 0,
    penalties_applied INTEGER DEFAULT 0,
    last_penalty_at TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

CREATE INDEX idx_user_trust_profile_user ON user_trust_profile(user_id);
CREATE INDEX idx_user_trust_profile_score ON user_trust_profile(trust_score);

-- QR Code Usage Log (Replay Detection)
CREATE TABLE IF NOT EXISTS qr_scan_log (
    id SERIAL PRIMARY KEY,
    qr_code_hash VARCHAR(255) NOT NULL,
    event_id INTEGER NOT NULL REFERENCES events(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    device_hash VARCHAR(255),
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_valid BOOLEAN DEFAULT TRUE,
    rejection_reason VARCHAR(100)
);

CREATE INDEX idx_qr_scan_qr ON qr_scan_log(qr_code_hash);
CREATE INDEX idx_qr_scan_event ON qr_scan_log(event_id);
CREATE INDEX idx_qr_scan_time ON qr_scan_log(scanned_at);
