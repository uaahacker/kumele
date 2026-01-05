"""
SQLAlchemy Database Models for Kumele AI/ML Backend.
All tables are defined here following the locked schema specifications.
"""
import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, Boolean, 
    ForeignKey, DateTime, Date, Numeric, JSON, ARRAY,
    CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


# ============================================
# USERS (Reference Table)
# ============================================
class User(Base):
    __tablename__ = "users"
    
    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    age = Column(Integer)
    gender = Column(Text)
    location_lat = Column(Numeric(10, 7))
    location_lon = Column(Numeric(10, 7))
    preferred_language = Column(Text, default="en")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Matching & Rewards fields
    reward_tier = Column(Text, default="none")  # Business signal for matching
    
    __table_args__ = (
        CheckConstraint("gender IN ('male', 'female', 'other')"),
        CheckConstraint("reward_tier IN ('none', 'bronze', 'silver', 'gold')"),
    )


# ============================================
# EVENTS
# ============================================
class Event(Base):
    __tablename__ = "events"
    
    event_id = Column(BigInteger, primary_key=True, autoincrement=True)
    host_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(Text)
    location = Column(Text)
    location_lat = Column(Numeric(10, 7))
    location_lon = Column(Numeric(10, 7))
    capacity = Column(Integer)
    price = Column(Numeric(12, 2), default=0)
    event_date = Column(DateTime)
    status = Column(Text, default="scheduled")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Matching pipeline fields (per requirements)
    moderation_status = Column(Text, default="pending")  # Hard filter: must be 'approved'
    language = Column(Text, default="en")  # Hard filter: match user preference
    has_discount = Column(Boolean, default=False)  # Business signal boost
    is_sponsored = Column(Boolean, default=False)  # Business signal boost (capped)
    tags = Column(ARRAY(Text))  # For event embedding generation
    
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'scheduled', 'ongoing', 'completed', 'cancelled')"),
        CheckConstraint("moderation_status IN ('pending', 'approved', 'rejected')"),
    )


# ============================================
# EVENT ATTENDANCE (for tracking RSVPs and check-ins)
# ============================================
class EventAttendance(Base):
    __tablename__ = "event_attendance"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(BigInteger, ForeignKey("events.event_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    rsvp_status = Column(Text, default="pending")
    checked_in = Column(Boolean, default=False)
    checked_in_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("rsvp_status IN ('pending', 'confirmed', 'cancelled', 'attended')"),
        UniqueConstraint("event_id", "user_id", name="uq_event_user_attendance"),
    )


# ============================================
# EVENT RATINGS (Attendee Feedback)
# ============================================
class EventRating(Base):
    __tablename__ = "event_ratings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(BigInteger, ForeignKey("events.event_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    
    # Rating dimensions (1-5 scale)
    communication = Column(Numeric(2, 1), nullable=False)
    respect = Column(Numeric(2, 1), nullable=False)
    professionalism = Column(Numeric(2, 1), nullable=False)
    atmosphere = Column(Numeric(2, 1), nullable=False)
    value_for_money = Column(Numeric(2, 1))  # Optional for free events
    
    comment = Column(Text)
    moderation_status = Column(Text, default="pending")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("communication >= 1 AND communication <= 5"),
        CheckConstraint("respect >= 1 AND respect <= 5"),
        CheckConstraint("professionalism >= 1 AND professionalism <= 5"),
        CheckConstraint("atmosphere >= 1 AND atmosphere <= 5"),
        CheckConstraint("value_for_money IS NULL OR (value_for_money >= 1 AND value_for_money <= 5)"),
        CheckConstraint("moderation_status IN ('pending', 'approved', 'rejected')"),
        UniqueConstraint("event_id", "user_id", name="uq_event_user_rating"),
    )


