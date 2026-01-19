"""
SQLAlchemy ORM Models for Kumele AI/ML Service
"""
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, 
    ForeignKey, Date, JSON, Numeric, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from kumele_ai.db.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    age = Column(Integer)
    gender = Column(String(20))
    address = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    city = Column(String(100))
    country = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    hobbies = relationship("UserHobby", back_populates="user")
    events_hosted = relationship("Event", back_populates="host")
    user_events = relationship("UserEvent", back_populates="user")
    activities = relationship("UserActivity", back_populates="user")
    reward_coupons = relationship("RewardCoupon", back_populates="user")


class Hobby(Base):
    __tablename__ = "hobbies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(100))
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    users = relationship("UserHobby", back_populates="hobby")


class UserHobby(Base):
    __tablename__ = "user_hobbies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    hobby_id = Column(Integer, ForeignKey("hobbies.id"), nullable=False)
    skill_level = Column(String(50))
    interest_level = Column(Integer, default=5)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'hobby_id', name='unique_user_hobby'),
    )
    
    # Relationships
    user = relationship("User", back_populates="hobbies")
    hobby = relationship("Hobby", back_populates="users")


class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    hobby_id = Column(Integer, ForeignKey("hobbies.id"))
    hobby_tags = Column(JSONB)
    event_date = Column(DateTime, nullable=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    location = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    city = Column(String(100))
    country = Column(String(100))
    capacity = Column(Integer)
    is_paid = Column(Boolean, default=False)
    price = Column(Numeric(10, 2), default=0)
    currency = Column(String(10), default="USD")
    status = Column(String(50), default="upcoming")  # upcoming, completed, cancelled
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    host = relationship("User", back_populates="events_hosted")
    attendees = relationship("UserEvent", back_populates="event")
    ratings = relationship("EventRating", back_populates="event")


class UserEvent(Base):
    __tablename__ = "user_events"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    rsvp_status = Column(String(50), default="registered")  # registered, attended, no_show, cancelled
    checked_in = Column(Boolean, default=False)
    check_in_time = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'event_id', name='unique_user_event'),
    )
    
    # Relationships
    user = relationship("User", back_populates="user_events")
    event = relationship("Event", back_populates="attendees")


class EventRating(Base):
    __tablename__ = "event_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Float, nullable=False)
    communication_score = Column(Float)
    respect_score = Column(Float)
    professionalism_score = Column(Float)
    atmosphere_score = Column(Float)
    value_score = Column(Float)
    comment = Column(Text)
    moderation_status = Column(String(50), default="pending")
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'event_id', name='unique_user_event_rating'),
    )
    
    # Relationships
    event = relationship("Event", back_populates="ratings")


class Blog(Base):
    __tablename__ = "blogs"
    
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    hobby_tags = Column(JSONB)
    status = Column(String(50), default="published")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    interactions = relationship("BlogInteraction", back_populates="blog")


class BlogInteraction(Base):
    __tablename__ = "blog_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    blog_id = Column(Integer, ForeignKey("blogs.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    interaction_type = Column(String(50), nullable=False)  # view, like, share, comment
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    blog = relationship("Blog", back_populates="interactions")


class Ad(Base):
    __tablename__ = "ads"
    
    id = Column(Integer, primary_key=True, index=True)
    advertiser_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    image_url = Column(Text)
    image_tags = Column(JSONB)
    target_hobbies = Column(JSONB)
    target_locations = Column(JSONB)
    target_age_min = Column(Integer)
    target_age_max = Column(Integer)
    budget = Column(Numeric(10, 2))
    cpc = Column(Numeric(10, 4))
    status = Column(String(50), default="draft")
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    interactions = relationship("AdInteraction", back_populates="ad")


class AdInteraction(Base):
    __tablename__ = "ad_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    ad_id = Column(Integer, ForeignKey("ads.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    interaction_type = Column(String(50), nullable=False)  # impression, click, conversion
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    ad = relationship("Ad", back_populates="interactions")


