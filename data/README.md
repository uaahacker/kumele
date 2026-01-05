# Kumele AI/ML Backend - Data README

This folder contains synthetic test data generated for the Kumele AI/ML Backend.

## 📁 Files

| File | Records | Description |
|------|---------|-------------|
| `users.csv` | 100 | User profiles with demographics, location |
| `events.csv` | 200 | Events across various hobbies/categories |
| `interactions.csv` | 500 | User-event interactions (views, RSVPs, attendance) |
| `ratings.csv` | 300 | Event ratings and reviews |
| `user_hobbies.csv` | ~300 | User hobby preferences |
| `user_activities.csv` | 400 | Activity log for rewards calculation |
| `reward_coupons.csv` | 50 | Issued reward coupons |
| `timeseries_daily.csv` | 90 | Daily metrics (Prophet-ready) |
| `timeseries_hourly.csv` | 168 | Hourly metrics |
| `ads.csv` | 30 | Ad campaigns |
| `knowledge_documents.csv` | 5 | Chatbot knowledge base documents |
| `interest_taxonomy.csv` | ~23 | Hobby/interest categories |
| `ui_strings.csv` | ~22 | UI translation strings |
| `manifest.json` | - | Generation metadata & statistics |

## 🔄 Regenerating Data

To regenerate fresh data:

```bash
cd /path/to/newapi
python scripts/generate_synthetic_data.py
```

## 📊 Data Schema

### users.csv
- `user_id` (int): Primary key
- `external_id` (uuid): External reference
- `email`: User email
- `first_name`, `last_name`: Name
- `age_group`: 18-24, 25-34, 35-44, 45-54, 55+
- `city`, `country`: Location
- `latitude`, `longitude`: Coordinates
- `reward_status`: none/bronze/silver/gold
- `created_at`: Registration date

### events.csv
- `event_id` (uuid): Primary key
- `host_id`: References users.user_id
- `title`: Event title
- `category`: Hobby category
- `city`, `country`: Location
- `latitude`, `longitude`: Coordinates
- `event_date`: When event occurs
- `capacity`: Max attendees
- `price`: Ticket price (0 = free)
- `status`: draft/published/completed

### timeseries_daily.csv (Prophet format)
- `ds`: Date (YYYY-MM-DD)
- `y`: Target value (attendance)
- `category`: Event category
- `city`: Location
- Additional features for forecasting

## 🎯 Usage

### Load into PostgreSQL

```sql
-- Copy users
COPY users(user_id, email, created_at) 
FROM '/path/to/data/users.csv' 
WITH (FORMAT csv, HEADER true);

-- Or use the generator's auto-insert feature
```

### Use with APIs

Once data is loaded:

```bash
# Get recommendations (will use real data)
curl "http://localhost:8000/recommendations/events?user_id=1"

# Get rewards (calculates from user_activities)
curl "http://localhost:8000/rewards/suggestion?user_id=1"
```

## ⚠️ Notes

- This is SYNTHETIC data for testing only
- Replace with real data for production
- Data relationships are internally consistent
- Generated dates are relative to generation time
