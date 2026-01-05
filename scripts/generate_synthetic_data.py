"""
Kumele AI/ML Backend - Synthetic Data Generator
================================================
This script generates synthetic test data for all API endpoints.

Run this script to populate the database with realistic test data:
    python scripts/generate_synthetic_data.py

Output:
- Populates PostgreSQL database with test data
- Creates CSV files in /data folder for reference
- Generates manifest.json with data statistics
"""

import asyncio
import csv
import json
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Ensure we can import from app
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / "data"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://kumele:kumele123@localhost:5432/kumele_db")

# =============================================================================
# DATA TEMPLATES
# =============================================================================

CITIES = [
    {"name": "London", "country": "UK", "lat": 51.5074, "lon": -0.1278},
    {"name": "New York", "country": "USA", "lat": 40.7128, "lon": -74.0060},
    {"name": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522},
    {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
    {"name": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093},
    {"name": "Dubai", "country": "UAE", "lat": 25.2048, "lon": 55.2708},
    {"name": "Berlin", "country": "Germany", "lat": 52.5200, "lon": 13.4050},
    {"name": "Toronto", "country": "Canada", "lat": 43.6532, "lon": -79.3832},
    {"name": "Singapore", "country": "Singapore", "lat": 1.3521, "lon": 103.8198},
    {"name": "Mumbai", "country": "India", "lat": 19.0760, "lon": 72.8777},
]

HOBBIES = [
    {"id": "cooking", "name": "Cooking & Culinary", "category": "lifestyle"},
    {"id": "photography", "name": "Photography", "category": "arts"},
    {"id": "hiking", "name": "Hiking & Outdoors", "category": "sports"},
    {"id": "yoga", "name": "Yoga & Meditation", "category": "wellness"},
    {"id": "painting", "name": "Painting & Art", "category": "arts"},
    {"id": "music", "name": "Music & Instruments", "category": "arts"},
    {"id": "gaming", "name": "Gaming", "category": "entertainment"},
    {"id": "reading", "name": "Book Club & Reading", "category": "education"},
    {"id": "fitness", "name": "Fitness & Gym", "category": "sports"},
    {"id": "tech", "name": "Tech & Coding", "category": "education"},
    {"id": "dancing", "name": "Dancing", "category": "arts"},
    {"id": "gardening", "name": "Gardening", "category": "lifestyle"},
    {"id": "crafts", "name": "DIY & Crafts", "category": "lifestyle"},
    {"id": "languages", "name": "Language Learning", "category": "education"},
    {"id": "travel", "name": "Travel & Adventure", "category": "lifestyle"},
]

EVENT_TITLES = {
    "cooking": ["Italian Pasta Masterclass", "Sushi Making Workshop", "Vegan Cooking Night", "BBQ & Grill Session"],
    "photography": ["Street Photography Walk", "Portrait Photography 101", "Night Photography Tour", "Photo Editing Workshop"],
    "hiking": ["Mountain Trail Adventure", "Sunrise Hike", "Nature Photography Hike", "Beginner Hiking Group"],
    "yoga": ["Morning Yoga Flow", "Meditation & Mindfulness", "Yoga in the Park", "Power Yoga Session"],
    "fitness": ["HIIT Workout Class", "CrossFit Intro", "Running Club Meetup", "Strength Training Basics"],
    "tech": ["Python Workshop", "Web Dev Meetup", "AI/ML Discussion", "Startup Networking"],
    "music": ["Acoustic Jam Session", "Guitar for Beginners", "Music Production Workshop", "Open Mic Night"],
    "gaming": ["Board Game Night", "Esports Tournament", "Retro Gaming Meetup", "VR Gaming Experience"],
}

FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery", "Skyler", "Parker",
               "Jamie", "Drew", "Reese", "Sage", "Finley", "Rowan", "Hayden", "Emery", "Phoenix", "River"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Jackson", "Martin", "Lee", "Thompson", "White"]

FEEDBACK_TEXTS = {
    "positive": [
        "Great event! Really enjoyed it.",
        "Amazing experience, will definitely come again!",
        "The host was fantastic and very knowledgeable.",
        "Met wonderful people, highly recommend!",
        "Exceeded my expectations, thank you!",
    ],
    "negative": [
        "Not what I expected.",
        "Could have been organized better.",
        "The venue was too small.",
        "Started late and felt rushed.",
        "Needs improvement.",
    ],
    "neutral": [
        "It was okay, nothing special.",
        "Average experience overall.",
        "Some parts were good, others not so much.",
        "Met a few interesting people.",
        "Would consider attending again.",
    ]
}

# =============================================================================
# DATA GENERATORS
# =============================================================================

def generate_uuid() -> str:
    return str(uuid.uuid4())

def random_date(start_days_ago: int, end_days_from_now: int) -> datetime:
    """Generate random date between start_days_ago and end_days_from_now."""
    start = datetime.now() - timedelta(days=start_days_ago)
    end = datetime.now() + timedelta(days=end_days_from_now)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + timedelta(days=random_days)

def generate_users(count: int = 100) -> List[Dict[str, Any]]:
    """Generate synthetic user data."""
    users = []
    for i in range(count):
        city = random.choice(CITIES)
        # Add some randomness to lat/lon (within ~10km)
        lat = city["lat"] + random.uniform(-0.1, 0.1)
        lon = city["lon"] + random.uniform(-0.1, 0.1)
        
        user = {
            "user_id": i + 1,  # BigInteger in DB
            "external_id": generate_uuid(),  # For API reference
            "email": f"user{i+1}@example.com",
            "first_name": random.choice(FIRST_NAMES),
            "last_name": random.choice(LAST_NAMES),
            "age_group": random.choice(["18-24", "25-34", "35-44", "45-54", "55+"]),
            "city": city["name"],
            "country": city["country"],
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "reward_status": random.choice(["none", "bronze", "silver", "gold"]),
            "activity_frequency": random.choice(["low", "medium", "high"]),
            "created_at": random_date(365, 0).isoformat(),
            "is_active": random.random() > 0.1,  # 90% active
        }
        users.append(user)
    return users

def generate_user_hobbies(users: List[Dict], hobbies_per_user: int = 3) -> List[Dict[str, Any]]:
    """Generate user hobby preferences."""
    user_hobbies = []
    for user in users:
        selected_hobbies = random.sample(HOBBIES, min(hobbies_per_user, len(HOBBIES)))
        for hobby in selected_hobbies:
            user_hobby = {
                "id": len(user_hobbies) + 1,
                "user_id": user["user_id"],
                "hobby_id": hobby["id"],
                "preference_score": round(random.uniform(0.5, 1.0), 2),
                "created_at": user["created_at"],
            }
            user_hobbies.append(user_hobby)
    return user_hobbies

def generate_events(users: List[Dict], count: int = 200) -> List[Dict[str, Any]]:
    """Generate synthetic event data."""
    events = []
    hosts = random.sample(users, min(50, len(users)))  # Select some users as hosts
    
    for i in range(count):
        host = random.choice(hosts)
        hobby = random.choice(HOBBIES)
        city = random.choice(CITIES)
        titles = EVENT_TITLES.get(hobby["id"], [f"{hobby['name']} Meetup"])
        
        event_date = random_date(-30, 60)  # Past 30 days to 60 days future
        is_past = event_date < datetime.now()
        
        event = {
            "event_id": generate_uuid(),
            "host_id": host["user_id"],
            "title": random.choice(titles),
            "description": f"Join us for an exciting {hobby['name'].lower()} session!",
            "category": hobby["id"],
            "city": city["name"],
            "country": city["country"],
            "latitude": city["lat"] + random.uniform(-0.05, 0.05),
            "longitude": city["lon"] + random.uniform(-0.05, 0.05),
            "event_date": event_date.isoformat(),
            "capacity": random.choice([10, 15, 20, 25, 30, 50]),
            "price": random.choice([0, 0, 0, 10, 15, 20, 25, 30, 50]),  # Many free events
            "is_free": random.random() > 0.4,  # 60% free
            "status": "completed" if is_past else random.choice(["published", "published", "draft"]),
            "created_at": (event_date - timedelta(days=random.randint(7, 30))).isoformat(),
        }
        events.append(event)
    return events

def generate_interactions(users: List[Dict], events: List[Dict], count: int = 500) -> List[Dict[str, Any]]:
    """Generate user-event interactions (RSVPs, attendance, clicks)."""
    interactions = []
    past_events = [e for e in events if datetime.fromisoformat(e["event_date"]) < datetime.now()]
    
    for i in range(count):
        user = random.choice(users)
        event = random.choice(past_events) if past_events else random.choice(events)
        
        # Determine interaction type and outcome
        rsvp = random.random() > 0.3  # 70% RSVP
        attended = rsvp and random.random() > 0.2  # 80% of RSVPs attend
        
        interaction = {
            "id": i + 1,
            "user_id": user["user_id"],
            "event_id": event["event_id"],
            "interaction_type": "attendance" if attended else ("rsvp" if rsvp else "view"),
            "rsvp": rsvp,
            "attended": attended,
            "clicked": True,
            "viewed_at": random_date(60, 0).isoformat(),
            "created_at": random_date(60, 0).isoformat(),
        }
        interactions.append(interaction)
    return interactions

def generate_ratings(users: List[Dict], events: List[Dict], count: int = 300) -> List[Dict[str, Any]]:
    """Generate event ratings."""
    ratings = []
    past_events = [e for e in events if e["status"] == "completed"]
    
    for i in range(min(count, len(past_events) * 5)):
        user = random.choice(users)
        event = random.choice(past_events) if past_events else random.choice(events)
        
        # Generate weighted rating (most ratings are positive)
        base_rating = random.choices([3, 4, 5], weights=[1, 3, 6])[0]
        
        sentiment = "positive" if base_rating >= 4 else ("neutral" if base_rating == 3 else "negative")
        
        rating = {
            "id": generate_uuid(),
            "event_id": event["event_id"],
            "user_id": user["user_id"],
            "host_id": event["host_id"],
            "overall_rating": base_rating,
            "communication": min(5, base_rating + random.randint(-1, 1)),
            "respect": min(5, base_rating + random.randint(-1, 1)),
            "professionalism": min(5, base_rating + random.randint(-1, 1)),
            "atmosphere": min(5, base_rating + random.randint(-1, 1)),
            "value_for_money": min(5, base_rating + random.randint(-1, 1)) if not event["is_free"] else None,
            "comment": random.choice(FEEDBACK_TEXTS[sentiment]),
            "created_at": event["event_date"],
        }
        ratings.append(rating)
    return ratings

def generate_user_activities(users: List[Dict], events: List[Dict], count: int = 400) -> List[Dict[str, Any]]:
    """Generate user activities for rewards calculation."""
    activities = []
    past_events = [e for e in events if e["status"] == "completed"]
    
    for i in range(count):
        user = random.choice(users)
        event = random.choice(past_events) if past_events else random.choice(events)
        
        activity_type = random.choice(["event_attended", "event_created"])
        
        activity = {
            "id": i + 1,
            "user_id": user["user_id"],
            "activity_type": activity_type,
            "event_id": event["event_id"],
            "activity_date": random_date(45, 0).isoformat(),
            "success": random.random() > 0.1,  # 90% successful
            "points_earned": random.choice([10, 20, 50]) if random.random() > 0.5 else 0,
        }
        activities.append(activity)
    return activities

def generate_reward_coupons(users: List[Dict], count: int = 50) -> List[Dict[str, Any]]:
    """Generate reward coupons."""
    coupons = []
    
    for i in range(count):
        user = random.choice(users)
        tier = random.choice(["silver", "gold", "gold"])  # More gold coupons
        
        coupon = {
            "coupon_id": generate_uuid(),
            "user_id": user["user_id"],
            "status_level": tier,
            "discount_value": 4 if tier == "silver" else 8,
            "stackable": tier == "gold",
            "is_redeemed": random.random() > 0.7,  # 30% redeemed
            "issued_at": random_date(30, 0).isoformat(),
            "redeemed_at": random_date(15, 0).isoformat() if random.random() > 0.7 else None,
            "expires_at": random_date(0, 60).isoformat(),
        }
        coupons.append(coupon)
    return coupons

def generate_timeseries_daily(days: int = 90) -> List[Dict[str, Any]]:
    """Generate daily time series data for Prophet."""
    data = []
    base_date = datetime.now() - timedelta(days=days)
    
    for i in range(days):
        date = base_date + timedelta(days=i)
        # Simulate weekly patterns (weekends higher)
        day_of_week = date.weekday()
        base_value = 50 + (20 if day_of_week >= 5 else 0)
        
        # Add some trend and noise
        trend = i * 0.1  # Slight upward trend
        noise = random.uniform(-10, 10)
        
        record = {
            "ds": date.strftime("%Y-%m-%d"),  # Prophet format
            "y": max(0, int(base_value + trend + noise)),
            "category": random.choice(["cooking", "fitness", "tech", "music"]),
            "city": random.choice(["London", "New York", "Paris"]),
            "events_count": random.randint(5, 20),
            "total_attendance": random.randint(50, 200),
            "avg_rating": round(random.uniform(3.5, 5.0), 2),
        }
        data.append(record)
    return data

def generate_timeseries_hourly(days: int = 7) -> List[Dict[str, Any]]:
    """Generate hourly time series data."""
    data = []
    base_date = datetime.now() - timedelta(days=days)
    
    for day in range(days):
        for hour in range(24):
            timestamp = base_date + timedelta(days=day, hours=hour)
            
            # Simulate hourly patterns (peak at evening)
            if 9 <= hour <= 11:
                base_value = 30
            elif 17 <= hour <= 21:
                base_value = 60
            elif 0 <= hour <= 6:
                base_value = 5
            else:
                base_value = 20
            
            noise = random.uniform(-5, 5)
            
            record = {
                "timestamp": timestamp.isoformat(),
                "hour": hour,
                "day_of_week": timestamp.weekday(),
                "active_users": max(0, int(base_value + noise)),
                "events_live": random.randint(0, 10),
                "api_requests": random.randint(100, 1000),
            }
            data.append(record)
    return data

def generate_ads(count: int = 30) -> List[Dict[str, Any]]:
    """Generate ad data."""
    ads = []
    
    for i in range(count):
        hobby = random.choice(HOBBIES)
        
        ad = {
            "ad_id": generate_uuid(),
            "title": f"Discover {hobby['name']} Events Near You!",
            "description": f"Join the best {hobby['name'].lower()} community. Meet new people, learn new skills.",
            "category": hobby["id"],
            "target_age_groups": random.sample(["18-24", "25-34", "35-44", "45-54"], 2),
            "target_cities": random.sample([c["name"] for c in CITIES], 3),
            "budget": random.choice([100, 200, 500, 1000]),
            "status": random.choice(["active", "active", "paused", "completed"]),
            "created_at": random_date(60, 0).isoformat(),
            "impressions": random.randint(1000, 50000),
            "clicks": random.randint(50, 2000),
            "conversions": random.randint(5, 200),
        }
        ads.append(ad)
    return ads

def generate_knowledge_documents() -> List[Dict[str, Any]]:
    """Generate knowledge base documents for chatbot."""
    documents = [
        {
            "doc_id": "faq-001",
            "title": "How to Create an Event",
            "content": """To create an event on Kumele:
1. Log in to your account
2. Click the "Create Event" button in the top menu
3. Fill in the event details:
   - Title: Give your event a catchy name
   - Category: Select the hobby/interest category
   - Date & Time: When will it happen
   - Location: Where will it be held
   - Capacity: Maximum number of attendees
   - Price: Set a price or make it free
4. Add a description explaining what attendees can expect
5. Upload a cover image
6. Click "Publish" to make it live

Your event will be visible to users interested in that category.""",
            "category": "faq",
            "language": "en",
        },
        {
            "doc_id": "faq-002",
            "title": "How Rewards Work",
            "content": """Kumele Rewards Program:

**Tiers:**
- Bronze: Attend or host 1+ events in 30 days
- Silver: Attend or host 3+ events in 30 days → Get 4% discount
- Gold: Attend or host 4+ events in 30 days → Get 8% discount (stacks!)

**How it works:**
- Your tier is calculated based on the last 30 days of activity
- Only completed events count (no-shows don't count)
- Gold discounts stack: 4 events = 8%, 8 events = 16%, etc.
- Discounts apply to paid events only

**Redeeming rewards:**
1. Go to your Profile → Rewards
2. View available coupons
3. Apply coupon at checkout""",
            "category": "faq",
            "language": "en",
        },
        {
            "doc_id": "faq-003",
            "title": "Cancellation and Refund Policy",
            "content": """Cancellation Policy:

**For Attendees:**
- Cancel 48+ hours before: Full refund
- Cancel 24-48 hours before: 50% refund
- Cancel less than 24 hours: No refund

**For Hosts:**
- You can cancel anytime, but:
  - All attendees get full refunds
  - Your reliability score decreases
  - Frequent cancellations may affect your visibility

**How to cancel:**
1. Go to My Events
2. Select the event
3. Click "Cancel Registration" or "Cancel Event"
4. Confirm cancellation

Refunds are processed within 5-7 business days.""",
            "category": "policy",
            "language": "en",
        },
        {
            "doc_id": "faq-004",
            "title": "Rating and Review Guidelines",
            "content": """Rating System:

**After attending an event, you can rate:**
- Overall experience (1-5 stars)
- Communication
- Respect
- Professionalism
- Atmosphere
- Value for money (if paid event)

**Guidelines:**
- Be honest and constructive
- Focus on the event experience
- No personal attacks
- No spam or promotional content
- Reviews are moderated for inappropriate content

**Host Score Calculation:**
Host Score = (70% × Attendee Ratings) + (30% × System Reliability)

Reliability includes:
- Event completion rate
- No-show rate
- Repeat attendee ratio""",
            "category": "help",
            "language": "en",
        },
        {
            "doc_id": "guide-001",
            "title": "Getting Started Guide",
            "content": """Welcome to Kumele!

**Step 1: Create Your Profile**
- Add your interests/hobbies
- Set your location
- Upload a profile photo

**Step 2: Discover Events**
- Browse by category
- Filter by location, date, price
- Save events you're interested in

**Step 3: Join Your First Event**
- Click "Join" on any event
- Complete payment (if paid)
- Add to your calendar

**Step 4: Attend & Connect**
- Show up on time
- Meet new people
- Have fun!

**Step 5: Rate & Review**
- Share your experience
- Help others find great events
- Build your community reputation""",
            "category": "guide",
            "language": "en",
        },
    ]
    return documents

def generate_interest_taxonomy() -> List[Dict[str, Any]]:
    """Generate interest taxonomy."""
    taxonomy = []
    
    # Level 0 - Top categories
    categories = [
        {"interest_id": "sports_fitness", "name": "Sports & Fitness", "level": 0},
        {"interest_id": "arts_culture", "name": "Arts & Culture", "level": 0},
        {"interest_id": "education", "name": "Education & Learning", "level": 0},
        {"interest_id": "lifestyle", "name": "Lifestyle", "level": 0},
        {"interest_id": "entertainment", "name": "Entertainment", "level": 0},
        {"interest_id": "wellness", "name": "Health & Wellness", "level": 0},
    ]
    
    # Level 1 - Sub-categories
    subcategories = [
        {"interest_id": "fitness", "parent_id": "sports_fitness", "name": "Fitness & Gym", "level": 1},
        {"interest_id": "hiking", "parent_id": "sports_fitness", "name": "Hiking & Outdoors", "level": 1},
        {"interest_id": "running", "parent_id": "sports_fitness", "name": "Running", "level": 1},
        {"interest_id": "photography", "parent_id": "arts_culture", "name": "Photography", "level": 1},
        {"interest_id": "painting", "parent_id": "arts_culture", "name": "Painting & Art", "level": 1},
        {"interest_id": "music", "parent_id": "arts_culture", "name": "Music", "level": 1},
        {"interest_id": "dancing", "parent_id": "arts_culture", "name": "Dancing", "level": 1},
        {"interest_id": "tech", "parent_id": "education", "name": "Tech & Coding", "level": 1},
        {"interest_id": "languages", "parent_id": "education", "name": "Language Learning", "level": 1},
        {"interest_id": "reading", "parent_id": "education", "name": "Book Club", "level": 1},
        {"interest_id": "cooking", "parent_id": "lifestyle", "name": "Cooking & Culinary", "level": 1},
        {"interest_id": "gardening", "parent_id": "lifestyle", "name": "Gardening", "level": 1},
        {"interest_id": "travel", "parent_id": "lifestyle", "name": "Travel", "level": 1},
        {"interest_id": "gaming", "parent_id": "entertainment", "name": "Gaming", "level": 1},
        {"interest_id": "movies", "parent_id": "entertainment", "name": "Movies & Film", "level": 1},
        {"interest_id": "yoga", "parent_id": "wellness", "name": "Yoga & Meditation", "level": 1},
        {"interest_id": "nutrition", "parent_id": "wellness", "name": "Nutrition", "level": 1},
    ]
    
    for cat in categories:
        cat["parent_id"] = None
        cat["is_active"] = True
        cat["created_at"] = datetime.now().isoformat()
        taxonomy.append(cat)
    
    for subcat in subcategories:
        subcat["is_active"] = True
        subcat["created_at"] = datetime.now().isoformat()
        taxonomy.append(subcat)
    
    return taxonomy

def generate_ui_strings() -> List[Dict[str, Any]]:
    """Generate UI strings for i18n."""
    strings = [
        {"key": "common.welcome", "default_text": "Welcome", "scope": "common"},
        {"key": "common.login", "default_text": "Log In", "scope": "common"},
        {"key": "common.signup", "default_text": "Sign Up", "scope": "common"},
        {"key": "common.logout", "default_text": "Log Out", "scope": "common"},
        {"key": "common.save", "default_text": "Save", "scope": "common"},
        {"key": "common.cancel", "default_text": "Cancel", "scope": "common"},
        {"key": "common.submit", "default_text": "Submit", "scope": "common"},
        {"key": "common.search", "default_text": "Search", "scope": "common"},
        {"key": "common.loading", "default_text": "Loading...", "scope": "common"},
        {"key": "common.error", "default_text": "An error occurred", "scope": "common"},
        {"key": "events.create", "default_text": "Create Event", "scope": "events"},
        {"key": "events.join", "default_text": "Join Event", "scope": "events"},
        {"key": "events.leave", "default_text": "Leave Event", "scope": "events"},
        {"key": "events.capacity", "default_text": "Capacity", "scope": "events"},
        {"key": "events.date", "default_text": "Date & Time", "scope": "events"},
        {"key": "profile.edit", "default_text": "Edit Profile", "scope": "profile"},
        {"key": "profile.interests", "default_text": "My Interests", "scope": "profile"},
        {"key": "profile.events", "default_text": "My Events", "scope": "profile"},
        {"key": "chat.send", "default_text": "Send", "scope": "chat"},
        {"key": "chat.typing", "default_text": "Typing...", "scope": "chat"},
        {"key": "support.help", "default_text": "Help & Support", "scope": "support"},
        {"key": "support.contact", "default_text": "Contact Us", "scope": "support"},
    ]
    
    for s in strings:
        s["created_at"] = datetime.now().isoformat()
        s["updated_at"] = datetime.now().isoformat()
    
    return strings

# =============================================================================
# CSV EXPORT
# =============================================================================

def save_to_csv(data: List[Dict], filename: str):
    """Save data to CSV file."""
    if not data:
        return
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    filepath = OUTPUT_DIR / filename
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    
    print(f"  ✓ Saved {len(data)} records to {filename}")

def save_manifest(stats: Dict):
    """Save manifest.json with generation statistics."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    filepath = OUTPUT_DIR / "manifest.json"
    
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "version": "1.0.0",
        "statistics": stats,
        "files": [
            "users.csv",
            "events.csv",
            "interactions.csv",
            "ratings.csv",
            "user_hobbies.csv",
            "user_activities.csv",
            "reward_coupons.csv",
            "timeseries_daily.csv",
            "timeseries_hourly.csv",
            "ads.csv",
            "knowledge_documents.csv",
            "interest_taxonomy.csv",
            "ui_strings.csv",
        ]
    }
    
    with open(filepath, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"  ✓ Saved manifest.json")

# =============================================================================
# DATABASE INSERTION
# =============================================================================

async def insert_to_database(data_dict: Dict[str, List[Dict]]):
    """Insert generated data into PostgreSQL database."""
    print("\n📊 Inserting data into PostgreSQL...")
    
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            # Insert users
            if data_dict.get("users"):
                for user in data_dict["users"]:
                    await session.execute(text("""
                        INSERT INTO users (user_id, email, created_at)
                        VALUES (:user_id, :email, :created_at)
                        ON CONFLICT (user_id) DO NOTHING
                    """), {"user_id": user["user_id"], "email": user["email"], "created_at": user["created_at"]})
                print(f"  ✓ Inserted {len(data_dict['users'])} users")
            
            # Insert interest taxonomy
            if data_dict.get("interest_taxonomy"):
                for item in data_dict["interest_taxonomy"]:
                    await session.execute(text("""
                        INSERT INTO interest_taxonomy (interest_id, parent_id, level, is_active, created_at)
                        VALUES (:interest_id, :parent_id, :level, :is_active, :created_at)
                        ON CONFLICT (interest_id) DO NOTHING
                    """), item)
                print(f"  ✓ Inserted {len(data_dict['interest_taxonomy'])} taxonomy items")
            
            # Insert UI strings
            if data_dict.get("ui_strings"):
                for item in data_dict["ui_strings"]:
                    await session.execute(text("""
                        INSERT INTO ui_strings (key, default_text, scope, created_at, updated_at)
                        VALUES (:key, :default_text, :scope, :created_at, :updated_at)
                        ON CONFLICT (key) DO UPDATE SET default_text = :default_text
                    """), item)
                print(f"  ✓ Inserted {len(data_dict['ui_strings'])} UI strings")
            
            # Insert user activities
            if data_dict.get("user_activities"):
                for item in data_dict["user_activities"][:100]:  # Limit for demo
                    await session.execute(text("""
                        INSERT INTO user_activities (user_id, activity_type, event_id, activity_date, success, points_earned)
                        VALUES (:user_id, :activity_type, :event_id, :activity_date, :success, :points_earned)
                    """), item)
                print(f"  ✓ Inserted {min(100, len(data_dict['user_activities']))} user activities")
            
            await session.commit()
            print("  ✓ Database commit successful!")
            
    except Exception as e:
        print(f"  ⚠ Database insertion failed: {e}")
        print("    (This is okay - CSV files are still available)")

# =============================================================================
# MAIN GENERATOR
# =============================================================================

def main():
    """Main entry point for data generation."""
    print("=" * 60)
    print("🚀 Kumele Synthetic Data Generator")
    print("=" * 60)
    
    # Generate all data
    print("\n📦 Generating synthetic data...")
    
    users = generate_users(100)
    print(f"  ✓ Generated {len(users)} users")
    
    user_hobbies = generate_user_hobbies(users, hobbies_per_user=3)
    print(f"  ✓ Generated {len(user_hobbies)} user hobbies")
    
    events = generate_events(users, count=200)
    print(f"  ✓ Generated {len(events)} events")
    
    interactions = generate_interactions(users, events, count=500)
    print(f"  ✓ Generated {len(interactions)} interactions")
    
    ratings = generate_ratings(users, events, count=300)
    print(f"  ✓ Generated {len(ratings)} ratings")
    
    user_activities = generate_user_activities(users, events, count=400)
    print(f"  ✓ Generated {len(user_activities)} user activities")
    
    reward_coupons = generate_reward_coupons(users, count=50)
    print(f"  ✓ Generated {len(reward_coupons)} reward coupons")
    
    timeseries_daily = generate_timeseries_daily(days=90)
    print(f"  ✓ Generated {len(timeseries_daily)} daily time series records")
    
    timeseries_hourly = generate_timeseries_hourly(days=7)
    print(f"  ✓ Generated {len(timeseries_hourly)} hourly time series records")
    
    ads = generate_ads(count=30)
    print(f"  ✓ Generated {len(ads)} ads")
    
    knowledge_docs = generate_knowledge_documents()
    print(f"  ✓ Generated {len(knowledge_docs)} knowledge documents")
    
    interest_taxonomy = generate_interest_taxonomy()
    print(f"  ✓ Generated {len(interest_taxonomy)} taxonomy items")
    
    ui_strings = generate_ui_strings()
    print(f"  ✓ Generated {len(ui_strings)} UI strings")
    
    # Save to CSV
    print("\n💾 Saving to CSV files...")
    save_to_csv(users, "users.csv")
    save_to_csv(user_hobbies, "user_hobbies.csv")
    save_to_csv(events, "events.csv")
    save_to_csv(interactions, "interactions.csv")
    save_to_csv(ratings, "ratings.csv")
    save_to_csv(user_activities, "user_activities.csv")
    save_to_csv(reward_coupons, "reward_coupons.csv")
    save_to_csv(timeseries_daily, "timeseries_daily.csv")
    save_to_csv(timeseries_hourly, "timeseries_hourly.csv")
    save_to_csv(ads, "ads.csv")
    save_to_csv(knowledge_docs, "knowledge_documents.csv")
    save_to_csv(interest_taxonomy, "interest_taxonomy.csv")
    save_to_csv(ui_strings, "ui_strings.csv")
    
    # Save manifest
    stats = {
        "users": len(users),
        "user_hobbies": len(user_hobbies),
        "events": len(events),
        "interactions": len(interactions),
        "ratings": len(ratings),
        "user_activities": len(user_activities),
        "reward_coupons": len(reward_coupons),
        "timeseries_daily": len(timeseries_daily),
        "timeseries_hourly": len(timeseries_hourly),
        "ads": len(ads),
        "knowledge_documents": len(knowledge_docs),
        "interest_taxonomy": len(interest_taxonomy),
        "ui_strings": len(ui_strings),
    }
    save_manifest(stats)
    
    # Try to insert into database
    asyncio.run(insert_to_database({
        "users": users,
        "user_activities": user_activities,
        "interest_taxonomy": interest_taxonomy,
        "ui_strings": ui_strings,
    }))
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ Data generation complete!")
    print("=" * 60)
    print(f"\n📁 Output directory: {OUTPUT_DIR}")
    print("\nGenerated files:")
    for filename in OUTPUT_DIR.glob("*.csv"):
        print(f"  - {filename.name}")
    print(f"  - manifest.json")
    
    print("\n📋 Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n🎯 Next steps:")
    print("  1. Review generated CSV files in /data folder")
    print("  2. Import into database if not auto-imported")
    print("  3. Test APIs with synthetic data")
    print("  4. Replace with real data when ready")

if __name__ == "__main__":
    main()