# ============================================
# HOST RATING AGGREGATES (Cached)
# ============================================
class HostRatingAggregate(Base):
    __tablename__ = "host_rating_aggregates"
    
    host_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    
    # Overall score (0-100 or 0-5)
    overall_score = Column(Numeric(5, 2))
    overall_score_5 = Column(Numeric(3, 2))  # 5-star equivalent
    
    # Review counts
    reviews_count = Column(Integer, default=0)
    
    # Attendee rating averages (1-5)
    avg_communication = Column(Numeric(3, 2))
    avg_respect = Column(Numeric(3, 2))
    avg_professionalism = Column(Numeric(3, 2))
    avg_atmosphere = Column(Numeric(3, 2))
    avg_value_for_money = Column(Numeric(3, 2))
    
    # System reliability metrics (0-1)
    event_completion_ratio = Column(Numeric(5, 4))
    attendance_follow_through = Column(Numeric(5, 4))
    repeat_attendee_ratio = Column(Numeric(5, 4))
    
    # Matching pipeline field (alias for event_completion_ratio)
    completion_rate = Column(Numeric(5, 4))  # Used by trust scoring: 0.7×reviews + 0.3×completion
    
    # Badges (JSON array)
    badges = Column(JSONB, default=[])
    
    last_calculated = Column(DateTime, default=datetime.utcnow)


# ============================================
# EVENT STATS (for system reliability calculation)
# ============================================
class EventStats(Base):
    __tablename__ = "event_stats"
    
    event_id = Column(BigInteger, ForeignKey("events.event_id", ondelete="CASCADE"), primary_key=True)
    rsvp_count = Column(Integer, default=0)
    attendance_count = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    cancelled = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Engagement metrics for matching pipeline
    clicks = Column(Integer, default=0)  # Event page views
    saves = Column(Integer, default=0)  # User bookmarks/saves


# ============================================
# ADS
# ============================================
class Ad(Base):
    __tablename__ = "ads"
    
    ad_id = Column(BigInteger, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    title = Column(Text, nullable=False)
    description = Column(Text)
    image_url = Column(Text)
    budget = Column(Numeric(12, 2))
    target_hobby = Column(Text)
    target_location_lat = Column(Numeric(10, 7))
    target_location_lon = Column(Numeric(10, 7))
    status = Column(Text, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'paused', 'completed')"),
    )


# ============================================
# AUDIENCE SEGMENTS
# ============================================
class AudienceSegment(Base):
    __tablename__ = "audience_segments"
    
    segment_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ad_id = Column(BigInteger, ForeignKey("ads.ad_id", ondelete="CASCADE"))
    segment_name = Column(Text, nullable=False)
    match_score = Column(Numeric(5, 4))
    audience_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================
# AD PREDICTIONS
# ============================================
class AdPrediction(Base):
    __tablename__ = "ad_predictions"
    
    prediction_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ad_id = Column(BigInteger, ForeignKey("ads.ad_id", ondelete="CASCADE"))
    predicted_ctr = Column(Numeric(6, 5))
    predicted_engagement = Column(Numeric(6, 5))
    confidence = Column(Numeric(5, 4))
    suggestions = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================
# AD LOGS
# ============================================
class AdLog(Base):
    __tablename__ = "ad_logs"
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ad_id = Column(BigInteger, ForeignKey("ads.ad_id", ondelete="CASCADE"))
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    action = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("action IN ('viewed', 'clicked', 'ignored', 'dismissed')"),
    )


# ============================================
# UGC CONTENT
# ============================================
class UGCContent(Base):
    __tablename__ = "ugc_content"
    
    content_id = Column(BigInteger, primary_key=True, autoincrement=True)
    content_type = Column(Text, nullable=False)
    ref_id = Column(BigInteger, nullable=False)
    author_id = Column(BigInteger, ForeignKey("users.user_id"))
    text = Column(Text, nullable=False)
    language = Column(String(8))
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================
# NLP SENTIMENT
# ============================================
class NLPSentiment(Base):
    __tablename__ = "nlp_sentiment"
    
    sentiment_id = Column(BigInteger, primary_key=True, autoincrement=True)
    content_id = Column(BigInteger, ForeignKey("ugc_content.content_id", ondelete="CASCADE"))
    sentiment_label = Column(String(16))
    polarity_score = Column(Numeric(6, 4))
    analysed_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("sentiment_label IN ('positive', 'neutral', 'negative')"),
        Index("idx_nlp_sentiment_content", "content_id"),
    )


# ============================================
# NLP KEYWORDS
# ============================================
class NLPKeyword(Base):
    __tablename__ = "nlp_keywords"
    
    kw_id = Column(BigInteger, primary_key=True, autoincrement=True)
    content_id = Column(BigInteger, ForeignKey("ugc_content.content_id", ondelete="CASCADE"))
    keyword = Column(Text, nullable=False)
    keyword_type = Column(String(32))
    relevance = Column(Numeric(6, 4))
    extracted_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_nlp_keywords_content", "content_id"),
        Index("idx_nlp_keywords_kw", "keyword"),
    )


