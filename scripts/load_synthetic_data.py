#!/usr/bin/env python3
"""
Kumele Synthetic Data Loader
=============================

Generates and loads synthetic data directly into PostgreSQL.
Run this script inside the kumele-api container.

Usage:
------
docker exec -it kumele-api python scripts/load_synthetic_data.py --users 500 --events 200

This will:
1. Generate synthetic data matching the database schema
2. Insert directly into PostgreSQL tables
3. Print progress and statistics
"""

import argparse
import random
import hashlib
import asyncio
import sys
import os
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict, Any
import uuid

# Add app to path
sys.path.insert(0, '/app')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://kumele:kumele_password@postgres:5432/kumele_db")

HOBBIES = [
    ("fitness", "Fitness & Gym", "sports"),
    ("yoga", "Yoga & Meditation", "wellness"),
    ("running", "Running & Jogging", "sports"),
    ("cycling", "Cycling", "sports"),
    ("swimming", "Swimming", "sports"),
    ("basketball", "Basketball", "sports"),
    ("football", "Football/Soccer", "sports"),
    ("tennis", "Tennis", "sports"),
    ("hiking", "Hiking & Trekking", "outdoor"),
    ("photography", "Photography", "arts"),
    ("music", "Music & Instruments", "arts"),
    ("cooking", "Cooking & Baking", "lifestyle"),
    ("gaming", "Video Gaming", "entertainment"),
    ("reading", "Reading & Books", "education"),
    ("travel", "Travel & Exploration", "lifestyle"),
    ("tech", "Technology & Coding", "tech"),
    ("crypto", "Crypto & Web3", "tech"),
    ("art", "Art & Design", "arts"),
    ("movies", "Movies & Cinema", "entertainment"),
    ("wine", "Wine & Spirits", "lifestyle"),
]

CITIES = [
    ("New York", "NY", "USA", 40.7128, -74.0060),
    ("Los Angeles", "CA", "USA", 34.0522, -118.2437),
    ("Chicago", "IL", "USA", 41.8781, -87.6298),
    ("Miami", "FL", "USA", 25.7617, -80.1918),
    ("San Francisco", "CA", "USA", 37.7749, -122.4194),
    ("Austin", "TX", "USA", 30.2672, -97.7431),
    ("Seattle", "WA", "USA", 47.6062, -122.3321),
    ("Denver", "CO", "USA", 39.7392, -104.9903),
    ("Boston", "MA", "USA", 42.3601, -71.0589),
    ("Atlanta", "GA", "USA", 33.7490, -84.3880),
]

EVENT_TYPES = ["social", "sports", "music", "food", "tech", "art", "outdoor", "wellness", "networking", "gaming"]

FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth",
               "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen",
               "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery", "Peyton", "Dakota"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]


def generate_wallet_address() -> str:
    """Generate a fake Solana wallet address."""
    chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return "".join(random.choices(chars, k=44))


