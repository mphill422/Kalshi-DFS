# DFS Tier Optimizer — NBA DraftKings
**Repo:** mphill422/Kalshi-DFS  
**Stack:** Streamlit Cloud · Supabase · NBA Stats API · The Odds API

---

## What It Does
- Fetches today's NBA DraftKings tier contest slate
- Scores every player using projections, matchup grades, blowout risk, injury status
- Recommends top 2 players per tier (Tiers 1–6)
- You make the final pick per tier
- Saves lineups to Supabase for tracking

---

## Setup

### 1. Create GitHub Repo
```
mphill422/Kalshi-DFS
```
Push all files from this folder.

### 2. Supabase Tables
Run `supabase_schema.sql` in your Supabase SQL editor at:
`oirnfhhuyjuotkrlymxd.supabase.co`

### 3. Streamlit Cloud
- Connect to `mphill422/Kalshi-DFS`
- Main file: `app.py`
- Add secrets (see `.streamlit/secrets.toml.template`)

### 4. Secrets to Add in Streamlit Cloud
```
SUPABASE_URL = "https://oirnfhhuyjuotkrlymxd.supabase.co"
SUPABASE_KEY = "your-anon-key"
ODDS_API_KEY = "your-key"   # Free: https://the-odds-api.com
```

---

## API Notes

### DraftKings API
- Uses unofficial DK endpoints (no auth required)
- Tier contests use `contestTypeId=96`
- Tier players identified by `rosterSlotId` 150–155 = Tiers 1–6
- Enable "Demo Mode" in sidebar if DK API is unavailable

### NBA Stats API
- Free, no key required
- `stats.nba.com/stats/` endpoints
- Requires proper headers (User-Agent, Referer)

### The Odds API
- Free tier: 500 requests/month
- Sign up: https://the-odds-api.com
- Used for spread/total data and blowout detection

### Injury Feed
- Scrapes Rotowire injury table (no auth)
- Refreshes every 5 minutes

---

## Scoring Model
Each player scored 0–100:
- Base: 50 points
- DK projection: up to +25
- Close game (spread ≤4): +8
- Heavy favorite: +5
- High O/U (230+): +6
- Blowout underdog risk (spread 12+): -15
- Low total (210-): -5
- GTD/Questionable: -20
- OUT: score = 0

---

## Version History
- V1.0 — Initial build: slate fetch, scoring engine, tier UI, lineup builder, Supabase logging