# ============================================
# NLP TOPIC DAILY
# ============================================
class NLPTopicDaily(Base):
    __tablename__ = "nlp_topic_daily"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    topic = Column(Text, nullable=False)
    topic_type = Column(String(32))
    ds = Column(Date, nullable=False)
    location = Column(String(200))
    mentions = Column(Integer, default=0)
    weighted_score = Column(Numeric(10, 4))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("topic", "topic_type", "ds", "location"),
    )


# ============================================
# NLP TRENDS
# ============================================
class NLPTrend(Base):
    __tablename__ = "nlp_trends"
    
    trend_id = Column(BigInteger, primary_key=True, autoincrement=True)
    topic = Column(Text, nullable=False)
    topic_type = Column(String(32))
    location = Column(String(200))
    first_seen = Column(Date)
    last_seen = Column(Date)
    current_mentions = Column(Integer)
    growth_rate = Column(Numeric(6, 4))
    trend_score = Column(Numeric(6, 4))
    computed_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_nlp_trends_topic", "topic"),
    )


# ============================================
# MODERATION JOBS
# ============================================
class ModerationJob(Base):
    __tablename__ = "moderation_jobs"
    
    content_id = Column(Text, primary_key=True)
    content_type = Column(Text)
    subtype = Column(Text)
    status = Column(Text, default="pending")
    decision = Column(Text)
    labels = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
    
    __table_args__ = (
        CheckConstraint("content_type IN ('text', 'image', 'video')"),
        CheckConstraint("status IN ('pending', 'completed')"),
        CheckConstraint("decision IN ('approve', 'reject', 'needs_review')"),
    )


# ============================================
# KNOWLEDGE DOCUMENTS (Chatbot)
# ============================================
class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(Text)
    language = Column(String(10), default="en")
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("category IN ('faq', 'blog', 'event', 'policy', 'help')"),
    )


# ============================================
# EMBEDDINGS METADATA
# ============================================
class EmbeddingsMetadata(Base):
    __tablename__ = "embeddings_metadata"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"))
    chunk_index = Column(Integer)
    vector_id = Column(Text, nullable=False)
    embedding_model = Column(Text)
    last_indexed = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_doc_embedding", "document_id"),
    )


# ============================================
# KNOWLEDGE EMBEDDINGS (spec requirement)
# Note: Actual embeddings stored in Qdrant, NOT PostgreSQL
# This table tracks embedding metadata only
# ============================================
class KnowledgeEmbedding(Base):
    """
    Tracks knowledge base embeddings.
    
    IMPORTANT: Per spec, embeddings are stored in Qdrant vector DB,
    NOT in PostgreSQL. This table only stores metadata/references.
    """
    __tablename__ = "knowledge_embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"))
    chunk_text = Column(Text)  # Optional: store text for reference
    chunk_index = Column(Integer, default=0)
    vector_id = Column(Text, nullable=False)  # Qdrant vector ID reference
    embedding_model = Column(Text, default="sentence-transformers/all-MiniLM-L6-v2")
    dimensions = Column(Integer, default=384)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_knowledge_emb_doc", "document_id"),
        Index("idx_knowledge_emb_vector", "vector_id"),
    )


# ============================================
# CHATBOT LOGS
# ============================================
class ChatbotLog(Base):
    __tablename__ = "chatbot_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    language = Column(Text, default="en")
    confidence = Column(Numeric(5, 4))
    source_docs = Column(ARRAY(Text))
    feedback = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("feedback IN ('positive', 'negative')"),
    )


# ============================================
# SUPPORT EMAILS
# ============================================
class SupportEmail(Base):
    __tablename__ = "support_emails"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), nullable=False)
    from_email = Column(Text, nullable=False)
    to_email = Column(Text, nullable=False)
    subject = Column(Text)
    raw_body = Column(Text, nullable=False)
    cleaned_body = Column(Text, nullable=False)
    language = Column(Text, default="en")
    status = Column(Text, default="received")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("status IN ('received', 'processing', 'awaiting_human', 'replied', 'closed')"),
        Index("idx_support_thread", "thread_id"),
        Index("idx_support_status", "status"),
    )