def generate_hash(text: str) -> str:
    """Generate a hash for text."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def create_tables(engine):
    """Create additional tables and add missing columns to existing tables."""
    async with engine.begin() as conn:
        # Add missing columns to users table (if they don't exist)
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reward_tier TEXT DEFAULT 'none'"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_language TEXT DEFAULT 'en'"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lat NUMERIC(10,7)"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS location_lon NUMERIC(10,7)"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT"))
            print("✓ Users table columns verified/added")
        except Exception as e:
            print(f"  Note: Users columns may already exist: {e}")
        
        # Add missing columns to events table (if they don't exist)
        try:
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS moderation_status TEXT DEFAULT 'pending'"))
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en'"))
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS has_discount BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS is_sponsored BOOLEAN DEFAULT FALSE"))
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS category TEXT"))
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS location TEXT"))
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS location_lat NUMERIC(10,7)"))
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS location_lon NUMERIC(10,7)"))
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS tags TEXT[]"))
            print("✓ Events table columns verified/added")
        except Exception as e:
            print(f"  Note: Events columns may already exist: {e}")
        
        # Blogs table (if not exists)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS blogs (
                blog_id SERIAL PRIMARY KEY,
                author_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content TEXT,
                category TEXT,
                tags TEXT[],
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                published_at TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # Blog interactions
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS blog_interactions (
                id SERIAL PRIMARY KEY,
                blog_id INTEGER REFERENCES blogs(blog_id) ON DELETE CASCADE,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                interaction_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # User wallets
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_wallets (
                wallet_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                wallet_address TEXT UNIQUE NOT NULL,
                wallet_type TEXT DEFAULT 'solana',
                is_primary BOOLEAN DEFAULT FALSE,
                verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # User NFTs
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_nfts (
                nft_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                wallet_id INTEGER REFERENCES user_wallets(wallet_id),
                mint_address TEXT UNIQUE NOT NULL,
                name TEXT,
                collection TEXT,
                image_url TEXT,
                rarity TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # Reward coupons
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS reward_coupons (
                coupon_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                code TEXT UNIQUE NOT NULL,
                discount_type TEXT DEFAULT 'percentage',
                discount_value NUMERIC(10, 2),
                is_used BOOLEAN DEFAULT FALSE,
                used_at TIMESTAMP,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # User activities (for retention analysis)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_activities (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                activity_type TEXT NOT NULL,
                activity_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        print("✓ Additional tables created/verified")


async def load_data(args):
    """Generate and load synthetic data."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    print("\n" + "=" * 60)
    print("Kumele Synthetic Data Loader")
    print("=" * 60)
    print(f"Users: {args.users}")
    print(f"Events: {args.events}")
    print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print("=" * 60 + "\n")
    
    random.seed(args.seed)
    now = datetime.utcnow()
    
    async with async_session() as session:
        try:
            # Create additional tables
            await create_tables(engine)
            
            # 1. Load interest taxonomy (hobbies) - uses VARCHAR interest_id
            print("Loading interest taxonomy...")
            hobby_slugs = []  # Store slugs for later use
            for slug, name, category in HOBBIES:
                await session.execute(text("""
                    INSERT INTO interest_taxonomy (interest_id, parent_id, level, is_active)
                    VALUES (:interest_id, :parent_id, :level, :is_active)
                    ON CONFLICT (interest_id) DO NOTHING
                """), {
                    "interest_id": slug,  # Use slug as interest_id (VARCHAR)
                    "parent_id": category,  # Use category as parent
                    "level": 1,
                    "is_active": True
                })
                hobby_slugs.append(slug)
                
                # Also insert translation for English
                await session.execute(text("""
                    INSERT INTO interest_translations (interest_id, language_code, label, description)
                    VALUES (:interest_id, :lang, :label, :description)
                    ON CONFLICT (interest_id, language_code) DO NOTHING
                """), {
                    "interest_id": slug,
                    "lang": "en",
                    "label": name,
                    "description": f"Interest in {name.lower()}"
                })
            await session.commit()
            print(f"  ✓ {len(HOBBIES)} hobbies loaded")
            
            # 2. Generate and load users (matches actual User model)
            print("Loading users...")
            user_ids = []
            for i in range(1, args.users + 1):
                city = random.choice(CITIES)
                first_name = random.choice(FIRST_NAMES)
                last_name = random.choice(LAST_NAMES)
                email = f"{first_name.lower()}.{last_name.lower()}{i}@example.com"
                
                await session.execute(text("""
                    INSERT INTO users (user_id, name, email, age, gender, location_lat, location_lon, 
                                       preferred_language, reward_tier, created_at)
                    VALUES (:user_id, :name, :email, :age, :gender, :lat, :lon,
                            :lang, :tier, :created_at)
                    ON CONFLICT (user_id) DO NOTHING
                """), {
                    "user_id": i,
                    "name": f"{first_name} {last_name}",
                    "email": email,
                    "age": random.randint(18, 65),
                    "gender": random.choice(["male", "female", "other"]),
                    "lat": city[3] + random.uniform(-0.1, 0.1),
                    "lon": city[4] + random.uniform(-0.1, 0.1),
                    "lang": random.choice(["en", "en", "en", "es", "fr"]),
                    "tier": random.choice(["none", "none", "bronze", "silver", "gold"]),
                    "created_at": now - timedelta(days=random.randint(1, 365)),
                })
                user_ids.append(i)
            await session.commit()
            print(f"  ✓ {args.users} users loaded")
            
            # 3. Assign hobbies to users (uses hobby_id as VARCHAR)
            print("Loading user hobbies...")
            hobby_count = 0
            for user_id in user_ids:
                num_hobbies = random.randint(2, 6)
                selected_hobbies = random.sample(hobby_slugs, num_hobbies)
                for hobby_slug in selected_hobbies:
                    await session.execute(text("""
                        INSERT INTO user_hobbies (user_id, hobby_id, preference_score)
                        VALUES (:user_id, :hobby_id, :score)
                        ON CONFLICT ON CONSTRAINT uq_user_hobby DO NOTHING
                    """), {
                        "user_id": user_id,
                        "hobby_id": hobby_slug,  # VARCHAR hobby_id
                        "score": round(random.uniform(0.3, 1.0), 2)
                    })
                    hobby_count += 1
            await session.commit()
            print(f"  ✓ {hobby_count} user-hobby relationships loaded")
            
            # 4. Generate and load events (matches actual Event model)
            print("Loading events...")
            event_ids = []
            categories = ["music", "sports", "tech", "food", "art", "outdoor", "wellness", "networking"]
            for i in range(1, args.events + 1):
                city = random.choice(CITIES)
                category = random.choice(categories)
                event_date = now + timedelta(days=random.randint(-60, 90))
                
                await session.execute(text("""
                    INSERT INTO events (event_id, host_id, title, description, category, location,
                                        location_lat, location_lon, capacity, price, event_date,
                                        status, moderation_status, language, has_discount, is_sponsored, created_at)
                    VALUES (:event_id, :host_id, :title, :description, :category, :location,
                            :lat, :lon, :capacity, :price, :event_date,
                            :status, :mod_status, :lang, :discount, :sponsored, :created_at)
                    ON CONFLICT (event_id) DO NOTHING
                """), {
                    "event_id": i,
                    "host_id": random.choice(user_ids[:min(50, len(user_ids))]),
                    "title": f"{category.title()} Event #{i}",
                    "description": f"Join us for an amazing {category} experience in {city[0]}!",
                    "category": category,
                    "location": f"{city[0]} {random.choice(['Center', 'Arena', 'Park', 'Hall', 'Club'])}",
                    "lat": city[3] + random.uniform(-0.05, 0.05),
                    "lon": city[4] + random.uniform(-0.05, 0.05),
                    "capacity": random.choice([50, 100, 200, 500, 1000]),
                    "price": round(random.uniform(0, 150), 2),
                    "event_date": event_date,
                    "status": random.choice(["scheduled", "scheduled", "scheduled", "ongoing", "completed"]),
                    "mod_status": random.choice(["approved", "approved", "approved", "pending"]),
                    "lang": random.choice(["en", "en", "en", "es", "fr"]),
                    "discount": random.random() < 0.2,
                    "sponsored": random.random() < 0.1,
                    "created_at": event_date - timedelta(days=random.randint(7, 60)),
                })
                event_ids.append(i)
            await session.commit()
            print(f"  ✓ {args.events} events loaded")
            
            # 5. Generate event attendance
            print("Loading event attendance...")
            attendance_count = 0
            for event_id in event_ids:
                num_attendees = random.randint(5, 50)
                attendees = random.sample(user_ids, min(num_attendees, len(user_ids)))
                for user_id in attendees:
                    checked_in = random.random() > 0.3
                    await session.execute(text("""
                        INSERT INTO event_attendance (event_id, user_id, rsvp_status, checked_in, checked_in_at, created_at)
                        VALUES (:event_id, :user_id, :rsvp_status, :checked_in, :checked_in_at, :created_at)
                        ON CONFLICT ON CONSTRAINT uq_event_user_attendance DO NOTHING
                    """), {
                        "event_id": event_id,
                        "user_id": user_id,
                        "rsvp_status": random.choice(["confirmed", "confirmed", "confirmed", "pending", "attended"]),
                        "checked_in": checked_in,
                        "checked_in_at": now - timedelta(days=random.randint(0, 60)) if checked_in else None,
                        "created_at": now - timedelta(days=random.randint(1, 90)),
                    })
                    attendance_count += 1
            await session.commit()
            print(f"  ✓ {attendance_count} attendance records loaded")
            
            # 6. Generate event ratings
            print("Loading event ratings...")
            rating_count = 0
            for event_id in event_ids[:int(len(event_ids) * 0.7)]:  # 70% of events have ratings
                num_ratings = random.randint(3, 15)
                raters = random.sample(user_ids, min(num_ratings, len(user_ids)))
                for user_id in raters:
                    await session.execute(text("""
                        INSERT INTO event_ratings (event_id, user_id, rating, review_text, created_at)
                        VALUES (:event_id, :user_id, :rating, :review, :created_at)
                        ON CONFLICT ON CONSTRAINT uq_event_user_rating DO NOTHING
                    """), {
                        "event_id": event_id,
                        "user_id": user_id,
                        "rating": random.randint(3, 5),
                        "review": random.choice([
                            "Great event!", "Had a wonderful time.", "Would recommend!",
                            "Amazing experience.", "Well organized.", "Loved it!",
                            "Good event, will come again.", "Nice atmosphere.",
                            None, None  # Some without reviews
                        ]),
                        "created_at": now - timedelta(days=random.randint(0, 60)),
                    })
                    rating_count += 1
            await session.commit()
            print(f"  ✓ {rating_count} event ratings loaded")
            
            # 7. Generate blogs
            print("Loading blogs...")
            blog_ids = []
            categories = ["lifestyle", "travel", "tech", "sports", "food", "music", "art"]
            for i in range(1, min(100, args.users // 5) + 1):
                author_id = random.choice(user_ids)
                category = random.choice(categories)
                await session.execute(text("""
                    INSERT INTO blogs (blog_id, author_id, title, content, category, view_count, like_count, published_at)
                    VALUES (:blog_id, :author_id, :title, :content, :category, :views, :likes, :published)
                    ON CONFLICT (blog_id) DO NOTHING
                """), {
                    "blog_id": i,
                    "author_id": author_id,
                    "title": f"My {category.title()} Journey #{i}",
                    "content": f"This is a blog post about {category}. " * 20,
                    "category": category,
                    "views": random.randint(10, 5000),
                    "likes": random.randint(0, 500),
                    "published": now - timedelta(days=random.randint(1, 180)),
                })
                blog_ids.append(i)
            await session.commit()
            print(f"  ✓ {len(blog_ids)} blogs loaded")
            
            # 8. Generate blog interactions
            print("Loading blog interactions...")
            interaction_count = 0
            for blog_id in blog_ids:
                num_interactions = random.randint(5, 30)
                interactors = random.sample(user_ids, min(num_interactions, len(user_ids)))
                for user_id in interactors:
                    await session.execute(text("""
                        INSERT INTO blog_interactions (blog_id, user_id, interaction_type, created_at)
                        VALUES (:blog_id, :user_id, :type, :created_at)
                    """), {
                        "blog_id": blog_id,
                        "user_id": user_id,
                        "type": random.choice(["view", "view", "view", "like", "share", "comment"]),
                        "created_at": now - timedelta(days=random.randint(0, 90)),
                    })
                    interaction_count += 1
            await session.commit()
            print(f"  ✓ {interaction_count} blog interactions loaded")
            
            # 9. Generate ads
            print("Loading ads...")
            ad_ids = []
            for i in range(1, 51):
                await session.execute(text("""
                    INSERT INTO ads (ad_id, advertiser_id, title, description, target_audience, 
                                     budget, spent, status, ctr, created_at)
                    VALUES (:ad_id, :advertiser_id, :title, :description, :target, 
                            :budget, :spent, :status, :ctr, :created_at)
                    ON CONFLICT (ad_id) DO NOTHING
                """), {
                    "ad_id": i,
                    "advertiser_id": random.choice(user_ids[:20]),
                    "title": f"Amazing Product #{i}",
                    "description": f"Check out our amazing offer!",
                    "target": random.choice(["young_adults", "professionals", "fitness", "tech_savvy", "all"]),
                    "budget": round(random.uniform(100, 5000), 2),
                    "spent": round(random.uniform(0, 1000), 2),
                    "status": random.choice(["active", "active", "active", "paused", "completed"]),
                    "ctr": round(random.uniform(0.01, 0.15), 4),
                    "created_at": now - timedelta(days=random.randint(1, 90)),
                })
                ad_ids.append(i)
            await session.commit()
            print(f"  ✓ {len(ad_ids)} ads loaded")
            
            # 10. Generate ad logs
            print("Loading ad logs...")
            ad_log_count = 0
            for ad_id in ad_ids:
                num_impressions = random.randint(100, 1000)
                for _ in range(num_impressions):
                    user_id = random.choice(user_ids)
                    clicked = random.random() < 0.05
                    converted = clicked and random.random() < 0.1
                    await session.execute(text("""
                        INSERT INTO ad_logs (ad_id, user_id, event_type, created_at)
                        VALUES (:ad_id, :user_id, :event_type, :created_at)
                    """), {
                        "ad_id": ad_id,
                        "user_id": user_id,
                        "event_type": "conversion" if converted else ("click" if clicked else "impression"),
                        "created_at": now - timedelta(hours=random.randint(0, 720)),
                    })
                    ad_log_count += 1
            await session.commit()
            print(f"  ✓ {ad_log_count} ad log entries loaded")
            
            # 11. Generate wallets
            print("Loading user wallets...")
            wallet_count = 0
            wallet_ids = {}
            for user_id in random.sample(user_ids, int(len(user_ids) * 0.4)):
                await session.execute(text("""
                    INSERT INTO user_wallets (user_id, wallet_address, wallet_type, is_primary, verified)
                    VALUES (:user_id, :address, :type, :is_primary, :verified)
                    RETURNING wallet_id
                """), {
                    "user_id": user_id,
                    "address": generate_wallet_address(),
                    "type": "solana",
                    "is_primary": True,
                    "verified": random.random() > 0.3,
                })
                wallet_count += 1
            await session.commit()
            print(f"  ✓ {wallet_count} wallets loaded")
            
            # 12. Generate NFTs
            print("Loading user NFTs...")
            nft_count = 0
            collections = ["Kumele OG", "Event Pass", "Achievement Badge", "Special Edition", "Community Hero"]
            rarities = ["common", "uncommon", "rare", "epic", "legendary"]
            
            result = await session.execute(text("SELECT wallet_id, user_id FROM user_wallets"))
            wallets = result.fetchall()
            
            for wallet_id, user_id in wallets:
                num_nfts = random.randint(1, 5)
                for j in range(num_nfts):
                    await session.execute(text("""
                        INSERT INTO user_nfts (user_id, wallet_id, mint_address, name, collection, rarity)
                        VALUES (:user_id, :wallet_id, :mint, :name, :collection, :rarity)
                        ON CONFLICT (mint_address) DO NOTHING
                    """), {
                        "user_id": user_id,
                        "wallet_id": wallet_id,
                        "mint": generate_wallet_address(),
                        "name": f"NFT #{nft_count + 1}",
                        "collection": random.choice(collections),
                        "rarity": random.choices(rarities, weights=[40, 30, 20, 8, 2])[0],
                    })
                    nft_count += 1
            await session.commit()
            print(f"  ✓ {nft_count} NFTs loaded")
            
            # 13. Generate reward coupons
            print("Loading reward coupons...")
            coupon_count = 0
            for user_id in random.sample(user_ids, int(len(user_ids) * 0.3)):
                num_coupons = random.randint(1, 3)
                for _ in range(num_coupons):
                    is_used = random.random() < 0.4
                    await session.execute(text("""
                        INSERT INTO reward_coupons (user_id, code, discount_type, discount_value, 
                                                    is_used, used_at, expires_at)
                        VALUES (:user_id, :code, :type, :value, :is_used, :used_at, :expires_at)
                        ON CONFLICT (code) DO NOTHING
                    """), {
                        "user_id": user_id,
                        "code": f"KUMELE-{generate_hash(str(user_id) + str(random.random()))[:8].upper()}",
                        "type": random.choice(["percentage", "fixed"]),
                        "value": random.choice([5, 10, 15, 20, 25, 50]),
                        "is_used": is_used,
                        "used_at": now - timedelta(days=random.randint(1, 30)) if is_used else None,
                        "expires_at": now + timedelta(days=random.randint(30, 180)),
                    })
                    coupon_count += 1
            await session.commit()
            print(f"  ✓ {coupon_count} coupons loaded")
            
            # 14. Generate user activities
            print("Loading user activities...")
            activity_count = 0
            activity_types = ["login", "event_view", "event_rsvp", "blog_read", "profile_update", 
                            "message_sent", "search", "share", "purchase"]
            for user_id in user_ids:
                num_activities = random.randint(10, 100)
                for _ in range(num_activities):
                    await session.execute(text("""
                        INSERT INTO user_activities (user_id, activity_type, created_at)
                        VALUES (:user_id, :type, :created_at)
                    """), {
                        "user_id": user_id,
                        "type": random.choice(activity_types),
                        "created_at": now - timedelta(hours=random.randint(0, 2160)),  # 90 days
                    })
                    activity_count += 1
            await session.commit()
            print(f"  ✓ {activity_count} user activities loaded")
            
            # 15. Generate pricing history
            print("Loading pricing history...")
            pricing_count = 0
            categories = ["concert", "sports", "meetup", "workshop", "party"]
            for event_id in event_ids:
                num_records = random.randint(3, 10)
                for j in range(num_records):
                    original = round(random.uniform(20, 200), 2)
                    await session.execute(text("""
                        INSERT INTO pricing_history (event_id, category, original_price, final_price, 
                                                    demand_score, capacity, sold, recorded_at)
                        VALUES (:event_id, :category, :original, :final, :demand, :capacity, :sold, :recorded_at)
                    """), {
                        "event_id": event_id,
                        "category": random.choice(categories),
                        "original": original,
                        "final": round(original * random.uniform(0.7, 1.3), 2),
                        "demand": round(random.uniform(0.2, 0.95), 2),
                        "capacity": random.choice([50, 100, 200, 500]),
                        "sold": random.randint(10, 450),
                        "recorded_at": now - timedelta(days=j * 7),
                    })
                    pricing_count += 1
            await session.commit()
            print(f"  ✓ {pricing_count} pricing history records loaded")
            
            # 16. Generate messages
            print("Loading messages...")
            message_count = 0
            for _ in range(args.users * 5):
                sender = random.choice(user_ids)
                receiver = random.choice([u for u in user_ids if u != sender])
                await session.execute(text("""
                    INSERT INTO messages (sender_id, receiver_id, content, is_read, created_at)
                    VALUES (:sender, :receiver, :content, :is_read, :created_at)
                """), {
                    "sender": sender,
                    "receiver": receiver,
                    "content": random.choice([
                        "Hey! Are you going to the event?",
                        "Great meeting you yesterday!",
                        "Thanks for the recommendation!",
                        "See you there!",
                        "What time does it start?",
                        "Can't wait for the event!",
                    ]),
                    "is_read": random.random() > 0.4,
                    "created_at": now - timedelta(hours=random.randint(0, 720)),
                })
                message_count += 1
            await session.commit()
            print(f"  ✓ {message_count} messages loaded")
            
            # 17. Generate notifications
            print("Loading notifications...")
            notif_count = 0
            notif_types = ["event_reminder", "new_message", "reward_earned", "event_nearby", 
                         "friend_joined", "price_drop", "event_update"]
            for user_id in user_ids:
                num_notifs = random.randint(5, 20)
                for _ in range(num_notifs):
                    notif_type = random.choice(notif_types)
                    is_read = random.random() > 0.5
                    await session.execute(text("""
                        INSERT INTO notifications (user_id, type, title, body, is_read, opened_at, created_at)
                        VALUES (:user_id, :type, :title, :body, :is_read, :opened_at, :created_at)
                    """), {
                        "user_id": user_id,
                        "type": notif_type,
                        "title": f"{notif_type.replace('_', ' ').title()}",
                        "body": f"You have a new {notif_type.replace('_', ' ')}!",
                        "is_read": is_read,
                        "opened_at": now - timedelta(hours=random.randint(0, 48)) if is_read else None,
                        "created_at": now - timedelta(hours=random.randint(0, 168)),
                    })
                    notif_count += 1
            await session.commit()
            print(f"  ✓ {notif_count} notifications loaded")
            
            # 18. Generate UGC content for moderation
            print("Loading UGC content...")
            ugc_count = 0
            content_types = ["comment", "review", "bio", "event_description"]
            for _ in range(min(200, args.users)):
                await session.execute(text("""
                    INSERT INTO ugc_content (user_id, content_type, content, status, created_at)
                    VALUES (:user_id, :type, :content, :status, :created_at)
                """), {
                    "user_id": random.choice(user_ids),
                    "type": random.choice(content_types),
                    "content": random.choice([
                        "This is a great platform!",
                        "Amazing community here.",
                        "Looking forward to more events!",
                        "Best experience ever!",
                        "Highly recommended!",
                    ]),
                    "status": random.choice(["approved", "approved", "approved", "pending", "rejected"]),
                    "created_at": now - timedelta(days=random.randint(0, 90)),
                })
                ugc_count += 1
            await session.commit()
            print(f"  ✓ {ugc_count} UGC content items loaded")
            
            # Print summary
            print("\n" + "=" * 60)
            print("Data Loading Complete!")
            print("=" * 60)
            print(f"""
Summary:
--------
- Users: {args.users}
- Events: {args.events}
- Hobbies: {len(HOBBIES)}
- User-Hobby links: ~{hobby_count}
- Event attendance: ~{attendance_count}
- Event ratings: ~{rating_count}
- Blogs: {len(blog_ids)}
- Blog interactions: ~{interaction_count}
- Ads: {len(ad_ids)}
- Ad logs: ~{ad_log_count}
- Wallets: ~{wallet_count}
- NFTs: ~{nft_count}
- Coupons: ~{coupon_count}
- User activities: ~{activity_count}
- Pricing history: ~{pricing_count}
- Messages: ~{message_count}
- Notifications: ~{notif_count}
- UGC content: ~{ugc_count}

Your database is now populated with test data!
Try the APIs at: http://YOUR_IP:8000/docs
""")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
            raise


def main():
    parser = argparse.ArgumentParser(description="Load synthetic data into Kumele PostgreSQL")
    parser.add_argument("--users", type=int, default=500, help="Number of users (default: 500)")
    parser.add_argument("--events", type=int, default=200, help="Number of events (default: 200)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()
    
    asyncio.run(load_data(args))


if __name__ == "__main__":
    main()
