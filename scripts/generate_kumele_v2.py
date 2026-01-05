#!/usr/bin/env python3
"""
Kumele Synthetic Data Generator V2
===================================

Generates comprehensive synthetic dataset for the Kumele platform.

Usage:
------
python generate_kumele_v2.py --users 1000 --events 500 --months 6

CLI Arguments:
--------------
--users         Number of users to generate (default: 1000)
--events        Number of events to generate (default: 500)
--months        Months of historical data (default: 6)
--output-dir    Output directory (default: ./synthetic_data)
--seed          Random seed for reproducibility (default: 42)

Output Files:
-------------
- users.csv                 User profiles with demographics
- hobbies.csv               Hobby/interest taxonomy
- user_hobbies.csv          User-hobby relationships with preference scores
- events.csv                Event listings with all metadata
- user_events.csv           Event attendance/RSVP records
- blogs.csv                 Blog/article content
- blog_interactions.csv     User-blog interaction logs
- ads.csv                   Advertisement listings
- ad_interactions.csv       Ad click/conversion tracking
- user_wallets.csv          Solana wallet connections
- user_nfts.csv             NFT ownership records
- reward_coupons.csv        Reward/coupon redemptions
- timeseries_daily.csv      Daily aggregated metrics
- timeseries_hourly.csv     Hourly activity patterns
- embeddings_qdrant.json    Pre-computed embeddings for Qdrant import
- manifest.json             Dataset metadata and statistics
- README.md                 Dataset documentation

Author: Kumele AI Team
Version: 2.0
"""

import argparse
import csv
import json
import os
import random
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import math

# ==============================================================================
# CONSTANTS & CONFIGURATION
# ==============================================================================

HOBBIES = [
    # Fitness & Sports
    ("fitness", "Fitness & Gym", "sports"),
    ("yoga", "Yoga & Meditation", "wellness"),
    ("running", "Running & Jogging", "sports"),
    ("cycling", "Cycling", "sports"),
    ("swimming", "Swimming", "sports"),
    ("basketball", "Basketball", "sports"),
    ("football", "Football/Soccer", "sports"),
    ("tennis", "Tennis", "sports"),
    ("golf", "Golf", "sports"),
    ("martial_arts", "Martial Arts", "sports"),
    ("hiking", "Hiking & Trekking", "outdoor"),
    ("climbing", "Rock Climbing", "outdoor"),
    ("camping", "Camping", "outdoor"),
    ("skiing", "Skiing & Snowboarding", "outdoor"),
    ("surfing", "Surfing", "outdoor"),
    
    # Arts & Creative
    ("painting", "Painting & Drawing", "arts"),
    ("photography", "Photography", "arts"),
    ("music", "Music & Instruments", "arts"),
    ("dance", "Dance", "arts"),
    ("theater", "Theater & Drama", "arts"),
    ("crafts", "Arts & Crafts", "arts"),
    ("writing", "Creative Writing", "arts"),
    ("pottery", "Pottery & Ceramics", "arts"),
    
    # Food & Drinks
    ("cooking", "Cooking & Culinary", "food"),
    ("baking", "Baking", "food"),
    ("wine", "Wine Tasting", "food"),
    ("coffee", "Coffee & Barista", "food"),
    ("vegan", "Vegan & Plant-Based", "food"),
    
    # Technology
    ("coding", "Programming & Coding", "tech"),
    ("gaming", "Video Gaming", "tech"),
    ("ai_ml", "AI & Machine Learning", "tech"),
    ("blockchain", "Blockchain & Web3", "tech"),
    ("robotics", "Robotics", "tech"),
    
    # Social & Networking
    ("networking", "Professional Networking", "social"),
    ("volunteering", "Volunteering", "social"),
    ("languages", "Language Learning", "education"),
    ("book_club", "Book Clubs", "education"),
    ("mentoring", "Mentoring", "social"),
    
    # Wellness
    ("meditation", "Meditation & Mindfulness", "wellness"),
    ("spa", "Spa & Self-Care", "wellness"),
]

LOCATIONS = [
    {"city": "New York", "country": "USA", "lat": 40.7128, "lng": -74.0060, "timezone": "America/New_York"},
    {"city": "Los Angeles", "country": "USA", "lat": 34.0522, "lng": -118.2437, "timezone": "America/Los_Angeles"},
    {"city": "London", "country": "UK", "lat": 51.5074, "lng": -0.1278, "timezone": "Europe/London"},
    {"city": "Paris", "country": "France", "lat": 48.8566, "lng": 2.3522, "timezone": "Europe/Paris"},
    {"city": "Berlin", "country": "Germany", "lat": 52.5200, "lng": 13.4050, "timezone": "Europe/Berlin"},
    {"city": "Tokyo", "country": "Japan", "lat": 35.6762, "lng": 139.6503, "timezone": "Asia/Tokyo"},
    {"city": "Sydney", "country": "Australia", "lat": -33.8688, "lng": 151.2093, "timezone": "Australia/Sydney"},
    {"city": "Dubai", "country": "UAE", "lat": 25.2048, "lng": 55.2708, "timezone": "Asia/Dubai"},
    {"city": "Singapore", "country": "Singapore", "lat": 1.3521, "lng": 103.8198, "timezone": "Asia/Singapore"},
    {"city": "Toronto", "country": "Canada", "lat": 43.6532, "lng": -79.3832, "timezone": "America/Toronto"},
    {"city": "Amsterdam", "country": "Netherlands", "lat": 52.3676, "lng": 4.9041, "timezone": "Europe/Amsterdam"},
    {"city": "Barcelona", "country": "Spain", "lat": 41.3851, "lng": 2.1734, "timezone": "Europe/Madrid"},
]