class Referral(Base):
    __tablename__ = "referrals"
    
    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referral_code = Column(String(50), unique=True)
    status = Column(String(50), default="pending")  # pending, completed, rewarded
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)


# Rewards Tables
class UserActivity(Base):
    __tablename__ = "user_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity_type = Column(String(50), nullable=False)  # event_created, event_attended
    event_id = Column(Integer, ForeignKey("events.id"))
    activity_date = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_user_activity_date', 'user_id', 'activity_date'),
    )
    
    # Relationships
    user = relationship("User", back_populates="activities")


class RewardCoupon(Base):
    __tablename__ = "reward_coupons"
    
    coupon_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status_level = Column(String(20), nullable=False)  # Bronze, Silver, Gold
    discount_value = Column(Float, nullable=False)
    stackable = Column(Boolean, default=False)
    is_redeemed = Column(Boolean, default=False)
    issued_at = Column(DateTime, server_default=func.now())
    redeemed_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="reward_coupons")


# Moderation Tables
class ModerationJob(Base):
    __tablename__ = "moderation_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(String(255), nullable=False, index=True)
    content_type = Column(String(50), nullable=False)  # text, image, video
    subtype = Column(String(100))
    content_data = Column(Text)
    status = Column(String(50), default="pending")  # pending, processing, completed
    decision = Column(String(50))  # approve, reject, needs_review
    labels = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now())
    reviewed_at = Column(DateTime)


# Knowledge Base Tables
class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # faq, blog, event, policy
    language = Column(String(10), default="en")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class KnowledgeEmbedding(Base):
    __tablename__ = "knowledge_embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text)
    embedding_model = Column(String(255))
    vector_id = Column(String(255))  # Qdrant point ID
    last_indexed = Column(DateTime, server_default=func.now())


class ChatbotLog(Base):
    __tablename__ = "chatbot_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    query = Column(Text, nullable=False)
    response = Column(Text)
    language = Column(String(10))
    confidence = Column(Float)
    source_docs = Column(JSONB)
    feedback = Column(String(50))  # helpful, not_helpful
    created_at = Column(DateTime, server_default=func.now())


# Support Email Tables
class SupportEmail(Base):
    __tablename__ = "support_emails"
    
    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String(255), index=True)
    from_email = Column(String(255), nullable=False)
    to_email = Column(String(255))
    subject = Column(String(500))
    raw_body = Column(Text)
    cleaned_text = Column(Text)
    received_at = Column(DateTime, server_default=func.now())
    status = Column(String(50), default="new")  # new, analyzed, replied, escalated, closed


class SupportEmailAnalysis(Base):
    __tablename__ = "support_email_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("support_emails.id"), nullable=False)
    category = Column(String(100))
    sentiment = Column(String(50))
    sentiment_score = Column(Float)
    urgency = Column(String(50))
    keywords = Column(JSONB)
    suggested_response = Column(Text)
    confidence = Column(Float)
    analyzed_at = Column(DateTime, server_default=func.now())


class SupportEmailReply(Base):
    __tablename__ = "support_email_replies"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("support_emails.id"), nullable=False)
    draft_response = Column(Text)
    final_response = Column(Text)
    response_type = Column(String(50))  # ai_generated, human_edited, human_written
    sent_status = Column(String(50), default="draft")  # draft, sent, failed
    sent_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())


class SupportEmailEscalation(Base):
    __tablename__ = "support_email_escalations"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("support_emails.id"), nullable=False)
    escalation_reason = Column(Text)
    escalation_level = Column(String(50))
    assigned_to = Column(String(255))
    escalated_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)


# Action Logs
class AIActionLog(Base):
    __tablename__ = "ai_action_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String(100), nullable=False)
    endpoint = Column(String(255))
    user_id = Column(Integer)
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    model_used = Column(String(255))
    processing_time_ms = Column(Integer)
    status = Column(String(50))
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


