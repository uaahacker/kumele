# Kumele AI/ML Backend - Required Configuration Details

Dear Client,

To complete the setup and testing of the Kumele AI/ML Backend Service, I need the following credentials and configuration details from you. Please provide these securely.

---

## 1. Database Credentials

| Item | Description | Example |
|------|-------------|---------|
| **Database Host** | PostgreSQL server hostname/IP | `db.example.com` or `192.168.1.100` |
| **Database Port** | PostgreSQL port | `5432` (default) |
| **Database Name** | Name of the database | `kumele_ai` |
| **Database Username** | PostgreSQL username | `kumele_user` |
| **Database Password** | PostgreSQL password | `your_secure_password` |

---


## 3. Email / SMTP Configuration

For sending support emails, notifications, and system alerts:

| Item | Description | Example |
|------|-------------|---------|
| **SMTP Host** | SMTP server hostname | `smtp.gmail.com` or `smtp.office365.com` |
| **SMTP Port** | SMTP port | `587` (TLS) or `465` (SSL) |
| **SMTP Username** | Email account username | `noreply@kumele.com` |
| **SMTP Password** | Email account password or App Password | `your_smtp_password` |
| **From Email Address** | Sender email address | `noreply@kumele.com` |
| **From Name** | Sender display name | `Kumele Support` |

> **Note:** If using Gmail, you'll need to generate an "App Password" from Google Account settings.

---

## 6. Geocoding Configuration (Optional)

For location-based event matching. Using free OpenStreetMap Nominatim by default:

| Item | Description | Default |
|------|-------------|---------|
| **Nominatim User Agent** | Identifier for API requests | `KumeleAI/1.0 (your@email.com)` |

> **Note:** Nominatim requires a valid contact email in the User-Agent. Please provide an email for this.

---

## 7. Content Moderation Thresholds (Optional)

Default values are already set, but if you want to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| Text Toxicity Threshold | 0.60 | Reject text above this toxicity score |
| Hate Speech Threshold | 0.30 | Flag content above this hate speech score |
| Spam Threshold | 0.70 | Flag content above this spam score |
| Image Nudity Threshold | 0.60 | Reject images above this nudity score |
| Image Violence Threshold | 0.50 | Flag images above this violence score |

---


Once I receive these details, I will:
1. Configure the backend service
2. Run integration tests
3. Verify all features are working
4. Provide you with test results and demo

Please let me know if you have any questions.

Best regards,
[Your Name]