# ============================================
# SUPPORT EMAIL ANALYSIS
# ============================================
class SupportEmailAnalysis(Base):
    __tablename__ = "support_email_analysis"
    
    email_id = Column(UUID(as_uuid=True), ForeignKey("support_emails.id", ondelete="CASCADE"), primary_key=True)
    category = Column(Text)
    sentiment = Column(Text)
    sentiment_score = Column(Numeric(5, 4))
    confidence = Column(Numeric(5, 4))
    model_name = Column(Text, nullable=False)
    model_version = Column(Text, nullable=False)
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("category IN ('support', 'billing', 'partnership', 'feedback', 'abuse', 'other')"),
        CheckConstraint("sentiment IN ('positive', 'neutral', 'negative')"),
    )


# ============================================
# SUPPORT EMAIL REPLIES
# ============================================
class SupportEmailReply(Base):
    __tablename__ = "support_email_replies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(UUID(as_uuid=True), ForeignKey("support_emails.id", ondelete="CASCADE"))
    draft_body = Column(Text, nullable=False)
    final_body = Column(Text)
    is_ai_generated = Column(Boolean, default=True)
    approved_by = Column(Text)
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_email_reply_email", "email_id"),
    )


# ============================================
# SUPPORT EMAIL ESCALATIONS
# ============================================
class SupportEmailEscalation(Base):
    __tablename__ = "support_email_escalations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(UUID(as_uuid=True), ForeignKey("support_emails.id", ondelete="CASCADE"))
    reason = Column(Text)
    triggered_by = Column(Text)
    escalated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("triggered_by IN ('sentiment', 'confidence', 'manual')"),
    )


# ============================================
# AI ACTION LOGS
# ============================================
class AIActionLog(Base):
    __tablename__ = "ai_action_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_type = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    input_snapshot = Column(JSONB)
    output_snapshot = Column(JSONB)
    model_name = Column(Text)
    model_version = Column(Text)
    status = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("status IN ('success', 'failed')"),
        Index("idx_ai_action_type", "action_type"),
        Index("idx_ai_entity", "entity_type", "entity_id"),
    )


# ============================================
# AI MODEL REGISTRY
# ============================================
class AIModelRegistry(Base):
    __tablename__ = "ai_model_registry"
    
    name = Column(Text, primary_key=True)
    version = Column(Text, nullable=False)
    type = Column(Text)
    loaded_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("type IN ('llm', 'embedder', 'classifier', 'translator')"),
    )


# ============================================
# UI STRINGS (Translation Source)
# ============================================
class UIString(Base):
    __tablename__ = "ui_strings"
    
    key = Column(String(255), primary_key=True)
    default_text = Column(Text, nullable=False)
    context = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ============================================
# UI TRANSLATIONS
# ============================================
class UITranslation(Base):
    __tablename__ = "ui_translations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), ForeignKey("ui_strings.key", ondelete="CASCADE"), nullable=False)
    language = Column(String(5), nullable=False)
    machine_text = Column(Text)
    approved_text = Column(Text)
    status = Column(Text, default="pending")
    reviewed_by = Column(String(255))
    reviewed_at = Column(DateTime)
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved')"),
        UniqueConstraint("key", "language", name="uq_key_language"),
    )


# ============================================
# INTEREST TAXONOMY
# ============================================
class InterestTaxonomy(Base):
    __tablename__ = "interest_taxonomy"
    
    interest_id = Column(String(64), primary_key=True)
    parent_id = Column(String(64))
    level = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ============================================
# INTEREST METADATA
# ============================================
class InterestMetadata(Base):
    __tablename__ = "interest_metadata"
    
    interest_id = Column(String(64), ForeignKey("interest_taxonomy.interest_id"), primary_key=True)
    icon_key = Column(String(64))
    color_token = Column(String(32))
    display_order = Column(Integer)


# ============================================
# INTEREST TRANSLATIONS
# ============================================
class InterestTranslation(Base):
    __tablename__ = "interest_translations"
    
    interest_id = Column(String(64), ForeignKey("interest_taxonomy.interest_id"), primary_key=True)
    language_code = Column(String(10), primary_key=True)
    label = Column(Text)
    description = Column(Text)