# Model Registry
class AIModelRegistry(Base):
    __tablename__ = "ai_model_registry"
    
    name = Column(String(255), primary_key=True)
    version = Column(String(100))
    type = Column(String(50))  # llm, embedder, classifier, translator
    status = Column(String(50), default="inactive")  # active, inactive, loading
    loaded_at = Column(DateTime)
    config = Column(JSONB)


# NLP Results
class NLPSentiment(Base):
    __tablename__ = "nlp_sentiment"
    
    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(String(255), index=True)
    content_hash = Column(String(64), index=True)
    text = Column(Text)
    sentiment = Column(String(50))
    confidence = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class NLPKeyword(Base):
    __tablename__ = "nlp_keywords"
    
    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(String(255), index=True)
    keyword = Column(String(255))
    keyword_type = Column(String(50))  # topic, entity, hobby
    score = Column(Float)
    extracted_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_keyword_date', 'keyword', 'extracted_at'),
    )


# Pricing Tables
class PricingHistory(Base):
    __tablename__ = "pricing_history"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    turnout = Column(Integer)
    host_score = Column(Float)
    city = Column(String(100))
    date = Column(Date)
    revenue = Column(Numeric(12, 2))
    created_at = Column(DateTime, server_default=func.now())


class DiscountSuggestion(Base):
    __tablename__ = "discount_suggestions"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    discount_type = Column(String(50))
    value_percent = Column(Float)
    segment = Column(String(100))
    expected_uplift = Column(Float)
    expected_roi = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


# Host Ratings Breakdown
class HostRating(Base):
    __tablename__ = "host_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_events = Column(Integer, default=0)
    completed_events = Column(Integer, default=0)
    total_attendees = Column(Integer, default=0)
    repeat_attendees = Column(Integer, default=0)
    avg_communication = Column(Float)
    avg_respect = Column(Float)
    avg_professionalism = Column(Float)
    avg_atmosphere = Column(Float)
    avg_value = Column(Float)
    overall_score = Column(Float)
    last_calculated = Column(DateTime, server_default=func.now())


# ============================================================
# TIMESERIES TABLES - Analytics & Forecasting
# ============================================================

class TimeseriesDaily(Base):
    """Daily aggregated metrics for forecasting and dashboards"""
    __tablename__ = "timeseries_daily"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    total_visits = Column(Integer, default=0)
    unique_visitors = Column(Integer, default=0)
    registrations = Column(Integer, default=0)
    events_created = Column(Integer, default=0)
    events_completed = Column(Integer, default=0)
    total_revenue = Column(Numeric(12, 2), default=0)
    active_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class TimeseriesHourly(Base):
    """Hourly metrics for real-time monitoring and load analysis"""
    __tablename__ = "timeseries_hourly"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, unique=True, nullable=False, index=True)
    visits = Column(Integer, default=0)
    api_calls = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    avg_response_time_ms = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_timeseries_hourly_timestamp', 'timestamp'),
    )


# ============================================================
# INTEREST TAXONOMY - ML-Owned Canonical Interests
# ============================================================

class InterestTaxonomy(Base):
    """
    Canonical interest/hobby taxonomy owned by ML.
    
    Key principles:
    - Interest IDs (not strings) drive the system
    - Frontend displays: label + icon
    - ML consumes: interest_id
    - Translations, grouping, embeddings are derived
    """
    __tablename__ = "interest_taxonomy"
    
    interest_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(100))
    parent_id = Column(Integer, ForeignKey("interest_taxonomy.interest_id"))
    icon_key = Column(String(100))
    color_token = Column(String(50))
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    embedding_vector = Column(JSONB)  # Stored embedding for similarity
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_interest_taxonomy_category', 'category'),
        Index('idx_interest_taxonomy_active', 'is_active'),
        Index('idx_interest_taxonomy_updated', 'updated_at'),
    )
    
    # Self-referential relationship for hierarchy
    children = relationship("InterestTaxonomy", backref="parent", remote_side=[interest_id])


