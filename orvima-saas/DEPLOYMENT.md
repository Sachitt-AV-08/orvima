# Orvima SaaS Deployment Guide

## Prerequisites

- Docker & Docker Compose installed
- Railway account (for managed deployment) or VPS
- Supabase project (for auth)
- Stripe account (for payments)
- Domain name (for production)

---

## Option 1: Railway (Recommended - Easiest)

### 1. Create Railway Project

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
cd orvima-saas
railway init
```

### 2. Configure Environment Variables

In Railway Dashboard → Variables, add:

```bash
# Backend
ORVIMA_SAAS_BASE_PORT=9222
ORVIMA_SAAS_MAX_SESSIONS=20
ORVIMA_SAAS_TTL_MINUTES=60

# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_TEAM_PRICE_ID=price_...

# Frontend
NEXT_PUBLIC_APP_URL=https://orvima.in
```

### 3. Deploy

```bash
railway up
```

---

## Option 2: VPS + Docker Compose

### 1. Provision VPS

- Ubuntu 22.04 LTS
- 2 vCPU, 4GB RAM minimum
- 50GB SSD
- Domain DNS: `A orvima.in → your-vps-ip`, `A api.orvima.in → your-vps-ip`

### 2. Setup Server

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER
newgrp docker

# Install Docker Compose
apt install docker-compose-plugin -y
```

### 3. Deploy

```bash
git clone https://github.com/Sachitt-AV-08/orvima.git
cd orvima/orvima-saas

# Copy env template and edit
cp frontend/.env.example frontend/.env.local
# Edit frontend/.env.local with your values

# Build and start
docker-compose up -d --build

# Verify
curl http://localhost:8000/health
curl http://localhost:3000
```

### 4. Configure Nginx + SSL

```bash
# Install Nginx + Certbot
apt install nginx certbot python3-certbot-nginx -y

# Configure Nginx
# /etc/nginx/sites-available/orvima.in
server {
    listen 80;
    server_name orvima.in www.orvima.in;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name orvima.in www.orvima.in;

    ssl_certificate /etc/letsencrypt/live/orvima.in/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/orvima.in/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

server {
    listen 80;
    server_name api.orvima.in;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.orvima.in;

    ssl_certificate /etc/letsencrypt/live/orvima.in/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/orvima.in/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
# Enable site
ln -s /etc/nginx/sites-available/orvima.in /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Get SSL cert
certbot --nginx -d orvima.in -d www.orvima.in -d api.orvima.in
```

---

## Option 3: Manual Python (Development)

```bash
cd orvima
python -m uvicorn orvima.saas_api:app --host 0.0.0.0 --port 8000
```

---

## Supabase Setup

1. Create project at https://supabase.com
2. Go to Authentication → Providers → Enable Email/Password
3. Run SQL in SQL Editor:

```sql
create table profiles (
  id uuid references auth.users primary key,
  plan text default 'free',
  api_key text,
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamp with time zone default timezone('utc'::text, now()),
  updated_at timestamp with time zone default timezone('utc'::text, now())
);

alter table profiles enable row level security;

create policy "Users can view own profile" on profiles
  for select using (auth.uid() = id);

create policy "Users can update own profile" on profiles
  for update using (auth.uid() = id);
```

---

## Stripe Setup

1. Create products in Stripe Dashboard:
   - "Pro Plan" - $19/mo recurring
   - "Team Plan" - $49/mo recurring
2. Copy Price IDs to environment variables
3. Create webhook endpoint: `https://api.orvima.in/api/webhook/stripe`
4. Subscribe to events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
4. Copy webhook signing secret to `STRIPE_WEBHOOK_SECRET`

---

## DNS Configuration

| Type | Name | Value |
|------|------|-------|
| A | @ | YOUR_VPS_IP |
| A | www | YOUR_VPS_IP |
| A | api | YOUR_VPS_IP |

---

## Verification

```bash
# Health check
curl https://api.orvima.in/health

# Deploy session
curl -X POST https://api.orvima.in/api/deploy \
  -H "Content-Type: application/json" \
  -d '{"headless": true, "ttl_minutes": 30}'

# Frontend
curl https://orvima.in
```

---

## Monitoring

- **Railway**: Built-in logs & metrics
- **VPS**: `docker-compose logs -f`, `htop`, `df -h`
- **Health**: `curl https://api.orvima.in/health` every minute
- **Sessions**: `curl https://api.orvima.in/api/sessions`

---

## Backup & Recovery

```bash
# Backup Supabase
pg_dump -h db.xxx.supabase.co -U postgres postgres > backup.sql

# Restore
psql -h db.xxx.supabase.co -U postgres postgres < backup.sql

# Backup Docker volumes
docker run --rm -v orvima-saas_backend_data:/data -v $(pwd):/backup alpine tar czf /backup/backend-data.tar.gz /data
```