#!/usr/bin/env python3
"""
Database Seeder for Kumele AI/ML

A comprehensive script to populate the database with synthetic data for testing.
This is separate from generate_data.py to focus on direct database insertion.

Usage:
    # From project root with venv activated:
    python scripts/seed_database.py
    
    # Or via docker:
    docker-compose exec api python scripts/seed_database.py
    
    # With options:
    python scripts/seed_database.py --users 500 --events 200 --clear

Features:
    - Creates realistic users with hobbies and locations
    - Creates events with proper host relationships
    - Creates interactions, ratings, and bookings
    - Seeds taxonomy (interests) and i18n strings
    - Seeds timeseries data for dashboards
    - Seeds reward coupons
    - Seeds attendance profiles and trust profiles
"""
import argparse
import os
import random
import string
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
DEFAULT_NUM_USERS = 200
DEFAULT_NUM_EVENTS = 100
DEFAULT_NUM_INTERACTIONS = 1000

# Data pools
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Emma", "Olivia", "Ava", "Isabella", "Sophia", "Mia", "Charlotte", "Amelia",
    "Liam", "Noah", "Oliver", "Elijah", "Lucas", "Mason", "Logan", "Alexander",
    "Mohamed", "Chen", "Wei", "Raj", "Priya", "Yuki", "Sakura", "Jin", "Fatima", "Ali"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Lee", "Kim", "Wong", "Liu", "Chen", "Patel", "Kumar", "Singh", "Tanaka", "Ahmed"
]

CITIES = [
    {"name": "New York", "lat": 40.7128, "lng": -74.0060, "country": "US"},
    {"name": "Los Angeles", "lat": 34.0522, "lng": -118.2437, "country": "US"},
    {"name": "London", "lat": 51.5074, "lng": -0.1278, "country": "GB"},
    {"name": "Paris", "lat": 48.8566, "lng": 2.3522, "country": "FR"},
    {"name": "Tokyo", "lat": 35.6762, "lng": 139.6503, "country": "JP"},
    {"name": "Dubai", "lat": 25.2048, "lng": 55.2708, "country": "AE"},
    {"name": "Sydney", "lat": -33.8688, "lng": 151.2093, "country": "AU"},
    {"name": "Berlin", "lat": 52.5200, "lng": 13.4050, "country": "DE"},
    {"name": "Toronto", "lat": 43.6532, "lng": -79.3832, "country": "CA"},
    {"name": "Singapore", "lat": 1.3521, "lng": 103.8198, "country": "SG"},
]

LANGUAGES = ["en", "es", "fr", "de", "ar", "zh", "ja", "pt", "it", "ko"]

TIERS = ["bronze", "silver", "gold", "platinum"]

CATEGORIES = [
    "music", "sports", "arts", "food", "technology",
    "outdoor", "fitness", "education", "gaming", "travel"
]

INTERESTS = [
    {"name": "Photography", "category": "arts", "icon": "📷"},
    {"name": "Hiking", "category": "outdoor", "icon": "🥾"},
    {"name": "Cooking", "category": "food", "icon": "👨‍🍳"},
    {"name": "Reading", "category": "education", "icon": "📚"},
    {"name": "Gaming", "category": "gaming", "icon": "🎮"},
    {"name": "Yoga", "category": "fitness", "icon": "🧘"},
    {"name": "Running", "category": "fitness", "icon": "🏃"},
    {"name": "Painting", "category": "arts", "icon": "🎨"},
    {"name": "Music", "category": "music", "icon": "🎵"},
    {"name": "Dancing", "category": "music", "icon": "💃"},
    {"name": "Swimming", "category": "fitness", "icon": "🏊"},
    {"name": "Cycling", "category": "fitness", "icon": "🚴"},
    {"name": "Gardening", "category": "outdoor", "icon": "🌱"},
    {"name": "Writing", "category": "arts", "icon": "✍️"},
    {"name": "Meditation", "category": "fitness", "icon": "🧘‍♂️"},
    {"name": "Rock Climbing", "category": "outdoor", "icon": "🧗"},
    {"name": "Tennis", "category": "sports", "icon": "🎾"},
    {"name": "Basketball", "category": "sports", "icon": "🏀"},
    {"name": "Soccer", "category": "sports", "icon": "⚽"},
    {"name": "Piano", "category": "music", "icon": "🎹"},
    {"name": "Guitar", "category": "music", "icon": "🎸"},
    {"name": "Coding", "category": "technology", "icon": "💻"},
    {"name": "Chess", "category": "gaming", "icon": "♟️"},
    {"name": "Board Games", "category": "gaming", "icon": "🎲"},
    {"name": "Wine Tasting", "category": "food", "icon": "🍷"},
    {"name": "Travel", "category": "travel", "icon": "✈️"},
    {"name": "Volunteering", "category": "education", "icon": "🤝"},
    {"name": "Film", "category": "arts", "icon": "🎬"},
    {"name": "Theater", "category": "arts", "icon": "🎭"},
    {"name": "Astronomy", "category": "education", "icon": "🔭"},
]