class InterestTranslation(Base):
    """Translations for interests - lazy loaded by language"""
    __tablename__ = "interest_translations"
    
    id = Column(Integer, primary_key=True, index=True)
    interest_id = Column(Integer, ForeignKey("interest_taxonomy.interest_id"), nullable=False)
    language = Column(String(10), nullable=False)
    label = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('interest_id', 'language', name='unique_interest_language'),
        Index('idx_interest_translations_lang', 'language'),
    )


# ============================================================
# I18N TABLES - Lazy Loading Translations by Scope
# ============================================================

class I18nScope(Base):
    """Translation scopes for lazy loading (common, events, profile, etc.)"""
    __tablename__ = "i18n_scopes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class I18nString(Base):
    """Translation strings organized by scope for lazy loading"""
    __tablename__ = "i18n_strings"
    
    id = Column(Integer, primary_key=True, index=True)
    scope_id = Column(Integer, ForeignKey("i18n_scopes.id"), nullable=False)
    key = Column(String(255), nullable=False)
    language = Column(String(10), nullable=False)
    value = Column(Text, nullable=False)
    is_approved = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('scope_id', 'key', 'language', name='unique_scope_key_lang'),
        Index('idx_i18n_strings_scope', 'scope_id'),
        Index('idx_i18n_strings_lang', 'language'),
        Index('idx_i18n_strings_key', 'key'),
        Index('idx_i18n_strings_approved', 'is_approved'),
    )


# ============================================================
# NO-SHOW PREDICTION SYSTEM (Behavioral Forecasting)
# ============================================================

class UserAttendanceProfile(Base):
    """User behavioral profile for no-show prediction"""
    __tablename__ = "user_attendance_profile"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    total_rsvps = Column(Integer, default=0)
    total_check_ins = Column(Integer, default=0)
    total_no_shows = Column(Integer, default=0)
    late_cancellations = Column(Integer, default=0)
    payment_timeouts = Column(Integer, default=0)
    failed_payments = Column(Integer, default=0)
    avg_rsvp_to_event_hours = Column(Float)
    last_minute_rsvp_count = Column(Integer, default=0)
    avg_distance_km = Column(Float)
    max_distance_km = Column(Float)
    check_in_rate = Column(Float)
    no_show_rate = Column(Float)
    last_updated = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_user_attendance_profile_user', 'user_id'),
        Index('idx_user_attendance_profile_noshow', 'no_show_rate'),
    )


class NoShowPrediction(Base):
    """Audit log for no-show predictions"""
    __tablename__ = "no_show_predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    no_show_probability = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    features = Column(JSONB, nullable=False)
    price_mode = Column(String(20))
    distance_km = Column(Float)
    rsvp_timestamp = Column(DateTime)
    event_start_timestamp = Column(DateTime)
    hours_until_event = Column(Float)
    model_version = Column(String(50))
    actual_outcome = Column(String(20))
    outcome_recorded_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_noshow_pred_user', 'user_id'),
        Index('idx_noshow_pred_event', 'event_id'),
        Index('idx_noshow_pred_created', 'created_at'),
        Index('idx_noshow_pred_outcome', 'actual_outcome'),
    )


class EventCategoryNoShowStats(Base):
    """Aggregated no-show rates by category/time"""
    __tablename__ = "event_category_noshow_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False)
    price_mode = Column(String(20), nullable=False)
    day_of_week = Column(Integer)
    hour_of_day = Column(Integer)
    total_rsvps = Column(Integer, default=0)
    total_no_shows = Column(Integer, default=0)
    avg_no_show_rate = Column(Float)
    last_updated = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('category', 'price_mode', 'day_of_week', 'hour_of_day', 
                        name='unique_category_noshow_stats'),
        Index('idx_category_noshow_stats', 'category', 'price_mode'),
    )