# ============================================
# PRICING HISTORY
# ============================================
class PricingHistory(Base):
    """
    Historical pricing data for sklearn regression training.
    Used to model price elasticity and predict optimal prices.
    """
    __tablename__ = "pricing_history"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(BigInteger, ForeignKey("events.event_id", ondelete="CASCADE"))
    price = Column(Numeric(12, 2))
    turnout = Column(Integer)
    host_score = Column(Numeric(5, 2))
    city = Column(Text)
    category = Column(Text)  # Event category for similar event matching
    capacity = Column(Integer)  # Event capacity
    event_date = Column(Date)
    revenue = Column(Numeric(14, 2))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_pricing_history_category", "category"),
        Index("idx_pricing_history_city", "city"),
    )


# ============================================
# DISCOUNT SUGGESTIONS
# ============================================
class DiscountSuggestion(Base):
    __tablename__ = "discount_suggestions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(BigInteger, ForeignKey("events.event_id", ondelete="CASCADE"))
    discount_type = Column(Text)
    value_percent = Column(Numeric(5, 2))
    segment = Column(Text)
    expected_uplift = Column(Numeric(5, 4))
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================
# USER INTERACTIONS (for recommendations)
# ============================================
class UserInteraction(Base):
    __tablename__ = "user_interactions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    item_type = Column(Text, nullable=False)  # event, hobby, blog
    item_id = Column(BigInteger, nullable=False)
    interaction_type = Column(Text, nullable=False)  # view, click, rsvp, attend, like
    score = Column(Numeric(3, 2), default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_user_interactions_user", "user_id"),
        Index("idx_user_interactions_item", "item_type", "item_id"),
    )


# ============================================
# USER HOBBIES
# ============================================
class UserHobby(Base):
    __tablename__ = "user_hobbies"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    hobby_id = Column(String(64), ForeignKey("interest_taxonomy.interest_id"))
    preference_score = Column(Numeric(3, 2), default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("user_id", "hobby_id", name="uq_user_hobby"),
    )


# ============================================
# RECOMMENDATION CACHE
# ============================================
class RecommendationCache(Base):
    __tablename__ = "recommendation_cache"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    recommendation_type = Column(Text, nullable=False)  # events, hobbies
    recommendations = Column(JSONB, nullable=False)
    computed_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    __table_args__ = (
        Index("idx_rec_cache_user", "user_id", "recommendation_type"),
    )


# ============================================
# USER ACTIVITIES (for rewards - source of truth)
# ============================================
class UserActivity(Base):
    __tablename__ = "user_activities"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    activity_type = Column(Text, nullable=False)  # event_created, event_attended
    event_id = Column(BigInteger, ForeignKey("events.event_id", ondelete="CASCADE"))
    activity_date = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, default=True)  # Only successful activities count for rewards
    
    __table_args__ = (
        CheckConstraint("activity_type IN ('event_created', 'event_attended')"),
        Index("idx_user_activities_user", "user_id"),
        Index("idx_user_activities_date", "activity_date"),
    )


# ============================================
# REWARD COUPONS
# ============================================
class RewardCoupon(Base):
    __tablename__ = "reward_coupons"
    
    coupon_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    status_level = Column(Text, nullable=False)  # bronze, silver, gold
    discount_value = Column(Numeric(5, 2), nullable=False)  # Percentage discount
    stackable = Column(Boolean, default=False)  # Only Gold is stackable
    is_redeemed = Column(Boolean, default=False)
    redeemed_at = Column(DateTime)
    redeemed_event_id = Column(BigInteger, ForeignKey("events.event_id", ondelete="SET NULL"))
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    __table_args__ = (
        CheckConstraint("status_level IN ('bronze', 'silver', 'gold')"),
        Index("idx_reward_coupons_user", "user_id"),
        Index("idx_reward_coupons_status", "is_redeemed"),
    )


# ============================================
# USER REWARD PROGRESS (cached/computed)
# ============================================
class UserRewardProgress(Base):
    __tablename__ = "user_reward_progress"
    
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    current_tier = Column(Text, default="none")  # none, bronze, silver, gold
    gold_count = Column(Integer, default=0)  # Number of gold stacks
    successful_events_30d = Column(Integer, default=0)
    events_attended_30d = Column(Integer, default=0)
    events_hosted_30d = Column(Integer, default=0)
    next_tier = Column(Text)
    events_to_next_tier = Column(Integer)
    last_computed = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("current_tier IN ('none', 'bronze', 'silver', 'gold')"),
    )