EVENT_TITLES = [
    "Weekend Yoga Session", "Photography Walk", "Cooking Class: Italian Cuisine",
    "Book Club Meeting", "Gaming Night", "Morning Running Club",
    "Art Workshop: Watercolors", "Live Music Jam Session", "Salsa Dance Class",
    "Hiking Adventure", "Tech Meetup: AI/ML", "Language Exchange",
    "Board Game Night", "Wine Tasting Evening", "Movie Marathon",
    "Meditation Retreat", "Fitness Bootcamp", "Poetry Reading",
    "Startup Pitch Night", "Beach Volleyball", "Rock Climbing Session",
    "Tennis Tournament", "Soccer Match", "Piano Recital", "Guitar Workshop"
]

I18N_SCOPES = ["common", "events", "profile", "auth", "settings", "chat", "ads", "moderation"]

# Common translations for seeding
I18N_STRINGS = {
    "common": {
        "welcome": {"en": "Welcome", "es": "Bienvenido", "fr": "Bienvenue", "de": "Willkommen"},
        "search": {"en": "Search", "es": "Buscar", "fr": "Rechercher", "de": "Suchen"},
        "home": {"en": "Home", "es": "Inicio", "fr": "Accueil", "de": "Startseite"},
        "profile": {"en": "Profile", "es": "Perfil", "fr": "Profil", "de": "Profil"},
        "settings": {"en": "Settings", "es": "Configuración", "fr": "Paramètres", "de": "Einstellungen"},
        "logout": {"en": "Logout", "es": "Cerrar sesión", "fr": "Déconnexion", "de": "Abmelden"},
        "save": {"en": "Save", "es": "Guardar", "fr": "Enregistrer", "de": "Speichern"},
        "cancel": {"en": "Cancel", "es": "Cancelar", "fr": "Annuler", "de": "Abbrechen"},
    },
    "events": {
        "create_event": {"en": "Create Event", "es": "Crear Evento", "fr": "Créer un événement", "de": "Event erstellen"},
        "join_event": {"en": "Join Event", "es": "Unirse al Evento", "fr": "Rejoindre", "de": "Beitreten"},
        "event_details": {"en": "Event Details", "es": "Detalles del Evento", "fr": "Détails de l'événement", "de": "Event Details"},
        "attendees": {"en": "Attendees", "es": "Asistentes", "fr": "Participants", "de": "Teilnehmer"},
        "date_time": {"en": "Date & Time", "es": "Fecha y Hora", "fr": "Date et Heure", "de": "Datum & Zeit"},
    },
    "auth": {
        "login": {"en": "Login", "es": "Iniciar sesión", "fr": "Connexion", "de": "Anmelden"},
        "register": {"en": "Register", "es": "Registrarse", "fr": "S'inscrire", "de": "Registrieren"},
        "forgot_password": {"en": "Forgot Password?", "es": "¿Olvidaste tu contraseña?", "fr": "Mot de passe oublié?", "de": "Passwort vergessen?"},
        "email": {"en": "Email", "es": "Correo electrónico", "fr": "E-mail", "de": "E-Mail"},
        "password": {"en": "Password", "es": "Contraseña", "fr": "Mot de passe", "de": "Passwort"},
    }
}