FIRST_NAMES = [
    "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason",
    "Isabella", "William", "Mia", "James", "Charlotte", "Benjamin", "Amelia",
    "Lucas", "Harper", "Henry", "Evelyn", "Alexander", "Sakura", "Yuki",
    "Wei", "Chen", "Ahmed", "Fatima", "Mohammed", "Priya", "Raj", "Aiko",
    "Carlos", "Maria", "Jean", "Pierre", "Hans", "Greta", "Giovanni", "Lucia"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Wilson", "Anderson", "Taylor", "Thomas",
    "Moore", "Jackson", "Martin", "Lee", "Thompson", "White", "Tanaka", "Yamamoto",
    "Wang", "Li", "Kumar", "Patel", "Khan", "Singh", "Müller", "Schmidt"
]

EVENT_TITLES = {
    "sports": [
        "Morning Yoga in the Park",
        "5K Charity Run",
        "Beach Volleyball Tournament",
        "Beginner Tennis Clinic",
        "Hiking Adventure: Mountain Trail",
        "CrossFit Challenge",
        "Basketball Pickup Game",
        "Swimming Lessons for Adults",
    ],
    "arts": [
        "Watercolor Workshop",
        "Photography Walk: Urban Landscapes",
        "Live Jazz Night",
        "Dance Salsa: Beginner Class",
        "Open Mic Poetry Night",
        "Art Gallery Tour",
        "Film Screening & Discussion",
        "Pottery Making Workshop",
    ],
    "food": [
        "Italian Cooking Class",
        "Wine Tasting Evening",
        "Coffee Cupping Session",
        "Vegan Brunch Meetup",
        "Farmers Market Tour",
        "Cocktail Making Workshop",
        "Sushi Rolling Class",
        "BBQ Masterclass",
    ],
    "tech": [
        "Python Programming Workshop",
        "AI/ML Hackathon",
        "Web3 & Blockchain Talk",
        "Gaming Tournament: Esports",
        "Tech Startup Pitch Night",
        "Robotics Demo Day",
        "Data Science Meetup",
        "Cybersecurity Workshop",
    ],
    "social": [
        "Professional Networking Mixer",
        "Book Club: Monthly Discussion",
        "Language Exchange Café",
        "Volunteer Day: Beach Cleanup",
        "Speed Friending Event",
        "Community Potluck",
        "Charity Fundraiser Gala",
        "Mentorship Kickoff",
    ],
    "wellness": [
        "Meditation & Mindfulness Session",
        "Spa Day Retreat",
        "Sound Healing Workshop",
        "Stress Management Seminar",
        "Breathwork Class",
        "Digital Detox Weekend",
        "Wellness Retreat",
        "Sleep Optimization Talk",
    ],
}

BLOG_TITLES = [
    "Top 10 Tips for Meeting New People at Events",
    "How to Find Your Perfect Hobby Match",
    "The Art of Networking: A Complete Guide",
    "Why Community Matters in the Digital Age",
    "Building Meaningful Connections Through Shared Interests",
    "The Science of Social Bonding",
    "Local Events vs Online Meetups: Pros and Cons",
    "How to Host Your First Community Event",
    "Finding Balance: Work, Life, and Hobbies",
    "The Benefits of Trying New Things",
]

AD_TYPES = ["banner", "sponsored_event", "promoted_host", "native"]
AD_CATEGORIES = ["fitness", "food", "tech", "travel", "lifestyle", "education"]

REWARD_TIERS = ["none", "bronze", "silver", "gold"]
MODERATION_STATUSES = ["pending", "approved", "rejected"]

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def generate_bigint_id() -> int:
    """Generate a BigInt ID (like from external platform)."""
    return random.randint(1_000_000_000_000, 9_999_999_999_999)

def generate_uuid() -> str:
    """Generate a UUID-like string."""
    return hashlib.md5(str(random.random()).encode()).hexdigest()[:32]

def random_date(start: datetime, end: datetime) -> datetime:
    """Generate random datetime between start and end."""
    delta = end - start
    random_days = random.randint(0, delta.days)
    random_seconds = random.randint(0, 86400)
    return start + timedelta(days=random_days, seconds=random_seconds)

def generate_solana_address() -> str:
    """Generate a realistic Solana wallet address (base58)."""
    chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return ''.join(random.choices(chars, k=44))

