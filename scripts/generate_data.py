#!/usr/bin/env python3
"""
Synthetic Data Generator for Kumele AI/ML

Generates:
- users.csv (~1000 users)
- events.csv
- interactions.csv
- timeseries_daily.csv
- timeseries_hourly.csv
- reward_coupons.csv
- manifest.json
- README.md

Optionally pushes data to PostgreSQL via SQLAlchemy.
"""
import argparse
import csv
import json
import os
import random
import string
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
from uuid import uuid4

# Configuration
NUM_USERS = 1000
NUM_EVENTS = 500
NUM_INTERACTIONS = 5000
NUM_DAYS = 90
NUM_COUPONS = 200

# Categories and Hobbies
CATEGORIES = [
    "music", "sports", "arts", "food", "technology",
    "outdoor", "fitness", "education", "gaming", "travel"
]

HOBBIES = [
    "Photography", "Hiking", "Cooking", "Reading", "Gaming",
    "Yoga", "Running", "Painting", "Music", "Dancing",
    "Swimming", "Cycling", "Gardening", "Writing", "Meditation",
    "Rock Climbing", "Tennis", "Basketball", "Soccer", "Volleyball",
    "Piano", "Guitar", "Singing", "Theater", "Film",
    "Coding", "Robotics", "Chess", "Board Games", "Card Games"
]

# Locations
CITIES = [
    {"name": "New York", "lat": 40.7128, "lng": -74.0060},
    {"name": "Los Angeles", "lat": 34.0522, "lng": -118.2437},
    {"name": "Chicago", "lat": 41.8781, "lng": -87.6298},
    {"name": "Houston", "lat": 29.7604, "lng": -95.3698},
    {"name": "Phoenix", "lat": 33.4484, "lng": -112.0740},
    {"name": "Philadelphia", "lat": 39.9526, "lng": -75.1652},
    {"name": "San Antonio", "lat": 29.4241, "lng": -98.4936},
    {"name": "San Diego", "lat": 32.7157, "lng": -117.1611},
    {"name": "Dallas", "lat": 32.7767, "lng": -96.7970},
    {"name": "Seattle", "lat": 47.6062, "lng": -122.3321},
]

# Reward Tiers
TIERS = ["bronze", "silver", "gold", "platinum"]

# Languages
LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko", "ar"]


def random_date(start: datetime, end: datetime) -> datetime:
    """Generate random date between start and end"""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def random_email(name: str) -> str:
    """Generate email from name"""
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "mail.com"]
    clean_name = name.lower().replace(" ", ".").replace("'", "")
    suffix = random.randint(1, 999)
    return f"{clean_name}{suffix}@{random.choice(domains)}"


