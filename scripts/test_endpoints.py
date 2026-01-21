#!/usr/bin/env python3
"""
API Endpoint Testing Script

Automated testing of all Kumele API endpoints after deployment.

Usage:
    python scripts/test_endpoints.py
    python scripts/test_endpoints.py --base-url http://your-server:8000
    python scripts/test_endpoints.py --verbose
"""
import argparse
import json
import sys
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("Please install requests: pip install requests")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def log_success(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def log_error(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def log_warning(msg):
    print(f"{Colors.YELLOW}!{Colors.RESET} {msg}")


def log_info(msg):
    print(f"{Colors.BLUE}→{Colors.RESET} {msg}")


class APITester:
    def __init__(self, base_url: str, verbose: bool = False):
        self.base_url = base_url.rstrip('/')
        self.verbose = verbose
        self.results = {"passed": 0, "failed": 0, "warnings": 0}
    
    def request(self, method: str, endpoint: str, **kwargs):
        """Make HTTP request and return response"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = getattr(requests, method.lower())(url, timeout=30, **kwargs)
            if self.verbose:
                print(f"    Response [{response.status_code}]: {response.text[:200]}...")
            return response
        except Exception as e:
            return None
    
    def test_endpoint(self, name: str, method: str, endpoint: str, expected_status=200, **kwargs):
        """Test a single endpoint"""
        if self.verbose:
            log_info(f"Testing: {method.upper()} {endpoint}")
        
        response = self.request(method, endpoint, **kwargs)
        
        if response is None:
            log_error(f"{name}: Connection failed")
            self.results["failed"] += 1
            return False
        
        # Check status code
        if isinstance(expected_status, (list, tuple)):
            status_ok = response.status_code in expected_status
        else:
            status_ok = response.status_code == expected_status
        
        if status_ok:
            log_success(f"{name} [{response.status_code}]")
            self.results["passed"] += 1
            return True
        else:
            log_error(f"{name} - Expected {expected_status}, got {response.status_code}")
            if self.verbose:
                print(f"    Response: {response.text[:500]}")
            self.results["failed"] += 1
            return False
    
    def run_tests(self):
        """Run all endpoint tests"""
        print("\n" + "=" * 60)
        print("Kumele API Endpoint Tests")
        print("=" * 60)
        print(f"Base URL: {self.base_url}")
        print()
        
        # =================================================================
        # 1. Health & Root
        # =================================================================
        print("\n--- Health & Root ---")
        self.test_endpoint("Root endpoint", "GET", "/")
        self.test_endpoint("Health check", "GET", "/health")
        
        # =================================================================
        # 2. Check-in API
        # =================================================================
        print("\n--- Check-in API ---")
        
        self.test_endpoint("Validate check-in", "POST", "/checkin/validate", 
            expected_status=[200, 400, 404],
            json={
                "event_id": 1,
                "user_id": 1,
                "mode": "self_check",
                "user_latitude": 40.7128,
                "user_longitude": -74.0060
            })
        
        self.test_endpoint("Verify check-in", "POST", "/checkin/verify",
            expected_status=[200, 400, 404],
            json={
                "event_id": 1,
                "user_id": 1,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "device_hash": "test123"
            })
        
        self.test_endpoint("Fraud detect", "POST", "/checkin/fraud-detect",
            expected_status=[200, 400, 404],
            json={
                "event_id": 1,
                "user_id": 1,
                "device_hash": "test123",
                "latitude": 40.7128,
                "longitude": -74.0060
            })
        
        self.test_endpoint("Host compliance", "GET", "/checkin/host/1/compliance",
            expected_status=[200, 404])
        
        # =================================================================
        # 2.5. QR Code API
        # =================================================================
        print("\n--- QR Code API ---")
        
        # Generate QR code
        qr_response = self.request("POST", "/checkin/qr/generate", json={
            "user_id": 1,
            "event_id": 1,
            "validity_minutes": 30
        })
        qr_token = None
        if qr_response and qr_response.status_code == 200:
            log_success("Generate QR code [200]")
            self.results["passed"] += 1
            try:
                qr_token = qr_response.json().get("qr_token")
            except:
                pass
        else:
            status = qr_response.status_code if qr_response else "N/A"
            if status in [400, 404]:
                log_warning(f"Generate QR code [{status}] - User/Event not found (expected)")
                self.results["passed"] += 1
            else:
                log_error(f"Generate QR code - Got {status}")
                self.results["failed"] += 1
        
        # Test other QR endpoints with token or placeholder
        test_token = qr_token or "test_token_placeholder"
        
        self.test_endpoint("Validate QR token", "GET", f"/checkin/qr/{test_token}",
            expected_status=[200, 404])
        
        self.test_endpoint("Get user active QRs", "GET", "/checkin/qr/user/1/active",
            expected_status=[200])
        
        self.test_endpoint("Refresh QR code", "POST", "/checkin/qr/refresh",
            expected_status=[200, 400, 404],
            json={
                "user_id": 1,
                "event_id": 1,
                "validity_minutes": 60
            })
        
        self.test_endpoint("Batch generate QR", "POST", "/checkin/qr/batch",
            expected_status=[200, 400, 404],
            json={
                "event_id": 1,
                "user_ids": [1, 2, 3],
                "validity_minutes": 60
            })
        
        # =================================================================
        # 3. NFT Badge API
        # =================================================================
        print("\n--- NFT Badge API ---")
        
        self.test_endpoint("Badge eligibility", "GET", "/nft/badge/eligibility/1",
            expected_status=[200, 404])
        
        self.test_endpoint("Issue badge", "POST", "/nft/badge/issue",
            expected_status=[200, 400, 404],
            json={"user_id": 1})
        
        self.test_endpoint("User badges", "GET", "/nft/badge/user/1",
            expected_status=[200, 404])
        
        self.test_endpoint("Badge history", "GET", "/nft/badge/history/1",
            expected_status=[200, 404])
        
        self.test_endpoint("Trust score", "GET", "/nft/trust-score/1",
            expected_status=[200, 404])
        
        self.test_endpoint("Host priority", "GET", "/nft/host-priority/1",
            expected_status=[200, 404])
        
        self.test_endpoint("Discount eligibility", "GET", "/nft/discount-eligibility/1",
            expected_status=[200, 404])
        
        self.test_endpoint("Payment reliability", "GET", "/nft/payment-reliability/1",
            expected_status=[200, 404])
        
        self.test_endpoint("Event ranking boost", "GET", "/nft/event-ranking-boost/1",
            expected_status=[200, 404])
        
        # =================================================================
        # 4. Chat API
        # =================================================================
        print("\n--- Chat API ---")
        
        self.test_endpoint("List chat rooms", "GET", "/chat/rooms",
            expected_status=[200])
        
        self.test_endpoint("Create chat room", "POST", "/chat/rooms",
            expected_status=[200, 400, 404],
            json={"event_id": 1, "chat_type": "event"})
        
        self.test_endpoint("Get chat room", "GET", "/chat/rooms/1",
            expected_status=[200, 404])
        
        self.test_endpoint("Get chat messages", "GET", "/chat/rooms/1/messages",
            expected_status=[200, 404])
        
        self.test_endpoint("Chat popularity", "GET", "/chat/rooms/1/popularity",
            expected_status=[200, 404])
        
        self.test_endpoint("Chat sentiment", "GET", "/chat/rooms/1/sentiment",
            expected_status=[200, 404])
        
        self.test_endpoint("Moderation stats", "GET", "/chat/rooms/1/moderation-stats",
            expected_status=[200, 404])
        
        # =================================================================
        # 5. Matching API
        # =================================================================
        print("\n--- Matching API ---")
        
        self.test_endpoint("Match events", "GET", "/match/events?user_id=1",
            expected_status=[200, 400, 404])
        
        self.test_endpoint("Match events with filters", "GET", 
            "/match/events?user_id=1&min_age=18&max_age=40&verified_hosts_only=true",
            expected_status=[200, 400, 404])
        
        self.test_endpoint("Events with capacity", "GET", "/match/events/with-capacity?user_id=1",
            expected_status=[200, 400, 404])
        
        self.test_endpoint("Events by host reputation", "GET", "/match/events/by-host-reputation?user_id=1",
            expected_status=[200, 400, 404])
        
        # =================================================================
        # 6. Payment API
        # =================================================================
        print("\n--- Payment API ---")
        
        self.test_endpoint("Create payment window", "POST", "/payment/window/create",
            expected_status=[200, 400, 404, 422],
            json={
                "user_id": 1,
                "event_id": 1,
                "amount": 25.00,
                "window_minutes": 15
            })
        
        self.test_endpoint("Get payment window", "GET", "/payment/window/1",
            expected_status=[200, 404])
        
        self.test_endpoint("Event urgency", "GET", "/payment/urgency/event/1",
            expected_status=[200, 404])
        
        # =================================================================
        # 7. Predictions API
        # =================================================================
        print("\n--- Predictions API ---")
        
        self.test_endpoint("Predict attendance", "POST", "/predict/attendance",
            expected_status=[200, 400, 422],
            json={
                "hobby": "hiking",
                "location": "New York",
                "date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "is_paid": False,
                "host_experience": 5,
                "host_rating": 4.5,
                "capacity": 20
            })
        
        self.test_endpoint("Predict no-show", "GET", "/predict/noshow/1",
            expected_status=[200, 404])
        
        # =================================================================
        # 8. Moderation API
        # =================================================================
        print("\n--- Moderation API ---")
        
        self.test_endpoint("Moderate text", "POST", "/moderation/text",
            expected_status=[200, 400, 422],
            json={
                "text": "Hello world!",
                "context": "chat_message"
            })
        
        self.test_endpoint("Moderate image", "POST", "/moderation/image",
            expected_status=[200, 400, 422],
            json={
                "image_url": "https://example.com/image.jpg",
                "context": "profile_photo"
            })
        
        # =================================================================
        # 9. Pricing API
        # =================================================================
        print("\n--- Pricing API ---")
        
        self.test_endpoint("Dynamic pricing", "GET", "/pricing/event/1",
            expected_status=[200, 404])
        
        # =================================================================
        # 10. Fraud API
        # =================================================================
        print("\n--- Fraud API ---")
        
        self.test_endpoint("Fraud signals", "GET", "/fraud/signals/1",
            expected_status=[200, 404])
        
        # =================================================================
        # 11. Referral API
        # =================================================================
        print("\n--- Referral API ---")
        
        self.test_endpoint("User referrals", "GET", "/referrals/user/1",
            expected_status=[200, 404])
        
        # =================================================================
        # 12. Rewards API
        # =================================================================
        print("\n--- Rewards API ---")
        
        self.test_endpoint("User rewards", "GET", "/rewards/user/1",
            expected_status=[200, 404])
        
        self.test_endpoint("User coupons", "GET", "/rewards/coupons/1",
            expected_status=[200, 404])
        
        # =================================================================
        # 13. Support API
        # =================================================================
        print("\n--- Support API ---")
        
        self.test_endpoint("Chatbot query", "POST", "/support/chatbot/query",
            expected_status=[200, 400, 422],
            json={
                "user_id": 1,
                "query": "How do I create an event?"
            })
        
        # =================================================================
        # 14. Interests API
        # =================================================================
        print("\n--- Interests API ---")
        
        self.test_endpoint("List interests", "GET", "/interests/",
            expected_status=[200])
        
        self.test_endpoint("Get interest", "GET", "/interests/1",
            expected_status=[200, 404])
        
        # =================================================================
        # Summary
        # =================================================================
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"  {Colors.GREEN}Passed: {self.results['passed']}{Colors.RESET}")
        print(f"  {Colors.RED}Failed: {self.results['failed']}{Colors.RESET}")
        total = self.results['passed'] + self.results['failed']
        if total > 0:
            pct = (self.results['passed'] / total) * 100
            print(f"  Success Rate: {pct:.1f}%")
        print()
        
        return self.results['failed'] == 0


def main():
    parser = argparse.ArgumentParser(description="Test Kumele API endpoints")
    parser.add_argument("--base-url", default="http://localhost:8000",
                       help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed output")
    
    args = parser.parse_args()
    
    tester = APITester(args.base_url, verbose=args.verbose)
    success = tester.run_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