# ============================================
# TIME SERIES DAILY (for Prophet forecasting)
# ============================================
class TimeSeriesDaily(Base):
    __tablename__ = "timeseries_daily"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ds = Column(Date, nullable=False)  # Prophet requires 'ds' column
    y = Column(Numeric(10, 2))  # Target value (attendance, etc.)
    category = Column(Text)
    location = Column(Text)
    metric_type = Column(Text, nullable=False)  # attendance, events_count, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("ds", "category", "location", "metric_type"),
        Index("idx_timeseries_daily_ds", "ds"),
    )


# ============================================
# TIME SERIES HOURLY (for Prophet forecasting)
# ============================================
class TimeSeriesHourly(Base):
    __tablename__ = "timeseries_hourly"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ds = Column(DateTime, nullable=False)  # Prophet requires 'ds' column
    y = Column(Numeric(10, 2))  # Target value
    category = Column(Text)
    location = Column(Text)
    metric_type = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("ds", "category", "location", "metric_type"),
        Index("idx_timeseries_hourly_ds", "ds"),
    )


# ============================================
# USER BLOCKS - For matching pipeline hard filters
# ============================================
class UserBlock(Base):
    """
    User block relationships - used in matching pipeline to exclude
    events from blocked users/hosts.
    
    Hard filter in Step 1: Events from blocked hosts are excluded.
    """
    __tablename__ = "user_blocks"
    
    block_id = Column(BigInteger, primary_key=True, autoincrement=True)
    blocker_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    blocked_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block"),
        Index("idx_user_blocks_blocker", "blocker_id"),
        Index("idx_user_blocks_blocked", "blocked_id"),
    )


# ============================================
# WEB3 / SOLANA - USER WALLETS
# ============================================
class UserWallet(Base):
    """
    User cryptocurrency wallets - Solana only (per requirements).
    No Polygon/Hardhat/ethers.
    """
    __tablename__ = "user_wallets"
    
    wallet_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    wallet_address = Column(Text, unique=True, nullable=False)  # Solana public key
    wallet_type = Column(Text, default="solana")  # Only solana supported
    is_primary = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_signature = Column(Text)  # Signature proving ownership
    sol_balance = Column(Numeric(18, 9), default=0)  # SOL balance (9 decimals)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_synced = Column(DateTime)
    
    __table_args__ = (
        CheckConstraint("wallet_type = 'solana'"),  # Solana only
        Index("idx_user_wallets_user", "user_id"),
        Index("idx_user_wallets_address", "wallet_address"),
    )


# ============================================
# WEB3 / SOLANA - USER NFTs
# ============================================
class UserNFT(Base):
    """
    User-owned NFTs on Solana blockchain.
    Used for rewards, badges, and event tickets.
    """
    __tablename__ = "user_nfts"
    
    nft_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("user_wallets.wallet_id", ondelete="CASCADE"))
    mint_address = Column(Text, unique=True, nullable=False)  # Solana NFT mint address
    token_account = Column(Text)  # Associated token account
    nft_type = Column(Text, nullable=False)  # badge, ticket, reward, collectible
    name = Column(Text)
    symbol = Column(Text)
    uri = Column(Text)  # Metadata URI (usually Arweave/IPFS)
    image_url = Column(Text)
    attributes = Column(JSONB)  # NFT attributes/traits
    collection_address = Column(Text)  # Collection mint address
    is_compressed = Column(Boolean, default=False)  # Compressed NFT (cNFT)
    acquired_at = Column(DateTime, default=datetime.utcnow)
    acquisition_type = Column(Text)  # mint, purchase, reward, transfer
    event_id = Column(BigInteger, ForeignKey("events.event_id", ondelete="SET NULL"))  # If ticket NFT
    
    __table_args__ = (
        CheckConstraint("nft_type IN ('badge', 'ticket', 'reward', 'collectible', 'membership')"),
        CheckConstraint("acquisition_type IN ('mint', 'purchase', 'reward', 'transfer', 'airdrop')"),
        Index("idx_user_nfts_user", "user_id"),
        Index("idx_user_nfts_wallet", "wallet_id"),
        Index("idx_user_nfts_type", "nft_type"),
        Index("idx_user_nfts_collection", "collection_address"),
    )


