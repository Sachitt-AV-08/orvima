# Orvima SaaS Frontend

Next.js 14 landing page + dashboard for Orvima browser session deployment.

## Features

- **Landing Page**: Hero, features, live terminal demo, pricing
- **Authentication**: Supabase Auth (email/password)
- **Payments**: Stripe Checkout + Webhooks
- **Dashboard**: Session management, API keys, usage stats
- **Design**: Orvima brand (#F5A524 on #0D1117), WCAG AA compliant

## Quick Start

```bash
cd orvima-saas/frontend

# Install dependencies
npm install

# Copy env template
cp .env.example .env.local
# Edit .env.local with your keys

# Run dev server
npm run dev
```

Open http://localhost:3000

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Stripe publishable key |
| `STRIPE_PRO_PRICE_ID` | Stripe Price ID for Pro plan |
| `STRIPE_TEAM_PRICE_ID` | Stripe Price ID for Team plan |
| `NEXT_PUBLIC_APP_URL` | Your app URL (for redirects) |

## Supabase Setup

1. Create project at https://supabase.com
2. Enable Email/Password auth
3. Create `profiles` table:

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

## Stripe Setup

1. Create products/prices in Stripe Dashboard
2. Set `STRIPE_PRO_PRICE_ID` and `STRIPE_TEAM_PRICE_ID`
3. Add webhook endpoint: `https://yourdomain.com/api/webhook/stripe`
4. Subscribe to events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
4. Set `STRIPE_WEBHOOK_SECRET`

## Deploy

### Vercel (Frontend)
```bash
vercel deploy
```

### Railway/Render (Backend)
```bash
# From orvima-saas root
docker build -f Dockerfile.backend -t orvima-backend ..
docker run -p 8000:8000 orvima-backend
```

### Docker Compose (Full Stack)
```bash
docker-compose up -d
```

## Project Structure

```
orvima-saas/
├── frontend/
│   ├── app/
│   │   ├── page.tsx              # Landing page
│   │   ├── layout.tsx            # Root layout
│   │   ├── globals.css           # Global styles
│   │   ├── api/
│   │   │   ├── checkout/route.ts # Stripe checkout
│   │   │   └── webhook/stripe/   # Stripe webhooks
│   │   ├── auth/
│   │   │   ├── login/page.tsx
│   │   │   └── signup/page.tsx
│   │   └── dashboard/page.tsx    # User dashboard
│   ├── components/
│   │   ├── Hero.tsx              # Hero + Features
│   │   ├── TerminalDemo.tsx      # Live terminal demo
│   │   └── PricingCards.tsx      # Pricing table
│   └── lib/
│       ├── utils.ts
│       ├── supabase.ts
│       └── stripe.ts
└── backend/ (orvima.saas_api)
```

## API Endpoints (Backend)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/deploy` | Deploy new browser session |
| GET | `/api/sessions` | List sessions |
| GET | `/api/sessions/{id}` | Get session details |
| DELETE | `/api/sessions/{id}` | Destroy session |

## License

MIT