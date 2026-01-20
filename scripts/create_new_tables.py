#!/usr/bin/env python3
"""
Database Migration Script for New AI/ML Tables

Creates the new tables added for:
- Check-in System (checkins)
- NFT Badge System (nft_badges, nft_badge_history)
- Temp Chat System (temp_chats, temp_chat_messages, temp_chat_participants)
- ML Features (user_ml_features, event_ml_features)
- AI Ops Monitoring (ai_metrics, model_drift_log)

Usage:
    docker-compose exec api python scripts/create_new_tables.py
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

try:
    from kumele_ai.db.database import engine
except ImportError:
    print("Error: Could not import database engine.")
    print("Make sure you're running from the project root with dependencies installed.")
    sys.exit(1)


# SQL statements to create new tables
CREATE_TABLES_SQL = """
-- ============================================================
-- CHECK-IN SYSTEM
-- ============================================================
CREATE TABLE IF NOT EXISTS checkins (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    mode VARCHAR(20) NOT NULL,
    is_valid BOOLEAN DEFAULT FALSE,
    distance_km FLOAT,
    risk_score FLOAT DEFAULT 0.0,
    reason_code VARCHAR(100),
    user_latitude FLOAT,
    user_longitude FLOAT,
    qr_code_hash VARCHAR(255),
    device_hash VARCHAR(255),
    host_confirmed BOOLEAN DEFAULT FALSE,
    check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_start_time TIMESTAMP,
    minutes_from_start FLOAT,
    verification_id INTEGER REFERENCES attendance_verifications(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_event_user_checkin UNIQUE (event_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_checkin_event ON checkins(event_id);
CREATE INDEX IF NOT EXISTS idx_checkin_user ON checkins(user_id);
CREATE INDEX IF NOT EXISTS idx_checkin_valid ON checkins(is_valid);
CREATE INDEX IF NOT EXISTS idx_checkin_mode ON checkins(mode);
CREATE INDEX IF NOT EXISTS idx_checkin_risk ON checkins(risk_score);

-- ============================================================
-- NFT BADGE SYSTEM
-- ============================================================
CREATE TABLE IF NOT EXISTS nft_badges (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    badge_type VARCHAR(50) NOT NULL,
    token_id VARCHAR(255) UNIQUE,
    contract_address VARCHAR(255),
    chain VARCHAR(50) DEFAULT 'polygon',
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    earned_reason VARCHAR(255),
    experience_points INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    trust_boost FLOAT DEFAULT 0.0,
    price_discount_percent FLOAT DEFAULT 0.0,
    priority_matching BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    revoked_at TIMESTAMP,
    revoked_reason VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_nft_badge_user ON nft_badges(user_id);
CREATE INDEX IF NOT EXISTS idx_nft_badge_type ON nft_badges(badge_type);
CREATE INDEX IF NOT EXISTS idx_nft_badge_active ON nft_badges(is_active);

CREATE TABLE IF NOT EXISTS nft_badge_history (
    id SERIAL PRIMARY KEY,
    badge_id INTEGER NOT NULL REFERENCES nft_badges(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    old_level INTEGER,
    new_level INTEGER,
    old_xp INTEGER,
    new_xp INTEGER,
    reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TEMP CHAT SYSTEM
-- ============================================================
CREATE TABLE IF NOT EXISTS temp_chats (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    chat_type VARCHAR(50) DEFAULT 'event',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    close_reason VARCHAR(100),
    message_count INTEGER DEFAULT 0,
    active_participants INTEGER DEFAULT 0,
    last_message_at TIMESTAMP,
    avg_messages_per_hour FLOAT DEFAULT 0.0,
    toxic_message_count INTEGER DEFAULT 0,
    moderation_flags INTEGER DEFAULT 0,
    is_suspended BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_temp_chat_event ON temp_chats(event_id);
CREATE INDEX IF NOT EXISTS idx_temp_chat_status ON temp_chats(status);
CREATE INDEX IF NOT EXISTS idx_temp_chat_expires ON temp_chats(expires_at);

CREATE TABLE IF NOT EXISTS temp_chat_messages (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES temp_chats(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    is_moderated BOOLEAN DEFAULT FALSE,
    moderation_status VARCHAR(50),
    toxicity_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edited_at TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_temp_chat_msg_chat ON temp_chat_messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_temp_chat_msg_user ON temp_chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_temp_chat_msg_moderated ON temp_chat_messages(is_moderated);

CREATE TABLE IF NOT EXISTS temp_chat_participants (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES temp_chats(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'attendee',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    message_count INTEGER DEFAULT 0,
    last_read_at TIMESTAMP,
    CONSTRAINT unique_chat_participant UNIQUE (chat_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_temp_chat_part_chat ON temp_chat_participants(chat_id);
CREATE INDEX IF NOT EXISTS idx_temp_chat_part_user ON temp_chat_participants(user_id);

-- ============================================================
-- USER ML FEATURES
-- ============================================================
CREATE TABLE IF NOT EXISTS user_ml_features (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    verified_attendance_30d INTEGER DEFAULT 0,
    verified_attendance_90d INTEGER DEFAULT 0,
    attendance_rate_30d FLOAT DEFAULT 0.0,
    attendance_rate_90d FLOAT DEFAULT 0.0,
    no_show_rate_30d FLOAT DEFAULT 0.0,
    no_show_rate_90d FLOAT DEFAULT 0.0,
    reward_tier VARCHAR(20) DEFAULT 'None',
    total_rewards_earned INTEGER DEFAULT 0,
    coupons_available INTEGER DEFAULT 0,
    nft_badge_type VARCHAR(50),
    nft_badge_level INTEGER DEFAULT 0,
    nft_trust_boost FLOAT DEFAULT 0.0,
    payment_method_mix JSONB,
    avg_payment_time_minutes FLOAT,
    payment_timeout_rate FLOAT DEFAULT 0.0,
    payment_failure_rate FLOAT DEFAULT 0.0,
    trust_score FLOAT DEFAULT 1.0,
    fraud_flag_count INTEGER DEFAULT 0,
    events_attended_total INTEGER DEFAULT 0,
    events_hosted_total INTEGER DEFAULT 0,
    avg_rating_given FLOAT,
    avg_rating_received FLOAT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_ml_features_user ON user_ml_features(user_id);
CREATE INDEX IF NOT EXISTS idx_user_ml_features_trust ON user_ml_features(trust_score);
CREATE INDEX IF NOT EXISTS idx_user_ml_features_tier ON user_ml_features(reward_tier);
CREATE INDEX IF NOT EXISTS idx_user_ml_features_nft ON user_ml_features(nft_badge_type);

-- ============================================================
-- EVENT ML FEATURES
-- ============================================================
CREATE TABLE IF NOT EXISTS event_ml_features (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL UNIQUE REFERENCES events(id),
    capacity INTEGER,
    current_rsvps INTEGER DEFAULT 0,
    capacity_filled_percent FLOAT DEFAULT 0.0,
    host_id INTEGER REFERENCES users(id),
    host_tier VARCHAR(20),
    host_nft_badge VARCHAR(50),
    host_reliability_score FLOAT DEFAULT 0.5,
    host_avg_rating FLOAT,
    host_total_events INTEGER DEFAULT 0,
    is_paid BOOLEAN DEFAULT FALSE,
    price FLOAT,
    price_mode VARCHAR(20),
    dynamic_price_suggested FLOAT,
    predicted_attendance INTEGER,
    predicted_no_show_rate FLOAT,
    verified_attendance_required BOOLEAN DEFAULT TRUE,
    hours_until_event FLOAT,
    day_of_week INTEGER,
    is_weekend BOOLEAN DEFAULT FALSE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_ml_features_event ON event_ml_features(event_id);
CREATE INDEX IF NOT EXISTS idx_event_ml_features_host ON event_ml_features(host_id);

-- ============================================================
-- AI OPS MONITORING
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    labels JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_metrics_name ON ai_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_time ON ai_metrics(timestamp);

CREATE TABLE IF NOT EXISTS model_drift_log (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),
    feature_drift_score FLOAT,
    prediction_drift_score FLOAT,
    accuracy_current FLOAT,
    accuracy_baseline FLOAT,
    drift_detected BOOLEAN DEFAULT FALSE,
    alert_triggered BOOLEAN DEFAULT FALSE,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    sample_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_drift_name ON model_drift_log(model_name);
CREATE INDEX IF NOT EXISTS idx_model_drift_detected ON model_drift_log(drift_detected);
"""


def create_tables():
    """Create all new tables"""
    print("=" * 60)
    print("Creating New AI/ML Tables")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Split into individual statements and execute
        statements = [s.strip() for s in CREATE_TABLES_SQL.split(';') if s.strip() and not s.strip().startswith('--')]
        
        for i, statement in enumerate(statements, 1):
            try:
                conn.execute(text(statement))
                # Extract table/index name for logging
                if 'CREATE TABLE' in statement:
                    table_name = statement.split('EXISTS')[1].split('(')[0].strip() if 'EXISTS' in statement else 'unknown'
                    print(f"  ✓ Created table: {table_name}")
                elif 'CREATE INDEX' in statement:
                    idx_name = statement.split('EXISTS')[1].split('ON')[0].strip() if 'EXISTS' in statement else 'unknown'
                    print(f"  ✓ Created index: {idx_name}")
            except Exception as e:
                print(f"  ⚠ Statement {i} warning: {e}")
        
        conn.commit()
    
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print("\nCreated tables:")
    print("  - checkins")
    print("  - nft_badges")
    print("  - nft_badge_history")
    print("  - temp_chats")
    print("  - temp_chat_messages")
    print("  - temp_chat_participants")
    print("  - user_ml_features")
    print("  - event_ml_features")
    print("  - ai_metrics")
    print("  - model_drift_log")
    print("\nYou can now run the seed script:")
    print("  docker-compose exec api python scripts/seed_database.py --clear")


if __name__ == "__main__":
    create_tables()
