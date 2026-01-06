"""
Pydantic Schemas for Kumele AI/ML Backend APIs.
Request and Response models for all endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================
# ENUMS
# ============================================
class SentimentLabel(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class ModerationDecision(str, Enum):
    approve = "approve"
    reject = "reject"
    flag_for_review = "flag_for_review"


class ContentType(str, Enum):
    text = "text"
    image = "image"
    video = "video"


class FeedbackType(str, Enum):
    helpful = "helpful"
    not_helpful = "not_helpful"
    incorrect = "incorrect"
    incomplete = "incomplete"


class TranslationStatus(str, Enum):
    pending = "pending"
    approved = "approved"


# ============================================
# RATING SCHEMAS
# ============================================
class RatingSubmission(BaseModel):
    """Request to submit event rating."""
    user_id: str = Field(..., description="User ID submitting the rating")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: Optional[str] = Field(None, max_length=2000, description="Optional feedback text")


class RatingResponse(BaseModel):
    """Response after submitting rating."""
    success: bool
    message: str
    rating_id: Optional[str] = None
    event_id: Optional[str] = None
    host_id: Optional[str] = None


class HostRatingResponse(BaseModel):
    """Host rating aggregated response."""
    host_id: str
    weighted_score: float = Field(..., description="Weighted score 0-5")
    weighted_score_percent: float = Field(..., description="Weighted score as percentage")
    attendee_avg: float
    attendee_count: int
    system_reliability_score: float
    total_events_hosted: int
    total_attendees: int
    badges: List[str] = []


# ============================================
# RECOMMENDATION SCHEMAS
# ============================================
class HobbyRecommendationItem(BaseModel):
    """Single hobby recommendation."""
    hobby_id: str
    hobby_name: str
    score: float = Field(..., ge=0, le=1)
    reason: Optional[str] = None


class HobbyRecommendationResponse(BaseModel):
    """Response for hobby recommendations."""
    user_id: str
    recommendations: List[HobbyRecommendationItem]
    cached: bool = False


class EventRecommendationItem(BaseModel):
    """Single event recommendation."""
    event_id: str
    title: str
    score: float = Field(..., ge=0, le=1)
    category: Optional[str] = None
    event_date: Optional[datetime] = None
    reason: Optional[str] = None


class EventRecommendationResponse(BaseModel):
    """Response for event recommendations."""
    user_id: str
    recommendations: List[EventRecommendationItem]
    cached: bool = False


# ============================================
# ADS SCHEMAS
# ============================================
class AudienceMatchRequest(BaseModel):
    """Request for audience matching."""
    ad_id: Optional[str] = None
    ad_content: str = Field(..., min_length=1)
    target_interests: Optional[List[str]] = None
    target_locations: Optional[List[str]] = None
    target_age_min: Optional[int] = None
    target_age_max: Optional[int] = None


class AudienceSegmentItem(BaseModel):
    """Single audience segment."""
    segment_id: str
    segment_name: str
    match_score: float = Field(..., ge=0, le=100)
    audience_size: int
    targeting_hobbies: Optional[List[str]] = None


class AudienceMatchResponse(BaseModel):
    """Response for audience matching."""
    ad_id: Optional[str] = None
    segments: List[AudienceSegmentItem]
    total_reach: int
    extracted_themes: Optional[List[str]] = None  # Themes extracted via NLP
    model: Optional[str] = None  # Model used


class AdPerformancePredictionRequest(BaseModel):
    """Request for performance prediction."""
    ad_id: str
    budget: float = Field(..., gt=0)
    duration_days: int = Field(..., ge=1, le=365)
    audience_segment_ids: Optional[List[str]] = None
    ad_content: Optional[str] = None  # For sentiment/clarity analysis


class AdPerformancePredictionResponse(BaseModel):
    """Response for performance prediction."""
    ad_id: str
    predicted_impressions: int
    predicted_clicks: int
    predicted_ctr: float
    predicted_cpc: float
    predicted_engagement_rate: float
    confidence: float
    recommendations: List[str] = []
    content_analysis: Optional[Dict[str, Any]] = None  # Sentiment/clarity analysis
    model: Optional[str] = None  # Model used for prediction


# ============================================
# NLP SCHEMAS
# ============================================
class SentimentRequest(BaseModel):
    """Request for sentiment analysis."""
    text: str = Field(..., min_length=1, max_length=10000)
    content_id: Optional[str] = None
    content_type: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "I absolutely loved this event! The host was amazing and I learned so much."
            }
        }


class SentimentResponse(BaseModel):
    """Response for sentiment analysis."""
    sentiment: str
    score: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)


class KeywordRequest(BaseModel):
    """Request for keyword extraction."""
    text: str = Field(..., min_length=1, max_length=10000)
    max_keywords: Optional[int] = Field(10, ge=1, le=50)
    content_id: Optional[str] = None  # For storing keywords in nlp_keywords table
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Looking for photography workshops in downtown Chicago near the Art Institute. Interested in portrait and landscape photography.",
                "max_keywords": 10
            }
        }


class KeywordItem(BaseModel):
    """Single keyword."""
    keyword: str
    score: float
    category: Optional[str] = None


class KeywordResponse(BaseModel):
    """Response for keyword extraction."""
    keywords: List[KeywordItem]
    entities: List[str] = []


class TrendItem(BaseModel):
    """Single trending topic."""
    topic: str
    mentions: int
    growth_rate: Optional[float] = None
    sentiment: Optional[str] = None


class TrendingTopicsResponse(BaseModel):
    """Response for trending topics."""
    timeframe: str
    trends: List[TrendItem]
    category: Optional[str] = None


# ============================================
# MODERATION SCHEMAS
# ============================================
class ModerationRequest(BaseModel):
    """Request for content moderation."""
    content_id: Optional[str] = None  # Auto-generated if not provided
    content_type: ContentType
    text: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    user_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "content_type": "text",
                "text": "This is a great event! I really enjoyed it."
            }
        }


class ModerationFlag(BaseModel):
    """Single moderation flag."""
    flag_type: str
    score: float
    threshold: float


class ModerationResponse(BaseModel):
    """Response for moderation."""
    content_id: str
    content_type: str
    decision: str
    confidence: float
    flags: List[ModerationFlag]
    reasons: List[str] = []
    job_id: Optional[str] = None


class ModerationStatus(BaseModel):
    """Response for moderation status check."""
    content_id: str
    content_type: str
    status: str
    decision: Optional[str] = None
    flags: Optional[List[ModerationFlag]] = None
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None


# ============================================
# CHATBOT SCHEMAS
# ============================================
class ChatbotAskRequest(BaseModel):
    """Request to ask chatbot."""
    query: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None  # Auto-generated if not provided
    language: Optional[str] = "en"
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How do I create an event?",
                "language": "en"
            }
        }


class ChatbotAskResponse(BaseModel):
    """Response from chatbot."""
    answer: str
    source_docs: List[str] = []
    confidence: float
    query_id: str


class KnowledgeSyncRequest(BaseModel):
    """Request to sync knowledge document."""
    doc_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    category: Optional[str] = "faq"
    language: Optional[str] = "en"


class KnowledgeSyncResponse(BaseModel):
    """Response for knowledge sync."""
    success: bool
    doc_id: str
    chunks_indexed: int
    message: str


class ChatbotFeedbackRequest(BaseModel):
    """Request to submit chatbot feedback.
    
    Feedback can be any text. Common values like 'good', 'helpful', 'great', 'excellent',
    'useful' are mapped to 'positive'. Values like 'bad', 'wrong', 'incorrect', 'unhelpful',
    'not helpful' are mapped to 'negative'. Any other text defaults to 'positive'.
    """
    query_id: str
    user_id: Optional[str] = None
    feedback: str = Field(
        ..., 
        description="User feedback text (e.g., 'good', 'helpful', 'bad', 'unhelpful', or any text)",
        examples=["good", "helpful", "it was great", "not helpful", "the answer was wrong"]
    )


class ChatbotFeedbackResponse(BaseModel):
    """Response for chatbot feedback."""
    success: bool
    message: str


# ============================================
# TRANSLATION SCHEMAS
# ============================================
class TranslateRequest(BaseModel):
    """Request for text translation."""
    text: str = Field(..., min_length=1, max_length=10000)
    source_language: str = Field(..., min_length=2, max_length=5)
    target_language: str = Field(..., min_length=2, max_length=5)


class TranslateResponse(BaseModel):
    """Response for translation."""
    translated_text: str
    source_language: str
    target_language: str
    confidence: float


class I18nStringsResponse(BaseModel):
    """Response for i18n strings."""
    language: str
    strings: Dict[str, str]
    is_rtl: bool = False
    direction: str = "ltr"  # "ltr" or "rtl"


class TranslationApprovalRequest(BaseModel):
    """Request to approve translation."""
    translation_id: str
    approved_by: str


class TranslationApprovalResponse(BaseModel):
    """Response for translation approval."""
    success: bool
    message: str
    translation_id: Optional[str] = None


# ============================================
# SUPPORT SCHEMAS
# ============================================
class SupportEmailIncomingRequest(BaseModel):
    """Request for incoming support email."""
    from_email: str
    subject: str
    body: str
    user_id: Optional[str] = None
    thread_id: Optional[str] = None


class SupportEmailResponse(BaseModel):
    """Response for processed support email."""
    email_id: str
    category: str
    sentiment: str
    priority: int
    needs_escalation: bool
    draft_reply: str
    entities: Dict[str, Any] = {}
    status: str


class SupportEmailReplyRequest(BaseModel):
    """Request to reply to support email."""
    reply_body: str
    agent_id: str


class SupportEmailReplyResponse(BaseModel):
    """Response for email reply."""
    success: bool
    reply_id: Optional[str] = None
    message: str


class SupportEmailEscalateRequest(BaseModel):
    """Request to escalate support email."""
    reason: str
    escalated_by: str


class SupportEmailEscalateResponse(BaseModel):
    """Response for email escalation."""
    success: bool
    email_id: Optional[str] = None
    new_priority: Optional[int] = None
    message: str


class SupportEmailDetailsResponse(BaseModel):
    """Response for email details."""
    id: str
    from_email: str
    to_email: Optional[str] = None
    subject: str
    body: str
    status: str
    priority: int
    created_at: str
    replied_at: Optional[str] = None
    thread: List[Dict[str, Any]] = []
    analysis: Optional[Dict[str, Any]] = None


# ============================================
# PRICING SCHEMAS
# ============================================
class PriceTier(BaseModel):
    """Single price tier recommendation."""
    name: str  # economy, standard, premium
    price: float
    predicted_attendance: int
    predicted_revenue: float


class PriceOptimizeResponse(BaseModel):
    """Response for price optimization with tiers."""
    event_id: str
    base_price: float
    price_tiers: List[PriceTier]
    optimal_tier: PriceTier
    factors: Dict[str, float]
    metrics: Dict[str, Any]
    confidence: float
    recommendation: str
    note: str = "Prices are recommendations only. Host decides final price."


class UpliftEstimate(BaseModel):
    """Uplift estimation for discount."""
    uplift_percent: float
    expected_additional_bookings: float
    estimated_revenue_gain: float
    discount_cost: float
    estimated_roi: float
    confidence: float
    model: str = "prophet_regression_hybrid"


class DiscountSuggestionItem(BaseModel):
    """Single discount suggestion with uplift analysis."""
    type: str
    segment: Optional[str] = None  # gold, silver, bronze, new_user, etc.
    code: Optional[str] = None
    discount_percent: int
    description: str
    valid_until: Optional[str] = None
    relevance_score: float
    uplift: Optional[UpliftEstimate] = None
    roi: Optional[float] = None


class SegmentAnalysis(BaseModel):
    """User/event segment analysis."""
    segment: Optional[str] = None
    tier: Optional[str] = None
    discount_cap: Optional[int] = None


class DiscountSuggestionResponse(BaseModel):
    """Response for discount suggestions with ROI optimization."""
    best_discount: Optional[DiscountSuggestionItem] = None
    alternates: List[DiscountSuggestionItem] = []
    segment_analysis: Dict[str, Any] = {}
    all_suggestions: List[DiscountSuggestionItem] = []
    confidence: float
    user_id: Optional[str] = None
    event_id: Optional[str] = None
    generated_at: str
    note: str = "Discount suggestions are recommendations only."


# ============================================
# SYSTEM SCHEMAS
# ============================================
class ComponentHealth(BaseModel):
    """Health status of a component."""
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class SystemMetrics(BaseModel):
    """System resource metrics."""
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    disk: Dict[str, Any]


class SystemHealthResponse(BaseModel):
    """Response for system health check."""
    status: str
    timestamp: str
    check_duration_ms: float
    components: Dict[str, ComponentHealth]
    system: SystemMetrics
    version: Dict[str, str]


# ============================================
# TAXONOMY SCHEMAS
# ============================================
class TaxonomyItem(BaseModel):
    """Single taxonomy item."""
    id: str
    name: str
    slug: str
    icon: Optional[str] = None
    level: int
    children: Optional[List["TaxonomyItem"]] = None


TaxonomyItem.model_rebuild()


class TaxonomyResponse(BaseModel):
    """Response for taxonomy."""
    categories: List[TaxonomyItem]


# ============================================
# GENERIC RESPONSES
# ============================================
class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Generic error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None


# ============================================
# REWARDS SCHEMAS
# ============================================
class RewardCurrentStatus(BaseModel):
    """Current reward status."""
    tier: str
    gold_count: int
    total_discount_percent: int
    successful_events_30d: int
    events_attended: int
    events_hosted: int


class RewardProgress(BaseModel):
    """Progress to next tier."""
    next_tier: str
    events_needed: int
    progress_percent: float
    evaluation_window_days: int


class RewardCouponItem(BaseModel):
    """A single reward coupon."""
    coupon_id: str
    discount_percent: int
    tier: str
    stackable: bool
    is_redeemed: bool
    issued_at: str


class RewardsSuggestionResponse(BaseModel):
    """Response for rewards suggestion API."""
    user_id: str
    current_status: RewardCurrentStatus
    progress: RewardProgress
    available_coupons: List[RewardCouponItem]
    computed_at: str
    history: Optional[List[Dict[str, Any]]] = None


class RewardProgressResponse(BaseModel):
    """Detailed reward progress response."""
    user_id: str
    current_tier: str
    gold_count: int
    successful_events: int
    events_breakdown: Dict[str, int]
    next_tier: str
    events_to_next_tier: int
    progress_percent: float
    days_remaining_in_window: int
    window_end_date: str


# ============================================
# MATCHING SCHEMAS
# ============================================
class ScoreBreakdown(BaseModel):
    """Score breakdown for matching pipeline."""
    relevance: float = 0.0      # ML embedding similarity
    trust: float = 0.0          # Host rating + reliability
    engagement: float = 0.0     # Event popularity (clicks, RSVPs)
    freshness: float = 0.0      # Event recency
    business: float = 0.0       # Rewards & promotions


class EventMatchItem(BaseModel):
    """Single matched event."""
    event_id: str
    title: str
    category: Optional[str] = None
    event_date: Optional[str] = None
    location: Optional[str] = None
    distance_km: Optional[float] = None
    score: float
    reasons: Optional[List[str]] = None
    score_breakdown: ScoreBreakdown
    host_id: Optional[str] = None


class EventMatchResponse(BaseModel):
    """Response for event matching."""
    user_id: str
    matched_events: List[EventMatchItem]
    total_found: int
    total_returned: int
    filters_applied: Dict[str, Any]
    weights_used: Optional[Dict[str, float]] = None
    processing_time_ms: Optional[float] = None
    computed_at: str
    pipeline_version: Optional[str] = None


# ============================================
# PREDICTION SCHEMAS
# ============================================
class AttendancePredictionRequest(BaseModel):
    """Request for attendance prediction."""
    event_id: Optional[str] = None
    event_date: Optional[datetime] = None
    category: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = None
    host_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_date": "2025-12-25T14:00:00",
                "category": "photography",
                "location": "New York",
                "capacity": 50
            }
        }


class ConfidenceInterval(BaseModel):
    """Confidence interval for predictions."""
    lower: int
    upper: int
    confidence_level: float


class AttendancePredictionResponse(BaseModel):
    """Response for attendance prediction."""
    event_id: Optional[str] = None
    predicted_attendance: int
    confidence_interval: ConfidenceInterval
    expected_actual_attendance: int
    estimated_no_show_rate: float
    factors: Dict[str, float]
    metrics: Dict[str, Any]  # Changed to Any to support nested metrics
    computed_at: str


class RankedDay(BaseModel):
    """Ranked day for trends."""
    day: str
    day_index: int
    avg_attendance: float
    factor: float
    data_points: Optional[int] = None  # Number of data points (for timeseries)


class RankedTime(BaseModel):
    """Ranked time period for trends."""
    time_period: str
    avg_attendance: float
    factor: float


class BestCombination(BaseModel):
    """Best day/time combination."""
    day: str
    time_period: str
    expected_attendance: float


class TrendPredictionResponse(BaseModel):
    """Response for trend prediction."""
    category: Optional[str] = None
    location: Optional[str] = None
    ranked_days: List[RankedDay]
    ranked_times: List[RankedTime]
    best_combination: BestCombination
    historical_events_analyzed: int
    data_source: Optional[str] = None  # 'timeseries_daily' or 'event_attendance'
    model: Optional[str] = None  # Model used
    confidence_score: float
    computed_at: str