# ============================================================
# ATTENDANCE VERIFICATION AI (Trust & Fraud Detection)
# ============================================================

class AttendanceVerification(Base):
    """Audit log for attendance verification decisions"""
    __tablename__ = "attendance_verifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    # Verification Result
    check_in_status = Column(String(20), nullable=False)
    risk_score = Column(Float, nullable=False)
    action = Column(String(30), nullable=False)
    signals = Column(JSONB, nullable=False)
    # Input Signals Snapshot
    user_latitude = Column(Float)
    user_longitude = Column(Float)
    event_latitude = Column(Float)
    event_longitude = Column(Float)
    distance_km = Column(Float)
    qr_scan_timestamp = Column(DateTime)
    event_start_timestamp = Column(DateTime)
    event_end_timestamp = Column(DateTime)
    minutes_from_start = Column(Float)
    device_hash = Column(String(255))
    device_os = Column(String(50))
    app_instance_id = Column(String(255))
    host_confirmed = Column(Boolean)
    # Model metadata
    model_version = Column(String(50))
    rules_triggered = Column(JSONB)
    ml_score = Column(Float)
    # Support Resolution
    support_decision = Column(String(30))
    support_decision_at = Column(DateTime)
    support_notes = Column(Text)
    # Outcome
    rewards_unlocked = Column(Boolean, default=False)
    reviews_unlocked = Column(Boolean, default=False)
    escrow_released = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_attendance_verify_user', 'user_id'),
        Index('idx_attendance_verify_event', 'event_id'),
        Index('idx_attendance_verify_status', 'check_in_status'),
        Index('idx_attendance_verify_action', 'action'),
        Index('idx_attendance_verify_created', 'created_at'),
    )


class DeviceFingerprint(Base):
    """Device fingerprint registry for fraud detection"""
    __tablename__ = "device_fingerprints"
    
    id = Column(Integer, primary_key=True, index=True)
    device_hash = Column(String(255), nullable=False)
    device_os = Column(String(50))
    app_instance_id = Column(String(255))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    first_seen = Column(DateTime, server_default=func.now())
    last_seen = Column(DateTime, server_default=func.now())
    check_in_count = Column(Integer, default=0)
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(Text)
    
    __table_args__ = (
        UniqueConstraint('device_hash', 'user_id', name='unique_device_user'),
        Index('idx_device_fp_hash', 'device_hash'),
        Index('idx_device_fp_user', 'user_id'),
        Index('idx_device_fp_flagged', 'is_flagged'),
    )


class UserTrustProfile(Base):
    """Aggregated user trust/fraud signals"""
    __tablename__ = "user_trust_profile"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    trust_score = Column(Float, default=1.0)
    total_verifications = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    suspicious_count = Column(Integer, default=0)
    fraudulent_count = Column(Integer, default=0)
    gps_mismatch_count = Column(Integer, default=0)
    qr_replay_count = Column(Integer, default=0)
    device_anomaly_count = Column(Integer, default=0)
    penalties_applied = Column(Integer, default=0)
    last_penalty_at = Column(DateTime)
    last_updated = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_user_trust_profile_user', 'user_id'),
        Index('idx_user_trust_profile_score', 'trust_score'),
    )


class QRScanLog(Base):
    """QR code scan log for replay detection"""
    __tablename__ = "qr_scan_log"
    
    id = Column(Integer, primary_key=True, index=True)
    qr_code_hash = Column(String(255), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_hash = Column(String(255))
    scanned_at = Column(DateTime, server_default=func.now())
    is_valid = Column(Boolean, default=True)
    rejection_reason = Column(String(100))
    
    __table_args__ = (
        Index('idx_qr_scan_qr', 'qr_code_hash'),
        Index('idx_qr_scan_event', 'event_id'),
        Index('idx_qr_scan_time', 'scanned_at'),
    )
