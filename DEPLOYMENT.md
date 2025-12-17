# Deployment Guide: DigitalOcean 4GB Droplet

This guide covers deploying Kumele AI/ML backend on a DigitalOcean droplet with 4GB RAM using OpenRouter for LLM inference.

## Prerequisites

1. **DigitalOcean Account** - [Sign up](https://www.digitalocean.com/)
2. **OpenRouter API Key** - Get from [openrouter.ai/keys](https://openrouter.ai/keys)
3. **Domain (optional)** - For HTTPS with Caddy/Nginx

## Cost Estimate

| Resource | Monthly Cost |
|----------|-------------|
| DO Droplet (4GB/2vCPU) | ~$24 |
| OpenRouter API (est.) | ~$5-20 |
| **Total** | ~$29-44 |

---

## Step 1: Create Droplet

1. Go to DigitalOcean → Create → Droplets
2. Choose:
   - **Image**: Ubuntu 24.04 LTS
   - **Plan**: Basic → Regular → $24/mo (4GB RAM, 2 vCPU, 80GB SSD)
   - **Region**: Choose closest to your users
   - **Authentication**: SSH Key (recommended) or Password
3. Click **Create Droplet**
4. Note the IP address

---

## Step 2: Initial Server Setup

SSH into your droplet:

```bash
ssh root@YOUR_DROPLET_IP
```

### 2.1 Update System

```bash
apt update && apt upgrade -y
```

### 2.2 Create Non-Root User

```bash
adduser kumele
usermod -aG sudo kumele
```

### 2.3 Setup Firewall

```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw allow 8000  # API port (remove after setting up reverse proxy)
ufw enable
```

### 2.4 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Add user to docker group
usermod -aG docker kumele

# Install Docker Compose
apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

### 2.5 Setup Swap (Important for 4GB RAM)

```bash
# Create 4GB swap file
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab

# Optimize swappiness for server
echo 'vm.swappiness=10' | tee -a /etc/sysctl.conf
sysctl -p
```

---

## Step 3: Deploy Application

### 3.1 Switch to kumele user

```bash
su - kumele
```

### 3.2 Clone Repository

```bash
cd ~
git clone https://github.com/YOUR_REPO/aliproject.git kumele-backend
cd kumele-backend
```

### 3.3 Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your settings
nano .env
```

**Required changes in `.env`:**

```env
# Change these!
APP_ENV=production
APP_DEBUG=false
SECRET_KEY=your-64-char-random-string-here
API_KEY=your-internal-api-key-here

# Database password (change for security)
POSTGRES_PASSWORD=your-secure-db-password

# OpenRouter (REQUIRED)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key-from-openrouter
OPENROUTER_MODEL=mistralai/mistral-7b-instruct

# Optional: Disable translation to save RAM
TRANSLATE_URL=
```

Generate a secure SECRET_KEY:

```bash
openssl rand -hex 32
```

### 3.4 Start Services

```bash
# Use the development compose file (no GPU/Mistral)
docker compose -f docker-compose.dev.yml up -d

# Check status
docker compose -f docker-compose.dev.yml ps

# View logs
docker compose -f docker-compose.dev.yml logs -f api
```

### 3.5 Wait for Initialization

First startup takes 2-5 minutes. Watch the logs:

```bash
docker compose -f docker-compose.dev.yml logs -f
```

Wait until you see:
```
kumele_api  | INFO:     Application startup complete.
kumele_api  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3.6 Verify Deployment

```bash
# Health check
curl http://localhost:8000/ai/health

# Test LLM (should use OpenRouter)
curl -X POST http://localhost:8000/chatbot/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello, what is Kumele?"}'
```

---

## Step 4: Seed Database

```bash
# Run the seeder inside the container
docker compose -f docker-compose.dev.yml exec api python scripts/seed_database.py --clear

# Or with custom amounts
docker compose -f docker-compose.dev.yml exec api python scripts/seed_database.py \
  --users 500 --events 200 --interactions 2000 --clear
```

---

## Step 5: Setup Reverse Proxy (Caddy - Recommended)

Caddy automatically handles HTTPS with Let's Encrypt.

### 5.1 Install Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### 5.2 Configure Caddy

```bash
sudo nano /etc/caddy/Caddyfile
```

Replace with:

```caddyfile
# Replace with your domain
api.yourdomain.com {
    reverse_proxy localhost:8000
}
```

**If you don't have a domain**, use IP with HTTP:

```caddyfile
:80 {
    reverse_proxy localhost:8000
}
```

### 5.3 Start Caddy

```bash
sudo systemctl enable caddy
sudo systemctl start caddy
sudo systemctl status caddy
```

### 5.4 Remove Direct Port Access

```bash
sudo ufw delete allow 8000
```

Now access your API at `https://api.yourdomain.com` or `http://YOUR_DROPLET_IP`

---

## Step 6: Setup Auto-Restart

Create systemd service for Docker Compose:

```bash
sudo nano /etc/systemd/system/kumele.service
```

```ini
[Unit]
Description=Kumele AI/ML Backend
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=kumele
WorkingDirectory=/home/kumele/kumele-backend
ExecStart=/usr/bin/docker compose -f docker-compose.dev.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.dev.yml down

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl enable kumele
sudo systemctl start kumele
```

---

## Step 7: Monitoring & Maintenance

### View Logs

```bash
# All services
docker compose -f docker-compose.dev.yml logs -f

# Specific service
docker compose -f docker-compose.dev.yml logs -f api
docker compose -f docker-compose.dev.yml logs -f postgres
```

### Check Resource Usage

```bash
# Docker stats
docker stats

# System resources
htop
```

### Restart Services

```bash
docker compose -f docker-compose.dev.yml restart

# Restart specific service
docker compose -f docker-compose.dev.yml restart api
```

### Update Application

```bash
cd ~/kumele-backend
git pull
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up -d
```

### Backup Database

```bash
# Create backup
docker compose -f docker-compose.dev.yml exec postgres pg_dump -U kumele kumele_ai > backup_$(date +%Y%m%d).sql

# Restore backup
docker compose -f docker-compose.dev.yml exec -T postgres psql -U kumele kumele_ai < backup_20260119.sql
```

---

## Troubleshooting

### Out of Memory

```bash
# Check memory
free -h

# Check which container is using most
docker stats --no-stream

# Increase swap if needed
sudo fallocate -l 8G /swapfile2
sudo chmod 600 /swapfile2
sudo mkswap /swapfile2
sudo swapon /swapfile2
```

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.dev.yml logs api

# Check for port conflicts
sudo netstat -tulpn | grep :8000

# Rebuild from scratch
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d --build
```

### OpenRouter Errors

```bash
# Test API key directly
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer sk-or-v1-your-key"

# Check if key is set in container
docker compose -f docker-compose.dev.yml exec api env | grep OPENROUTER
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker compose -f docker-compose.dev.yml ps postgres

# Connect manually
docker compose -f docker-compose.dev.yml exec postgres psql -U kumele -d kumele_ai

# Reinitialize database
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
```

---

## API Endpoints Quick Reference

Once deployed, these endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ai/health` | GET | Health check |
| `/chatbot/ask` | POST | RAG chatbot |
| `/match/events` | GET | Event matching |
| `/recommendations/events` | GET | Personalized recommendations |
| `/ml/no-show/predict` | POST | No-show prediction |
| `/ml/attendance/verify` | POST | Attendance verification |
| `/taxonomy/interests` | GET | Interest taxonomy |
| `/i18n/{lang}` | GET | Translations |

Full API docs at: `http://YOUR_DOMAIN/docs`

---

## Switching to Local Mistral Later

When you get a GPU server:

1. Update `.env`:
```env
LLM_PROVIDER=local
# or
LLM_PROVIDER=auto  # tries local first, falls back to OpenRouter
```

2. Use main docker-compose.yml:
```bash
docker compose -f docker-compose.yml up -d
```

That's it! The code automatically handles the switch.

---

## Security Checklist

- [ ] Changed default database password
- [ ] Set strong SECRET_KEY
- [ ] Set strong API_KEY
- [ ] Disabled root SSH login
- [ ] Setup UFW firewall
- [ ] Using HTTPS (via Caddy)
- [ ] Regular backups configured
- [ ] Log monitoring setup

---

## Support

For issues:
1. Check logs: `docker compose -f docker-compose.dev.yml logs -f`
2. Check health: `curl localhost:8000/ai/health`
3. Check OpenRouter dashboard for API usage