def hash_to_embedding(text: str, dim: int = 128) -> List[float]:
    """Generate deterministic embedding from text."""
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    embedding = []
    for i in range(dim):
        char_idx = i % len(text_hash)
        value = (int(text_hash[char_idx], 16) - 8) / 8.0
        embedding.append(round(value, 4))
    # Normalize
    norm = math.sqrt(sum(v*v for v in embedding))
    if norm > 0:
        embedding = [round(v/norm, 4) for v in embedding]
    return embedding

# ==============================================================================
# DATA GENERATORS
# ==============================================================================

def generate_users(num_users: int, seed: int) -> List[Dict]:
    """Generate user profiles."""
    random.seed(seed)
    users = []
    
    for i in range(num_users):
        location = random.choice(LOCATIONS)
        age = random.choices(
            [random.randint(18, 25), random.randint(26, 35), random.randint(36, 50), random.randint(51, 70)],
            weights=[0.25, 0.40, 0.25, 0.10]
        )[0]
        gender = random.choice(["male", "female", "non-binary", "prefer_not_to_say"])
        
        # Reward tier distribution: 70% none, 15% bronze, 10% silver, 5% gold
        reward_tier = random.choices(
            REWARD_TIERS,
            weights=[0.70, 0.15, 0.10, 0.05]
        )[0]
        
        # User radius preference
        radius_km = random.choices(
            [5, 10, 25, 50, 100],
            weights=[0.10, 0.35, 0.35, 0.15, 0.05]
        )[0]
        
        users.append({
            "user_id": generate_bigint_id(),
            "email": f"user{i+1}@kumele-test.com",
            "name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "age": age,
            "gender": gender,
            "city": location["city"],
            "country": location["country"],
            "latitude": location["lat"] + random.uniform(-0.1, 0.1),
            "longitude": location["lng"] + random.uniform(-0.1, 0.1),
            "radius_km": radius_km,
            "reward_tier": reward_tier,
            "reputation_score": round(random.uniform(3.0, 5.0), 2),
            "created_at": random_date(datetime(2023, 1, 1), datetime(2024, 1, 1)).isoformat(),
            "is_active": random.random() > 0.1,  # 90% active
        })
    
    return users

def generate_hobbies() -> List[Dict]:
    """Generate hobby taxonomy."""
    hobbies = []
    for i, (hobby_id, hobby_name, category) in enumerate(HOBBIES):
        hobbies.append({
            "hobby_id": i + 1,
            "hobby_code": hobby_id,
            "hobby_name": hobby_name,
            "category": category,
            "description": f"Community for {hobby_name.lower()} enthusiasts",
            "popularity_score": round(random.uniform(0.3, 1.0), 2),
        })
    return hobbies

def generate_user_hobbies(users: List[Dict], hobbies: List[Dict], seed: int) -> List[Dict]:
    """Generate user-hobby relationships."""
    random.seed(seed + 1)
    user_hobbies = []
    
    for user in users:
        # Each user has 2-8 hobbies
        num_hobbies = random.randint(2, 8)
        selected_hobbies = random.sample(hobbies, min(num_hobbies, len(hobbies)))
        
        for hobby in selected_hobbies:
            user_hobbies.append({
                "user_id": user["user_id"],
                "hobby_id": hobby["hobby_id"],
                "preference_score": round(random.uniform(0.3, 1.0), 2),
                "skill_level": random.choice(["beginner", "intermediate", "advanced", "expert"]),
                "years_experience": random.randint(0, 20),
                "created_at": user["created_at"],
            })
    
    return user_hobbies

