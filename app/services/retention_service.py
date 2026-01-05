"""
Retention Risk / Churn Prediction Service.

Implements ML-based user churn prediction per requirements:
==============================================================================

1. Prediction Endpoint
   - GET /engagement/retention-risk?user_id=123
   - Returns churn_probability (0.0 - 1.0)
   - Returns risk_band: low | medium | high

2. Features (exactly per spec)
   - days_since_last_login
   - days_since_last_event
   - events_attended_30d
   - events_attended_60d
   - events_attended_90d
   - messages_sent_30d
   - blog_interactions_30d
   - event_interactions_30d
   - notification_open_ratio
   - reward_tier
   - has_purchase

3. Model Stack (Open Source)
   - Scikit-learn (LogisticRegression / RandomForestClassifier)
   - NO external APIs required
   - Pre-trained model or rule-based fallback

4. Response
   - churn_probability: float (0-1)
   - risk_band: low | medium | high
   - recommended_action: str
   - feature_importance: dict

Persistence:
==============================================================================
- Results stored in user_retention_risk table
- Features as JSONB
- prediction_date and valid_until

"""
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import logging
import pickle
import os
import numpy as np

from app.models.database_models import (
    UserRetentionRisk, User, Event, EventAttendance,
    Message, Notification, UserReward
)
from app.config import settings

logger = logging.getLogger(__name__)


