"""
DFS Shadow Validation — Nightly Snapshot Job
=============================================
Runs at 6 PM ET via GitHub Actions cron.

Workflow:
1. Pull today's NBA + MLB props from Odds API
2. For each prop, fetch player history (BDL for NBA, MLB Stats for MLB)
3. Run Negative Binomial Monte Carlo (matches Streamlit app methodology)
4. Compute Trust + Edge + Tier scores
5. Filter to 🔥 / 🎯 / 💎 tier picks only
6. Write to dfs_shadow_picks Supabase table

Required env vars (set as GitHub Action secrets):
- SUPABASE_URL
- SUPABASE_KEY  (service_role key)
- ODDS_API_KEY
- BDL_API_KEY
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta, date, timezone
from typing import Optional

import numpy as np
import pandas as pd
import requests

# ============================================================
# CONFIG
# ============================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
BDL_API_KEY = os.environ.get("BDL_API_KEY", "")

# Sanity check
missing = [k for k, v in {
    "SUPABASE_URL": SUPABASE_URL, "SUPABASE_KEY": SUPABASE_KEY,
    "ODDS_API_KEY": ODDS_API_KEY, "BDL_API_KEY": BDL_API_KEY,
}.items() if not v]
if missing:
    print(f"❌ Missing env vars: {', '.join(missing)}")
    sys.exit(1)

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
BDL_BASE = "https://api.balldontlie.io/v1"
MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"
ESPN_NBA_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
ESPN_MLB_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/injuries"

# Model config — must match Streamlit app
N_SIMULATIONS = 10_000  # Reduced from 50K for batch speed; calibration is still consistent
L25_WINDOW = 25
L10_WEIGHT = 0.70
TRUST_THRESHOLD = 65
EDGE_THRESHOLD = 5

# Tiers to log
LOG_TIERS = ["🔥", "🎯", "💎"]

NBA_STAT_MARKETS = {
    "Points": "player_points", "Rebounds": "player_rebounds",
    "Assists": "player_assists", "Blocks": "player_blocks",
    "Steals": "player_steals", "3PM": "player_threes",
}
MLB_STAT_MARKETS = {
    "Hits": "batter_hits", "Total Bases": "batter_total_bases",
    "RBI": "batter_rbis", "Runs": "batter_runs_scored",
    "Home Runs": "batter_home_runs",
    "Strikeouts": "pitcher_strikeouts", "Earned Runs": "pitcher_earned_runs",
    "Outs Recorded": "pitcher_outs", "Hits Allowed": "pitcher_hits_allowed",
    "Walks Issued": "pitcher_walks",
}
BDL_STAT_FIELDS = {
    "Points": "pts", "Rebounds": "reb", "Assists": "ast",
    "Blocks": "blk", "Steals": "stl", "3PM": "fg3m",
}
STATUS_MULTIPLIER = {
    "Active": 1.0, "Probable": 0.95, "Day-To-Day": 0.85,
    "Questionable": 0.70, "Doubtful": 0.30, "Out": 0.0, "IR": 0.0,
}


# ============================================================
# SUPABASE HELPERS
# ============================================================

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def supabase_insert(table: str, rows: list):
    """Bulk insert rows. Returns count inserted."""
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    inserted = 0
    # Chunk to 500 rows max per request
    for i in range(0, len(rows), 500):
        chunk = rows[i:i+500]
        try:
            r = requests.post(url, headers=supabase_headers(),
                              json=chunk, timeout=30)
            if r.status_code in (200, 201):
                inserted += len(chunk)
            else:
                print(f"⚠️  Insert chunk failed: {r.status_code} {r.text[:300]}")
        except Exception as e:
            print(f"⚠️  Insert chunk exception: {e}")
    return inserted


def supabase_upsert(table: str, rows: list, on_conflict: str):
    """Upsert (insert or update on conflict)."""
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    headers = supabase_headers()
    headers["Prefer"] = "return=minimal,resolution=merge-duplicates"
    upserted = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i+500]
        try:
            r = requests.post(url, headers=headers, json=chunk, timeout=30)
            if r.status_code in (200, 201, 204):
                upserted += len(chunk)
            else:
                print(f"⚠️  Upsert chunk failed: {r.status_code} {r.text[:300]}")
        except Exception as e:
            print(f"⚠️  Upsert chunk exception: {e}")
    return upserted


def log_run_start(run_type: str, league: str = None):
    """Insert a run_log row, return its id."""
    url = f"{SUPABASE_URL}/rest/v1/dfs_run_log"
    row = {"run_type": run_type, "status": "running", "league": league}
    try:
        r = requests.post(url, headers=supabase_headers(), json=row, timeout=15)
        if r.status_code in (200, 201):
            data = r.json()
            return data[0]["id"] if data else None
    except Exception:
        pass
    return None


def log_run_end(run_id: int, status: str, processed: int, written: int,
                errors: str = None, metadata: dict = None):
    if run_id is None:
        return
    url = f"{SUPABASE_URL}/rest/v1/dfs_run_log?id=eq.{run_id}"
    headers = supabase_headers()
    headers["Prefer"] = "return=minimal"
    patch = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "rows_processed": processed,
        "rows_written": written,
        "errors": errors,
        "metadata": metadata or {},
    }
    try:
        requests.patch(url, headers=headers, json=patch, timeout=15)
    except Exception:
        pass


# ============================================================
# ODDS API
# ============================================================

def fetch_odds_props(sport: str, markets: list):
    """Pull all player props for given sport + markets."""
    events_url = f"{ODDS_API_BASE}/sports/{sport}/events"
    try:
        r = requests.get(events_url, params={"apiKey": ODDS_API_KEY}, timeout=15)
        if r.status_code != 200:
            return [], f"Events API {r.status_code}"
        events = r.json()
    except Exception as e:
        return [], f"Events fetch: {e}"

    if not events:
        return [], "No events"

    today = datetime.utcnow().date()
    todays_events = []
    for ev in events:
        try:
            ev_date = datetime.fromisoformat(
                ev.get("commence_time", "").replace("Z", "+00:00")
            ).date()
            if ev_date == today or ev_date == today + timedelta(days=1):
                todays_events.append(ev)
        except Exception:
            continue

    all_props = []
    markets_str = ",".join(markets)
    for ev in todays_events:
        odds_url = f"{ODDS_API_BASE}/sports/{sport}/events/{ev['id']}/odds"
        try:
            r = requests.get(odds_url, params={
                "apiKey": ODDS_API_KEY, "regions": "us", "markets": markets_str,
                "oddsFormat": "american", "bookmakers": "draftkings,fanduel",
            }, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            for book in data.get("bookmakers", []):
                for m in book.get("markets", []):
                    for o in m.get("outcomes", []):
                        all_props.append({
                            "event_id": ev["id"],
                            "home": data.get("home_team", ""),
                            "away": data.get("away_team", ""),
                            "commence_time": data.get("commence_time"),
                            "book": book.get("key", ""),
                            "market": m.get("key", ""),
                            "player": o.get("description", ""),
                            "side": o.get("name", ""),
                            "line": o.get("point"),
                            "odds": o.get("price"),
                        })
        except Exception:
            continue
    return all_props, None


def fetch_event_total(sport: str, event_id: str):
    """Pull Vegas total for a game."""
    if not event_id:
        return None
    try:
        r = requests.get(
            f"{ODDS_API_BASE}/sports/{sport}/events/{event_id}/odds",
            params={"apiKey": ODDS_API_KEY, "regions": "us",
                    "markets": "totals", "bookmakers": "draftkings"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        for book in r.json().get("bookmakers", []):
            for m in book.get("markets", []):
                if m.get("key") == "totals":
                    for o in m.get("outcomes", []):
                        if o.get("name") == "Over":
                            return o.get("point")
    except Exception:
        return None
    return None


def consolidate_props(props: list, market_map: dict) -> list:
    """Group Over/Under outcomes per player+line+book into single rows."""
    if not props:
        return []
    df = pd.DataFrame(props)
    rev = {v: k for k, v in market_map.items()}
    df["stat"] = df["market"].map(rev)
    df = df[df["stat"].notna()]

    rows = []
    for keys, grp in df.groupby(
        ["player", "stat", "line", "book", "home", "away",
         "commence_time", "event_id"]
    ):
        player, stat, line, book, home, away, commence, event_id = keys
        over = grp[grp["side"] == "Over"]["odds"].values
        under = grp[grp["side"] == "Under"]["odds"].values
        rows.append({
            "player": player, "stat": stat, "line": line, "book": book,
            "home": home, "away": away, "commence_time": commence,
            "event_id": event_id,
            "over_odds": float(over[0]) if len(over) else None,
            "under_odds": float(under[0]) if len(under) else None,
        })
    return rows


# ============================================================
# BALLDONTLIE
# ============================================================

_bdl_player_cache = {}

def bdl_player_id(name: str):
    if name in _bdl_player_cache:
        return _bdl_player_cache[name]
    parts = name.strip().split()
    if not parts:
        return None
    try:
        r = requests.get(f"{BDL_BASE}/players",
                         params={"search": parts[-1], "per_page": 25},
                         headers={"Authorization": BDL_API_KEY}, timeout=10)
        if r.status_code != 200:
            return None
        target = name.lower().strip()
        for p in r.json().get("data", []):
            full = f"{p.get('first_name', '')} {p.get('last_name', '')}".lower().strip()
            if full == target:
                _bdl_player_cache[name] = p["id"]
                return p["id"]
        last = parts[-1].lower()
        for p in r.json().get("data", []):
            if p.get("last_name", "").lower() == last:
                _bdl_player_cache[name] = p["id"]
                return p["id"]
    except Exception:
        pass
    _bdl_player_cache[name] = None
    return None


def bdl_game_log(player_id: int, season: int = None):
    if player_id is None:
        return pd.DataFrame()
    if season is None:
        today = date.today()
        season = today.year if today.month >= 10 else today.year - 1

    rows = []
    cursor = None
    for _ in range(10):
        params = {"player_ids[]": player_id, "seasons[]": season, "per_page": 100}
        if cursor:
            params["cursor"] = cursor
        try:
            r = requests.get(f"{BDL_BASE}/stats", params=params,
                             headers={"Authorization": BDL_API_KEY}, timeout=15)
            if r.status_code != 200:
                break
            payload = r.json()
            for s in payload.get("data", []):
                rows.append({
                    "date": s.get("game", {}).get("date"),
                    "min": parse_minutes(s.get("min")),
                    "pts": s.get("pts", 0), "reb": s.get("reb", 0),
                    "ast": s.get("ast", 0), "blk": s.get("blk", 0),
                    "stl": s.get("stl", 0), "fg3m": s.get("fg3m", 0),
                })
            cursor = payload.get("meta", {}).get("next_cursor")
            if not cursor:
                break
        except Exception:
            break

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date", ascending=False).reset_index(drop=True)
    # Filter DNPs
    return df[df["min"] > 0].reset_index(drop=True)


def parse_minutes(m):
    if m is None or m == "":
        return 0.0
    try:
        if isinstance(m, (int, float)):
            return float(m)
        if ":" in str(m):
            parts = str(m).split(":")
            return float(parts[0]) + float(parts[1]) / 60.0
        return float(m)
    except Exception:
        return 0.0


# ============================================================
# MLB STATS API
# ============================================================

def mlb_player_id(name: str):
    season = date.today().year
    try:
        r = requests.get(f"{MLB_STATS_BASE}/sports/1/players",
                         params={"season": season}, timeout=15)
        if r.status_code != 200:
            return None
        target = name.lower().strip()
        people = r.json().get("people", [])
        for p in people:
            if p.get("fullName", "").lower() == target:
                return p["id"]
        last = name.split()[-1].lower()
        for p in people:
            if p.get("fullName", "").lower().endswith(last):
                return p["id"]
    except Exception:
        pass
    return None


def mlb_game_log(player_id: int, group: str):
    if player_id is None:
        return pd.DataFrame()
    season = date.today().year
    try:
        r = requests.get(f"{MLB_STATS_BASE}/people/{player_id}/stats",
                         params={"stats": "gameLog", "group": group,
                                 "season": season, "sportId": 1}, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        stats_arr = r.json().get("stats", [])
        if not stats_arr:
            return pd.DataFrame()
        rows = []
        for s in stats_arr[0].get("splits", []):
            stat = s.get("stat", {})
            rows.append({
                "date": s.get("date"),
                "hits": stat.get("hits", 0),
                "totalBases": stat.get("totalBases", 0),
                "rbi": stat.get("rbi", 0), "runs": stat.get("runs", 0),
                "homeRuns": stat.get("homeRuns", 0),
                "strikeouts": stat.get("strikeOuts", 0),
                "earnedRuns": stat.get("earnedRuns", 0),
                "hitsAllowed": stat.get("hits", 0) if group == "pitching" else 0,
                "walks": stat.get("baseOnBalls", 0),
                "outsRecorded": ip_to_outs(stat.get("inningsPitched", 0)),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"]).sort_values("date", ascending=False).reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


def ip_to_outs(ip):
    try:
        ip_str = str(ip)
        if "." in ip_str:
            whole, frac = ip_str.split(".")
            return int(whole) * 3 + int(frac)
        return int(float(ip)) * 3
    except Exception:
        return 0


# ============================================================
# INJURIES
# ============================================================

def fetch_injuries(league: str) -> dict:
    url = ESPN_NBA_INJURIES if league == "nba" else ESPN_MLB_INJURIES
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return {}
        out = {}
        for team in r.json().get("injuries", []):
            for inj in team.get("injuries", []):
                ath = inj.get("athlete", {})
                name = ath.get("displayName", "")
                if name:
                    out[name.lower()] = {"status": inj.get("status", "Active")}
        return out
    except Exception:
        return {}


# ============================================================
# MONTE CARLO (matches Streamlit app)
# ============================================================

def build_distribution(values: np.ndarray, n_sims: int = N_SIMULATIONS) -> np.ndarray:
    vals = np.asarray(values, dtype=float)
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return np.zeros(n_sims, dtype=int)
    if len(vals) < 5:
        mean = max(np.mean(vals), 0.1)
        return np.random.poisson(lam=mean, size=n_sims).astype(int)
    if len(vals) < 10:
        # Negative Binomial fit
        mean = np.mean(vals)
        var = np.var(vals, ddof=1)
        if var > mean and mean > 0:
            p = mean / var
            n = mean * p / (1 - p)
            if n > 0 and np.isfinite(n):
                return np.random.negative_binomial(n=n, p=p, size=n_sims)
        return np.random.poisson(lam=max(np.mean(vals), 0.1),
                                  size=n_sims).astype(int)
    # Bootstrap with L10 weighting
    l10 = vals[:min(10, len(vals))]
    l_older = vals[10:min(L25_WINDOW, len(vals))]
    if len(l_older) > 0:
        n_l10 = int(n_sims * L10_WEIGHT)
        sims = np.concatenate([
            np.random.choice(l10, size=n_l10, replace=True),
            np.random.choice(l_older, size=n_sims - n_l10, replace=True),
        ])
        np.random.shuffle(sims)
    else:
        sims = np.random.choice(l10, size=n_sims, replace=True)
    return np.round(sims).astype(int).clip(min=0)


def hit_prob(sims, line, side):
    if side.lower() == "over":
        return float(np.mean(sims > line))
    return float(np.mean(sims <= line))


def implied_from_american(odds):
    if odds is None or pd.isna(odds):
        return None
    return 100.0 / (odds + 100.0) if odds > 0 else -odds / (-odds + 100.0)


def trust_score(values, line, side, l10, season, status):
    vals = np.asarray(values, dtype=float)
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return 0.0
    hits = int(np.sum(vals > line)) if side.lower() == "over" else int(np.sum(vals <= line))
    hit_pct = (hits / len(vals)) * 100
    sample_score = min(len(vals) / 25.0, 1.0) * 100
    mean = np.mean(vals)
    consistency = max(0, (1 - min(np.std(vals, ddof=1) / mean if (mean > 0 and len(vals) > 1) else 1, 1)) * 100)
    form = max(0, 100 - abs(l10 - season) / season * 100) if (season and season > 0 and l10 is not None) else 50
    status_map = {"active": 100, "probable": 90, "day-to-day": 75,
                  "questionable": 50, "doubtful": 20, "out": 0, "ir": 0}
    status_sc = status_map.get((status or "active").lower().split()[0], 100)
    return round(hit_pct * 0.4 + sample_score * 0.2 + consistency * 0.15 + form * 0.15 + status_sc * 0.1, 1)


def signal_tier(trust, edge_pp):
    if edge_pp is None:
        return "⚪"
    if trust >= TRUST_THRESHOLD and edge_pp >= EDGE_THRESHOLD:
        return "🔥"
    if trust >= TRUST_THRESHOLD:
        return "🎯"
    if edge_pp >= EDGE_THRESHOLD:
        return "💎"
    if edge_pp < 0:
        return "🔴"
    return "🟡"


def bet_size(trust, edge_pp, tier):
    if tier == "🔥":
        return 10
    if tier == "🎯":
        if trust >= 90: return 10
        if trust >= 80: return 7
        return 5
    if tier == "💎":
        if edge_pp >= 12 and trust >= 70: return 7
        if edge_pp >= 8 and trust >= 65: return 5
        if edge_pp >= 5 and trust >= 60: return 3
    return 0


# ============================================================
# PIPELINE
# ============================================================

def get_nba_history(player: str, stat: str):
    pid = bdl_player_id(player)
    if pid is None:
        return None
    log = bdl_game_log(pid)
    if log.empty:
        return None
    col = BDL_STAT_FIELDS.get(stat)
    if col is None or col not in log.columns:
        return None
    values = log[col].astype(float).values
    if len(values) == 0:
        return None
    return {
        "values": values,
        "n_games": len(values),
        "season_avg": float(np.mean(values)),
        "l10_avg": float(np.mean(values[:min(10, len(values))])),
        "std_dev": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
    }


def get_mlb_history(player: str, stat: str):
    pid = mlb_player_id(player)
    if pid is None:
        return None
    pitcher = stat in {"Strikeouts", "Earned Runs", "Outs Recorded", "Hits Allowed", "Walks Issued"}
    log = mlb_game_log(pid, "pitching" if pitcher else "hitting")
    if log.empty:
        return None
    field_map = {"Hits": "hits", "Total Bases": "totalBases", "RBI": "rbi", "Runs": "runs",
                 "Home Runs": "homeRuns", "Strikeouts": "strikeouts",
                 "Earned Runs": "earnedRuns", "Outs Recorded": "outsRecorded",
                 "Hits Allowed": "hitsAllowed", "Walks Issued": "walks"}
    col = field_map.get(stat)
    if col is None or col not in log.columns:
        return None
    values = log[col].astype(float).values
    if len(values) == 0:
        return None
    return {
        "values": values, "n_games": len(values),
        "season_avg": float(np.mean(values)),
        "l10_avg": float(np.mean(values[:min(10, len(values))])),
        "std_dev": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
    }


def analyze_one(prop: dict, league: str, injuries: dict, vegas_total: float):
    """Returns row dict if tier qualifies, else None."""
    player = prop["player"]
    stat = prop["stat"]
    line = prop["line"]
    over_odds = prop.get("over_odds")
    under_odds = prop.get("under_odds")

    hist = get_nba_history(player, stat) if league == "nba" else get_mlb_history(player, stat)
    if hist is None:
        return None

    inj_status = injuries.get(player.lower(), {}).get("status", "Active") or "Active"
    minutes_mult = STATUS_MULTIPLIER.get(inj_status.split()[0] if inj_status else "Active", 1.0)

    total_mult = 1.0
    if vegas_total:
        if league == "nba" and stat in ("Points", "Rebounds", "Assists"):
            total_mult = vegas_total / 225.0
        elif league == "mlb" and stat in ("Hits", "Total Bases", "RBI", "Runs", "Home Runs"):
            total_mult = vegas_total / 8.5

    sims = build_distribution(hist["values"])
    if minutes_mult != 1.0 or total_mult != 1.0:
        sims = np.round(sims * minutes_mult * total_mult).astype(int).clip(min=0)

    p_over = hit_prob(sims, line, "Over")
    p_under = 1 - p_over
    imp_over = implied_from_american(over_odds)
    imp_under = implied_from_american(under_odds)

    # Pick best side
    best_side, best_p, best_imp = "Over", p_over, imp_over
    if imp_over is None and imp_under is not None:
        best_side, best_p, best_imp = "Under", p_under, imp_under
    elif imp_over is not None and imp_under is not None:
        if (p_under - imp_under) > (p_over - imp_over):
            best_side, best_p, best_imp = "Under", p_under, imp_under

    if best_imp is None:
        return None

    trust = trust_score(hist["values"], line, best_side,
                        hist["l10_avg"], hist["season_avg"], inj_status)
    edge_pp = (best_p - best_imp) * 100
    edge_sc = min(max(edge_pp, 0) / 25.0, 1.0) * 100

    tier = signal_tier(trust, edge_pp)
    if tier not in LOG_TIERS:
        return None  # Skip non-qualifying tiers

    bet = bet_size(trust, edge_pp, tier)

    return {
        "snapshot_date": date.today().isoformat(),
        "league": league,
        "event_id": prop.get("event_id"),
        "commence_time": prop.get("commence_time"),
        "home_team": prop.get("home", ""),
        "away_team": prop.get("away", ""),
        "player": player,
        "stat": stat,
        "line": float(line),
        "side": best_side,
        "book": prop.get("book", ""),
        "over_odds": over_odds,
        "under_odds": under_odds,
        "tier": tier,
        "trust_score": trust,
        "edge_score": round(edge_sc, 1),
        "edge_pp": round(edge_pp, 2),
        "model_prob_over": round(p_over * 100, 2),
        "model_prob_under": round(p_under * 100, 2),
        "implied_prob_over": round(imp_over * 100, 2) if imp_over else None,
        "implied_prob_under": round(imp_under * 100, 2) if imp_under else None,
        "suggested_bet_dollars": bet,
        "l10_avg": round(hist["l10_avg"], 2),
        "season_avg": round(hist["season_avg"], 2),
        "sample_size": hist["n_games"],
        "std_dev": round(hist["std_dev"], 2),
        "injury_status": inj_status,
        "minutes_mult": minutes_mult,
        "vegas_total": vegas_total,
        "notes": None,
    }


def run_league_snapshot(league: str):
    """Run snapshot for one league. Returns (processed, written)."""
    print(f"\n=== Snapshot: {league.upper()} ===")
    if league == "nba":
        sport = "basketball_nba"
        markets = list(NBA_STAT_MARKETS.values())
        market_map = NBA_STAT_MARKETS
    else:
        sport = "baseball_mlb"
        markets = list(MLB_STAT_MARKETS.values())
        market_map = MLB_STAT_MARKETS

    raw_props, err = fetch_odds_props(sport, markets)
    if err:
        print(f"⚠️  Props fetch: {err}")
        return 0, 0

    grouped = consolidate_props(raw_props, market_map)
    print(f"  Props pulled: {len(grouped)}")

    if not grouped:
        return 0, 0

    injuries = fetch_injuries(league)
    print(f"  Injury feed: {len(injuries)} entries")

    # Pre-fetch totals per unique event
    event_totals = {}
    unique_events = set(p.get("event_id") for p in grouped if p.get("event_id"))
    for eid in unique_events:
        event_totals[eid] = fetch_event_total(sport, eid)
        time.sleep(0.1)  # gentle rate limiting

    # Analyze each prop
    qualifying = []
    for i, prop in enumerate(grouped):
        if i % 25 == 0:
            print(f"  Analyzing {i}/{len(grouped)}...")
        try:
            vegas_total = event_totals.get(prop.get("event_id"))
            row = analyze_one(prop, league, injuries, vegas_total)
            if row:
                qualifying.append(row)
        except Exception as e:
            print(f"  ⚠️  Error on {prop.get('player')}: {e}")

    print(f"  Qualifying picks (🔥/🎯/💎): {len(qualifying)}")

    # Write to Supabase
    written = supabase_upsert("dfs_shadow_picks", qualifying,
                              on_conflict="snapshot_date,league,player,stat,line,side,book")
    print(f"  Written to Supabase: {written}")

    return len(grouped), written


def main():
    print(f"=== DFS Snapshot — {datetime.now().isoformat()} ===")
    run_id = log_run_start("snapshot")

    total_processed = 0
    total_written = 0
    errors_log = []

    for league in ("nba", "mlb"):
        try:
            proc, writ = run_league_snapshot(league)
            total_processed += proc
            total_written += writ
        except Exception as e:
            err_msg = f"{league}: {e}"
            print(f"❌ {err_msg}")
            errors_log.append(err_msg)

    status = "success" if not errors_log else ("partial" if total_written > 0 else "failed")
    log_run_end(run_id, status, total_processed, total_written,
                "; ".join(errors_log) if errors_log else None)

    print(f"\n=== Done ===")
    print(f"Total processed: {total_processed}")
    print(f"Total written: {total_written}")
    print(f"Status: {status}")
    sys.exit(0 if status != "failed" else 1)


if __name__ == "__main__":
    main()
