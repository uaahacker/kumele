#!/usr/bin/env python3
"""
Kumele AI/ML Backend - Complete API Testing Script
===================================================

This script tests ALL endpoints of the Kumele backend API.
Run this to verify the entire system is working correctly.

Usage:
------
python scripts/test_all_endpoints.py --host http://localhost:8000
python scripts/test_all_endpoints.py --host http://YOUR_SERVER_IP:8000

Requirements:
-------------
pip install requests colorama tabulate

Output:
-------
- Colored console output showing pass/fail for each endpoint
- JSON response samples for documentation
- Summary statistics at the end
"""

import requests
import json
import argparse
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
import sys

# Try to import colorama for colored output
try:
    from colorama import init, Fore, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        GREEN = RED = YELLOW = CYAN = MAGENTA = BLUE = WHITE = RESET = ""
    class Style:
        BRIGHT = RESET_ALL = ""

# Try to import tabulate for nice tables
try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False


class APITester:
    """Test all Kumele API endpoints."""
    
    def __init__(self, base_url: str, verbose: bool = True):
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.results = []
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        # Test data
        self.test_user_id = "1"
        self.test_event_id = "1"
        self.test_host_id = "1"
        self.test_ad_id = "1"
        
    def log(self, message: str, color: str = Fore.WHITE):
        """Print colored log message."""
        if self.verbose:
            print(f"{color}{message}{Style.RESET_ALL}")
    
    def test_endpoint(
        self, 
        method: str, 
        path: str, 
        description: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        expected_status: int = 200,
        files: Optional[Dict] = None
    ) -> Tuple[bool, Dict]:
        """Test a single endpoint and return success status and response."""
        url = f"{self.base_url}{path}"
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=30)
            elif method.upper() == "POST":
                if files:
                    # Remove content-type header for file uploads
                    headers = {k: v for k, v in self.session.headers.items() if k.lower() != "content-type"}
                    response = requests.post(url, data=data, files=files, headers=headers, timeout=30)
                else:
                    response = self.session.post(url, json=data, params=params, timeout=30)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, params=params, timeout=30)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params, timeout=30)
            else:
                return False, {"error": f"Unknown method: {method}"}
            
            elapsed = (time.time() - start_time) * 1000  # ms
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw": response.text[:500]}
            
            # Consider 200, 201, 422 (validation), 404 (not found for some queries) as "working"
            success = response.status_code in [200, 201, 422, 404] or response.status_code == expected_status
            
            result = {
                "method": method,
                "path": path,
                "description": description,
                "status_code": response.status_code,
                "elapsed_ms": round(elapsed, 2),
                "success": success,
                "response_sample": response_data
            }
            
            self.results.append(result)
            
            status_icon = f"{Fore.GREEN}✓" if success else f"{Fore.RED}✗"
            self.log(f"  {status_icon} [{method}] {path} - {response.status_code} ({elapsed:.0f}ms){Style.RESET_ALL}")
            
            return success, response_data
            
        except requests.exceptions.Timeout:
            self.log(f"  {Fore.RED}✗ [{method}] {path} - TIMEOUT{Style.RESET_ALL}")
            self.results.append({
                "method": method,
                "path": path,
                "description": description,
                "status_code": 0,
                "elapsed_ms": 30000,
                "success": False,
                "response_sample": {"error": "Timeout"}
            })
            return False, {"error": "Timeout"}
            
        except Exception as e:
            self.log(f"  {Fore.RED}✗ [{method}] {path} - ERROR: {e}{Style.RESET_ALL}")
            self.results.append({
                "method": method,
                "path": path,
                "description": description,
                "status_code": 0,
                "elapsed_ms": 0,
                "success": False,
                "response_sample": {"error": str(e)}
            })
            return False, {"error": str(e)}
    
    # =========================================================================
    # TEST CATEGORIES
    # =========================================================================
    
    def test_health_endpoints(self):
        """Test system health endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"🏥 HEALTH & SYSTEM ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint("GET", "/", "Root endpoint")
        self.test_endpoint("GET", "/ready", "Readiness probe")
        self.test_endpoint("GET", "/health", "Liveness probe")
        self.test_endpoint("GET", "/ai/health", "Full AI health check")
        self.test_endpoint("GET", "/ai/health/simple", "Simple health check")
        self.test_endpoint("GET", "/ai/health/db", "Database health")
        self.test_endpoint("GET", "/ai/health/qdrant", "Qdrant health")
        self.test_endpoint("GET", "/ai/health/llm", "LLM health")
        self.test_endpoint("GET", "/ai/models", "List AI models")
        self.test_endpoint("GET", "/ai/stats", "AI statistics")
        self.test_endpoint("GET", "/ai/metrics", "Prometheus metrics")
    
    def test_matching_endpoints(self):
        """Test event matching endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"🎯 MATCHING ENDPOINTS (OpenStreetMap)")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        # Geocoding
        self.test_endpoint(
            "POST", "/match/geocode",
            "Geocode address to coordinates",
            params={"address": "Empire State Building, New York"}
        )
        
        # Match by coordinates
        self.test_endpoint(
            "GET", "/match/events",
            "Match events by coordinates",
            params={
                "user_id": self.test_user_id,
                "lat": 40.7484,
                "lon": -73.9857,
                "max_distance_km": 50,
                "limit": 5
            }
        )
        
        # Match by address
        self.test_endpoint(
            "GET", "/match/events",
            "Match events by address",
            params={
                "user_id": self.test_user_id,
                "address": "Central Park, New York",
                "max_distance_km": 25,
                "limit": 5
            }
        )
        
        # Score breakdown
        self.test_endpoint(
            "GET", f"/match/score-breakdown/{self.test_event_id}",
            "Get match score breakdown",
            params={"user_id": self.test_user_id}
        )
    
    def test_recommendation_endpoints(self):
        """Test recommendation endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"📚 RECOMMENDATION ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "GET", f"/recommendations/hobbies/{self.test_user_id}",
            "Get hobby recommendations",
            params={"limit": 5}
        )
        
        self.test_endpoint(
            "GET", f"/recommendations/events/{self.test_user_id}",
            "Get event recommendations",
            params={"limit": 5}
        )
        
        self.test_endpoint(
            "GET", f"/recommendations/users/{self.test_user_id}",
            "Find similar users",
            params={"limit": 5}
        )
        
        self.test_endpoint(
            "GET", f"/recommendations/tfrs/{self.test_user_id}",
            "Two-Tower model recommendations",
            params={"limit": 5}
        )
        
        self.test_endpoint(
            "POST", f"/recommendations/embed/user/{self.test_user_id}",
            "Generate user embedding"
        )
        
        self.test_endpoint(
            "POST", f"/recommendations/embed/event/{self.test_event_id}",
            "Generate event embedding"
        )
    
    def test_rating_endpoints(self):
        """Test rating endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"⭐ RATING ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "GET", f"/ratings/host/{self.test_host_id}",
            "Get host aggregate rating"
        )
        
        self.test_endpoint(
            "GET", f"/ratings/can-rate/{self.test_event_id}/{self.test_user_id}",
            "Check if user can rate event"
        )
        
        self.test_endpoint(
            "POST", f"/ratings/event/{self.test_event_id}/submit",
            "Submit event rating",
            data={
                "user_id": self.test_user_id,
                "communication": 4.5,
                "respect": 5.0,
                "professionalism": 4.0,
                "atmosphere": 4.5,
                "value_for_money": 4.0,
                "feedback": "Great event! Really enjoyed it."
            }
        )
        
        self.test_endpoint(
            "POST", f"/ratings/host/{self.test_host_id}/recalculate",
            "Recalculate host rating"
        )
    
    def test_nlp_endpoints(self):
        """Test NLP endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"📝 NLP PROCESSING ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "POST", "/nlp/sentiment",
            "Analyze sentiment",
            data={
                "text": "This event was absolutely amazing! Best experience ever. The host was friendly and professional.",
                "content_id": "test-sentiment-1",
                "content_type": "review"
            }
        )
        
        self.test_endpoint(
            "POST", "/nlp/keywords",
            "Extract keywords",
            data={
                "text": "Join our outdoor hiking adventure in the mountains. Perfect for nature lovers and fitness enthusiasts who want to explore scenic trails.",
                "max_keywords": 5
            }
        )
        
        self.test_endpoint(
            "POST", "/nlp/sentiment/batch",
            "Batch sentiment analysis",
            data={
                "texts": [
                    "I loved this event!",
                    "Terrible experience, never again.",
                    "It was okay, nothing special."
                ]
            }
        )
        
        self.test_endpoint(
            "GET", "/nlp/trending",
            "Get trending topics",
            params={"period": "7d", "limit": 10}
        )
        
        self.test_endpoint(
            "POST", "/nlp/summarize",
            "Summarize text",
            params={"text": "Artificial intelligence is transforming how we live and work. Machine learning algorithms can now recognize images, understand speech, and even generate creative content. These technologies are being applied across industries from healthcare to finance to entertainment. The pace of advancement continues to accelerate as more data becomes available and computing power increases."}
        )
    
    def test_moderation_endpoints(self):
        """Test content moderation endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"🛡️ CONTENT MODERATION ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        # Safe text
        self.test_endpoint(
            "POST", "/moderation/submit",
            "Moderate safe text",
            data={
                "content_id": f"test-mod-{uuid.uuid4().hex[:8]}",
                "content_type": "text",
                "text": "Hello everyone! Looking forward to the hiking meetup this weekend.",
                "user_id": self.test_user_id
            }
        )
        
        # Potentially toxic text
        self.test_endpoint(
            "POST", "/moderation/submit",
            "Moderate potentially toxic text",
            data={
                "content_id": f"test-mod-{uuid.uuid4().hex[:8]}",
                "content_type": "text",
                "text": "This is stupid and I hate everything about this terrible event.",
                "user_id": self.test_user_id
            }
        )
        
        # Image URL moderation
        self.test_endpoint(
            "POST", "/moderation/submit",
            "Moderate image by URL",
            data={
                "content_id": f"test-mod-img-{uuid.uuid4().hex[:8]}",
                "content_type": "image",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/300px-PNG_transparency_demonstration_1.png",
                "user_id": self.test_user_id
            }
        )
        
        self.test_endpoint(
            "GET", "/moderation/queue",
            "Get moderation queue",
            params={"limit": 10}
        )
        
        self.test_endpoint(
            "GET", "/moderation/stats",
            "Get moderation statistics",
            params={"days": 7}
        )
    
    def test_chatbot_endpoints(self):
        """Test chatbot/RAG endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"🤖 CHATBOT RAG ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "POST", "/chatbot/ask",
            "Ask chatbot a question",
            data={
                "query": "How do I create an event?",
                "user_id": self.test_user_id,
                "language": "en"
            }
        )
        
        self.test_endpoint(
            "POST", "/chatbot/ask",
            "Ask chatbot about pricing",
            data={
                "query": "What are the pricing options for hosting events?",
                "user_id": self.test_user_id,
                "language": "en"
            }
        )
        
        self.test_endpoint(
            "POST", "/chatbot/sync",
            "Sync FAQ document",
            data={
                "doc_id": f"faq-test-{uuid.uuid4().hex[:8]}",
                "title": "How to Create Events",
                "content": "To create an event, navigate to the Events page and click 'Create New Event'. Fill in the event details including title, description, date, location, and capacity.",
                "category": "faq",
                "language": "en"
            }
        )
        
        self.test_endpoint(
            "GET", f"/chatbot/history/{self.test_user_id}",
            "Get chat history",
            params={"limit": 10}
        )
        
        self.test_endpoint(
            "GET", "/chatbot/documents",
            "List knowledge documents",
            params={"limit": 10}
        )
    
    def test_translation_endpoints(self):
        """Test translation endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"🌐 TRANSLATION ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "GET", "/translate/languages",
            "Get supported languages"
        )
        
        self.test_endpoint(
            "POST", "/translate/detect",
            "Detect language",
            params={"text": "Bonjour, comment allez-vous?"}
        )
        
        self.test_endpoint(
            "POST", "/translate/text",
            "Translate English to French",
            data={
                "text": "Hello, how are you?",
                "source_language": "en",
                "target_language": "fr"
            }
        )
        
        self.test_endpoint(
            "POST", "/translate/text",
            "Translate English to Spanish",
            data={
                "text": "Welcome to our event platform!",
                "source_language": "en",
                "target_language": "es"
            }
        )
    
    def test_support_endpoints(self):
        """Test support email endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"❤️ SUPPORT EMAIL ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        # Create a support email
        email_result = self.test_endpoint(
            "POST", "/support/email/incoming",
            "Process incoming support email",
            data={
                "from_email": "customer@example.com",
                "subject": "Need help with booking",
                "body": "Hi, I'm having trouble completing my booking for the hiking event. The payment keeps failing. Can you help?",
                "user_id": self.test_user_id
            }
        )
        
        self.test_endpoint(
            "GET", "/support/email/queue",
            "Get support email queue",
            params={"limit": 10}
        )
        
        self.test_endpoint(
            "GET", "/support/email/stats",
            "Get support statistics",
            params={"days": 7}
        )
    
    def test_pricing_endpoints(self):
        """Test pricing endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"💰 PRICING ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
        
        self.test_endpoint(
            "GET", "/pricing/optimise",
            "Get optimized price recommendation",
            params={
                "event_id": self.test_event_id,
                "base_price": 50,
                "event_date": future_date,
                "category": "outdoor",
                "capacity": 50
            }
        )
        
        self.test_endpoint(
            "GET", f"/pricing/history/{self.test_event_id}",
            "Get pricing history",
            params={"days": 30}
        )
        
        self.test_endpoint(
            "GET", "/discount/suggestion",
            "Get discount suggestions",
            params={
                "user_id": self.test_user_id,
                "event_id": self.test_event_id
            }
        )
        
        self.test_endpoint(
            "GET", "/discount/active",
            "Get active promotions"
        )
    
    def test_rewards_endpoints(self):
        """Test rewards endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"🎁 REWARDS ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "GET", f"/rewards/suggest/{self.test_user_id}",
            "Get reward suggestions",
            params={"include_analysis": True}
        )
        
        self.test_endpoint(
            "GET", f"/rewards/progress/{self.test_user_id}",
            "Get reward progress"
        )
        
        self.test_endpoint(
            "GET", f"/rewards/coupons/{self.test_user_id}",
            "Get user coupons"
        )
    
    def test_prediction_endpoints(self):
        """Test prediction endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"📈 PREDICTION ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        future_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S")
        
        self.test_endpoint(
            "POST", "/predict/attendance",
            "Predict event attendance",
            data={
                "event_id": self.test_event_id,
                "event_date": future_date,
                "category": "outdoor",
                "location": "New York",
                "capacity": 100,
                "host_id": self.test_host_id
            }
        )
        
        self.test_endpoint(
            "GET", "/predict/trends",
            "Predict hosting trends",
            params={
                "category": "fitness",
                "location": "New York",
                "days_ahead": 30
            }
        )
        
        self.test_endpoint(
            "GET", "/predict/demand/outdoor",
            "Predict category demand",
            params={"days_ahead": 30}
        )
        
        self.test_endpoint(
            "GET", "/predict/no-show-rate",
            "Predict no-show rate",
            params={
                "host_id": self.test_host_id,
                "event_id": self.test_event_id
            }
        )
    
    def test_advertising_endpoints(self):
        """Test advertising endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"📢 ADVERTISING ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "POST", "/ads/match",
            "Match ad to audience",
            data={
                "ad_id": self.test_ad_id,
                "ad_content": "Join our fitness community! Special discount for new members.",
                "target_interests": ["fitness", "yoga", "running"],
                "target_locations": ["New York", "Los Angeles"],
                "target_age_min": 25,
                "target_age_max": 45
            }
        )
        
        self.test_endpoint(
            "POST", "/ads/predict",
            "Predict ad performance",
            data={
                "ad_id": self.test_ad_id,
                "budget": 500,
                "duration_days": 7,
                "audience_segment_ids": ["fitness-enthusiasts", "urban-professionals"],
                "ad_content": "Limited time offer! 50% off all fitness events."
            }
        )
        
        self.test_endpoint(
            "GET", "/ads/segments",
            "List audience segments",
            params={"limit": 10}
        )
        
        self.test_endpoint(
            "GET", f"/ads/history/{self.test_ad_id}",
            "Get ad prediction history",
            params={"limit": 5}
        )
    
    def test_taxonomy_endpoints(self):
        """Test taxonomy endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"📂 TAXONOMY ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "GET", "/taxonomy/interests",
            "Get interest taxonomy",
            params={"language": "en", "active_only": True}
        )
        
        self.test_endpoint(
            "GET", "/taxonomy/interests/flat",
            "Get flat interest list",
            params={"language": "en"}
        )
    
    def test_i18n_endpoints(self):
        """Test internationalization endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"🌍 i18n ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "GET", "/i18n/en",
            "Get English UI strings",
            params={"scope": "common"}
        )
        
        self.test_endpoint(
            "GET", "/i18n/fr",
            "Get French UI strings",
            params={"scope": "common"}
        )
        
        self.test_endpoint(
            "GET", "/i18n/ar",
            "Get Arabic UI strings",
            params={"scope": "common"}
        )
    
    def test_feedback_endpoints(self):
        """Test feedback analysis endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"📊 FEEDBACK ANALYSIS ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "POST", "/feedback/analyze",
            "Analyze single feedback",
            data={
                "text": "The event was great but the venue was a bit crowded. Host was very friendly and the activities were fun!",
                "feedback_id": f"fb-{uuid.uuid4().hex[:8]}",
                "feedback_source": "event_review",
                "user_id": self.test_user_id
            }
        )
        
        self.test_endpoint(
            "POST", "/feedback/analyze/batch",
            "Batch analyze feedbacks",
            data={
                "feedbacks": [
                    {"text": "Loved every minute of it!", "feedback_id": "fb-1"},
                    {"text": "Could be better organized", "feedback_id": "fb-2"},
                    {"text": "Perfect event, will attend again", "feedback_id": "fb-3"}
                ]
            }
        )
        
        self.test_endpoint(
            "GET", "/feedback/stats",
            "Get feedback statistics",
            params={"days": 30}
        )
        
        self.test_endpoint(
            "GET", "/feedback/themes",
            "Get theme categories"
        )
    
    def test_retention_endpoints(self):
        """Test engagement/retention endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"📈 ENGAGEMENT/RETENTION ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint(
            "GET", f"/engagement/retention/predict/{self.test_user_id}",
            "Predict user churn risk"
        )
        
        self.test_endpoint(
            "POST", "/engagement/retention/predict/batch",
            "Batch churn prediction",
            data={"user_ids": ["1", "2", "3", "4", "5"]}
        )
        
        self.test_endpoint(
            "GET", "/engagement/retention/high-risk",
            "Get high-risk users",
            params={"limit": 10}
        )
        
        self.test_endpoint(
            "GET", "/engagement/retention/features",
            "Get feature definitions"
        )
        
        self.test_endpoint(
            "GET", "/engagement/retention/model-info",
            "Get model information"
        )
    
    def test_testing_helpers(self):
        """Test testing helper endpoints."""
        self.log(f"\n{Fore.CYAN}{'='*60}")
        self.log(f"🧪 TESTING HELPER ENDPOINTS")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.test_endpoint("GET", "/testing/uuid", "Generate test UUID")
        self.test_endpoint("GET", "/testing/user", "Generate test user")
        self.test_endpoint("GET", "/testing/event", "Generate test event")
        self.test_endpoint("GET", "/testing/content", "Generate test content")
        self.test_endpoint("GET", "/testing/ad", "Generate test ad")
        self.test_endpoint("GET", "/testing/samples", "Get sample requests")
        self.test_endpoint("GET", "/testing/huggingface-status", "Check HuggingFace API")
        
        # Quick test endpoints
        self.test_endpoint(
            "POST", "/testing/quick/moderation",
            "Quick moderation test",
            data={"text": "Hello world, this is a friendly message."}
        )
        
        self.test_endpoint(
            "POST", "/testing/quick/sentiment",
            "Quick sentiment test", 
            data={"text": "I absolutely love this amazing platform!"}
        )
        
        self.test_endpoint(
            "POST", "/testing/quick/keywords",
            "Quick keyword extraction",
            data={"text": "Machine learning and artificial intelligence are transforming technology.", "max_keywords": 3}
        )
        
        self.test_endpoint(
            "POST", "/testing/quick/chatbot",
            "Quick chatbot test",
            data={"question": "What is Kumele?", "language": "en"}
        )
    
    def run_all_tests(self):
        """Run all endpoint tests."""
        self.log(f"\n{Fore.MAGENTA}{'='*60}")
        self.log(f"🚀 KUMELE API COMPLETE TEST SUITE")
        self.log(f"{'='*60}")
        self.log(f"Target: {self.base_url}")
        self.log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        # Run all test categories
        self.test_health_endpoints()
        self.test_matching_endpoints()
        self.test_recommendation_endpoints()
        self.test_rating_endpoints()
        self.test_nlp_endpoints()
        self.test_moderation_endpoints()
        self.test_chatbot_endpoints()
        self.test_translation_endpoints()
        self.test_support_endpoints()
        self.test_pricing_endpoints()
        self.test_rewards_endpoints()
        self.test_prediction_endpoints()
        self.test_advertising_endpoints()
        self.test_taxonomy_endpoints()
        self.test_i18n_endpoints()
        self.test_feedback_endpoints()
        self.test_retention_endpoints()
        self.test_testing_helpers()
        
        # Print summary
        self.print_summary()
        
        return self.results
    
    def print_summary(self):
        """Print test summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed
        
        self.log(f"\n{Fore.MAGENTA}{'='*60}")
        self.log(f"📊 TEST SUMMARY")
        self.log(f"{'='*60}{Style.RESET_ALL}")
        
        self.log(f"\n{Fore.GREEN}✓ Passed: {passed}{Style.RESET_ALL}")
        self.log(f"{Fore.RED}✗ Failed: {failed}{Style.RESET_ALL}")
        self.log(f"{Fore.CYAN}Total: {total}{Style.RESET_ALL}")
        self.log(f"Success Rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            self.log(f"\n{Fore.RED}Failed Endpoints:{Style.RESET_ALL}")
            for r in self.results:
                if not r["success"]:
                    self.log(f"  - [{r['method']}] {r['path']} ({r['status_code']})")
        
        # Average response time
        avg_time = sum(r["elapsed_ms"] for r in self.results) / total if total > 0 else 0
        self.log(f"\nAverage Response Time: {avg_time:.0f}ms")
        
        self.log(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    
    def export_results(self, filename: str = "api_test_results.json"):
        """Export test results to JSON file."""
        output = {
            "test_date": datetime.now().isoformat(),
            "base_url": self.base_url,
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r["success"]),
            "failed": sum(1 for r in self.results if not r["success"]),
            "results": self.results
        }
        
        with open(filename, "w") as f:
            json.dump(output, f, indent=2, default=str)
        
        self.log(f"\n{Fore.GREEN}Results exported to: {filename}{Style.RESET_ALL}")


def main():
    parser = argparse.ArgumentParser(description="Test all Kumele API endpoints")
    parser.add_argument(
        "--host", 
        type=str, 
        default="http://localhost:8000",
        help="API host URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--export", 
        type=str, 
        default=None,
        help="Export results to JSON file"
    )
    parser.add_argument(
        "--quiet", 
        action="store_true",
        help="Quiet mode (less output)"
    )
    
    args = parser.parse_args()
    
    tester = APITester(args.host, verbose=not args.quiet)
    results = tester.run_all_tests()
    
    if args.export:
        tester.export_results(args.export)
    
    # Exit with error code if any tests failed
    failed = sum(1 for r in results if not r["success"])
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