# ============================================
# BLOGS / ARTICLES
# ============================================
class Blog(Base):
    """
    Blog posts and articles for content engagement tracking.
    """
    __tablename__ = "blogs"
    
    blog_id = Column(BigInteger, primary_key=True, autoincrement=True)
    author_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    slug = Column(Text, unique=True)
    content = Column(Text)
    summary = Column(Text)
    category = Column(Text)
    tags = Column(ARRAY(Text))
    cover_image_url = Column(Text)
    status = Column(Text, default="draft")
    language = Column(Text, default="en")
    read_time_minutes = Column(Integer)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'archived', 'deleted')"),
        Index("idx_blogs_author", "author_id"),
        Index("idx_blogs_status", "status"),
        Index("idx_blogs_category", "category"),
    )


# ============================================
# BLOG INTERACTIONS
# ============================================
class BlogInteraction(Base):
    """
    User interactions with blog posts for ML training.
    """
    __tablename__ = "blog_interactions"
    
    interaction_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    blog_id = Column(BigInteger, ForeignKey("blogs.blog_id", ondelete="CASCADE"), nullable=False)
    interaction_type = Column(Text, nullable=False)  # view, like, comment, share, bookmark
    read_percentage = Column(Integer)  # 0-100 how much was read
    time_spent_seconds = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("interaction_type IN ('view', 'like', 'comment', 'share', 'bookmark', 'unlike')"),
        Index("idx_blog_interactions_user", "user_id"),
        Index("idx_blog_interactions_blog", "blog_id"),
        Index("idx_blog_interactions_type", "interaction_type"),
    )


# ============================================
# AD INTERACTIONS (for ML training)
# ============================================
class AdInteraction(Base):
    """
    Detailed ad interaction tracking for ML/recommendation training.
    """
    __tablename__ = "ad_interactions"
    
    interaction_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    ad_id = Column(BigInteger, ForeignKey("ads.ad_id", ondelete="CASCADE"), nullable=False)
    interaction_type = Column(Text, nullable=False)  # impression, click, conversion, dismiss
    placement = Column(Text)  # feed, sidebar, banner, interstitial
    device_type = Column(Text)  # mobile, desktop, tablet
    session_id = Column(Text)
    dwell_time_ms = Column(Integer)  # Time spent viewing
    converted = Column(Boolean, default=False)
    conversion_value = Column(Numeric(12, 2))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("interaction_type IN ('impression', 'click', 'conversion', 'dismiss', 'skip')"),
        Index("idx_ad_interactions_user", "user_id"),
        Index("idx_ad_interactions_ad", "ad_id"),
        Index("idx_ad_interactions_type", "interaction_type"),
    )


# ============================================
# ML MODEL TRAINING LOGS (read-only for AI/ML)
# ============================================
class MLTrainingLog(Base):
    """
    Logs for ML model training runs - write-only for backend, read-only for AI/ML.
    AI/ML does not touch migrations, schemas, logs, or DB governance.
    """
    __tablename__ = "ml_training_logs"
    
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(Text, nullable=False)  # tfrs_recommender, prophet_attendance, etc.
    model_version = Column(Text)
    training_started = Column(DateTime, nullable=False)
    training_completed = Column(DateTime)
    status = Column(Text, default="running")  # running, completed, failed
    metrics = Column(JSONB)  # accuracy, loss, etc.
    hyperparameters = Column(JSONB)
    dataset_size = Column(Integer)
    training_duration_seconds = Column(Integer)
    error_message = Column(Text)
    created_by = Column(Text)  # system, manual, scheduled
    
    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed', 'cancelled')"),
        Index("idx_ml_training_logs_model", "model_name"),
        Index("idx_ml_training_logs_status", "status"),
    )


# ============================================
# MATCHING LOGS (async logging per requirements)
# ============================================
class MatchingLog(Base):
    """
    Logs for matching pipeline runs - async only, never blocks response.
    """
    __tablename__ = "matching_logs"
    
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    event_id = Column(BigInteger, ForeignKey("events.event_id", ondelete="CASCADE"), nullable=False)
    relevance_score = Column(Numeric(5, 4))
    trust_score = Column(Numeric(5, 4))
    engagement_score = Column(Numeric(5, 4))
    freshness_score = Column(Numeric(5, 4))
    business_score = Column(Numeric(5, 4))
    final_score = Column(Numeric(5, 4))
    rank_position = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_matching_logs_user", "user_id"),
        Index("idx_matching_logs_event", "event_id"),
        Index("idx_matching_logs_created", "created_at"),
    )


