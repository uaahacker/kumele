#!/usr/bin/env python3
"""
Database Seeder for Kumele AI/ML

A comprehensive script to populate the database with synthetic data for testing.
Matches the actual ORM models defined in kumele_ai/db/models.py

Usage:
    # From project root with venv activated:
    python scripts/seed_database.py
    
    # Or via docker:
    docker-compose exec api python scripts/seed_database.py
    
    # With options:
    python scripts/seed_database.py --users 500 --events 200 --clear
"""
import argparse
import os
import random
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
DEFAULT_NUM_USERS = 200
DEFAULT_NUM_EVENTS = 100
DEFAULT_NUM_INTERACTIONS = 500

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

CATEGORIES = [
    "music", "sports", "arts", "food", "technology",
    "outdoor", "fitness", "education", "gaming", "travel"
]

INTERESTS = [
    {"name": "Photography", "category": "arts", "icon": "camera"},
    {"name": "Hiking", "category": "outdoor", "icon": "hiking"},
    {"name": "Cooking", "category": "food", "icon": "chef"},
    {"name": "Reading", "category": "education", "icon": "book"},
    {"name": "Gaming", "category": "gaming", "icon": "gamepad"},
    {"name": "Yoga", "category": "fitness", "icon": "yoga"},
    {"name": "Running", "category": "fitness", "icon": "running"},
    {"name": "Painting", "category": "arts", "icon": "palette"},
    {"name": "Music", "category": "music", "icon": "music"},
    {"name": "Dancing", "category": "music", "icon": "dance"},
    {"name": "Swimming", "category": "fitness", "icon": "swimming"},
    {"name": "Cycling", "category": "fitness", "icon": "cycling"},
    {"name": "Gardening", "category": "outdoor", "icon": "plant"},
    {"name": "Writing", "category": "arts", "icon": "pen"},
    {"name": "Meditation", "category": "fitness", "icon": "meditation"},
    {"name": "Rock Climbing", "category": "outdoor", "icon": "climbing"},
    {"name": "Tennis", "category": "sports", "icon": "tennis"},
    {"name": "Basketball", "category": "sports", "icon": "basketball"},
    {"name": "Soccer", "category": "sports", "icon": "soccer"},
    {"name": "Piano", "category": "music", "icon": "piano"},
    {"name": "Guitar", "category": "music", "icon": "guitar"},
    {"name": "Coding", "category": "technology", "icon": "code"},
    {"name": "Chess", "category": "gaming", "icon": "chess"},
    {"name": "Board Games", "category": "gaming", "icon": "dice"},
    {"name": "Wine Tasting", "category": "food", "icon": "wine"},
    {"name": "Travel", "category": "travel", "icon": "plane"},
    {"name": "Volunteering", "category": "education", "icon": "heart"},
    {"name": "Film", "category": "arts", "icon": "film"},
    {"name": "Theater", "category": "arts", "icon": "theater"},
    {"name": "Astronomy", "category": "education", "icon": "telescope"},
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
    suffix = random.randint(1, 9999)
    return f"{clean}{suffix}@{random.choice(domains)}"


def generate_password_hash() -> str:
    """Generate a fake bcrypt-like hash for seeding"""
    return f"$2b$12${uuid4().hex[:53]}"


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
        from kumele_ai.db.database import SessionLocal
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
            # Order matters due to foreign keys - child tables first
            tables_to_clear = [
                # No-show / Attendance
                "no_show_predictions", "user_attendance_profile", "event_category_noshow_stats",
                "attendance_verifications", "qr_scan_log", "device_fingerprints", "user_trust_profile",
                # Timeseries
                "timeseries_hourly", "timeseries_daily",
                # i18n
                "i18n_strings", "i18n_scopes",
                # Interests
                "interest_translations", "interest_taxonomy",
                # Pricing
                "discount_suggestions", "pricing_history",
                # Host ratings
                "host_ratings",
                # NLP
                "nlp_keywords", "nlp_sentiment",
                # AI
                "ai_action_logs", "ai_model_registry",
                # Support
                "support_email_escalations", "support_email_replies", "support_email_analysis", "support_emails",
                # Chatbot / Knowledge
                "chatbot_logs", "knowledge_embeddings", "knowledge_documents",
                # Moderation
                "moderation_jobs",
                # Rewards / Activities
                "reward_coupons", "user_activities",
                # Referrals
                "referrals",
                # Ads
                "ad_interactions", "ads",
                # Blogs
                "blog_interactions", "blogs",
                # Event ratings, user_events
                "event_ratings", "user_events",
                # Events
                "events",
                # User hobbies
                "user_hobbies",
                # Hobbies
                "hobbies",
                # Users
                "users"
            ]
            for table in tables_to_clear:
                try:
                    db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                except Exception as e:
                    pass  # Table might not exist
            db.commit()
            print("  Done clearing tables")
        
        # =====================================================================
        # 1. Seed Interest Taxonomy (uses interest_id, not id)
        # =====================================================================
        print("\n1. Seeding Interest Taxonomy...")
        for idx, interest in enumerate(INTERESTS, 1):
            taxonomy = models.InterestTaxonomy(
                interest_id=idx,
                name=interest["name"],
                category=interest["category"],
                icon_key=interest["icon"],
                color_token=f"color-{interest['category']}",
                display_order=idx,
                is_active=True,
            )
            db.add(taxonomy)
        db.commit()
        print(f"  Created {len(INTERESTS)} interests")
        
        # Add translations for interests
        for interest_id, interest in enumerate(INTERESTS, 1):
            for lang in ["en", "es", "fr", "de"]:
                trans = models.InterestTranslation(
                    interest_id=interest_id,
                    language=lang,
                    label=interest["name"],
                    description=f"{interest['name']} activities and events",
                )
                db.add(trans)
        db.commit()
        print(f"  Created interest translations")
        
        # =====================================================================
        # 2. Seed i18n Scopes and Strings
        # =====================================================================
        print("\n2. Seeding i18n...")
        scope_map = {}
        for scope in I18N_SCOPES:
            i18n_scope = models.I18nScope(
                name=scope,
                description=f"{scope.title()} scope translations",
            )
            db.add(i18n_scope)
            db.flush()  # Get the ID
            scope_map[scope] = i18n_scope.id
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
                        key=key,
                        language=lang,
                        value=value,
                        is_approved=True,
                        is_locked=False,
                    )
                    db.add(i18n_string)
                    string_count += 1
        db.commit()
        print(f"  Created {len(I18N_SCOPES)} scopes, {string_count} strings")
        
        # =====================================================================
        # 3. Seed Hobbies (based on Hobby model)
        # =====================================================================
        print("\n3. Seeding Hobbies...")
        hobby_map = {}
        for interest in INTERESTS:
            hobby = models.Hobby(
                name=interest["name"],
                category=interest["category"],
                description=f"Activities related to {interest['name']}",
            )
            db.add(hobby)
            db.flush()
            hobby_map[interest["name"]] = hobby.id
        db.commit()
        print(f"  Created {len(INTERESTS)} hobbies")
        
        # =====================================================================
        # 4. Seed Users (matches User model exactly)
        # =====================================================================
        print(f"\n4. Seeding {num_users} users...")
        users = []
        created_start = datetime.utcnow() - timedelta(days=365)
        created_end = datetime.utcnow()
        
        for i in range(num_users):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            city = random.choice(CITIES)
            
            # User model fields: username, email, password_hash, age, gender, 
            # address, latitude, longitude, city, country, is_active, created_at, updated_at
            user = models.User(
                username=f"{first.lower()}{last.lower()}{random.randint(1, 9999)}",
                email=random_email(first, last),
                password_hash=generate_password_hash(),
                age=random.randint(18, 65),
                gender=random.choice(["male", "female", "other", "prefer_not_to_say"]),
                address=f"{random.randint(1, 999)} {random.choice(['Main', 'Oak', 'Park', 'Lake', 'Hill'])} Street",
                latitude=city["lat"] + random.uniform(-0.1, 0.1),
                longitude=city["lng"] + random.uniform(-0.1, 0.1),
                city=city["name"],
                country=city["country"],
                is_active=random.random() < 0.95,
            )
            db.add(user)
            users.append(user)
            
            if (i + 1) % 100 == 0:
                print(f"    Created {i + 1}/{num_users} users...")
                db.flush()
        
        db.commit()
        
        # Refresh users to get IDs
        for user in users:
            db.refresh(user)
        
        print(f"  Created {num_users} users")
        
        # =====================================================================
        # 5. Seed UserHobbies (assign hobbies to users)
        # =====================================================================
        print("\n5. Assigning hobbies to users...")
        user_hobby_count = 0
        skill_levels = ["beginner", "intermediate", "advanced", "expert"]
        
        for user in users:
            user_hobbies = random.sample(list(hobby_map.keys()), random.randint(2, 5))
            for hobby_name in user_hobbies:
                user_hobby = models.UserHobby(
                    user_id=user.id,
                    hobby_id=hobby_map[hobby_name],
                    skill_level=random.choice(skill_levels),
                    interest_level=random.randint(1, 10),
                )
                db.add(user_hobby)
                user_hobby_count += 1
        db.commit()
        print(f"  Created {user_hobby_count} user-hobby associations")
        
        # =====================================================================
        # 6. Seed Events (matches Event model exactly)
        # =====================================================================
        print(f"\n6. Seeding {num_events} events...")
        
        # Pick some users as hosts (about 20%)
        hosts = random.sample(users, max(10, num_users // 5))
        
        events = []
        start_date = datetime.utcnow() - timedelta(days=60)
        end_date = datetime.utcnow() + timedelta(days=60)
        
        for i in range(num_events):
            host = random.choice(hosts)
            city = random.choice(CITIES)
            hobby_name = random.choice(list(hobby_map.keys()))
            hobby_id = hobby_map[hobby_name]
            event_datetime = random_date(start_date, end_date)
            event_duration = timedelta(hours=random.choice([1, 2, 3, 4]))
            capacity = random.choice([10, 20, 30, 50, 100])
            is_paid = random.random() < 0.3
            
            # Determine status based on date
            if event_datetime < datetime.utcnow() - timedelta(hours=4):
                status = random.choice(["completed", "cancelled"])
            elif event_datetime < datetime.utcnow():
                status = "completed"
            else:
                status = "upcoming"
            
            event = models.Event(
                host_id=host.id,
                title=f"{random.choice(EVENT_TITLES)} #{i + 1}",
                description=f"Join us for an amazing {hobby_name.lower()} experience! "
                           f"This is a great opportunity to connect with like-minded people.",
                hobby_id=hobby_id,
                hobby_tags=[hobby_name, random.choice(CATEGORIES)],
                event_date=event_datetime,
                start_time=event_datetime,
                end_time=event_datetime + event_duration,
                location=f"{city['name']} Community Center",
                latitude=city["lat"] + random.uniform(-0.05, 0.05),
                longitude=city["lng"] + random.uniform(-0.05, 0.05),
                city=city["name"],
                country=city["country"],
                capacity=capacity,
                is_paid=is_paid,
                price=Decimal(str(round(random.uniform(10, 100), 2))) if is_paid else Decimal("0"),
                currency="USD",
                status=status,
            )
            db.add(event)
            events.append(event)
        
        db.commit()
        
        # Refresh events to get IDs
        for event in events:
            db.refresh(event)
        
        print(f"  Created {num_events} events")
        
        # =====================================================================
        # 7. Seed UserEvents (event registrations/attendance)
        # =====================================================================
        print("\n7. Seeding event registrations...")
        user_event_count = 0
        rsvp_statuses = ["registered", "attended", "no_show", "cancelled"]
        
        for event in events:
            # Random attendees (5-80% of capacity)
            num_attendees = random.randint(max(1, event.capacity // 20), max(2, int(event.capacity * 0.8)))
            attendees = random.sample(users, min(num_attendees, len(users)))
            
            for user in attendees:
                # Don't register host as attendee
                if user.id == event.host_id:
                    continue
                
                # Status depends on event date
                if event.status == "completed":
                    status = random.choices(rsvp_statuses, weights=[10, 60, 20, 10])[0]
                    checked_in = status == "attended"
                elif event.status == "cancelled":
                    status = "cancelled"
                    checked_in = False
                else:
                    status = "registered"
                    checked_in = False
                
                user_event = models.UserEvent(
                    user_id=user.id,
                    event_id=event.id,
                    rsvp_status=status,
                    checked_in=checked_in,
                    check_in_time=event.start_time if checked_in else None,
                )
                db.add(user_event)
                user_event_count += 1
        
        db.commit()
        print(f"  Created {user_event_count} event registrations")
        
        # =====================================================================
        # 8. Seed Event Ratings (for completed events)
        # =====================================================================
        print("\n8. Seeding event ratings...")
        rating_count = 0
        completed_events = [e for e in events if e.status == "completed"]
        
        for event in completed_events:
            # Get attendees for this event
            attendees = db.query(models.UserEvent).filter(
                models.UserEvent.event_id == event.id,
                models.UserEvent.rsvp_status == "attended"
            ).all()
            
            # 30-80% of attendees leave reviews
            reviewers = random.sample(attendees, max(1, int(len(attendees) * random.uniform(0.3, 0.8)))) if attendees else []
            
            for user_event in reviewers:
                base_rating = random.uniform(3.0, 5.0)
                
                rating = models.EventRating(
                    event_id=event.id,
                    user_id=user_event.user_id,
                    rating=round(base_rating, 1),
                    communication_score=round(base_rating + random.uniform(-0.5, 0.5), 1),
                    respect_score=round(base_rating + random.uniform(-0.5, 0.5), 1),
                    professionalism_score=round(base_rating + random.uniform(-0.5, 0.5), 1),
                    atmosphere_score=round(base_rating + random.uniform(-0.5, 0.5), 1),
                    value_score=round(base_rating + random.uniform(-0.5, 0.5), 1),
                    comment=f"Great event! Really enjoyed the {random.choice(['atmosphere', 'activities', 'host', 'venue', 'community'])}.",
                    moderation_status=random.choice(["approved", "pending"]),
                )
                db.add(rating)
                rating_count += 1
        
        db.commit()
        print(f"  Created {rating_count} event ratings")
        
        # =====================================================================
        # 9. Seed User Activities (for rewards tracking)
        # =====================================================================
        print("\n9. Seeding user activities...")
        activity_count = 0
        activity_types = ["event_created", "event_attended", "blog_created", "blog_liked"]
        
        for user in random.sample(users, min(num_interactions, len(users))):
            num_activities = random.randint(1, 10)
            for _ in range(num_activities):
                activity = models.UserActivity(
                    user_id=user.id,
                    activity_type=random.choice(activity_types),
                    event_id=random.choice(events).id if events else None,
                )
                db.add(activity)
                activity_count += 1
        
        db.commit()
        print(f"  Created {activity_count} user activities")
        
        # =====================================================================
        # 10. Seed Reward Coupons
        # =====================================================================
        print("\n10. Seeding reward coupons...")
        coupon_count = 0
        status_levels = ["Bronze", "Silver", "Gold"]
        
        for user in random.sample(users, min(num_users // 4, len(users))):
            num_coupons = random.randint(1, 3)
            for _ in range(num_coupons):
                coupon = models.RewardCoupon(
                    user_id=user.id,
                    status_level=random.choice(status_levels),
                    discount_value=random.choice([5.0, 10.0, 15.0, 20.0, 25.0]),
                    stackable=random.random() < 0.3,
                    is_redeemed=random.random() < 0.2,
                )
                db.add(coupon)
                coupon_count += 1
        
        db.commit()
        print(f"  Created {coupon_count} reward coupons")
        
        # =====================================================================
        # 11. Seed Blogs
        # =====================================================================
        print("\n11. Seeding blogs...")
        blogs = []
        blog_titles = [
            "My Journey with Photography", "Best Hiking Trails in 2024",
            "Beginner's Guide to Cooking", "Why I Love Reading",
            "Gaming Tips and Tricks", "Morning Yoga Routine",
            "Running for Beginners", "Painting Techniques",
            "Music Production 101", "Dance Like Nobody's Watching"
        ]
        
        for i, title in enumerate(blog_titles):
            author = random.choice(users)
            blog = models.Blog(
                author_id=author.id,
                title=title,
                content=f"This is a detailed blog post about {title.lower()}. "
                        f"Learn tips, tricks, and insights from our community members. " * 5,
                hobby_tags=[random.choice(CATEGORIES)],
                status=random.choice(["published", "draft"]),
            )
            db.add(blog)
            blogs.append(blog)
        
        db.commit()
        
        # Refresh blogs to get IDs
        for blog in blogs:
            db.refresh(blog)
        
        print(f"  Created {len(blogs)} blogs")
        
        # =====================================================================
        # 12. Seed Blog Interactions
        # =====================================================================
        print("\n12. Seeding blog interactions...")
        interaction_count = 0
        interaction_types = ["view", "like", "share", "comment"]
        
        for blog in blogs:
            num_interactions = random.randint(10, 100)
            for _ in range(num_interactions):
                interaction = models.BlogInteraction(
                    blog_id=blog.id,
                    user_id=random.choice(users).id,
                    interaction_type=random.choices(
                        interaction_types, 
                        weights=[60, 25, 10, 5]
                    )[0],
                )
                db.add(interaction)
                interaction_count += 1
        
        db.commit()
        print(f"  Created {interaction_count} blog interactions")
        
        # =====================================================================
        # 13. Seed Ads
        # =====================================================================
        print("\n13. Seeding ads...")
        ads = []
        ad_titles = [
            "Premium Photography Equipment", "Hiking Gear Sale",
            "Cooking Class - 50% Off", "Book Fair 2024",
            "Gaming Convention Tickets", "Yoga Retreat Discount",
        ]
        
        for title in ad_titles:
            advertiser = random.choice(users)
            start = datetime.utcnow() - timedelta(days=random.randint(0, 30))
            
            ad = models.Ad(
                advertiser_id=advertiser.id,
                title=title,
                description=f"Amazing offer for {title.lower()}! Limited time only.",
                image_url=f"https://example.com/ads/{title.lower().replace(' ', '-')}.jpg",
                image_tags=[random.choice(CATEGORIES)],
                target_hobbies=[random.choice(list(hobby_map.keys()))],
                target_locations=[random.choice(CITIES)["name"]],
                target_age_min=18,
                target_age_max=random.choice([35, 45, 55, 65]),
                budget=Decimal(str(random.randint(100, 1000))),
                cpc=Decimal(str(round(random.uniform(0.1, 2.0), 4))),
                status=random.choice(["active", "paused", "draft"]),
                start_date=start,
                end_date=start + timedelta(days=random.randint(7, 60)),
            )
            db.add(ad)
            ads.append(ad)
        
        db.commit()
        
        # Refresh ads to get IDs
        for ad in ads:
            db.refresh(ad)
        
        print(f"  Created {len(ads)} ads")
        
        # =====================================================================
        # 14. Seed Ad Interactions
        # =====================================================================
        print("\n14. Seeding ad interactions...")
        ad_interaction_count = 0
        ad_interaction_types = ["impression", "click", "conversion"]
        
        for ad in ads:
            num_interactions = random.randint(50, 500)
            for _ in range(num_interactions):
                ad_interaction = models.AdInteraction(
                    ad_id=ad.id,
                    user_id=random.choice(users).id,
                    interaction_type=random.choices(
                        ad_interaction_types,
                        weights=[80, 18, 2]
                    )[0],
                )
                db.add(ad_interaction)
                ad_interaction_count += 1
        
        db.commit()
        print(f"  Created {ad_interaction_count} ad interactions")
        
        # =====================================================================
        # 15. Seed Host Ratings
        # =====================================================================
        print("\n15. Seeding host ratings...")
        host_rating_count = 0
        
        for host in hosts:
            host_events = [e for e in events if e.host_id == host.id]
            completed = [e for e in host_events if e.status == "completed"]
            
            host_rating = models.HostRating(
                host_id=host.id,
                total_events=len(host_events),
                completed_events=len(completed),
                total_attendees=random.randint(10, 500),
                repeat_attendees=random.randint(0, 50),
                avg_communication=round(random.uniform(3.5, 5.0), 2),
                avg_respect=round(random.uniform(3.5, 5.0), 2),
                avg_professionalism=round(random.uniform(3.5, 5.0), 2),
                avg_atmosphere=round(random.uniform(3.5, 5.0), 2),
                avg_value=round(random.uniform(3.5, 5.0), 2),
                overall_score=round(random.uniform(3.5, 5.0), 2),
            )
            db.add(host_rating)
            host_rating_count += 1
        
        db.commit()
        print(f"  Created {host_rating_count} host ratings")
        
        # =====================================================================
        # 16. Seed Timeseries Data (for dashboards)
        # =====================================================================
        print("\n16. Seeding timeseries data...")
        
        # Daily data for past 90 days
        daily_count = 0
        for i in range(90):
            day = date.today() - timedelta(days=i)
            daily = models.TimeseriesDaily(
                date=day,
                total_visits=random.randint(1000, 10000),
                unique_visitors=random.randint(500, 5000),
                registrations=random.randint(10, 100),
                events_created=random.randint(5, 30),
                events_completed=random.randint(2, 20),
                total_revenue=Decimal(str(random.randint(1000, 10000))),
                active_users=random.randint(200, 2000),
                new_users=random.randint(10, 100),
            )
            db.add(daily)
            daily_count += 1
        
        # Hourly data for past 48 hours
        hourly_count = 0
        for i in range(48):
            hour = datetime.utcnow() - timedelta(hours=i)
            hourly = models.TimeseriesHourly(
                timestamp=hour.replace(minute=0, second=0, microsecond=0),
                visits=random.randint(50, 500),
                api_calls=random.randint(500, 5000),
                errors=random.randint(0, 20),
                avg_response_time_ms=random.uniform(50, 300),
            )
            db.add(hourly)
            hourly_count += 1
        
        db.commit()
        print(f"  Created {daily_count} daily records, {hourly_count} hourly records")
        
        # =====================================================================
        # 17. Seed Knowledge Documents (for chatbot)
        # =====================================================================
        print("\n17. Seeding knowledge documents...")
        knowledge_docs = [
            {"title": "Getting Started with Kumele", "category": "faq", "content": "Welcome to Kumele! Here's how to get started..."},
            {"title": "How to Create an Event", "category": "faq", "content": "Creating events is easy. Just follow these steps..."},
            {"title": "Payment and Refunds Policy", "category": "policy", "content": "Our payment and refund policies ensure fair transactions..."},
            {"title": "Community Guidelines", "category": "policy", "content": "We expect all members to follow these guidelines..."},
            {"title": "Privacy Policy", "category": "policy", "content": "Your privacy is important to us. Here's how we handle your data..."},
        ]
        
        for doc in knowledge_docs:
            knowledge = models.KnowledgeDocument(
                title=doc["title"],
                content=doc["content"] * 10,  # Make it longer
                category=doc["category"],
                language="en",
            )
            db.add(knowledge)
        
        db.commit()
        print(f"  Created {len(knowledge_docs)} knowledge documents")
        
        # =====================================================================
        # 18. Seed User Attendance Profiles (for no-show prediction)
        # =====================================================================
        print("\n18. Seeding attendance profiles...")
        profile_count = 0
        
        for user in random.sample(users, min(num_users // 2, len(users))):
            total_rsvps = random.randint(5, 50)
            no_shows = random.randint(0, total_rsvps // 5)
            check_ins = total_rsvps - no_shows - random.randint(0, 3)
            
            profile = models.UserAttendanceProfile(
                user_id=user.id,
                total_rsvps=total_rsvps,
                total_check_ins=max(0, check_ins),
                total_no_shows=no_shows,
                late_cancellations=random.randint(0, 5),
                payment_timeouts=random.randint(0, 2),
                failed_payments=random.randint(0, 1),
                avg_rsvp_to_event_hours=random.uniform(24, 168),
                last_minute_rsvp_count=random.randint(0, 10),
                avg_distance_km=random.uniform(1, 50),
                max_distance_km=random.uniform(10, 200),
                check_in_rate=max(0, check_ins) / max(1, total_rsvps),
                no_show_rate=no_shows / max(1, total_rsvps),
            )
            db.add(profile)
            profile_count += 1
        
        db.commit()
        print(f"  Created {profile_count} attendance profiles")
        
        # =====================================================================
        # 19. Seed User Trust Profiles (for fraud detection)
        # =====================================================================
        print("\n19. Seeding trust profiles...")
        trust_count = 0
        
        for user in random.sample(users, min(num_users // 2, len(users))):
            total_verifications = random.randint(5, 50)
            suspicious = random.randint(0, 2)
            fraudulent = random.randint(0, 1) if random.random() < 0.05 else 0
            valid = total_verifications - suspicious - fraudulent
            
            trust = models.UserTrustProfile(
                user_id=user.id,
                trust_score=max(0.0, min(1.0, random.uniform(0.7, 1.0) - fraudulent * 0.3)),
                total_verifications=total_verifications,
                valid_count=valid,
                suspicious_count=suspicious,
                fraudulent_count=fraudulent,
                gps_mismatch_count=random.randint(0, 3),
                qr_replay_count=0,
                device_anomaly_count=random.randint(0, 2),
                penalties_applied=fraudulent,
            )
            db.add(trust)
            trust_count += 1
        
        db.commit()
        print(f"  Created {trust_count} trust profiles")
        
        # =====================================================================
        # Summary
        # =====================================================================
        print("\n" + "=" * 60)
        print("SEEDING COMPLETE!")
        print("=" * 60)
        print(f"  Users: {num_users}")
        print(f"  Hobbies: {len(INTERESTS)}")
        print(f"  Events: {num_events}")
        print(f"  Event Registrations: {user_event_count}")
        print(f"  Event Ratings: {rating_count}")
        print(f"  Blogs: {len(blogs)}")
        print(f"  Ads: {len(ads)}")
        print(f"  Host Ratings: {host_rating_count}")
        print(f"  Timeseries: {daily_count} daily, {hourly_count} hourly")
        print(f"  Attendance Profiles: {profile_count}")
        print(f"  Trust Profiles: {trust_count}")
        print()
        
    except Exception as e:
        print(f"\nError during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed Kumele database with synthetic data")
    parser.add_argument("--users", type=int, default=DEFAULT_NUM_USERS, help="Number of users to create")
    parser.add_argument("--events", type=int, default=DEFAULT_NUM_EVENTS, help="Number of events to create")
    parser.add_argument("--interactions", type=int, default=DEFAULT_NUM_INTERACTIONS, help="Number of interactions")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    
    args = parser.parse_args()
    
    seed_database(
        num_users=args.users,
        num_events=args.events,
        num_interactions=args.interactions,
        clear_existing=args.clear
    )


if __name__ == "__main__":
    main()