def random_date(start: datetime, end: datetime) -> datetime:
    """Generate random datetime between start and end"""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def random_email(first: str, last: str) -> str:
    """Generate email from name"""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "mail.com", "icloud.com"]
    clean = f"{first.lower()}.{last.lower()}".replace("'", "")
    suffix = random.randint(1, 999)
    return f"{clean}{suffix}@{random.choice(domains)}"


def generate_device_fingerprint() -> str:
    """Generate a mock device fingerprint"""
    return f"fp_{uuid4().hex[:24]}"


def seed_database(
    num_users: int = DEFAULT_NUM_USERS,
    num_events: int = DEFAULT_NUM_EVENTS,
    num_interactions: int = DEFAULT_NUM_INTERACTIONS,
    clear_existing: bool = False
):
    """Main seeding function"""
    try:
        from kumele_ai.db.database import SessionLocal, engine
        from kumele_ai.db import models
        from sqlalchemy import text
    except ImportError as e:
        print(f"Error importing database modules: {e}")
        print("Make sure you're running from the project root with dependencies installed.")
        sys.exit(1)
    
    print("=" * 60)
    print("Kumele Database Seeder")
    print("=" * 60)
    print(f"Users: {num_users}")
    print(f"Events: {num_events}")
    print(f"Interactions: {num_interactions}")
    print()
    
    db = SessionLocal()
    
    try:
        if clear_existing:
            print("Clearing existing data...")
            # Order matters due to foreign keys
            tables_to_clear = [
                "no_show_predictions", "user_attendance_profile", "event_category_noshow_stats",
                "attendance_verifications", "qr_scan_log", "device_fingerprints", "user_trust_profile",
                "timeseries_hourly", "timeseries_daily",
                "i18n_strings", "i18n_scopes",
                "interest_translations", "interest_taxonomy",
                "user_activities", "reward_coupons", "events", "user_hobbies", "hobbies", "users"
            ]
            for table in tables_to_clear:
                try:
                    db.execute(text(f"TRUNCATE {table} CASCADE"))
                except Exception:
                    pass  # Table might not exist
            db.commit()
            print("  Done clearing tables")
        
        # =====================================================================
        # 1. Seed Interest Taxonomy
        # =====================================================================
        print("\n1. Seeding Interest Taxonomy...")
        interest_map = {}
        for idx, interest in enumerate(INTERESTS, 1):
            taxonomy = models.InterestTaxonomy(
                id=idx,
                canonical_name=interest["name"],
                category=interest["category"],
                icon_emoji=interest["icon"],
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(taxonomy)
            interest_map[interest["name"]] = idx
        db.commit()
        print(f"  Created {len(INTERESTS)} interests")
        
        # Add translations for interests
        for interest_id, interest in enumerate(INTERESTS, 1):
            for lang in ["en", "es", "fr", "de"]:
                trans = models.InterestTranslation(
                    interest_id=interest_id,
                    language=lang,
                    translated_name=interest["name"],  # Same for now, could translate
                    is_approved=True,
                    created_at=datetime.utcnow()
                )
                db.add(trans)
        db.commit()
        print(f"  Created interest translations")
        
        # =====================================================================
        # 2. Seed i18n Scopes and Strings
        # =====================================================================
        print("\n2. Seeding i18n...")
        scope_map = {}
        for idx, scope in enumerate(I18N_SCOPES, 1):
            i18n_scope = models.I18nScope(
                id=idx,
                scope_name=scope,
                description=f"{scope.title()} scope translations",
                created_at=datetime.utcnow()
            )
            db.add(i18n_scope)
            scope_map[scope] = idx
        db.commit()
        
        string_count = 0
        for scope, keys in I18N_STRINGS.items():
            scope_id = scope_map.get(scope)
            if not scope_id:
                continue
            for key, translations in keys.items():
                for lang, value in translations.items():
                    i18n_string = models.I18nString(
                        scope_id=scope_id,
                        language=lang,
                        key=key,
                        value=value,
                        is_approved=True,
                        created_at=datetime.utcnow()
                    )
                    db.add(i18n_string)
                    string_count += 1
        db.commit()
        print(f"  Created {len(I18N_SCOPES)} scopes, {string_count} strings")
        
        # =====================================================================
        # 3. Seed Users
        # =====================================================================
        print(f"\n3. Seeding {num_users} users...")
        users = []
        created_start = datetime.utcnow() - timedelta(days=365)
        created_end = datetime.utcnow()
        
        for i in range(1, num_users + 1):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            city = random.choice(CITIES)
            
            user = models.User(
                id=i,
                name=f"{first} {last}",
                email=random_email(first, last),
                latitude=city["lat"] + random.uniform(-0.1, 0.1),
                longitude=city["lng"] + random.uniform(-0.1, 0.1),
                preferred_language=random.choice(LANGUAGES),
                reward_tier=random.choices(TIERS, weights=[50, 30, 15, 5])[0],
                is_host=random.random() < 0.2,
                is_active=random.random() < 0.95,
                created_at=random_date(created_start, created_end),
                updated_at=datetime.utcnow()
            )
            db.add(user)
            users.append(user)
            
            if i % 100 == 0:
                print(f"    Created {i}/{num_users} users...")
                db.flush()
        
        db.commit()
        print(f"  Created {num_users} users")
        
        # =====================================================================
        # 4. Seed Hobbies and User-Hobbies
        # =====================================================================
        print("\n4. Seeding hobbies...")
        hobby_map = {}
        for idx, interest in enumerate(INTERESTS, 1):
            hobby = models.Hobby(
                id=idx,
                name=interest["name"],
                category=interest["category"]
            )
            db.add(hobby)
            hobby_map[interest["name"]] = idx
        db.commit()
        
        # Assign hobbies to users (2-5 hobbies each)
        for user in users:
            user_hobbies = random.sample(list(hobby_map.keys()), random.randint(2, 5))
            for hobby_name in user_hobbies:
                user_hobby = models.UserHobby(
                    user_id=user.id,
                    hobby_id=hobby_map[hobby_name]
                )
                db.add(user_hobby)
        db.commit()
        print(f"  Created {len(INTERESTS)} hobbies with user assignments")
        
        # =====================================================================
        # 5. Seed Events
        # =====================================================================
        print(f"\n5. Seeding {num_events} events...")
        hosts = [u for u in users if u.is_host]
        if not hosts:
            hosts = users[:20]  # Fallback
        
        events = []
        start_date = datetime.utcnow() - timedelta(days=60)
        end_date = datetime.utcnow() + timedelta(days=60)
        
        for i in range(1, num_events + 1):
            host = random.choice(hosts)
            city = random.choice(CITIES)
            event_date = random_date(start_date, end_date)
            capacity = random.choice([10, 20, 30, 50, 100])
            base_price = Decimal(str(round(random.uniform(0, 100), 2)))
            
            event = models.Event(
                id=i,
                title=f"{random.choice(EVENT_TITLES)} #{i}",
                description=f"Join us for an amazing {random.choice(CATEGORIES)} experience!",
                host_id=host.id,
                category=random.choice(CATEGORIES),
                latitude=city["lat"] + random.uniform(-0.05, 0.05),
                longitude=city["lng"] + random.uniform(-0.05, 0.05),
                event_date=event_date,
                capacity=capacity,
                current_attendees=random.randint(0, capacity),
                base_price=base_price,
                is_active=random.random() < 0.9,
                created_at=event_date - timedelta(days=random.randint(7, 30)),
                updated_at=datetime.utcnow()
            )
            db.add(event)
            events.append(event)
        
        db.commit()
        print(f"  Created {num_events} events")
        
        # =====================================================================
        # 6. Seed User Activities (Interactions)
        # =====================================================================
        print(f"\n6. Seeding {num_interactions} interactions...")
        interaction_types = ["view", "click", "bookmark", "register", "attend", "review"]
        
        for i in range(num_interactions):
            user = random.choice(users)
            event = random.choice(events)
            action_type = random.choices(interaction_types, weights=[40, 25, 10, 15, 8, 2])[0]
            
            activity = models.UserActivity(
                user_id=user.id,
                event_id=event.id,
                action_type=action_type,
                rating=random.randint(1, 5) if action_type == "review" else None,
                created_at=random_date(
                    datetime.utcnow() - timedelta(days=90),
                    datetime.utcnow()
                )
            )
            db.add(activity)
            
            if (i + 1) % 500 == 0:
                print(f"    Created {i + 1}/{num_interactions} interactions...")
                db.flush()
        
        db.commit()
        print(f"  Created {num_interactions} interactions")
        
        # =====================================================================
        # 7. Seed Reward Coupons
        # =====================================================================
        print("\n7. Seeding reward coupons...")
        coupon_count = num_users // 5
        
        for i in range(coupon_count):
            user = random.choice(users)
            coupon_type = random.choice(["percentage", "fixed", "free_entry"])
            
            if coupon_type == "percentage":
                value = Decimal(random.choice([10, 15, 20, 25, 30]))
            elif coupon_type == "fixed":
                value = Decimal(random.choice([5, 10, 15, 20]))
            else:
                value = Decimal(100)
            
            coupon = models.RewardCoupon(
                user_id=user.id,
                code=f"KUMELE{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}",
                type=coupon_type,
                value=value,
                is_used=random.random() < 0.3,
                expires_at=datetime.utcnow() + timedelta(days=random.randint(7, 90)),
                created_at=datetime.utcnow()
            )
            db.add(coupon)
        
        db.commit()
        print(f"  Created {coupon_count} coupons")
        
        # =====================================================================
        # 8. Seed Timeseries Data
        # =====================================================================
        print("\n8. Seeding timeseries data...")
        
        # Daily data (90 days)
        start_date = datetime.utcnow() - timedelta(days=90)
        for day_offset in range(90):
            current_date = start_date + timedelta(days=day_offset)
            weekday = current_date.weekday()
            is_weekend = weekday >= 5
            
            base_visits = 1000 * (1.5 if is_weekend else 1.0)
            trend_factor = 1 + (day_offset / 90) * 0.3
            noise = random.uniform(0.8, 1.2)
            
            daily = models.TimeseriesDaily(
                date=current_date.date(),
                total_visits=int(base_visits * trend_factor * noise),
                unique_visitors=int(base_visits * 0.7 * trend_factor * noise),
                registrations=int(100 * (1.8 if is_weekend else 1.0) * trend_factor * noise),
                events_created=random.randint(3, 15),
                events_completed=random.randint(2, 10),
                total_revenue=Decimal(str(round(5000 * trend_factor * noise, 2))),
                active_users=random.randint(500, 1500),
                new_users=random.randint(10, 50)
            )
            db.add(daily)
        
        # Hourly data (7 days)
        start_hour = datetime.utcnow() - timedelta(days=7)
        for hour_offset in range(7 * 24):
            current_time = start_hour + timedelta(hours=hour_offset)
            hour = current_time.hour
            
            if 9 <= hour <= 12:
                hour_factor = 1.0
            elif 13 <= hour <= 17:
                hour_factor = 1.2
            elif 18 <= hour <= 22:
                hour_factor = 1.8
            elif hour >= 23 or hour <= 5:
                hour_factor = 0.3
            else:
                hour_factor = 0.7
            
            noise = random.uniform(0.8, 1.2)
            
            hourly = models.TimeseriesHourly(
                timestamp=current_time,
                visits=int(50 * hour_factor * noise),
                api_calls=int(200 * hour_factor * noise),
                errors=random.randint(0, 5),
                avg_response_time_ms=Decimal(str(round(random.uniform(50, 200), 2)))
            )
            db.add(hourly)
        
        db.commit()
        print(f"  Created 90 daily records, {7*24} hourly records")
        
        # =====================================================================
        # 9. Seed User Attendance Profiles (for No-Show prediction)
        # =====================================================================
        print("\n9. Seeding attendance profiles...")
        for user in users:
            profile = models.UserAttendanceProfile(
                user_id=user.id,
                total_bookings=random.randint(0, 50),
                total_attendances=random.randint(0, 45),
                total_no_shows=random.randint(0, 5),
                late_cancellations=random.randint(0, 3),
                avg_booking_lead_days=Decimal(str(round(random.uniform(1, 14), 2))),
                last_booking_at=random_date(
                    datetime.utcnow() - timedelta(days=60),
                    datetime.utcnow()
                ),
                updated_at=datetime.utcnow()
            )
            db.add(profile)
        
        db.commit()
        print(f"  Created {num_users} attendance profiles")
        
        # =====================================================================
        # 10. Seed User Trust Profiles (for Attendance Verification)
        # =====================================================================
        print("\n10. Seeding trust profiles...")
        for user in users:
            trust = models.UserTrustProfile(
                user_id=user.id,
                trust_score=Decimal(str(round(random.uniform(0.5, 1.0), 2))),
                total_check_ins=random.randint(0, 30),
                valid_check_ins=random.randint(0, 28),
                suspicious_check_ins=random.randint(0, 2),
                fraudulent_check_ins=0,
                support_overrides=random.randint(0, 1),
                last_check_in_at=random_date(
                    datetime.utcnow() - timedelta(days=30),
                    datetime.utcnow()
                ),
                updated_at=datetime.utcnow()
            )
            db.add(trust)
        
        db.commit()
        print(f"  Created {num_users} trust profiles")
        
        # =====================================================================
        # 11. Seed Device Fingerprints
        # =====================================================================
        print("\n11. Seeding device fingerprints...")
        device_count = 0
        for user in users:
            # Each user has 1-3 devices
            num_devices = random.randint(1, 3)
            for _ in range(num_devices):
                device = models.DeviceFingerprint(
                    user_id=user.id,
                    fingerprint_hash=generate_device_fingerprint(),
                    device_type=random.choice(["mobile", "tablet", "desktop"]),
                    first_seen_at=random_date(
                        datetime.utcnow() - timedelta(days=180),
                        datetime.utcnow()
                    ),
                    last_seen_at=datetime.utcnow(),
                    times_seen=random.randint(1, 50),
                    is_trusted=random.random() < 0.9
                )
                db.add(device)
                device_count += 1
        
        db.commit()
        print(f"  Created {device_count} device fingerprints")
        
        # =====================================================================
        # Done!
        # =====================================================================
        print("\n" + "=" * 60)
        print("✅ Database seeding complete!")
        print("=" * 60)
        print(f"""
Summary:
  - {len(INTERESTS)} interests (taxonomy)
  - {string_count} i18n strings
  - {num_users} users
  - {len(INTERESTS)} hobbies
  - {num_events} events
  - {num_interactions} interactions
  - {coupon_count} reward coupons
  - 90 days of daily timeseries
  - 7 days of hourly timeseries
  - {num_users} attendance profiles
  - {num_users} trust profiles
  - {device_count} device fingerprints
        """)
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Seed Kumele database with synthetic data"
    )
    parser.add_argument(
        "--users", "-u",
        type=int,
        default=DEFAULT_NUM_USERS,
        help=f"Number of users (default: {DEFAULT_NUM_USERS})"
    )
    parser.add_argument(
        "--events", "-e",
        type=int,
        default=DEFAULT_NUM_EVENTS,
        help=f"Number of events (default: {DEFAULT_NUM_EVENTS})"
    )
    parser.add_argument(
        "--interactions", "-i",
        type=int,
        default=DEFAULT_NUM_INTERACTIONS,
        help=f"Number of interactions (default: {DEFAULT_NUM_INTERACTIONS})"
    )
    parser.add_argument(
        "--clear", "-c",
        action="store_true",
        help="Clear existing data before seeding"
    )
    
    args = parser.parse_args()
    
    seed_database(
        num_users=args.users,
        num_events=args.events,
        num_interactions=args.interactions,
        clear_existing=args.clear
    )


if __name__ == "__main__":
    main()