# ============================================
# FEEDBACK ANALYSIS (ML Results Storage)
# ============================================
class FeedbackAnalysis(Base):
    """
    Stores ML analysis results for user feedback.
    
    Multi-label classification + Sentiment + Keywords.
    Raw feedback text remains in original source table.
    """
    __tablename__ = "feedback_analysis"
    
    analysis_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feedback_id = Column(Text, nullable=False)  # Reference to original feedback
    feedback_source = Column(Text, nullable=False)  # 'event_rating', 'support_email', 'app_feedback', etc.
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"))
    
    # Sentiment Analysis
    sentiment = Column(Text, nullable=False)  # positive | neutral | negative | mixed
    sentiment_score = Column(Numeric(5, 4))  # 0.0 to 1.0
    
    # Multi-label Theme Classification (JSONB)
    themes = Column(JSONB, default=list)  # ["UX", "Bugs/Technical", "Feature requests", etc.]
    theme_scores = Column(JSONB, default=dict)  # {"UX": 0.85, "Bugs/Technical": 0.72}
    
    # Keyword Extraction (JSONB)
    keywords = Column(JSONB, default=list)  # ["login", "slow", "crash"]
    keyword_scores = Column(JSONB, default=dict)  # {"login": 0.92, "slow": 0.78}
    
    # Overall confidence
    confidence_score = Column(Numeric(5, 4))
    
    # Model metadata
    model_version = Column(Text, default="v1.0")
    processing_time_ms = Column(Numeric(10, 2))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("sentiment IN ('positive', 'neutral', 'negative', 'mixed')"),
        Index("idx_feedback_analysis_source", "feedback_source"),
        Index("idx_feedback_analysis_sentiment", "sentiment"),
        Index("idx_feedback_analysis_created", "created_at"),
        Index("idx_feedback_analysis_user", "user_id"),
    )


# ============================================
# USER RETENTION RISK (Churn Prediction)
# ============================================
class UserRetentionRisk(Base):
    """
    Stores churn/retention risk predictions for users.
    
    Model predicts risk only; recommended actions are rule-based
    and can be adjusted later by business logic.
    """
    __tablename__ = "user_retention_risk"
    
    prediction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    
    # Churn Prediction
    churn_probability = Column(Numeric(5, 4), nullable=False)  # 0.0 to 1.0
    risk_band = Column(Text, nullable=False)  # low | medium | high
    
    # Rule-based recommended action
    recommended_action = Column(Text)  # 'send_winback_email', 'offer_discount', 'no_action', etc.
    action_priority = Column(Integer, default=0)  # 0=low, 1=medium, 2=high
    
    # Feature values used for prediction (for explainability)
    features = Column(JSONB, default=dict)
    # {
    #   "days_since_last_login": 15,
    #   "days_since_last_event": 30,
    #   "events_attended_30d": 2,
    #   "events_attended_60d": 5,
    #   "events_attended_90d": 8,
    #   "messages_sent_30d": 3,
    #   "blog_interactions": 12,
    #   "event_interactions": 8,
    #   "notification_open_ratio": 0.65,
    #   "reward_tier": "silver",
    #   "has_purchase": true
    # }
    
    # Feature importance (from model)
    feature_importance = Column(JSONB, default=dict)
    
    # Model metadata
    model_name = Column(Text, default="logistic_regression")
    model_version = Column(Text, default="v1.0")
    
    # Validity period
    prediction_date = Column(Date, default=date.today)
    valid_until = Column(Date)  # Predictions expire after N days
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("risk_band IN ('low', 'medium', 'high')"),
        CheckConstraint("churn_probability >= 0 AND churn_probability <= 1"),
        Index("idx_retention_risk_user", "user_id"),
        Index("idx_retention_risk_band", "risk_band"),
        Index("idx_retention_risk_date", "prediction_date"),
        UniqueConstraint("user_id", "prediction_date", name="uq_user_daily_prediction"),
    )