class RetentionRiskService:
    """
    Service for predicting user churn / retention risk.
    
    Uses scikit-learn models with fallback to rule-based scoring.
    """
    
    # Feature names (exactly per spec)
    FEATURE_NAMES = [
        "days_since_last_login",
        "days_since_last_event",
        "events_attended_30d",
        "events_attended_60d",
        "events_attended_90d",
        "messages_sent_30d",
        "blog_interactions_30d",
        "event_interactions_30d",
        "notification_open_ratio",
        "reward_tier",
        "has_purchase"
    ]
    
    # Risk band thresholds
    RISK_THRESHOLDS = {
        "high": 0.7,
        "medium": 0.4,
        "low": 0.0
    }
    
    # Recommended actions per risk band
    RECOMMENDED_ACTIONS = {
        "high": "Immediate outreach: personalized email with incentive offer",
        "medium": "Send targeted re-engagement campaign within 48 hours",
        "low": "Continue standard engagement flow"
    }
    
    # Model instance (lazy loaded)
    _model = None
    _model_path = os.path.join(os.path.dirname(__file__), "churn_model.pkl")

    # =========================================================================
    # MAIN PREDICTION ENTRY POINT
    # =========================================================================
    
    @staticmethod
    async def predict_retention_risk(
        user_id: int,
        db: AsyncSession,
        persist: bool = True
    ) -> Dict[str, Any]:
        """
        Predict retention risk / churn probability for a user.
        
        Args:
            user_id: User ID to analyze
            db: Database session
            persist: Whether to store prediction in database
        
        Returns:
            Prediction result with churn_probability, risk_band, etc.
        """
        start_time = datetime.utcnow()
        
        # Check for recent prediction (cache for 24 hours)
        cached = await RetentionRiskService._get_cached_prediction(user_id, db)
        if cached:
            return cached
        
        # 1. Extract features
        features = await RetentionRiskService._extract_features(user_id, db)
        
        if features is None:
            return {
                "error": "User not found or insufficient data",
                "user_id": user_id
            }
        
        # 2. Run prediction
        churn_probability, feature_importance = await RetentionRiskService._predict(features)
        
        # 3. Determine risk band
        risk_band = RetentionRiskService._get_risk_band(churn_probability)
        
        # 4. Get recommended action
        recommended_action = RetentionRiskService.RECOMMENDED_ACTIONS[risk_band]
        
        # 5. Get model name
        model_name = RetentionRiskService._get_model_name()
        
        processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        result = {
            "user_id": user_id,
            "churn_probability": round(churn_probability, 4),
            "risk_band": risk_band,
            "recommended_action": recommended_action,
            "features": {k: round(v, 4) if isinstance(v, float) else v for k, v in features.items()},
            "feature_importance": {k: round(v, 4) for k, v in feature_importance.items()},
            "model_name": model_name,
            "prediction_date": datetime.utcnow().isoformat(),
            "valid_until": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            "processing_time_ms": round(processing_time_ms, 2)
        }
        
        # Persist to database
        if persist:
            try:
                prediction = UserRetentionRisk(
                    user_id=user_id,
                    churn_probability=churn_probability,
                    risk_band=risk_band,
                    recommended_action=recommended_action,
                    features=features,
                    feature_importance=feature_importance,
                    model_name=model_name,
                    prediction_date=datetime.utcnow(),
                    valid_until=datetime.utcnow() + timedelta(hours=24)
                )
                db.add(prediction)
                await db.flush()
                result["prediction_id"] = str(prediction.prediction_id)
            except Exception as e:
                logger.error(f"Failed to persist retention risk prediction: {e}")
        
        return result

    # =========================================================================
    # FEATURE EXTRACTION
    # =========================================================================
    
    @staticmethod
    async def _extract_features(user_id: int, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Extract all features for a user.
        
        Features (per spec):
        - days_since_last_login
        - days_since_last_event
        - events_attended_30d, 60d, 90d
        - messages_sent_30d
        - blog_interactions_30d
        - event_interactions_30d
        - notification_open_ratio
        - reward_tier
        - has_purchase
        """
        now = datetime.utcnow()
        
        # Get user
        user = await db.get(User, user_id)
        if not user:
            return None
        
        features = {}
        
        # 1. days_since_last_login
        if hasattr(user, 'last_login') and user.last_login:
            features["days_since_last_login"] = (now - user.last_login).days
        elif hasattr(user, 'updated_at') and user.updated_at:
            features["days_since_last_login"] = (now - user.updated_at).days
        else:
            features["days_since_last_login"] = 30  # Default
        
        # 2. days_since_last_event
        last_event_query = select(func.max(Event.event_date)).join(
            EventAttendance, Event.event_id == EventAttendance.event_id
        ).where(
            EventAttendance.user_id == user_id,
            Event.event_date < now
        )
        
        try:
            result = await db.execute(last_event_query)
            last_event_date = result.scalar()
            if last_event_date:
                features["days_since_last_event"] = (now - last_event_date).days
            else:
                features["days_since_last_event"] = 365  # Never attended
        except:
            features["days_since_last_event"] = 365
        
        # 3. events_attended (30d, 60d, 90d)
        for days, key in [(30, "events_attended_30d"), (60, "events_attended_60d"), (90, "events_attended_90d")]:
            cutoff = now - timedelta(days=days)
            events_query = select(func.count(EventAttendance.event_id)).where(
                EventAttendance.user_id == user_id,
                EventAttendance.created_at >= cutoff
            )
            try:
                result = await db.execute(events_query)
                features[key] = result.scalar() or 0
            except:
                features[key] = 0
        
        # 4. messages_sent_30d
        cutoff_30d = now - timedelta(days=30)
        try:
            msg_query = select(func.count(Message.message_id)).where(
                Message.sender_id == user_id,
                Message.created_at >= cutoff_30d
            )
            result = await db.execute(msg_query)
            features["messages_sent_30d"] = result.scalar() or 0
        except:
            features["messages_sent_30d"] = 0
        
        # 5. blog_interactions_30d (from user activity or default)
        # Note: Requires BlogInteraction model or similar
        features["blog_interactions_30d"] = await RetentionRiskService._get_blog_interactions(user_id, db, cutoff_30d)
        
        # 6. event_interactions_30d (views, RSVPs, etc.)
        features["event_interactions_30d"] = await RetentionRiskService._get_event_interactions(user_id, db, cutoff_30d)
        
        # 7. notification_open_ratio
        features["notification_open_ratio"] = await RetentionRiskService._get_notification_ratio(user_id, db)
        
        # 8. reward_tier (0-5 scale)
        features["reward_tier"] = await RetentionRiskService._get_reward_tier(user_id, db)
        
        # 9. has_purchase (boolean -> 0/1)
        features["has_purchase"] = await RetentionRiskService._has_purchase(user_id, db)
        
        return features
    
    @staticmethod
    async def _get_blog_interactions(user_id: int, db: AsyncSession, cutoff: datetime) -> int:
        """Get blog interactions count."""
        # Try BlogInteraction model if exists
        try:
            from app.models.database_models import BlogInteraction
            query = select(func.count(BlogInteraction.interaction_id)).where(
                BlogInteraction.user_id == user_id,
                BlogInteraction.created_at >= cutoff
            )
            result = await db.execute(query)
            return result.scalar() or 0
        except:
            # Fallback: use generic activity log or return 0
            return 0
    
    @staticmethod
    async def _get_event_interactions(user_id: int, db: AsyncSession, cutoff: datetime) -> int:
        """Get event interactions count (views, RSVPs, comments)."""
        total = 0
        
        # Count event attendance registrations
        try:
            query = select(func.count(EventAttendance.event_id)).where(
                EventAttendance.user_id == user_id,
                EventAttendance.created_at >= cutoff
            )
            result = await db.execute(query)
            total += result.scalar() or 0
        except:
            pass
        
        # Could add: event views, comments, shares
        # For now, use registrations as proxy
        return total
    
    @staticmethod
    async def _get_notification_ratio(user_id: int, db: AsyncSession) -> float:
        """Get notification open ratio (opened / sent)."""
        try:
            # Total sent
            sent_query = select(func.count(Notification.notification_id)).where(
                Notification.user_id == user_id
            )
            sent_result = await db.execute(sent_query)
            total_sent = sent_result.scalar() or 0
            
            if total_sent == 0:
                return 0.5  # No data, neutral
            
            # Opened (is_read = True)
            opened_query = select(func.count(Notification.notification_id)).where(
                Notification.user_id == user_id,
                Notification.is_read == True
            )
            opened_result = await db.execute(opened_query)
            total_opened = opened_result.scalar() or 0
            
            return total_opened / total_sent
        except:
            return 0.5
    
    @staticmethod
    async def _get_reward_tier(user_id: int, db: AsyncSession) -> int:
        """Get user's reward tier (0-5)."""
        try:
            query = select(UserReward.reward_tier).where(
                UserReward.user_id == user_id
            ).order_by(UserReward.earned_at.desc()).limit(1)
            
            result = await db.execute(query)
            tier = result.scalar()
            
            if tier is not None:
                # Map tier to 0-5 scale
                tier_map = {
                    "bronze": 1,
                    "silver": 2,
                    "gold": 3,
                    "platinum": 4,
                    "diamond": 5
                }
                if isinstance(tier, str):
                    return tier_map.get(tier.lower(), 0)
                return min(5, max(0, int(tier)))
            return 0
        except:
            return 0
    
    @staticmethod
    async def _has_purchase(user_id: int, db: AsyncSession) -> int:
        """Check if user has made a purchase (returns 0 or 1)."""
        try:
            # Check EventAttendance with ticket_type or Payment table
            from app.models.database_models import Payment
            query = select(func.count(Payment.payment_id)).where(
                Payment.user_id == user_id,
                Payment.status == "completed"
            )
            result = await db.execute(query)
            count = result.scalar() or 0
            return 1 if count > 0 else 0
        except:
            # Fallback: check if user has any paid event attendee
            return 0

    # =========================================================================
    # PREDICTION
    # =========================================================================
    
    @staticmethod
    async def _predict(features: Dict[str, Any]) -> tuple:
        """
        Run churn prediction model.
        
        Returns:
            Tuple of (churn_probability, feature_importance)
        """
        # Try to load trained model
        model = RetentionRiskService._load_model()
        
        if model:
            return RetentionRiskService._model_predict(model, features)
        else:
            # Fallback to rule-based scoring
            return RetentionRiskService._rule_based_predict(features)
    
    @staticmethod
    def _load_model():
        """Load trained scikit-learn model if available."""
        if RetentionRiskService._model is not None:
            return RetentionRiskService._model
        
        if os.path.exists(RetentionRiskService._model_path):
            try:
                with open(RetentionRiskService._model_path, "rb") as f:
                    RetentionRiskService._model = pickle.load(f)
                logger.info("Loaded churn prediction model from disk")
                return RetentionRiskService._model
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
        
        return None
    
    @staticmethod
    def _model_predict(model, features: Dict[str, Any]) -> tuple:
        """Run prediction using sklearn model."""
        # Convert features to array in correct order
        X = np.array([[features.get(name, 0) for name in RetentionRiskService.FEATURE_NAMES]])
        
        # Predict probability
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)[0]
            churn_prob = proba[1] if len(proba) > 1 else proba[0]
        else:
            churn_prob = float(model.predict(X)[0])
        
        # Feature importance
        feature_importance = {}
        if hasattr(model, "feature_importances_"):
            for name, imp in zip(RetentionRiskService.FEATURE_NAMES, model.feature_importances_):
                feature_importance[name] = float(imp)
        elif hasattr(model, "coef_"):
            # For LogisticRegression
            coefs = model.coef_.flatten()
            for name, coef in zip(RetentionRiskService.FEATURE_NAMES, coefs):
                feature_importance[name] = abs(float(coef))
        else:
            # Fallback: use rule weights
            feature_importance = RetentionRiskService._get_rule_weights()
        
        # Normalize importance
        total = sum(feature_importance.values())
        if total > 0:
            feature_importance = {k: v / total for k, v in feature_importance.items()}
        
        return churn_prob, feature_importance
    
    @staticmethod
    def _rule_based_predict(features: Dict[str, Any]) -> tuple:
        """
        Rule-based churn prediction fallback.
        
        Uses weighted scoring based on domain knowledge.
        """
        weights = RetentionRiskService._get_rule_weights()
        
        score = 0.0
        
        # days_since_last_login (higher = higher risk)
        login_days = features.get("days_since_last_login", 30)
        if login_days > 60:
            score += weights["days_since_last_login"] * 1.0
        elif login_days > 30:
            score += weights["days_since_last_login"] * 0.7
        elif login_days > 14:
            score += weights["days_since_last_login"] * 0.4
        elif login_days > 7:
            score += weights["days_since_last_login"] * 0.2
        
        # days_since_last_event (higher = higher risk)
        event_days = features.get("days_since_last_event", 365)
        if event_days > 180:
            score += weights["days_since_last_event"] * 1.0
        elif event_days > 90:
            score += weights["days_since_last_event"] * 0.7
        elif event_days > 30:
            score += weights["days_since_last_event"] * 0.4
        
        # events_attended (lower = higher risk)
        events_30 = features.get("events_attended_30d", 0)
        events_90 = features.get("events_attended_90d", 0)
        
        if events_90 == 0:
            score += weights["events_attended_90d"] * 1.0
        elif events_30 == 0 and events_90 > 0:
            score += weights["events_attended_30d"] * 0.6
        elif events_30 < 2:
            score += weights["events_attended_30d"] * 0.3
        
        # messages_sent_30d (lower = higher risk)
        messages = features.get("messages_sent_30d", 0)
        if messages == 0:
            score += weights["messages_sent_30d"] * 0.8
        elif messages < 3:
            score += weights["messages_sent_30d"] * 0.4
        
        # notification_open_ratio (lower = higher risk)
        notif_ratio = features.get("notification_open_ratio", 0.5)
        if notif_ratio < 0.1:
            score += weights["notification_open_ratio"] * 1.0
        elif notif_ratio < 0.3:
            score += weights["notification_open_ratio"] * 0.6
        elif notif_ratio < 0.5:
            score += weights["notification_open_ratio"] * 0.3
        
        # reward_tier (higher tier = lower risk)
        tier = features.get("reward_tier", 0)
        if tier == 0:
            score += weights["reward_tier"] * 0.5
        elif tier < 2:
            score += weights["reward_tier"] * 0.3
        
        # has_purchase (purchase = lower risk)
        if not features.get("has_purchase", 0):
            score += weights["has_purchase"] * 0.4
        
        # blog_interactions + event_interactions
        blog_int = features.get("blog_interactions_30d", 0)
        event_int = features.get("event_interactions_30d", 0)
        
        if blog_int == 0 and event_int == 0:
            score += (weights["blog_interactions_30d"] + weights["event_interactions_30d"]) * 0.7
        elif blog_int + event_int < 3:
            score += (weights["blog_interactions_30d"] + weights["event_interactions_30d"]) * 0.3
        
        # Normalize to 0-1
        total_weight = sum(weights.values())
        churn_probability = min(1.0, max(0.0, score / total_weight))
        
        # Feature importance is the weights normalized
        feature_importance = {k: v / total_weight for k, v in weights.items()}
        
        return churn_probability, feature_importance
    
    @staticmethod
    def _get_rule_weights() -> Dict[str, float]:
        """Get feature weights for rule-based prediction."""
        return {
            "days_since_last_login": 0.20,
            "days_since_last_event": 0.18,
            "events_attended_30d": 0.12,
            "events_attended_60d": 0.05,
            "events_attended_90d": 0.08,
            "messages_sent_30d": 0.08,
            "blog_interactions_30d": 0.05,
            "event_interactions_30d": 0.07,
            "notification_open_ratio": 0.07,
            "reward_tier": 0.05,
            "has_purchase": 0.05
        }
    
    @staticmethod
    def _get_risk_band(churn_probability: float) -> str:
        """Determine risk band from probability."""
        if churn_probability >= RetentionRiskService.RISK_THRESHOLDS["high"]:
            return "high"
        elif churn_probability >= RetentionRiskService.RISK_THRESHOLDS["medium"]:
            return "medium"
        else:
            return "low"
    
    @staticmethod
    def _get_model_name() -> str:
        """Get name of the model being used."""
        if RetentionRiskService._model is not None:
            return type(RetentionRiskService._model).__name__
        return "RuleBasedChurnModel"

    # =========================================================================
    # CACHING
    # =========================================================================
    
    @staticmethod
    async def _get_cached_prediction(user_id: int, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Get cached prediction if still valid."""
        query = select(UserRetentionRisk).where(
            UserRetentionRisk.user_id == user_id,
            UserRetentionRisk.valid_until > datetime.utcnow()
        ).order_by(UserRetentionRisk.prediction_date.desc()).limit(1)
        
        try:
            result = await db.execute(query)
            prediction = result.scalar()
            
            if prediction:
                return {
                    "user_id": user_id,
                    "prediction_id": str(prediction.prediction_id),
                    "churn_probability": float(prediction.churn_probability),
                    "risk_band": prediction.risk_band,
                    "recommended_action": prediction.recommended_action,
                    "features": prediction.features,
                    "feature_importance": prediction.feature_importance,
                    "model_name": prediction.model_name,
                    "prediction_date": prediction.prediction_date.isoformat(),
                    "valid_until": prediction.valid_until.isoformat(),
                    "cached": True
                }
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
        
        return None

    # =========================================================================
    # BATCH & BULK OPERATIONS
    # =========================================================================
    
    @staticmethod
    async def predict_batch(
        user_ids: List[int],
        db: AsyncSession,
        persist: bool = True
    ) -> List[Dict[str, Any]]:
        """Predict retention risk for multiple users."""
        results = []
        
        for user_id in user_ids:
            try:
                result = await RetentionRiskService.predict_retention_risk(
                    user_id=user_id,
                    db=db,
                    persist=persist
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Batch prediction error for user {user_id}: {e}")
                results.append({
                    "user_id": user_id,
                    "error": str(e)
                })
        
        return results
    
    @staticmethod
    async def get_high_risk_users(
        db: AsyncSession,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get users with high churn risk."""
        query = select(UserRetentionRisk).where(
            UserRetentionRisk.risk_band == "high",
            UserRetentionRisk.valid_until > datetime.utcnow()
        ).order_by(
            UserRetentionRisk.churn_probability.desc()
        ).limit(limit)
        
        result = await db.execute(query)
        predictions = result.scalars().all()
        
        return [
            {
                "user_id": p.user_id,
                "churn_probability": float(p.churn_probability),
                "risk_band": p.risk_band,
                "recommended_action": p.recommended_action,
                "prediction_date": p.prediction_date.isoformat()
            }
            for p in predictions
        ]

    # =========================================================================
    # MODEL TRAINING (OFFLINE)
    # =========================================================================
    
    @staticmethod
    def train_model(
        X: np.ndarray,
        y: np.ndarray,
        model_type: str = "random_forest"
    ) -> Any:
        """
        Train a churn prediction model (offline operation).
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (0=retained, 1=churned)
            model_type: 'logistic' or 'random_forest'
        
        Returns:
            Trained model
        """
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score
        
        if model_type == "logistic":
            model = LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                random_state=42
            )
        else:
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                class_weight="balanced",
                random_state=42
            )
        
        # Cross-validation
        scores = cross_val_score(model, X, y, cv=5, scoring="roc_auc")
        logger.info(f"CV ROC-AUC: {scores.mean():.3f} (+/- {scores.std()*2:.3f})")
        
        # Train final model
        model.fit(X, y)
        
        # Save model
        with open(RetentionRiskService._model_path, "wb") as f:
            pickle.dump(model, f)
        
        logger.info(f"Model saved to {RetentionRiskService._model_path}")
        
        return model