def generate_users() -> List[Dict[str, Any]]:
    """Generate synthetic users"""
    first_names = [
        "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
        "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan",
        "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Emma",
        "Olivia", "Ava", "Isabella", "Sophia", "Mia", "Charlotte", "Amelia",
        "Harper", "Evelyn", "Liam", "Noah", "Oliver", "Elijah", "Lucas",
        "Mason", "Logan", "Alexander", "Ethan", "Jacob", "Aiden", "Mohamed",
        "Chen", "Wei", "Ming", "Raj", "Priya", "Yuki", "Sakura", "Jin"
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Thompson", "White", "Harris", "Sanchez", "Clark", "Lewis",
        "Robinson", "Walker", "Young", "Hall", "Allen", "King", "Wright",
        "Scott", "Green", "Adams", "Baker", "Nelson", "Hill", "Kim", "Wong",
        "Liu", "Chen", "Patel", "Kumar", "Singh", "Tanaka", "Yamamoto"
    ]
    
    users = []
    created_start = datetime.utcnow() - timedelta(days=365)
    created_end = datetime.utcnow()
    
    for i in range(NUM_USERS):
        first = random.choice(first_names)
        last = random.choice(last_names)
        full_name = f"{first} {last}"
        city = random.choice(CITIES)
        
        # User hobbies (2-5 hobbies)
        user_hobbies = random.sample(HOBBIES, random.randint(2, 5))
        
        user = {
            "id": i + 1,
            "name": full_name,
            "email": random_email(full_name),
            "latitude": city["lat"] + random.uniform(-0.1, 0.1),
            "longitude": city["lng"] + random.uniform(-0.1, 0.1),
            "city": city["name"],
            "preferred_language": random.choice(LANGUAGES),
            "reward_tier": random.choices(TIERS, weights=[50, 30, 15, 5])[0],
            "is_host": random.random() < 0.2,  # 20% are hosts
            "is_active": random.random() < 0.95,  # 95% active
            "hobbies": ",".join(user_hobbies),
            "created_at": random_date(created_start, created_end).isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        users.append(user)
    
    return users


def generate_events(users: List[Dict]) -> List[Dict[str, Any]]:
    """Generate synthetic events"""
    hosts = [u for u in users if u["is_host"]]
    
    event_titles = [
        "Weekend Yoga Session", "Photography Walk", "Cooking Class",
        "Book Club Meeting", "Gaming Night", "Running Club",
        "Art Workshop", "Music Jam Session", "Dance Class",
        "Hiking Adventure", "Tech Meetup", "Language Exchange",
        "Board Game Night", "Wine Tasting", "Movie Marathon",
        "Meditation Retreat", "Fitness Bootcamp", "Poetry Reading",
        "Startup Pitch Event", "Charity Run", "Beach Volleyball",
        "Rock Climbing Session", "Tennis Tournament", "Soccer Match"
    ]
    
    events = []
    start_date = datetime.utcnow() - timedelta(days=60)
    end_date = datetime.utcnow() + timedelta(days=30)
    
    for i in range(NUM_EVENTS):
        host = random.choice(hosts)
        city = random.choice(CITIES)
        event_date = random_date(start_date, end_date)
        
        base_price = random.uniform(0, 100)
        capacity = random.choice([10, 20, 30, 50, 100, 200])
        
        event = {
            "id": i + 1,
            "title": random.choice(event_titles) + f" #{i+1}",
            "description": f"Join us for an amazing {random.choice(CATEGORIES)} event!",
            "host_id": host["id"],
            "category": random.choice(CATEGORIES),
            "latitude": city["lat"] + random.uniform(-0.05, 0.05),
            "longitude": city["lng"] + random.uniform(-0.05, 0.05),
            "city": city["name"],
            "event_date": event_date.isoformat(),
            "duration_hours": random.choice([1, 2, 3, 4]),
            "capacity": capacity,
            "current_attendees": random.randint(0, capacity),
            "base_price": round(base_price, 2),
            "current_price": round(base_price * random.uniform(0.8, 1.5), 2),
            "is_active": random.random() < 0.9,
            "is_online": random.random() < 0.3,
            "created_at": (event_date - timedelta(days=random.randint(7, 30))).isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        events.append(event)
    
    return events


def generate_interactions(users: List[Dict], events: List[Dict]) -> List[Dict[str, Any]]:
    """Generate user-event interactions"""
    interaction_types = ["view", "click", "bookmark", "register", "attend", "review"]
    interactions = []
    
    start_date = datetime.utcnow() - timedelta(days=90)
    end_date = datetime.utcnow()
    
    for i in range(NUM_INTERACTIONS):
        user = random.choice(users)
        event = random.choice(events)
        
        # Weighted interaction types (more views than registers)
        int_type = random.choices(
            interaction_types,
            weights=[40, 25, 10, 15, 8, 2]
        )[0]
        
        interaction = {
            "id": i + 1,
            "user_id": user["id"],
            "event_id": event["id"],
            "interaction_type": int_type,
            "rating": random.randint(1, 5) if int_type == "review" else None,
            "timestamp": random_date(start_date, end_date).isoformat()
        }
        interactions.append(interaction)
    
    return interactions


def generate_timeseries_daily(events: List[Dict]) -> List[Dict[str, Any]]:
    """Generate daily time series data"""
    timeseries = []
    start_date = datetime.utcnow() - timedelta(days=NUM_DAYS)
    
    for day_offset in range(NUM_DAYS):
        current_date = start_date + timedelta(days=day_offset)
        
        # Base values with weekly seasonality
        weekday = current_date.weekday()
        is_weekend = weekday >= 5
        
        base_visits = 1000 * (1.5 if is_weekend else 1.0)
        base_registrations = 100 * (1.8 if is_weekend else 1.0)
        base_revenue = 5000 * (1.6 if is_weekend else 1.0)
        
        # Add noise and trend
        trend_factor = 1 + (day_offset / NUM_DAYS) * 0.3  # 30% growth
        noise = random.uniform(0.8, 1.2)
        
        record = {
            "date": current_date.date().isoformat(),
            "total_visits": int(base_visits * trend_factor * noise),
            "unique_visitors": int(base_visits * 0.7 * trend_factor * noise),
            "registrations": int(base_registrations * trend_factor * noise),
            "events_created": random.randint(3, 15),
            "events_completed": random.randint(2, 10),
            "total_revenue": round(base_revenue * trend_factor * noise, 2),
            "active_users": random.randint(500, 1500),
            "new_users": random.randint(10, 50)
        }
        timeseries.append(record)
    
    return timeseries


def generate_timeseries_hourly() -> List[Dict[str, Any]]:
    """Generate hourly time series data (last 7 days)"""
    timeseries = []
    start_date = datetime.utcnow() - timedelta(days=7)
    
    for hour_offset in range(7 * 24):
        current_time = start_date + timedelta(hours=hour_offset)
        hour = current_time.hour
        
        # Hour-based patterns (peak at evening hours)
        if 9 <= hour <= 12:
            hour_factor = 1.0
        elif 13 <= hour <= 17:
            hour_factor = 1.2
        elif 18 <= hour <= 22:
            hour_factor = 1.8
        elif 23 <= hour or hour <= 5:
            hour_factor = 0.3
        else:
            hour_factor = 0.7
        
        noise = random.uniform(0.8, 1.2)
        
        record = {
            "timestamp": current_time.isoformat(),
            "visits": int(50 * hour_factor * noise),
            "api_calls": int(200 * hour_factor * noise),
            "errors": random.randint(0, 5),
            "avg_response_time_ms": round(random.uniform(50, 200), 2)
        }
        timeseries.append(record)
    
    return timeseries


def generate_reward_coupons(users: List[Dict]) -> List[Dict[str, Any]]:
    """Generate reward coupons"""
    coupon_types = ["percentage", "fixed", "free_entry"]
    
    coupons = []
    for i in range(NUM_COUPONS):
        user = random.choice(users)
        coupon_type = random.choice(coupon_types)
        
        if coupon_type == "percentage":
            value = random.choice([10, 15, 20, 25, 30])
        elif coupon_type == "fixed":
            value = random.choice([5, 10, 15, 20, 25])
        else:
            value = 100
        
        expires = datetime.utcnow() + timedelta(days=random.randint(7, 90))
        
        coupon = {
            "id": i + 1,
            "user_id": user["id"],
            "code": f"KUMELE{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}",
            "type": coupon_type,
            "value": value,
            "min_order_value": random.choice([0, 10, 20, 50]),
            "max_uses": random.choice([1, 3, 5]),
            "current_uses": 0,
            "is_active": random.random() < 0.9,
            "expires_at": expires.isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        coupons.append(coupon)
    
    return coupons


def save_csv(data: List[Dict], filename: str, output_dir: str):
    """Save data to CSV file"""
    if not data:
        return
    
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    
    print(f"  Created: {filename} ({len(data)} records)")


def save_json(data: Any, filename: str, output_dir: str):
    """Save data to JSON file"""
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print(f"  Created: {filename}")


def create_manifest(output_dir: str, counts: Dict[str, int]) -> Dict:
    """Create manifest.json"""
    manifest = {
        "generated_at": datetime.utcnow().isoformat(),
        "generator_version": "1.0.0",
        "files": {
            "users.csv": {
                "records": counts["users"],
                "description": "User profiles with hobbies and locations"
            },
            "events.csv": {
                "records": counts["events"],
                "description": "Event data with pricing and capacity"
            },
            "interactions.csv": {
                "records": counts["interactions"],
                "description": "User-event interactions (views, clicks, registrations)"
            },
            "timeseries_daily.csv": {
                "records": counts["daily"],
                "description": "Daily platform metrics"
            },
            "timeseries_hourly.csv": {
                "records": counts["hourly"],
                "description": "Hourly platform metrics (last 7 days)"
            },
            "reward_coupons.csv": {
                "records": counts["coupons"],
                "description": "Reward coupons for users"
            }
        },
        "config": {
            "num_users": NUM_USERS,
            "num_events": NUM_EVENTS,
            "num_interactions": NUM_INTERACTIONS,
            "num_days": NUM_DAYS,
            "num_coupons": NUM_COUPONS
        }
    }
    
    save_json(manifest, "manifest.json", output_dir)
    return manifest


def create_readme(output_dir: str):
    """Create README.md for the generated data"""
    readme = """# Kumele AI/ML Synthetic Data

This directory contains synthetic data generated for testing and development.

## Files

| File | Description |
|------|-------------|
| `users.csv` | User profiles with hobbies, locations, and reward tiers |
| `events.csv` | Event data including pricing, capacity, and categories |
| `interactions.csv` | User-event interactions (views, clicks, bookmarks, registrations) |
| `timeseries_daily.csv` | Daily platform metrics for forecasting |
| `timeseries_hourly.csv` | Hourly metrics (last 7 days) |
| `reward_coupons.csv` | Generated reward coupons |
| `manifest.json` | Metadata about generated files |

## Loading Data

### Using Python/Pandas

```python
import pandas as pd

users = pd.read_csv("users.csv")
events = pd.read_csv("events.csv")
interactions = pd.read_csv("interactions.csv")
```

### Using the Generator to Push to PostgreSQL

```bash
python generate_data.py --push-to-db
```

Make sure to set the `DATABASE_URL` environment variable first.

## Data Schema

### Users
- `id`: Unique user ID
- `name`: Full name
- `email`: Email address
- `latitude`, `longitude`: Location coordinates
- `city`: City name
- `preferred_language`: ISO language code
- `reward_tier`: bronze/silver/gold/platinum
- `is_host`: Whether user is an event host
- `is_active`: Account status
- `hobbies`: Comma-separated list of hobbies
- `created_at`, `updated_at`: Timestamps

### Events
- `id`: Unique event ID
- `title`, `description`: Event details
- `host_id`: Reference to user
- `category`: Event category
- `latitude`, `longitude`, `city`: Location
- `event_date`: When the event occurs
- `duration_hours`: Event duration
- `capacity`: Maximum attendees
- `current_attendees`: Current count
- `base_price`, `current_price`: Pricing
- `is_active`, `is_online`: Status flags

### Interactions
- `id`: Unique interaction ID
- `user_id`, `event_id`: References
- `interaction_type`: view/click/bookmark/register/attend/review
- `rating`: 1-5 rating (for reviews only)
- `timestamp`: When interaction occurred

## Notes

- All timestamps are in UTC ISO format
- User locations have small random offsets from city centers
- Interaction types have realistic frequency distribution
- Time series data includes weekly seasonality patterns
"""
    
    filepath = os.path.join(output_dir, "README.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(readme)
    
    print(f"  Created: README.md")


def push_to_database(
    users: List[Dict],
    events: List[Dict],
    interactions: List[Dict],
    coupons: List[Dict]
):
    """Push generated data to PostgreSQL via SQLAlchemy"""
    try:
        from kumele_ai.db.database import SessionLocal, engine
        from kumele_ai.db import models
        from sqlalchemy import text
        
        print("\nPushing data to PostgreSQL...")
        
        db = SessionLocal()
        
        # Clear existing data (optional - be careful in production!)
        print("  Clearing existing data...")
        db.execute(text("TRUNCATE users, events, user_activities, reward_coupons CASCADE"))
        db.commit()
        
        # Insert users
        print(f"  Inserting {len(users)} users...")
        for u in users:
            user = models.User(
                id=u["id"],
                name=u["name"],
                email=u["email"],
                latitude=u["latitude"],
                longitude=u["longitude"],
                preferred_language=u["preferred_language"],
                reward_tier=u["reward_tier"],
                is_host=u["is_host"],
                is_active=u["is_active"],
                created_at=datetime.fromisoformat(u["created_at"]),
                updated_at=datetime.fromisoformat(u["updated_at"])
            )
            db.add(user)
        db.commit()
        
        # Insert hobbies and user_hobbies
        hobby_map = {}
        for u in users:
            for hobby_name in u["hobbies"].split(","):
                if hobby_name not in hobby_map:
                    hobby = models.Hobby(
                        name=hobby_name,
                        category=random.choice(CATEGORIES)
                    )
                    db.add(hobby)
                    db.flush()
                    hobby_map[hobby_name] = hobby.id
        db.commit()
        
        # Insert events
        print(f"  Inserting {len(events)} events...")
        for e in events:
            event = models.Event(
                id=e["id"],
                title=e["title"],
                description=e["description"],
                host_id=e["host_id"],
                category=e["category"],
                latitude=e["latitude"],
                longitude=e["longitude"],
                event_date=datetime.fromisoformat(e["event_date"]),
                capacity=e["capacity"],
                current_attendees=e["current_attendees"],
                base_price=e["base_price"],
                is_active=e["is_active"],
                created_at=datetime.fromisoformat(e["created_at"]),
                updated_at=datetime.fromisoformat(e["updated_at"])
            )
            db.add(event)
        db.commit()
        
        # Insert interactions as user_activities
        print(f"  Inserting {len(interactions)} interactions...")
        for i in interactions:
            activity = models.UserActivity(
                user_id=i["user_id"],
                event_id=i["event_id"],
                action_type=i["interaction_type"],
                rating=i["rating"],
                created_at=datetime.fromisoformat(i["timestamp"])
            )
            db.add(activity)
        db.commit()
        
        # Insert coupons
        print(f"  Inserting {len(coupons)} coupons...")
        for c in coupons:
            coupon = models.RewardCoupon(
                id=c["id"],
                user_id=c["user_id"],
                code=c["code"],
                type=c["type"],
                value=c["value"],
                is_used=False,
                expires_at=datetime.fromisoformat(c["expires_at"]),
                created_at=datetime.fromisoformat(c["created_at"])
            )
            db.add(coupon)
        db.commit()
        
        db.close()
        print("  Database push complete!")
        
    except ImportError as e:
        print(f"  Error: Could not import database modules. {e}")
        print("  Make sure you're running from the project directory with dependencies installed.")
    except Exception as e:
        print(f"  Error pushing to database: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic data for Kumele AI/ML"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="./synthetic_data",
        help="Output directory for generated files"
    )
    parser.add_argument(
        "--push-to-db",
        action="store_true",
        help="Push generated data to PostgreSQL"
    )
    parser.add_argument(
        "--num-users",
        type=int,
        default=NUM_USERS,
        help=f"Number of users to generate (default: {NUM_USERS})"
    )
    parser.add_argument(
        "--num-events",
        type=int,
        default=NUM_EVENTS,
        help=f"Number of events to generate (default: {NUM_EVENTS})"
    )
    
    args = parser.parse_args()
    
    # Update globals if provided
    global NUM_USERS, NUM_EVENTS
    NUM_USERS = args.num_users
    NUM_EVENTS = args.num_events
    
    # Create output directory
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Generating synthetic data in: {output_dir}")
    print(f"  Users: {NUM_USERS}")
    print(f"  Events: {NUM_EVENTS}")
    print(f"  Interactions: {NUM_INTERACTIONS}")
    print()
    
    # Generate data
    print("Generating users...")
    users = generate_users()
    
    print("Generating events...")
    events = generate_events(users)
    
    print("Generating interactions...")
    interactions = generate_interactions(users, events)
    
    print("Generating daily time series...")
    daily = generate_timeseries_daily(events)
    
    print("Generating hourly time series...")
    hourly = generate_timeseries_hourly()
    
    print("Generating reward coupons...")
    coupons = generate_reward_coupons(users)
    
    # Save files
    print("\nSaving files...")
    save_csv(users, "users.csv", output_dir)
    save_csv(events, "events.csv", output_dir)
    save_csv(interactions, "interactions.csv", output_dir)
    save_csv(daily, "timeseries_daily.csv", output_dir)
    save_csv(hourly, "timeseries_hourly.csv", output_dir)
    save_csv(coupons, "reward_coupons.csv", output_dir)
    
    # Create manifest and readme
    counts = {
        "users": len(users),
        "events": len(events),
        "interactions": len(interactions),
        "daily": len(daily),
        "hourly": len(hourly),
        "coupons": len(coupons)
    }
    create_manifest(output_dir, counts)
    create_readme(output_dir)
    
    print(f"\nGeneration complete!")
    
    # Push to database if requested
    if args.push_to_db:
        push_to_database(users, events, interactions, coupons)


if __name__ == "__main__":
    main()