def generate_events(
    num_events: int,
    users: List[Dict],
    hobbies: List[Dict],
    start_date: datetime,
    end_date: datetime,
    seed: int
) -> List[Dict]:
    """Generate event listings."""
    random.seed(seed + 2)
    events = []
    
    # Select ~20% of users as hosts
    potential_hosts = random.sample(users, max(10, len(users) // 5))
    
    for i in range(num_events):
        host = random.choice(potential_hosts)
        hobby = random.choice(hobbies)
        category = hobby["category"]
        location = random.choice(LOCATIONS)
        
        # Event title
        titles = EVENT_TITLES.get(category, EVENT_TITLES["social"])
        title = random.choice(titles)
        
        # Event date (future events and past events)
        if random.random() > 0.3:
            event_date = random_date(datetime.now(), end_date)  # Future
        else:
            event_date = random_date(start_date, datetime.now())  # Past
        
        # Price distribution
        price = random.choices(
            [0, random.uniform(5, 25), random.uniform(25, 75), random.uniform(75, 200)],
            weights=[0.30, 0.35, 0.25, 0.10]
        )[0]
        
        # Capacity
        capacity = random.choices(
            [10, 20, 50, 100, 500],
            weights=[0.20, 0.35, 0.25, 0.15, 0.05]
        )[0]
        
        events.append({
            "event_id": i + 1,
            "host_id": host["user_id"],
            "title": title,
            "description": f"Join us for an amazing {hobby['hobby_name'].lower()} experience in {location['city']}!",
            "category": category,
            "hobby_id": hobby["hobby_id"],
            "event_date": event_date.isoformat(),
            "duration_minutes": random.choice([60, 90, 120, 180, 240]),
            "city": location["city"],
            "country": location["country"],
            "latitude": location["lat"] + random.uniform(-0.05, 0.05),
            "longitude": location["lng"] + random.uniform(-0.05, 0.05),
            "venue_name": f"{random.choice(['The', 'Downtown', 'Central', 'City'])} {random.choice(['Studio', 'Center', 'Hub', 'Space', 'Park'])}",
            "price": round(price, 2),
            "currency": "USD",
            "capacity": capacity,
            "status": random.choices(["active", "scheduled", "completed", "cancelled"], weights=[0.40, 0.30, 0.25, 0.05])[0],
            "moderation_status": random.choices(MODERATION_STATUSES, weights=[0.10, 0.85, 0.05])[0],
            "language": random.choices(["en", "es", "fr", "de", "zh"], weights=[0.60, 0.15, 0.10, 0.10, 0.05])[0],
            "has_discount": random.random() > 0.8,
            "is_sponsored": random.random() > 0.9,
            "tags": ",".join(random.sample([hobby["hobby_code"], category, location["city"].lower(), "featured", "popular"], k=random.randint(2, 4))),
            "created_at": random_date(start_date, event_date).isoformat(),
        })
    
    return events

def generate_user_events(
    users: List[Dict],
    events: List[Dict],
    seed: int
) -> List[Dict]:
    """Generate user-event attendance records."""
    random.seed(seed + 3)
    user_events = []
    
    for event in events:
        # Each event has 5-80% capacity attendance
        num_attendees = random.randint(2, max(3, int(event["capacity"] * random.uniform(0.05, 0.80))))
        attendees = random.sample(users, min(num_attendees, len(users)))
        
        for user in attendees:
            if user["user_id"] == event["host_id"]:
                continue
            
            rsvp_date = random_date(
                datetime.fromisoformat(event["created_at"]),
                datetime.fromisoformat(event["event_date"])
            )
            
            checked_in = event["status"] == "completed" and random.random() > 0.2
            
            user_events.append({
                "user_id": user["user_id"],
                "event_id": event["event_id"],
                "rsvp_status": random.choices(["going", "interested", "not_going"], weights=[0.70, 0.20, 0.10])[0],
                "rsvp_date": rsvp_date.isoformat(),
                "checked_in": checked_in,
                "check_in_time": (datetime.fromisoformat(event["event_date"]) + timedelta(minutes=random.randint(-10, 30))).isoformat() if checked_in else None,
                "rating": random.randint(3, 5) if checked_in else None,
                "review": "Great event!" if checked_in and random.random() > 0.7 else None,
            })
    
    return user_events

def generate_blogs(num_blogs: int, users: List[Dict], seed: int) -> List[Dict]:
    """Generate blog posts."""
    random.seed(seed + 4)
    blogs = []
    
    authors = random.sample(users, min(num_blogs // 5, len(users)))
    
    for i in range(num_blogs):
        author = random.choice(authors)
        
        blogs.append({
            "blog_id": i + 1,
            "author_id": author["user_id"],
            "title": random.choice(BLOG_TITLES) + f" - Part {random.randint(1, 5)}",
            "slug": f"blog-post-{i+1}",
            "content": f"This is sample blog content #{i+1}. " * random.randint(50, 200),
            "category": random.choice(["lifestyle", "tips", "community", "events", "wellness", "tech"]),
            "tags": ",".join(random.sample(["featured", "popular", "trending", "how-to", "guide", "tips"], k=random.randint(2, 4))),
            "status": random.choices(["draft", "published", "archived"], weights=[0.10, 0.85, 0.05])[0],
            "views_count": random.randint(10, 5000),
            "likes_count": random.randint(0, 500),
            "created_at": random_date(datetime(2023, 6, 1), datetime.now()).isoformat(),
            "published_at": random_date(datetime(2023, 6, 1), datetime.now()).isoformat(),
        })
    
    return blogs

def generate_blog_interactions(
    users: List[Dict],
    blogs: List[Dict],
    seed: int
) -> List[Dict]:
    """Generate blog interaction logs."""
    random.seed(seed + 5)
    interactions = []
    
    for blog in blogs:
        # Each blog has various interactions
        num_interactions = random.randint(5, min(100, len(users)))
        interacting_users = random.sample(users, num_interactions)
        
        for user in interacting_users:
            interaction_type = random.choices(
                ["view", "like", "bookmark", "share", "comment"],
                weights=[0.50, 0.25, 0.10, 0.05, 0.10]
            )[0]
            
            interactions.append({
                "interaction_id": len(interactions) + 1,
                "user_id": user["user_id"],
                "blog_id": blog["blog_id"],
                "interaction_type": interaction_type,
                "created_at": random_date(
                    datetime.fromisoformat(blog["created_at"]),
                    datetime.now()
                ).isoformat(),
            })
    
    return interactions

def generate_ads(num_ads: int, seed: int) -> List[Dict]:
    """Generate advertisement listings."""
    random.seed(seed + 6)
    ads = []
    
    for i in range(num_ads):
        ads.append({
            "ad_id": i + 1,
            "advertiser_name": f"Advertiser {i+1}",
            "ad_type": random.choice(AD_TYPES),
            "category": random.choice(AD_CATEGORIES),
            "title": f"Special Offer from Partner {i+1}",
            "description": f"Check out our amazing offer for Kumele users!",
            "target_url": f"https://partner{i+1}.example.com/offer",
            "image_url": f"https://cdn.kumele.com/ads/ad_{i+1}.jpg",
            "budget": round(random.uniform(100, 10000), 2),
            "cpm": round(random.uniform(1, 10), 2),
            "cpc": round(random.uniform(0.10, 2.00), 2),
            "impressions": random.randint(1000, 100000),
            "clicks": random.randint(10, 5000),
            "conversions": random.randint(0, 500),
            "status": random.choices(["active", "paused", "completed"], weights=[0.60, 0.20, 0.20])[0],
            "start_date": random_date(datetime(2023, 6, 1), datetime.now()).isoformat(),
            "end_date": random_date(datetime.now(), datetime(2025, 1, 1)).isoformat(),
        })
    
    return ads

def generate_ad_interactions(
    users: List[Dict],
    ads: List[Dict],
    seed: int
) -> List[Dict]:
    """Generate ad interaction tracking data."""
    random.seed(seed + 7)
    interactions = []
    
    for ad in ads:
        # Generate interactions based on ad performance
        num_impressions = ad["impressions"] // 100  # Sample
        num_clicks = ad["clicks"] // 10
        num_conversions = ad["conversions"]
        
        for _ in range(min(num_impressions, len(users))):
            user = random.choice(users)
            interactions.append({
                "interaction_id": len(interactions) + 1,
                "user_id": user["user_id"],
                "ad_id": ad["ad_id"],
                "interaction_type": "impression",
                "created_at": random_date(
                    datetime.fromisoformat(ad["start_date"]),
                    datetime.now()
                ).isoformat(),
            })
        
        for _ in range(min(num_clicks, len(users))):
            user = random.choice(users)
            interactions.append({
                "interaction_id": len(interactions) + 1,
                "user_id": user["user_id"],
                "ad_id": ad["ad_id"],
                "interaction_type": "click",
                "created_at": random_date(
                    datetime.fromisoformat(ad["start_date"]),
                    datetime.now()
                ).isoformat(),
            })
        
        for _ in range(min(num_conversions, len(users))):
            user = random.choice(users)
            interactions.append({
                "interaction_id": len(interactions) + 1,
                "user_id": user["user_id"],
                "ad_id": ad["ad_id"],
                "interaction_type": "conversion",
                "revenue": round(random.uniform(5, 100), 2),
                "created_at": random_date(
                    datetime.fromisoformat(ad["start_date"]),
                    datetime.now()
                ).isoformat(),
            })
    
    return interactions

def generate_user_wallets(users: List[Dict], seed: int) -> List[Dict]:
    """Generate Solana wallet connections."""
    random.seed(seed + 8)
    wallets = []
    
    # ~20% of users have connected wallets
    wallet_users = random.sample(users, len(users) // 5)
    
    for user in wallet_users:
        wallets.append({
            "wallet_id": len(wallets) + 1,
            "user_id": user["user_id"],
            "wallet_address": generate_solana_address(),
            "wallet_type": "solana",
            "is_primary": True,
            "is_verified": random.random() > 0.1,
            "connected_at": random_date(datetime(2023, 6, 1), datetime.now()).isoformat(),
        })
    
    return wallets

def generate_user_nfts(wallets: List[Dict], seed: int) -> List[Dict]:
    """Generate NFT ownership records."""
    random.seed(seed + 9)
    nfts = []
    
    nft_collections = [
        "Kumele Founders",
        "Event Host Badge",
        "Community Champion",
        "Early Adopter",
        "Super Connector",
    ]
    
    for wallet in wallets:
        # Each wallet user has 0-5 NFTs
        num_nfts = random.choices([0, 1, 2, 3, 5], weights=[0.30, 0.35, 0.20, 0.10, 0.05])[0]
        
        for _ in range(num_nfts):
            collection = random.choice(nft_collections)
            nfts.append({
                "nft_id": len(nfts) + 1,
                "user_id": wallet["user_id"],
                "wallet_address": wallet["wallet_address"],
                "collection_name": collection,
                "token_id": generate_uuid()[:16],
                "mint_address": generate_solana_address(),
                "metadata_uri": f"https://nft.kumele.com/metadata/{len(nfts)+1}.json",
                "rarity": random.choice(["common", "uncommon", "rare", "legendary"]),
                "acquired_at": random_date(
                    datetime.fromisoformat(wallet["connected_at"]),
                    datetime.now()
                ).isoformat(),
            })
    
    return nfts

def generate_reward_coupons(users: List[Dict], seed: int) -> List[Dict]:
    """Generate reward/coupon redemptions."""
    random.seed(seed + 10)
    coupons = []
    
    # Users with reward tiers get coupons
    eligible_users = [u for u in users if u["reward_tier"] != "none"]
    
    for user in eligible_users:
        num_coupons = random.randint(1, 5)
        
        for _ in range(num_coupons):
            coupons.append({
                "coupon_id": len(coupons) + 1,
                "user_id": user["user_id"],
                "code": f"KUMELE-{generate_uuid()[:8].upper()}",
                "discount_type": random.choice(["percentage", "fixed"]),
                "discount_value": random.choice([10, 15, 20, 25, 50]),
                "min_purchase": random.choice([0, 10, 25, 50]),
                "status": random.choices(["active", "used", "expired"], weights=[0.40, 0.35, 0.25])[0],
                "reward_tier_required": user["reward_tier"],
                "created_at": random_date(datetime(2023, 6, 1), datetime.now()).isoformat(),
                "expires_at": random_date(datetime.now(), datetime(2025, 1, 1)).isoformat(),
                "used_at": random_date(datetime(2023, 6, 1), datetime.now()).isoformat() if random.random() > 0.5 else None,
            })
    
    return coupons

def generate_timeseries_daily(
    events: List[Dict],
    users: List[Dict],
    start_date: datetime,
    end_date: datetime,
    seed: int
) -> List[Dict]:
    """Generate daily aggregated metrics."""
    random.seed(seed + 11)
    timeseries = []
    
    current = start_date
    while current <= end_date:
        # Daily variation
        day_of_week = current.weekday()
        weekend_multiplier = 1.5 if day_of_week >= 5 else 1.0
        
        timeseries.append({
            "date": current.strftime("%Y-%m-%d"),
            "active_users": int(len(users) * random.uniform(0.05, 0.15) * weekend_multiplier),
            "new_users": random.randint(5, 50),
            "events_created": random.randint(2, 20),
            "events_completed": random.randint(5, 30),
            "total_rsvps": random.randint(50, 500),
            "total_check_ins": random.randint(30, 300),
            "avg_rating": round(random.uniform(4.0, 4.8), 2),
            "revenue": round(random.uniform(100, 2000) * weekend_multiplier, 2),
            "ad_impressions": random.randint(10000, 100000),
            "ad_clicks": random.randint(100, 2000),
        })
        
        current += timedelta(days=1)
    
    return timeseries

def generate_timeseries_hourly(
    start_date: datetime,
    end_date: datetime,
    seed: int
) -> List[Dict]:
    """Generate hourly activity patterns (last 7 days only)."""
    random.seed(seed + 12)
    timeseries = []
    
    # Only last 7 days at hourly granularity
    seven_days_ago = max(start_date, end_date - timedelta(days=7))
    current = seven_days_ago
    
    while current <= end_date:
        hour = current.hour
        day_of_week = current.weekday()
        
        # Activity patterns by hour
        if 6 <= hour <= 9:
            activity_multiplier = 0.5  # Morning
        elif 10 <= hour <= 12:
            activity_multiplier = 0.8  # Late morning
        elif 12 <= hour <= 14:
            activity_multiplier = 1.2  # Lunch
        elif 14 <= hour <= 18:
            activity_multiplier = 1.0  # Afternoon
        elif 18 <= hour <= 22:
            activity_multiplier = 1.5  # Evening peak
        else:
            activity_multiplier = 0.2  # Night
        
        # Weekend boost
        if day_of_week >= 5:
            activity_multiplier *= 1.3
        
        timeseries.append({
            "timestamp": current.isoformat(),
            "hour": hour,
            "day_of_week": day_of_week,
            "active_sessions": int(random.uniform(50, 500) * activity_multiplier),
            "api_requests": int(random.uniform(1000, 10000) * activity_multiplier),
            "events_viewed": int(random.uniform(100, 1000) * activity_multiplier),
            "searches": int(random.uniform(50, 500) * activity_multiplier),
            "chatbot_queries": int(random.uniform(10, 100) * activity_multiplier),
        })
        
        current += timedelta(hours=1)
    
    return timeseries

def generate_embeddings_for_qdrant(
    users: List[Dict],
    events: List[Dict],
    hobbies: List[Dict]
) -> Dict[str, Any]:
    """Generate pre-computed embeddings for Qdrant import."""
    embeddings = {
        "user_embeddings": [],
        "event_embeddings": [],
        "hobby_embeddings": [],
    }
    
    # User embeddings
    for user in users[:500]:  # Limit for demo
        user_text = f"{user['name']} {user['city']} age_{user['age']} {user['reward_tier']}"
        embeddings["user_embeddings"].append({
            "id": abs(hash(f"user_{user['user_id']}")) % (2**63),
            "vector": hash_to_embedding(user_text),
            "payload": {
                "user_id": str(user["user_id"]),
                "city": user["city"],
                "reward_tier": user["reward_tier"],
            }
        })
    
    # Event embeddings
    for event in events[:500]:  # Limit for demo
        event_text = f"{event['title']} {event['category']} {event['city']} {event['tags']}"
        embeddings["event_embeddings"].append({
            "id": abs(hash(f"event_{event['event_id']}")) % (2**63),
            "vector": hash_to_embedding(event_text),
            "payload": {
                "event_id": str(event["event_id"]),
                "title": event["title"],
                "category": event["category"],
                "city": event["city"],
            }
        })
    
    # Hobby embeddings
    for hobby in hobbies:
        hobby_text = f"{hobby['hobby_name']} {hobby['category']} {hobby['description']}"
        embeddings["hobby_embeddings"].append({
            "id": hobby["hobby_id"],
            "vector": hash_to_embedding(hobby_text),
            "payload": {
                "hobby_id": hobby["hobby_id"],
                "hobby_name": hobby["hobby_name"],
                "category": hobby["category"],
            }
        })
    
    return embeddings

# ==============================================================================
# MAIN GENERATOR
# ==============================================================================

def write_csv(data: List[Dict], filepath: str):
    """Write data to CSV file."""
    if not data:
        return
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    
    print(f"  ✓ {filepath} ({len(data):,} rows)")

def write_json(data: Any, filepath: str):
    """Write data to JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"  ✓ {filepath}")

def generate_manifest(
    output_dir: str,
    num_users: int,
    num_events: int,
    months: int,
    seed: int,
    stats: Dict[str, int]
) -> Dict:
    """Generate dataset manifest."""
    return {
        "name": "Kumele Synthetic Dataset V2",
        "version": "2.0.0",
        "generated_at": datetime.now().isoformat(),
        "parameters": {
            "num_users": num_users,
            "num_events": num_events,
            "months_of_data": months,
            "random_seed": seed,
        },
        "statistics": stats,
        "files": [
            "users.csv",
            "hobbies.csv",
            "user_hobbies.csv",
            "events.csv",
            "user_events.csv",
            "blogs.csv",
            "blog_interactions.csv",
            "ads.csv",
            "ad_interactions.csv",
            "user_wallets.csv",
            "user_nfts.csv",
            "reward_coupons.csv",
            "timeseries_daily.csv",
            "timeseries_hourly.csv",
            "embeddings_qdrant.json",
        ],
        "schema_version": "kumele_v2",
        "compatible_with": ["kumele-api>=1.0.0"],
    }

def generate_readme(stats: Dict[str, int], output_dir: str) -> str:
    """Generate README for dataset."""
    return f"""# Kumele Synthetic Dataset V2

## Overview
This synthetic dataset was generated for testing and development of the Kumele platform.

## Statistics
- **Users**: {stats['users']:,}
- **Events**: {stats['events']:,}
- **Hobbies**: {stats['hobbies']:,}
- **User-Hobby Relations**: {stats['user_hobbies']:,}
- **Event Attendances**: {stats['user_events']:,}
- **Blogs**: {stats['blogs']:,}
- **Blog Interactions**: {stats['blog_interactions']:,}
- **Ads**: {stats['ads']:,}
- **Ad Interactions**: {stats['ad_interactions']:,}
- **Wallets**: {stats['wallets']:,}
- **NFTs**: {stats['nfts']:,}
- **Coupons**: {stats['coupons']:,}

## Files

### Core Data
- `users.csv` - User profiles with demographics
- `hobbies.csv` - Hobby/interest taxonomy
- `user_hobbies.csv` - User-hobby relationships
- `events.csv` - Event listings
- `user_events.csv` - Event attendance records

### Content & Engagement
- `blogs.csv` - Blog/article content
- `blog_interactions.csv` - User-blog interactions

### Advertising
- `ads.csv` - Advertisement listings
- `ad_interactions.csv` - Ad performance tracking

### Web3/Blockchain
- `user_wallets.csv` - Solana wallet connections
- `user_nfts.csv` - NFT ownership records

### Rewards
- `reward_coupons.csv` - Coupon redemptions

### Time Series
- `timeseries_daily.csv` - Daily aggregated metrics
- `timeseries_hourly.csv` - Hourly activity patterns

### ML/Embeddings
- `embeddings_qdrant.json` - Pre-computed embeddings for Qdrant

## Usage

### Load into PostgreSQL
```sql
\\copy users FROM 'users.csv' CSV HEADER;
\\copy hobbies FROM 'hobbies.csv' CSV HEADER;
-- ... etc
```

### Load Embeddings into Qdrant
```python
import json
import httpx

with open('embeddings_qdrant.json') as f:
    embeddings = json.load(f)

# Create collections and upload
for collection, points in embeddings.items():
    httpx.put(f"http://localhost:6333/collections/{{collection}}/points", json={{"points": points}})
```

## Generated
- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Generator: Kumele Synthetic Data Generator V2
"""

def main():
    parser = argparse.ArgumentParser(description="Generate Kumele synthetic dataset")
    parser.add_argument("--users", type=int, default=1000, help="Number of users")
    parser.add_argument("--events", type=int, default=500, help="Number of events")
    parser.add_argument("--months", type=int, default=6, help="Months of historical data")
    parser.add_argument("--output-dir", type=str, default="./synthetic_data", help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Kumele Synthetic Data Generator V2")
    print("=" * 60)
    print(f"\nParameters:")
    print(f"  Users: {args.users:,}")
    print(f"  Events: {args.events:,}")
    print(f"  Months: {args.months}")
    print(f"  Seed: {args.seed}")
    print(f"  Output: {args.output_dir}")
    print()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.months * 30)
    
    print("Generating data...")
    
    # Generate all data
    users = generate_users(args.users, args.seed)
    print(f"  ✓ Users: {len(users):,}")
    
    hobbies = generate_hobbies()
    print(f"  ✓ Hobbies: {len(hobbies):,}")
    
    user_hobbies = generate_user_hobbies(users, hobbies, args.seed)
    print(f"  ✓ User-Hobbies: {len(user_hobbies):,}")
    
    events = generate_events(args.events, users, hobbies, start_date, end_date, args.seed)
    print(f"  ✓ Events: {len(events):,}")
    
    user_events = generate_user_events(users, events, args.seed)
    print(f"  ✓ User-Events: {len(user_events):,}")
    
    num_blogs = args.events // 5
    blogs = generate_blogs(num_blogs, users, args.seed)
    print(f"  ✓ Blogs: {len(blogs):,}")
    
    blog_interactions = generate_blog_interactions(users, blogs, args.seed)
    print(f"  ✓ Blog Interactions: {len(blog_interactions):,}")
    
    num_ads = args.events // 10
    ads = generate_ads(num_ads, args.seed)
    print(f"  ✓ Ads: {len(ads):,}")
    
    ad_interactions = generate_ad_interactions(users, ads, args.seed)
    print(f"  ✓ Ad Interactions: {len(ad_interactions):,}")
    
    wallets = generate_user_wallets(users, args.seed)
    print(f"  ✓ Wallets: {len(wallets):,}")
    
    nfts = generate_user_nfts(wallets, args.seed)
    print(f"  ✓ NFTs: {len(nfts):,}")
    
    coupons = generate_reward_coupons(users, args.seed)
    print(f"  ✓ Coupons: {len(coupons):,}")
    
    daily_ts = generate_timeseries_daily(events, users, start_date, end_date, args.seed)
    print(f"  ✓ Daily Timeseries: {len(daily_ts):,}")
    
    hourly_ts = generate_timeseries_hourly(start_date, end_date, args.seed)
    print(f"  ✓ Hourly Timeseries: {len(hourly_ts):,}")
    
    embeddings = generate_embeddings_for_qdrant(users, events, hobbies)
    print(f"  ✓ Embeddings: {sum(len(v) for v in embeddings.values()):,}")
    
    print("\nWriting files...")
    
    # Write CSV files
    write_csv(users, os.path.join(args.output_dir, "users.csv"))
    write_csv(hobbies, os.path.join(args.output_dir, "hobbies.csv"))
    write_csv(user_hobbies, os.path.join(args.output_dir, "user_hobbies.csv"))
    write_csv(events, os.path.join(args.output_dir, "events.csv"))
    write_csv(user_events, os.path.join(args.output_dir, "user_events.csv"))
    write_csv(blogs, os.path.join(args.output_dir, "blogs.csv"))
    write_csv(blog_interactions, os.path.join(args.output_dir, "blog_interactions.csv"))
    write_csv(ads, os.path.join(args.output_dir, "ads.csv"))
    write_csv(ad_interactions, os.path.join(args.output_dir, "ad_interactions.csv"))
    write_csv(wallets, os.path.join(args.output_dir, "user_wallets.csv"))
    write_csv(nfts, os.path.join(args.output_dir, "user_nfts.csv"))
    write_csv(coupons, os.path.join(args.output_dir, "reward_coupons.csv"))
    write_csv(daily_ts, os.path.join(args.output_dir, "timeseries_daily.csv"))
    write_csv(hourly_ts, os.path.join(args.output_dir, "timeseries_hourly.csv"))
    
    # Write JSON files
    write_json(embeddings, os.path.join(args.output_dir, "embeddings_qdrant.json"))
    
    # Statistics
    stats = {
        "users": len(users),
        "events": len(events),
        "hobbies": len(hobbies),
        "user_hobbies": len(user_hobbies),
        "user_events": len(user_events),
        "blogs": len(blogs),
        "blog_interactions": len(blog_interactions),
        "ads": len(ads),
        "ad_interactions": len(ad_interactions),
        "wallets": len(wallets),
        "nfts": len(nfts),
        "coupons": len(coupons),
        "daily_timeseries": len(daily_ts),
        "hourly_timeseries": len(hourly_ts),
    }
    
    # Write manifest
    manifest = generate_manifest(args.output_dir, args.users, args.events, args.months, args.seed, stats)
    write_json(manifest, os.path.join(args.output_dir, "manifest.json"))
    
    # Write README
    readme = generate_readme(stats, args.output_dir)
    with open(os.path.join(args.output_dir, "README.md"), 'w') as f:
        f.write(readme)
    print(f"  ✓ {os.path.join(args.output_dir, 'README.md')}")
    
    print("\n" + "=" * 60)
    print("Generation Complete!")
    print("=" * 60)
    print(f"\nTotal records: {sum(stats.values()):,}")
    print(f"Output directory: {os.path.abspath(args.output_dir)}")
    print("\nTo load into database:")
    print(f"  cd {args.output_dir}")
    print("  python -c \"import pandas; ...\"  # See README.md")

if __name__ == "__main__":
    main()
