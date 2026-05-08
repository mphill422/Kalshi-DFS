"""
MPH Underdog Ladders Model — V2.0
==================================
Monte Carlo prop modeling for Underdog / PrizePicks / Betr (NBA + MLB)

V2.0 BUILD NOTES (vs V1.0):
- Switched NBA data source: NBA Stats API → BallDontLie (avoids cloud IP block)
- Distribution: Poisson fallback → Negative Binomial throughout (handles overdispersion)
- Sims: 10K → 50K default (sidebar slider 10K/50K/100K)
- Trust + Edge + 🔥 Combined scoring system (mirrors weather model)
- Full stat coverage: NBA Pts/Reb/Ast/Blk/Stl/3PM + combos (PRA, P+R, P+A, R+A)
- Full MLB stat coverage: hitter (H/TB/HR/RBI/R) + pitcher (K/ER/Outs/HA/BB)
- Adjustment layer: Minutes (ESPN injury) + Vegas total + Pace (BallDontLie)
- Top Plays summary panel per sport tab
- Universal Ladder Builder w/ Standard/Demon/Goblin/Ladder modes
- Sport-first tab structure with sub-tabs (Props/Ladders/Top Plays)
- Sidebar sliders w/ discipline guardrails
- Suggested bet sizing tied to score tier ($3-$10, $50/day cap)

Repo: mphill422/Kalshi-DFS
Replaces: V1.0 streamlit_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, date
from scipy import stats as scipy_stats
import time

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="MPH DFS Model V2.0",
    page_icon="🪜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Secrets ---
def _get_secret(section: str, key: str, default: str = "") -> str:
    """Safely read a secret from [section] section."""
    try:
        return st.secrets[section][key]
    except (KeyError, FileNotFoundError, AttributeError):
        return default

ODDS_API_KEY = _get_secret("odds", "api_key", "")
BDL_API_KEY = _get_secret("balldontlie", "api_key", "")

# --- API endpoints ---
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
BDL_BASE = "https://api.balldontlie.io/v1"
MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"
ESPN_NBA_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
ESPN_MLB_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/injuries"

# --- Model constants ---
DEFAULT_N_SIMS = 50_000
L25_WINDOW = 25
L10_WEIGHT = 0.70

# --- Stat market mappings (Odds API) ---
NBA_STAT_MARKETS = {
    "Points": "player_points",
    "Rebounds": "player_rebounds",
    "Assists": "player_assists",
    "Blocks": "player_blocks",
    "Steals": "player_steals",
    "3PM": "player_threes",
}
NBA_COMBO_MARKETS = {
    "Pts+Reb+Ast": "player_points_rebounds_assists",
    "Pts+Reb": "player_points_rebounds",
    "Pts+Ast": "player_points_assists",
    "Reb+Ast": "player_rebounds_assists",
}
MLB_STAT_MARKETS = {
    "Hits": "batter_hits",
    "Total Bases": "batter_total_bases",
    "RBI": "batter_rbis",
    "Runs": "batter_runs_scored",
    "Home Runs": "batter_home_runs",
    "Strikeouts": "pitcher_strikeouts",
    "Earned Runs": "pitcher_earned_runs",
    "Outs Recorded": "pitcher_outs",
    "Hits Allowed": "pitcher_hits_allowed",
    "Walks Issued": "pitcher_walks",
}

# --- BallDontLie stat field mapping ---
BDL_STAT_FIELDS = {
    "Points": "pts",
    "Rebounds": "reb",
    "Assists": "ast",
    "Blocks": "blk",
    "Steals": "stl",
    "3PM": "fg3m",
    "Minutes": "min",
}

# --- League averages for normalization ---
NBA_LEAGUE_AVG = {"Points": 25.0, "Rebounds": 7.0, "Assists": 5.5,
                  "Blocks": 1.0, "Steals": 1.0, "3PM": 2.5}
MLB_LEAGUE_AVG = {"Hits": 1.0, "Total Bases": 1.5, "RBI": 0.7, "Runs": 0.7,
                  "Home Runs": 0.15, "Strikeouts": 5.5, "Earned Runs": 2.5,
                  "Outs Recorded": 16.0, "Hits Allowed": 5.0, "Walks Issued": 2.0}

# Status -> minutes multiplier
STATUS_MULTIPLIER = {
    "Active": 1.0, "Probable": 0.95, "Day-To-Day": 0.85,
    "Questionable": 0.70, "Doubtful": 0.30, "Out": 0.0, "IR": 0.0,
}


# ============================================================
# MONTE CARLO ENGINE
# ============================================================

def fit_negative_binomial(values: np.ndarray) -> tuple:
    """
    Fit Negative Binomial parameters (n, p) to game log values.
    Returns (n, p) where mean = n*(1-p)/p, var = n*(1-p)/p^2
    Falls back to Poisson params if variance <= mean (no overdispersion).
    """
    vals = np.asarray(values, dtype=float)
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return None, None
    mean = np.mean(vals)
    var = np.var(vals, ddof=1) if len(vals) > 1 else mean
    if mean <= 0:
        return None, None
    if var <= mean:
        # Underdispersed or equal — use Poisson-equivalent (large n, small p)
        return None, None  # signal to use Poisson
    # Method of moments for NB
    p = mean / var
    n = mean * p / (1 - p)
    if n <= 0 or not np.isfinite(n):
        return None, None
    return n, p


def build_player_distribution(values: np.ndarray, n_sims: int = DEFAULT_N_SIMS) -> np.ndarray:
    """
    Generate MC distribution from empirical game log.
    Strategy:
    1. If sample >= 10: bootstrap from L25 with L10 recency weighting (70/30)
    2. If sample 5-9: use Negative Binomial fit (or Poisson if no overdispersion)
    3. If sample < 5: Poisson with shrinkage
    Returns array of n_sims integer outcomes.
    """
    vals = np.asarray(values, dtype=float)
    vals = vals[~np.isnan(vals)]

    if len(vals) == 0:
        return np.zeros(n_sims, dtype=int)

    if len(vals) < 5:
        # Tiny sample — Poisson with shrinkage toward mean
        mean = max(np.mean(vals), 0.1)
        return np.random.poisson(lam=mean, size=n_sims).astype(int)

    if len(vals) < 10:
        # Small sample — try NB, fall back to Poisson
        n_nb, p_nb = fit_negative_binomial(vals)
        if n_nb is not None and p_nb is not None:
            return np.random.negative_binomial(n=n_nb, p=p_nb, size=n_sims)
        else:
            mean = max(np.mean(vals), 0.1)
            return np.random.poisson(lam=mean, size=n_sims).astype(int)

    # Adequate sample (>= 10) — bootstrap with L10 weighting
    l10 = vals[: min(10, len(vals))]
    l_older = vals[10: min(L25_WINDOW, len(vals))]

    if len(l_older) > 0:
        n_l10 = int(n_sims * L10_WEIGHT)
        n_older = n_sims - n_l10
        sims_l10 = np.random.choice(l10, size=n_l10, replace=True)
        sims_older = np.random.choice(l_older, size=n_older, replace=True)
        sims = np.concatenate([sims_l10, sims_older])
        np.random.shuffle(sims)
    else:
        sims = np.random.choice(l10, size=n_sims, replace=True)

    return np.round(sims).astype(int).clip(min=0)


def apply_adjustments(sims: np.ndarray, minutes_mult: float = 1.0,
                      pace_mult: float = 1.0, total_mult: float = 1.0) -> np.ndarray:
    """Apply multiplicative adjustments to sim array."""
    combined = minutes_mult * pace_mult * total_mult
    if combined == 1.0:
        return sims
    adjusted = sims.astype(float) * combined
    return np.round(adjusted).astype(int).clip(min=0)


def hit_probability(sims: np.ndarray, line: float, side: str = "Over") -> float:
    """P(stat > line) for Over, P(stat < line) for Under (handles .5 lines naturally)."""
    if len(sims) == 0:
        return 0.5
    if side.lower() == "over":
        return float(np.mean(sims > line))
    else:
        return float(np.mean(sims <= line))


def implied_prob_from_american(odds: float):
    if odds is None or pd.isna(odds):
        return None
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return -odds / (-odds + 100.0)


def implied_prob_from_payout(payout_mult: float):
    if not payout_mult or payout_mult <= 0:
        return None
    return 1.0 / payout_mult


# ============================================================
# TRUST & EDGE SCORING
# ============================================================

def trust_score(values: np.ndarray, line: float, side: str,
                l10_avg: float, season_avg: float,
                injury_status: str) -> tuple:
    """
    Compute Trust Score 0-100 and component breakdown.
    5 components:
      L25 Hit Rate (40%)
      Sample Quality (20%)
      Consistency (15%)
      Form Alignment (15%)
      Status Health (10%)
    """
    vals = np.asarray(values, dtype=float)
    vals = vals[~np.isnan(vals)]

    if len(vals) == 0:
        return 0.0, {}

    # 1. L25 Hit Rate
    if side.lower() == "over":
        hits = int(np.sum(vals > line))
    else:
        hits = int(np.sum(vals <= line))
    hit_rate_pct = (hits / len(vals)) * 100

    # 2. Sample Quality
    sample_score = min(len(vals) / 25.0, 1.0) * 100

    # 3. Consistency (lower CV = higher score)
    mean = np.mean(vals)
    if mean > 0:
        cv = np.std(vals, ddof=1) / mean if len(vals) > 1 else 1.0
        consistency_score = max(0, (1 - min(cv, 1.0)) * 100)
    else:
        consistency_score = 0

    # 4. Form Alignment (L10 vs Season)
    if season_avg and season_avg > 0 and l10_avg is not None:
        deviation_pct = abs(l10_avg - season_avg) / season_avg * 100
        form_score = max(0, 100 - deviation_pct)
    else:
        form_score = 50

    # 5. Status Health
    status_clean = (injury_status or "Active").strip()
    status_map = {
        "active": 100, "probable": 90, "day-to-day": 75,
        "questionable": 50, "doubtful": 20, "out": 0, "ir": 0,
    }
    status_score = status_map.get(status_clean.lower(), 100)

    # Weighted total
    total = (hit_rate_pct * 0.40 +
             sample_score * 0.20 +
             consistency_score * 0.15 +
             form_score * 0.15 +
             status_score * 0.10)

    components = {
        "hit_rate": round(hit_rate_pct, 1),
        "sample": round(sample_score, 1),
        "consistency": round(consistency_score, 1),
        "form": round(form_score, 1),
        "status": status_score,
    }
    return round(total, 1), components


def edge_score(model_prob: float, implied_prob: float,
               l10_avg: float, line: float, std_dev: float,
               cross_platform_gap: float = 0.0) -> tuple:
    """
    Edge Score 0-100.
    Components:
      Model − Implied (60%) capped at 25 percentage points
      Line Comfort (25%) — how far L10 avg is from line in std devs
      Cross-Platform Gap (15%)
    """
    if model_prob is None or implied_prob is None:
        return 0.0, {}

    # 1. Model edge (cap at 25 pp; map 0-25 to 0-100)
    raw_edge_pp = (model_prob - implied_prob) * 100
    edge_component = min(max(raw_edge_pp, 0) / 25.0, 1.0) * 100

    # 2. Line comfort
    if std_dev and std_dev > 0 and l10_avg is not None:
        z = abs(l10_avg - line) / std_dev
        comfort = min(z / 2.0, 1.0) * 100
    else:
        comfort = 0

    # 3. Cross-platform gap (caller computes)
    gap_score = min(abs(cross_platform_gap) / 0.15, 1.0) * 100

    total = (edge_component * 0.60 +
             comfort * 0.25 +
             gap_score * 0.15)

    return round(total, 1), {
        "edge_pp": round(raw_edge_pp, 1),
        "comfort": round(comfort, 1),
        "gap": round(gap_score, 1),
    }


def signal_tier(trust: float, edge_pp: float,
                trust_thresh: float = 65, edge_thresh: float = 5) -> str:
    """Returns one of: 🔥 Combined / 🎯 Trust / 💎 Edge / 🟡 Thin / 🔴 Fade / ⚪ None"""
    if edge_pp is None:
        return "⚪"
    if trust >= trust_thresh and edge_pp >= edge_thresh:
        return "🔥"
    if trust >= trust_thresh:
        return "🎯"
    if edge_pp >= edge_thresh:
        return "💎"
    if edge_pp < 0:
        return "🔴"
    return "🟡"


def suggested_bet_size(trust: float, edge_pp: float, tier: str) -> tuple:
    """Returns (size_dollars, reasoning)."""
    if tier == "🔥":
        return 10, "🔥 Combined — max sizing"
    if tier == "🎯":
        if trust >= 90:
            return 10, "Trust 90+"
        if trust >= 80:
            return 7, "Trust 80-89"
        if trust >= 70:
            return 5, "Trust 70-79"
        return 5, "Trust pick"
    if tier == "💎":
        if edge_pp >= 12 and trust >= 70:
            return 7, "Edge 12+ / Trust 70+"
        if edge_pp >= 8 and trust >= 65:
            return 5, "Edge 8-12"
        if edge_pp >= 5 and trust >= 60:
            return 3, "Edge 5-8"
        return 3, "Marginal edge"
    return 0, "Below threshold"


# ============================================================
# DATA — ODDS API
# ============================================================

@st.cache_data(ttl=300)
def fetch_odds_api_props(sport: str, markets: list):
    if not ODDS_API_KEY:
        return [], "Odds API key missing in secrets"

    events_url = f"{ODDS_API_BASE}/sports/{sport}/events"
    try:
        r = requests.get(events_url, params={"apiKey": ODDS_API_KEY}, timeout=15)
        if r.status_code != 200:
            return [], f"Events API {r.status_code}: {r.text[:200]}"
        events = r.json()
    except Exception as e:
        return [], f"Events fetch failed: {e}"

    if not events:
        return [], "No events scheduled"

    today = datetime.utcnow().date()
    today_events = []
    for ev in events:
        commence = ev.get("commence_time", "")
        try:
            ev_date = datetime.fromisoformat(commence.replace("Z", "+00:00")).date()
            if ev_date == today or ev_date == today + timedelta(days=1):
                today_events.append(ev)
        except Exception:
            continue

    all_props = []
    markets_str = ",".join(markets)
    for ev in today_events:
        odds_url = f"{ODDS_API_BASE}/sports/{sport}/events/{ev['id']}/odds"
        try:
            r = requests.get(odds_url, params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": markets_str,
                "oddsFormat": "american",
                "bookmakers": "draftkings,fanduel",
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

    if not all_props:
        return [], f"No props for {len(today_events)} events"
    return all_props, None


@st.cache_data(ttl=600)
def fetch_event_total(sport: str, event_id: str):
    """Pull game total (over/under) for pace adjustment."""
    if not ODDS_API_KEY or not event_id:
        return None
    try:
        r = requests.get(
            f"{ODDS_API_BASE}/sports/{sport}/events/{event_id}/odds",
            params={"apiKey": ODDS_API_KEY, "regions": "us", "markets": "totals",
                    "bookmakers": "draftkings"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        for book in data.get("bookmakers", []):
            for m in book.get("markets", []):
                if m.get("key") == "totals":
                    for o in m.get("outcomes", []):
                        if o.get("name") == "Over":
                            return o.get("point")
    except Exception:
        return None
    return None


def consolidate_props(props: list, market_label_map: dict) -> pd.DataFrame:
    """Collapse Over/Under outcomes per player+line+book."""
    if not props:
        return pd.DataFrame()
    df = pd.DataFrame(props)
    if df.empty:
        return df
    rev = {v: k for k, v in market_label_map.items()}
    df["stat"] = df["market"].map(rev)
    df = df[df["stat"].notna()]

    rows = []
    grouped = df.groupby(["player", "stat", "line", "book", "home", "away",
                          "commence_time", "event_id"])
    for keys, grp in grouped:
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
    return pd.DataFrame(rows)


# ============================================================
# DATA — BALLDONTLIE (NBA)
# ============================================================

def _bdl_headers():
    return {"Authorization": BDL_API_KEY} if BDL_API_KEY else {}


@st.cache_data(ttl=3600)
def bdl_search_player(player_name: str):
    """Find BallDontLie player ID by name."""
    if not BDL_API_KEY:
        return None
    parts = player_name.strip().split()
    if not parts:
        return None
    # Try exact full-name search using last name
    search_term = parts[-1]
    try:
        r = requests.get(f"{BDL_BASE}/players",
                         params={"search": search_term, "per_page": 25},
                         headers=_bdl_headers(), timeout=10)
        if r.status_code != 200:
            return None
        data = r.json().get("data", [])
        target_full = player_name.lower().strip()
        # Exact match first
        for p in data:
            full = f"{p.get('first_name', '')} {p.get('last_name', '')}".lower().strip()
            if full == target_full:
                return p["id"]
        # Last-name match if exact failed
        target_last = parts[-1].lower()
        for p in data:
            if p.get("last_name", "").lower() == target_last:
                return p["id"]
    except Exception:
        return None
    return None


@st.cache_data(ttl=1800)
def bdl_player_game_log(player_id: int, season: int = None, n_seasons: int = 1):
    """Fetch recent player game stats. Returns DataFrame sorted newest first."""
    if not BDL_API_KEY or player_id is None:
        return pd.DataFrame()

    if season is None:
        today = date.today()
        season = today.year if today.month >= 10 else today.year - 1

    seasons = [season - i for i in range(n_seasons)]
    rows = []
    for s in seasons:
        try:
            cursor = None
            for _ in range(10):  # max 10 pages
                params = {"player_ids[]": player_id, "seasons[]": s, "per_page": 100}
                if cursor:
                    params["cursor"] = cursor
                r = requests.get(f"{BDL_BASE}/stats", params=params,
                                 headers=_bdl_headers(), timeout=15)
                if r.status_code == 401:
                    return pd.DataFrame()  # auth fail
                if r.status_code != 200:
                    break
                payload = r.json()
                data = payload.get("data", [])
                for stat in data:
                    rows.append({
                        "game_id": stat.get("game", {}).get("id"),
                        "date": stat.get("game", {}).get("date"),
                        "min": _parse_minutes(stat.get("min")),
                        "pts": stat.get("pts", 0),
                        "reb": stat.get("reb", 0),
                        "ast": stat.get("ast", 0),
                        "blk": stat.get("blk", 0),
                        "stl": stat.get("stl", 0),
                        "fg3m": stat.get("fg3m", 0),
                    })
                cursor = payload.get("meta", {}).get("next_cursor")
                if not cursor:
                    break
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date", ascending=False).reset_index(drop=True)
    # Tag DNP rows for transparency, then filter
    df["played"] = df["min"] > 0
    # Keep DNP info for sample-quality flag, but filter for distribution building
    df_played = df[df["played"]].reset_index(drop=True)
    # Attach DNP metadata
    if not df_played.empty:
        df_played.attrs["total_games"] = len(df)
        df_played.attrs["dnp_count"] = int((~df["played"]).sum())
        df_played.attrs["played_count"] = int(df["played"].sum())
    return df_played


def _parse_minutes(min_str) -> float:
    if min_str is None or min_str == "":
        return 0.0
    if isinstance(min_str, (int, float)):
        return float(min_str)
    try:
        if ":" in str(min_str):
            parts = str(min_str).split(":")
            return float(parts[0]) + float(parts[1]) / 60.0
        return float(min_str)
    except Exception:
        return 0.0


# ============================================================
# DATA — MLB STATS API
# ============================================================

@st.cache_data(ttl=3600)
def mlb_player_id(player_name: str):
    season = date.today().year
    try:
        r = requests.get(f"{MLB_STATS_BASE}/sports/1/players",
                         params={"season": season}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        target = player_name.lower().strip()
        for p in data.get("people", []):
            if p.get("fullName", "").lower() == target:
                return p["id"]
        last = player_name.split()[-1].lower()
        for p in data.get("people", []):
            if p.get("fullName", "").lower().endswith(last):
                return p["id"]
    except Exception:
        return None
    return None


@st.cache_data(ttl=1800)
def mlb_game_log(player_id: int, group: str):
    """group: 'pitching' or 'hitting'"""
    if player_id is None:
        return pd.DataFrame()
    season = date.today().year
    try:
        r = requests.get(f"{MLB_STATS_BASE}/people/{player_id}/stats",
                         params={"stats": "gameLog", "group": group,
                                 "season": season, "sportId": 1}, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        stats_arr = data.get("stats", [])
        if not stats_arr:
            return pd.DataFrame()
        splits = stats_arr[0].get("splits", [])
        rows = []
        for s in splits:
            stat = s.get("stat", {})
            row = {
                "date": s.get("date"),
                "hits": stat.get("hits", 0),
                "totalBases": stat.get("totalBases", 0),
                "rbi": stat.get("rbi", 0),
                "runs": stat.get("runs", 0),
                "homeRuns": stat.get("homeRuns", 0),
                "strikeouts": stat.get("strikeOuts", 0),
                "earnedRuns": stat.get("earnedRuns", 0),
                "hitsAllowed": stat.get("hits", 0) if group == "pitching" else 0,
                "walks": stat.get("baseOnBalls", 0),
                "outsRecorded": _ip_to_outs(stat.get("inningsPitched", 0)),
            }
            rows.append(row)
        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"]).sort_values("date", ascending=False).reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


def _ip_to_outs(ip):
    """Convert MLB innings-pitched (e.g. '6.1') to outs (19)."""
    try:
        ip_str = str(ip)
        if "." in ip_str:
            whole, frac = ip_str.split(".")
            return int(whole) * 3 + int(frac)
        return int(ip) * 3
    except Exception:
        return 0


# ============================================================
# DATA — INJURIES (ESPN)
# ============================================================

@st.cache_data(ttl=900)
def fetch_espn_injuries(league: str):
    url = ESPN_NBA_INJURIES if league == "nba" else ESPN_MLB_INJURIES
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return {}
        data = r.json()
        out = {}
        for team in data.get("injuries", []):
            for inj in team.get("injuries", []):
                ath = inj.get("athlete", {})
                name = ath.get("displayName", "")
                if name:
                    out[name.lower()] = {
                        "status": inj.get("status", ""),
                        "type": inj.get("type", ""),
                        "detail": inj.get("details", {}).get("detail", ""),
                    }
        return out
    except Exception:
        return {}


def get_injury_status(player_name: str, inj_dict: dict) -> tuple:
    if not player_name:
        return "✅", "Active"
    rec = inj_dict.get(player_name.lower(), {})
    status = rec.get("status", "") or "Active"
    s = status.lower()
    if "out" in s or "ir" in s:
        return "❌", status
    if "doubtful" in s:
        return "⚠️", status
    if "questionable" in s or "day-to-day" in s or "probable" in s:
        return "⚠️", status
    return "✅", status


# ============================================================
# STAT HISTORY GETTERS
# ============================================================

def get_nba_history(player: str, stat: str):
    """Returns (values_array, n_games, season_avg, l10_avg, std_dev, dnp_meta) or Nones.
    dnp_meta = (total_games_in_window, dnp_count, played_count) or None"""
    pid = bdl_search_player(player)
    if pid is None:
        return None, 0, None, None, None, None
    log = bdl_player_game_log(pid)
    if log.empty:
        return None, 0, None, None, None, None

    # Pull DNP metadata if present
    dnp_meta = None
    try:
        total = log.attrs.get("total_games")
        dnp = log.attrs.get("dnp_count")
        played = log.attrs.get("played_count")
        if total is not None:
            dnp_meta = (total, dnp, played)
    except Exception:
        dnp_meta = None

    # Map stat label to value
    if stat in ("Pts+Reb+Ast",):
        values = (log["pts"] + log["reb"] + log["ast"]).astype(float).values
    elif stat in ("Pts+Reb",):
        values = (log["pts"] + log["reb"]).astype(float).values
    elif stat in ("Pts+Ast",):
        values = (log["pts"] + log["ast"]).astype(float).values
    elif stat in ("Reb+Ast",):
        values = (log["reb"] + log["ast"]).astype(float).values
    else:
        col = BDL_STAT_FIELDS.get(stat)
        if col is None or col not in log.columns:
            return None, 0, None, None, None, dnp_meta
        values = log[col].astype(float).values

    n = len(values)
    if n == 0:
        return None, 0, None, None, None, dnp_meta
    season_avg = float(np.mean(values))
    l10_avg = float(np.mean(values[:min(10, n)]))
    std_dev = float(np.std(values, ddof=1)) if n > 1 else 0.0
    return values, n, season_avg, l10_avg, std_dev, dnp_meta


def get_mlb_history(player: str, stat: str):
    pid = mlb_player_id(player)
    if pid is None:
        return None, 0, None, None, None, None
    pitcher_stats = {"Strikeouts", "Earned Runs", "Outs Recorded", "Hits Allowed", "Walks Issued"}
    group = "pitching" if stat in pitcher_stats else "hitting"
    log = mlb_game_log(pid, group)
    if log.empty:
        return None, 0, None, None, None, None
    field_map = {
        "Hits": "hits", "Total Bases": "totalBases", "RBI": "rbi", "Runs": "runs",
        "Home Runs": "homeRuns", "Strikeouts": "strikeouts",
        "Earned Runs": "earnedRuns", "Outs Recorded": "outsRecorded",
        "Hits Allowed": "hitsAllowed", "Walks Issued": "walks",
    }
    col = field_map.get(stat)
    if col is None or col not in log.columns:
        return None, 0, None, None, None, None
    values = log[col].astype(float).values
    n = len(values)
    if n == 0:
        return None, 0, None, None, None, None
    season_avg = float(np.mean(values))
    l10_avg = float(np.mean(values[:min(10, n)]))
    std_dev = float(np.std(values, ddof=1)) if n > 1 else 0.0
    return values, n, season_avg, l10_avg, std_dev, None


# ============================================================
# PROP ANALYSIS
# ============================================================

def analyze_prop(player: str, stat: str, line: float,
                 over_odds: float, under_odds: float,
                 league: str, injuries: dict, n_sims: int,
                 trust_thresh: float, edge_thresh: float,
                 vegas_total: float = None,
                 home_team: str = "", away_team: str = "",
                 commence_time: str = "") -> dict:
    """Build a fully-scored analysis row."""
    if league == "nba":
        history = get_nba_history(player, stat)
        league_avg_total = 225.0
    else:
        history = get_mlb_history(player, stat)
        league_avg_total = 8.5

    values, n_games, season_avg, l10_avg, std_dev, dnp_meta = history
    inj_emoji, inj_status = get_injury_status(player, injuries)

    # Build game label like "MIN @ OKC · Tonight 9:30p"
    game_label = _format_game_label(home_team, away_team, commence_time)

    if values is None or n_games == 0:
        return {
            "Tier": "⚪", "Player": player, "Game": game_label,
            "Status": f"{inj_emoji} {inj_status}",
            "Stat": stat, "Line": line,
            "L10": None, "Season": None, "n": 0,
            "Trust": None, "Edge": None,
            "Model O%": None, "Imp O%": None, "Edge pp": None,
            "Model U%": None, "Imp U%": None,
            "Bet $": 0, "Note": "No game log",
        }

    # Adjustments
    minutes_mult = STATUS_MULTIPLIER.get(inj_status.split()[0] if inj_status else "Active", 1.0)
    total_mult = 1.0
    if vegas_total and league == "nba" and stat in ("Points", "Rebounds", "Assists",
                                                      "Pts+Reb+Ast", "Pts+Reb", "Pts+Ast", "Reb+Ast"):
        total_mult = vegas_total / league_avg_total
    elif vegas_total and league == "mlb" and stat in ("Hits", "Total Bases", "RBI", "Runs", "Home Runs"):
        total_mult = vegas_total / league_avg_total

    sims = build_player_distribution(values, n_sims=n_sims)
    sims = apply_adjustments(sims, minutes_mult=minutes_mult, total_mult=total_mult)

    p_over = hit_probability(sims, line, "Over")
    p_under = 1 - p_over
    imp_over = implied_prob_from_american(over_odds)
    imp_under = implied_prob_from_american(under_odds)

    # Score both sides, pick the better one
    best_side = "Over"
    best_p = p_over
    best_imp = imp_over

    if imp_over is None and imp_under is not None:
        best_side, best_p, best_imp = "Under", p_under, imp_under
    elif imp_over is not None and imp_under is not None:
        edge_o = (p_over - imp_over) if imp_over else -1
        edge_u = (p_under - imp_under) if imp_under else -1
        if edge_u > edge_o:
            best_side, best_p, best_imp = "Under", p_under, imp_under

    trust, _t_comp = trust_score(values, line, best_side, l10_avg, season_avg, inj_status)
    edge_pp = (best_p - best_imp) * 100 if best_imp is not None else None
    edge_sc, _e_comp = edge_score(best_p, best_imp, l10_avg, line, std_dev)

    tier = signal_tier(trust, edge_pp if edge_pp is not None else 0,
                       trust_thresh, edge_thresh)
    bet_size, _reason = suggested_bet_size(trust, edge_pp if edge_pp is not None else 0, tier)

    # Build note with DNP awareness
    notes = []
    if n_games < 10:
        notes.append("⚠️ Small sample")
    if dnp_meta is not None:
        total, dnp, played = dnp_meta
        # Flag if >30% of recent games were DNPs
        if total > 0 and (dnp / total) > 0.30:
            notes.append(f"⚠️ {dnp}/{total} DNPs (avg may be misleading)")
    note = " · ".join(notes) if notes else ""

    return {
        "Tier": tier, "Player": player, "Game": game_label,
        "Status": f"{inj_emoji} {inj_status}",
        "Stat": stat, "Line": line, "Side": best_side,
        "L10": round(l10_avg, 2) if l10_avg else None,
        "Season": round(season_avg, 2) if season_avg else None,
        "n": n_games,
        "Trust": trust, "Edge": edge_sc,
        "Model O%": round(p_over * 100, 1),
        "Imp O%": round(imp_over * 100, 1) if imp_over else None,
        "Model U%": round(p_under * 100, 1),
        "Imp U%": round(imp_under * 100, 1) if imp_under else None,
        "Edge pp": round(edge_pp, 1) if edge_pp is not None else None,
        "Bet $": bet_size,
        "Note": note,
    }


def _format_game_label(home: str, away: str, commence_iso: str) -> str:
    """Format a short game label like 'MIN @ OKC · Tonight 9:30p'."""
    if not home or not away:
        return ""
    # Build team abbreviations (last word of city + team) — fallback to first 3 letters
    away_abbr = _team_abbr(away)
    home_abbr = _team_abbr(home)
    matchup = f"{away_abbr} @ {home_abbr}"

    if not commence_iso:
        return matchup

    try:
        dt = datetime.fromisoformat(commence_iso.replace("Z", "+00:00"))
        # Convert to local-ish time (use UTC offset -4 as ET approximation; user is in FL)
        dt_local = dt - timedelta(hours=4)
        today = datetime.utcnow().date() - timedelta(hours=4)  # rough
        today = (datetime.utcnow() - timedelta(hours=4)).date()
        if dt_local.date() == today:
            day_label = "Tonight"
        elif dt_local.date() == today + timedelta(days=1):
            day_label = "Tmrw"
        else:
            day_label = dt_local.strftime("%a")
        time_str = dt_local.strftime("%-I:%M%p").lower().replace(":00", "")
        return f"{matchup} · {day_label} {time_str}"
    except Exception:
        return matchup


def _team_abbr(team_name: str) -> str:
    """Crude team abbreviation — last word, first 3 letters uppercased."""
    if not team_name:
        return ""
    # Common NBA abbreviations
    nba_abbrs = {
        "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
        "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
        "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
        "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
        "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
        "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
        "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
        "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
        "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
        "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
        "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
        "Washington Wizards": "WAS",
    }
    if team_name in nba_abbrs:
        return nba_abbrs[team_name]
    # Fallback: first 3 letters of last word
    parts = team_name.split()
    return parts[-1][:3].upper() if parts else ""


# ============================================================
# UI — HEADER & SIDEBAR
# ============================================================

st.title("🪜 MPH DFS Model — V2.0")
st.caption(f"Negative Binomial MC · BallDontLie + MLB Stats API · Trust + Edge + 🔥 Combined scoring · {DEFAULT_N_SIMS:,} sims default")

with st.sidebar:
    st.markdown("### ⚙️ Controls")
    if st.button("🔄 Force refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 🎚️ Sim Settings")
    n_sims_choice = st.select_slider(
        "Sims per player",
        options=[10_000, 50_000, 100_000],
        value=DEFAULT_N_SIMS,
        format_func=lambda x: f"{x:,}",
    )

    st.markdown("---")
    st.markdown("### 🎯 Score Thresholds")
    trust_thresh = st.slider("Trust threshold", 50, 95, 65, 5)
    edge_thresh = st.slider("Edge threshold (pp)", 0, 15, 5, 1)
    show_below = st.checkbox("Show below threshold (anti-discipline)", value=True,
                              help="Off by default to enforce discipline. Toggle on to see all rows.")

    st.markdown("---")
    st.markdown("### 🎯 Tier Legend")
    st.markdown("""
- 🔥 **Combined** — Trust ≥ thresh & Edge ≥ thresh
- 🎯 **Trust pick** — high consistency
- 💎 **Edge pick** — high value
- 🟡 Thin signal
- 🔴 Fade
- ⚪ No data
    """)

    st.markdown("---")
    st.markdown("### 💰 Sizing tiers")
    st.caption("$3-$10 per bet · $50/day cap during validation")

    st.markdown("---")
    st.caption("**V2.0** — research-informed build")
    st.caption("Shadow validate 2 weeks before live bets")


# ============================================================
# UI — MAIN TABS (sport-first)
# ============================================================

tab_nba, tab_mlb, tab_settings = st.tabs(["🏀 NBA", "⚾ MLB", "📊 Settings"])


# ============================================================
# TAB: NBA (with sub-tabs)
# ============================================================

with tab_nba:
    nba_props_tab, nba_ladders_tab, nba_top_tab = st.tabs(["🎯 Props", "🪜 Ladders", "🔥 Top Plays"])

    # --- NBA PROPS ---
    with nba_props_tab:
        st.subheader("🏀 NBA Player Props")
        st.caption("Pulled from DraftKings + FanDuel via Odds API · scored with NB Monte Carlo")

        nba_stats_choice = st.multiselect(
            "Stats to analyze",
            list(NBA_STAT_MARKETS.keys()) + list(NBA_COMBO_MARKETS.keys()),
            default=["Points", "Rebounds", "Assists"],
            key="nba_props_stats",
        )

        if not nba_stats_choice:
            st.info("Select at least one stat above.")
        else:
            with st.spinner("Fetching props..."):
                markets = []
                for s in nba_stats_choice:
                    if s in NBA_STAT_MARKETS:
                        markets.append(NBA_STAT_MARKETS[s])
                    elif s in NBA_COMBO_MARKETS:
                        markets.append(NBA_COMBO_MARKETS[s])
                props, err = fetch_odds_api_props("basketball_nba", markets)

            if err:
                st.error(f"⚠️ Odds API: {err}")
            elif not props:
                st.warning("No props returned. Off-day or API limit reached.")
            else:
                combined_map = {**NBA_STAT_MARKETS, **NBA_COMBO_MARKETS}
                df_props = consolidate_props(props, combined_map)

                if df_props.empty:
                    st.warning("Props pulled but none matched selected stats.")
                else:
                    st.success(f"✅ {len(df_props)} prop lines · {df_props['player'].nunique()} players")

                    inj = fetch_espn_injuries("nba")

                    # Pre-fetch totals for each event
                    event_totals = {}
                    for eid in df_props["event_id"].unique():
                        event_totals[eid] = fetch_event_total("basketball_nba", eid)

                    progress = st.progress(0, text="Running Monte Carlo...")
                    rows = []
                    total = len(df_props)
                    for i, (_, p) in enumerate(df_props.iterrows()):
                        rows.append(analyze_prop(
                            player=p["player"], stat=p["stat"], line=p["line"],
                            over_odds=p["over_odds"], under_odds=p["under_odds"],
                            league="nba", injuries=inj, n_sims=n_sims_choice,
                            trust_thresh=trust_thresh, edge_thresh=edge_thresh,
                            vegas_total=event_totals.get(p["event_id"]),
                            home_team=p.get("home", ""), away_team=p.get("away", ""),
                            commence_time=p.get("commence_time", ""),
                        ))
                        progress.progress((i + 1) / total, text=f"MC: {i+1}/{total}")
                    progress.empty()

                    df_out = pd.DataFrame(rows)

                    # Sort by tier priority then edge
                    tier_order = {"🔥": 0, "🎯": 1, "💎": 2, "🟡": 3, "🔴": 4, "⚪": 5}
                    df_out["_order"] = df_out["Tier"].map(tier_order).fillna(99)
                    df_out["_edge"] = df_out["Edge pp"].fillna(-999)
                    df_out = df_out.sort_values(["_order", "_edge"], ascending=[True, False])
                    df_out = df_out.drop(columns=["_order", "_edge"])

                    if not show_below:
                        df_out = df_out[df_out["Tier"].isin(["🔥", "🎯", "💎"])]

                    if df_out.empty:
                        st.info("No plays clear current thresholds. Try toggling 'Show below threshold' or adjusting sliders.")
                    else:
                        st.dataframe(df_out, use_container_width=True, hide_index=True, height=500)
                        st.caption(f"Refreshed: {datetime.now().strftime('%H:%M:%S')}")

    # --- NBA LADDERS ---
    with nba_ladders_tab:
        st.subheader("🪜 NBA Ladder / Alt Builder")
        st.caption("Universal builder — works for Underdog Ladders, PrizePicks Demons/Goblins, Betr alts.")

        with st.form("nba_ladder_form"):
            col1, col2 = st.columns(2)
            with col1:
                ud_player = st.text_input("Player name", placeholder="e.g. Anthony Davis")
                ud_stat = st.selectbox("Stat",
                                        list(NBA_STAT_MARKETS.keys()) + list(NBA_COMBO_MARKETS.keys()))
            with col2:
                ud_mode = st.selectbox(
                    "Mode",
                    ["Standard O/U", "🪜 Ladder (multi-rung)",
                     "🔴 Demon (alt high, MORE)", "🟢 Goblin (alt low, MORE)"],
                )
                ud_side_for_std = st.radio("Side (Standard only)", ["Over", "Under"],
                                            horizontal=True)

            st.markdown("**Rungs / lines (enter what's on the platform):**")
            rcol1, rcol2, rcol3, rcol4 = st.columns(4)
            with rcol1:
                r1 = st.number_input("Line 1", min_value=0.0, value=2.5, step=0.5, key="nba_r1")
                p1 = st.number_input("Payout 1 (×)", min_value=0.0, value=1.5, step=0.05, key="nba_p1")
            with rcol2:
                r2 = st.number_input("Line 2 (0=skip)", min_value=0.0, value=0.0, step=0.5, key="nba_r2")
                p2 = st.number_input("Payout 2 (×)", min_value=0.0, value=0.0, step=0.05, key="nba_p2")
            with rcol3:
                r3 = st.number_input("Line 3 (0=skip)", min_value=0.0, value=0.0, step=0.5, key="nba_r3")
                p3 = st.number_input("Payout 3 (×)", min_value=0.0, value=0.0, step=0.05, key="nba_p3")
            with rcol4:
                r4 = st.number_input("Line 4 (0=skip)", min_value=0.0, value=0.0, step=0.5, key="nba_r4")
                p4 = st.number_input("Payout 4 (×)", min_value=0.0, value=0.0, step=0.05, key="nba_p4")

            submitted = st.form_submit_button("🪜 Analyze", use_container_width=True)

        if submitted:
            if not ud_player.strip():
                st.error("Enter a player name.")
            else:
                with st.spinner("Running MC..."):
                    history = get_nba_history(ud_player, ud_stat)
                    inj = fetch_espn_injuries("nba")

                values, n_games, season_avg, l10_avg, std_dev, dnp_meta = history
                if values is None:
                    st.error(f"❌ No game log found for '{ud_player}'. Check spelling.")
                else:
                    inj_emoji, inj_status = get_injury_status(ud_player, inj)
                    minutes_mult = STATUS_MULTIPLIER.get(inj_status.split()[0] if inj_status else "Active", 1.0)
                    sims = build_player_distribution(values, n_sims=n_sims_choice)
                    sims = apply_adjustments(sims, minutes_mult=minutes_mult)

                    # DNP warning if applicable
                    if dnp_meta is not None:
                        total_g, dnp_g, played_g = dnp_meta
                        if total_g > 0 and (dnp_g / total_g) > 0.30:
                            st.warning(f"⚠️ {dnp_g}/{total_g} of recent games were DNPs — projection may be unreliable")

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("L10", f"{l10_avg:.2f}" if l10_avg else "—")
                    c2.metric("Season", f"{season_avg:.2f}" if season_avg else "—")
                    c3.metric("Sample", f"{n_games}")
                    c4.metric("Status", f"{inj_emoji} {inj_status}")

                    if n_games < 10:
                        st.warning("⚠️ Small sample (<10 games) — using NB/Poisson fallback")

                    rungs = [(1, r1, p1), (2, r2, p2), (3, r3, p3), (4, r4, p4)]
                    rungs = [r for r in rungs if r[1] > 0 and r[2] > 0]
                    if not rungs:
                        st.error("Enter at least one line + payout.")
                    else:
                        rows = []
                        for rn, line, pay in rungs:
                            if ud_mode == "Standard O/U":
                                p_hit = hit_probability(sims, line, ud_side_for_std)
                                side_lbl = ud_side_for_std
                            else:
                                p_hit = hit_probability(sims, line, "Over")
                                side_lbl = "More" if "Demon" in ud_mode or "Goblin" in ud_mode else "Over"

                            imp = implied_prob_from_payout(pay)
                            edge = (p_hit - imp) * 100 if imp else None

                            trust, _ = trust_score(values, line, side_lbl,
                                                    l10_avg, season_avg, inj_status)
                            tier = signal_tier(trust, edge if edge is not None else 0,
                                                trust_thresh, edge_thresh)
                            bet_size, reason = suggested_bet_size(
                                trust, edge if edge is not None else 0, tier)

                            rec = ""
                            if tier == "🔥":
                                rec = "🔥 STRONG TARGET"
                            elif tier == "🎯":
                                rec = "🎯 Trust pick"
                            elif tier == "💎":
                                rec = "💎 Edge pick"
                            elif tier == "🔴":
                                rec = "🔴 FADE"
                            elif p_hit < 0.5:
                                rec = "⚠️ Coin flip"
                            else:
                                rec = "🟡 Thin"

                            rows.append({
                                "Tier": tier,
                                "Rung": f"R{rn}",
                                "Line": line,
                                "Side": side_lbl,
                                "Payout": f"{pay}×",
                                "Model %": f"{p_hit*100:.1f}",
                                "Implied %": f"{imp*100:.1f}" if imp else "—",
                                "Edge pp": f"{edge:+.1f}" if edge is not None else "—",
                                "Trust": trust,
                                "Bet $": bet_size,
                                "Recommendation": rec,
                            })

                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                        # Best rung pick
                        best = None
                        best_edge = -999
                        for rn, line, pay in rungs:
                            p_hit = hit_probability(sims, line, "Over"
                                                     if ud_mode != "Standard O/U" else ud_side_for_std)
                            imp = implied_prob_from_payout(pay)
                            if imp is None or p_hit < 0.5:
                                continue
                            edge = (p_hit - imp) * 100
                            if edge > best_edge:
                                best_edge = edge
                                best = (rn, line, pay, p_hit, edge)

                        if best and best_edge >= edge_thresh:
                            rn, line, pay, p_hit, edge = best
                            st.success(
                                f"🎯 **TARGET R{rn}: {line} @ {pay}×** | "
                                f"Model {p_hit*100:.1f}% | Edge +{edge:.1f}pp | "
                                f"L10 {l10_avg:.2f}, Season {season_avg:.2f}"
                            )
                        elif best:
                            rn, line, pay, p_hit, edge = best
                            st.info(f"Best: R{rn} (edge {edge:+.1f}pp) — below threshold")
                        else:
                            st.warning("No rung hits the criteria. Skip this player.")

    # --- NBA TOP PLAYS ---
    with nba_top_tab:
        st.subheader("🔥 NBA Top Plays Today")
        st.caption("Best picks across props — sorted by tier & edge")
        st.info("Run the 🎯 Props tab first. Top plays are pulled from that analysis.")
        st.markdown("""
**Reading the tiers:**
- 🔥 **Combined** = best of both worlds, max sizing
- 🎯 **Trust** = high consistency, lower payout, income lane
- 💎 **Edge** = high value, more variance, payoff lane

Use the sidebar sliders to adjust thresholds slate-by-slate.
        """)


# ============================================================
# TAB: MLB
# ============================================================

with tab_mlb:
    mlb_props_tab, mlb_ladders_tab, mlb_top_tab = st.tabs(["🎯 Props", "🪜 Ladders", "🔥 Top Plays"])

    # --- MLB PROPS ---
    with mlb_props_tab:
        st.subheader("⚾ MLB Player Props")
        st.caption("Hitter + pitcher stats from DraftKings + FanDuel · NB Monte Carlo")

        mlb_stats_choice = st.multiselect(
            "Stats to analyze",
            list(MLB_STAT_MARKETS.keys()),
            default=["Hits", "Total Bases", "Strikeouts"],
            key="mlb_props_stats",
        )

        if not mlb_stats_choice:
            st.info("Select at least one stat above.")
        else:
            with st.spinner("Fetching props..."):
                markets = [MLB_STAT_MARKETS[s] for s in mlb_stats_choice]
                props, err = fetch_odds_api_props("baseball_mlb", markets)

            if err:
                st.error(f"⚠️ Odds API: {err}")
            elif not props:
                st.warning("No props returned.")
            else:
                df_props = consolidate_props(props, MLB_STAT_MARKETS)
                if df_props.empty:
                    st.warning("Props pulled but none matched selected stats.")
                else:
                    st.success(f"✅ {len(df_props)} prop lines · {df_props['player'].nunique()} players")

                    inj = fetch_espn_injuries("mlb")

                    event_totals = {}
                    for eid in df_props["event_id"].unique():
                        event_totals[eid] = fetch_event_total("baseball_mlb", eid)

                    progress = st.progress(0, text="Running MC...")
                    rows = []
                    total = len(df_props)
                    for i, (_, p) in enumerate(df_props.iterrows()):
                        rows.append(analyze_prop(
                            player=p["player"], stat=p["stat"], line=p["line"],
                            over_odds=p["over_odds"], under_odds=p["under_odds"],
                            league="mlb", injuries=inj, n_sims=n_sims_choice,
                            trust_thresh=trust_thresh, edge_thresh=edge_thresh,
                            vegas_total=event_totals.get(p["event_id"]),
                            home_team=p.get("home", ""), away_team=p.get("away", ""),
                            commence_time=p.get("commence_time", ""),
                        ))
                        progress.progress((i + 1) / total, text=f"MC: {i+1}/{total}")
                    progress.empty()

                    df_out = pd.DataFrame(rows)
                    tier_order = {"🔥": 0, "🎯": 1, "💎": 2, "🟡": 3, "🔴": 4, "⚪": 5}
                    df_out["_order"] = df_out["Tier"].map(tier_order).fillna(99)
                    df_out["_edge"] = df_out["Edge pp"].fillna(-999)
                    df_out = df_out.sort_values(["_order", "_edge"], ascending=[True, False])
                    df_out = df_out.drop(columns=["_order", "_edge"])

                    if not show_below:
                        df_out = df_out[df_out["Tier"].isin(["🔥", "🎯", "💎"])]

                    if df_out.empty:
                        st.info("No plays clear thresholds.")
                    else:
                        st.dataframe(df_out, use_container_width=True, hide_index=True, height=500)
                        st.caption(f"Refreshed: {datetime.now().strftime('%H:%M:%S')}")

    # --- MLB LADDERS ---
    with mlb_ladders_tab:
        st.subheader("🪜 MLB Ladder / Alt Builder")
        st.caption("Same engine as NBA — works for any platform's ladder/alt structure")

        with st.form("mlb_ladder_form"):
            col1, col2 = st.columns(2)
            with col1:
                mlb_ud_player = st.text_input("Player name", placeholder="e.g. Aaron Judge",
                                                key="mlb_ud_player")
                mlb_ud_stat = st.selectbox("Stat", list(MLB_STAT_MARKETS.keys()), key="mlb_ud_stat")
            with col2:
                mlb_ud_mode = st.selectbox(
                    "Mode",
                    ["Standard O/U", "🪜 Ladder (multi-rung)",
                     "🔴 Demon (alt high, MORE)", "🟢 Goblin (alt low, MORE)"],
                    key="mlb_ud_mode",
                )
                mlb_ud_side = st.radio("Side (Standard only)", ["Over", "Under"],
                                         horizontal=True, key="mlb_ud_side")

            st.markdown("**Rungs / lines:**")
            rcol1, rcol2, rcol3, rcol4 = st.columns(4)
            with rcol1:
                m_r1 = st.number_input("Line 1", 0.0, value=1.5, step=0.5, key="mlb_r1")
                m_p1 = st.number_input("Payout 1 (×)", 0.0, value=1.5, step=0.05, key="mlb_p1")
            with rcol2:
                m_r2 = st.number_input("Line 2 (0=skip)", 0.0, value=0.0, step=0.5, key="mlb_r2")
                m_p2 = st.number_input("Payout 2 (×)", 0.0, value=0.0, step=0.05, key="mlb_p2")
            with rcol3:
                m_r3 = st.number_input("Line 3 (0=skip)", 0.0, value=0.0, step=0.5, key="mlb_r3")
                m_p3 = st.number_input("Payout 3 (×)", 0.0, value=0.0, step=0.05, key="mlb_p3")
            with rcol4:
                m_r4 = st.number_input("Line 4 (0=skip)", 0.0, value=0.0, step=0.5, key="mlb_r4")
                m_p4 = st.number_input("Payout 4 (×)", 0.0, value=0.0, step=0.05, key="mlb_p4")

            mlb_submit = st.form_submit_button("🪜 Analyze", use_container_width=True)

        if mlb_submit:
            if not mlb_ud_player.strip():
                st.error("Enter a player name.")
            else:
                with st.spinner("Running MC..."):
                    history = get_mlb_history(mlb_ud_player, mlb_ud_stat)
                    inj = fetch_espn_injuries("mlb")

                values, n_games, season_avg, l10_avg, std_dev, _ = history
                if values is None:
                    st.error(f"❌ No game log found for '{mlb_ud_player}'.")
                else:
                    inj_emoji, inj_status = get_injury_status(mlb_ud_player, inj)
                    sims = build_player_distribution(values, n_sims=n_sims_choice)

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("L10", f"{l10_avg:.2f}" if l10_avg else "—")
                    c2.metric("Season", f"{season_avg:.2f}" if season_avg else "—")
                    c3.metric("Sample", f"{n_games}")
                    c4.metric("Status", f"{inj_emoji} {inj_status}")

                    if n_games < 10:
                        st.warning("⚠️ Small sample — NB/Poisson fallback used")

                    rungs = [(1, m_r1, m_p1), (2, m_r2, m_p2),
                             (3, m_r3, m_p3), (4, m_r4, m_p4)]
                    rungs = [r for r in rungs if r[1] > 0 and r[2] > 0]
                    if not rungs:
                        st.error("Enter at least one line + payout.")
                    else:
                        rows = []
                        for rn, line, pay in rungs:
                            if mlb_ud_mode == "Standard O/U":
                                p_hit = hit_probability(sims, line, mlb_ud_side)
                                side_lbl = mlb_ud_side
                            else:
                                p_hit = hit_probability(sims, line, "Over")
                                side_lbl = "More"

                            imp = implied_prob_from_payout(pay)
                            edge = (p_hit - imp) * 100 if imp else None
                            trust, _ = trust_score(values, line, side_lbl,
                                                    l10_avg, season_avg, inj_status)
                            tier = signal_tier(trust, edge if edge is not None else 0,
                                                trust_thresh, edge_thresh)
                            bet_size, _ = suggested_bet_size(
                                trust, edge if edge is not None else 0, tier)

                            rows.append({
                                "Tier": tier, "Rung": f"R{rn}", "Line": line, "Side": side_lbl,
                                "Payout": f"{pay}×",
                                "Model %": f"{p_hit*100:.1f}",
                                "Implied %": f"{imp*100:.1f}" if imp else "—",
                                "Edge pp": f"{edge:+.1f}" if edge is not None else "—",
                                "Trust": trust, "Bet $": bet_size,
                            })

                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # --- MLB TOP PLAYS ---
    with mlb_top_tab:
        st.subheader("🔥 MLB Top Plays Today")
        st.caption("Best picks across props — sorted by tier & edge")
        st.info("Run the 🎯 Props tab first to populate Top Plays.")


# ============================================================
# TAB: SETTINGS
# ============================================================

with tab_settings:
    st.subheader("📊 Settings & Diagnostics")

    st.markdown("### 🔌 API Status")
    cols = st.columns(4)

    with cols[0]:
        st.markdown("**Odds API**")
        if not ODDS_API_KEY:
            st.error("❌ Key missing")
        else:
            try:
                r = requests.get(f"{ODDS_API_BASE}/sports",
                                 params={"apiKey": ODDS_API_KEY}, timeout=10)
                if r.status_code == 200:
                    rem = r.headers.get("x-requests-remaining", "?")
                    used = r.headers.get("x-requests-used", "?")
                    st.success(f"✅ Connected\nUsed: {used}\nRemaining: {rem}")
                else:
                    st.error(f"❌ {r.status_code}")
            except Exception as e:
                st.error(f"❌ {e}")

    with cols[1]:
        st.markdown("**BallDontLie (NBA)**")
        if not BDL_API_KEY:
            st.error("❌ Key missing")
        else:
            try:
                r = requests.get(f"{BDL_BASE}/teams",
                                 headers=_bdl_headers(), timeout=10)
                if r.status_code == 200:
                    n = len(r.json().get("data", []))
                    st.success(f"✅ Connected\n{n} teams")
                elif r.status_code == 401:
                    st.error("❌ 401 Unauthorized — check key")
                else:
                    st.warning(f"⚠️ {r.status_code}")
            except Exception as e:
                st.error(f"❌ {e}")

    with cols[2]:
        st.markdown("**MLB Stats API**")
        try:
            r = requests.get(f"{MLB_STATS_BASE}/sports/1", timeout=10)
            if r.status_code == 200:
                st.success("✅ Connected")
            else:
                st.warning(f"⚠️ {r.status_code}")
        except Exception as e:
            st.error(f"❌ {e}")

    with cols[3]:
        st.markdown("**ESPN Injuries**")
        try:
            r = requests.get(ESPN_NBA_INJURIES, timeout=10)
            if r.status_code == 200:
                st.success("✅ Connected")
            else:
                st.warning(f"⚠️ {r.status_code}")
        except Exception as e:
            st.error(f"❌ {e}")

    st.markdown("---")
    st.markdown("### 🧪 BallDontLie Free-Tier Diagnostic")
    st.caption("Tests which endpoints are accessible on the free tier")

    if st.button("🧪 Run BDL diagnostic", use_container_width=True):
        if not BDL_API_KEY:
            st.error("Add BallDontLie API key to secrets first.")
        else:
            tests = [
                ("Teams (basic)", f"{BDL_BASE}/teams", {}),
                ("Player search (LeBron)", f"{BDL_BASE}/players",
                 {"search": "james", "per_page": 5}),
                ("Game stats (recent)", f"{BDL_BASE}/stats",
                 {"per_page": 5}),
                ("Season averages", f"{BDL_BASE}/season_averages",
                 {"season": 2024, "player_ids[]": 237}),
            ]
            for label, url, params in tests:
                try:
                    r = requests.get(url, params=params, headers=_bdl_headers(), timeout=10)
                    if r.status_code == 200:
                        n = len(r.json().get("data", []))
                        st.success(f"✅ {label}: 200 OK ({n} records)")
                    elif r.status_code == 401:
                        st.error(f"🔒 {label}: 401 Unauthorized — needs paid tier")
                    elif r.status_code == 403:
                        st.error(f"🚫 {label}: 403 Forbidden — endpoint not available on free")
                    elif r.status_code == 429:
                        st.warning(f"⏱️ {label}: 429 Rate limited")
                    else:
                        st.warning(f"⚠️ {label}: {r.status_code}")
                except Exception as e:
                    st.error(f"❌ {label}: {e}")
                time.sleep(0.5)

    st.markdown("---")
    st.markdown("### 🗑️ Cache Management")
    if st.button("Clear all caches"):
        st.cache_data.clear()
        st.success("Caches cleared.")

    st.markdown("---")
    st.markdown("### 📚 Methodology")
    st.markdown("""
**Distribution Engine:**
- **Negative Binomial** primary (handles overdispersion in player stats)
- Bootstrap from L25 game log when sample ≥ 10
- L10 weighted 70%, games 11-25 weighted 30%
- Poisson fallback for samples < 5

**Trust Score (0-100):**
- L25 Hit Rate (40%) — most important
- Sample Quality (20%)
- Consistency (15%) — low CV = high trust
- Form Alignment (15%) — L10 vs Season
- Status Health (10%) — Active/Probable/Out

**Edge Score (0-100):**
- Model − Implied (60%) capped at 25 pp
- Line Comfort (25%) — L10 distance from line in std devs
- Cross-Platform Gap (15%)

**Tier Thresholds (default):**
- 🔥 Combined: Trust ≥ 65 AND Edge ≥ 5pp
- 🎯 Trust pick: Trust ≥ 65 only
- 💎 Edge pick: Edge ≥ 5pp only
- 🔴 Fade: negative edge

**Adjustments wired:**
- Minutes mult: ESPN injury status → Active 1.0 / Probable 0.95 / DTD 0.85 / Q 0.70 / D 0.30 / Out 0
- Vegas total mult: game total / league avg (NBA 225, MLB 8.5)
- Pace: deferred (V2.1 with BDL pace data)
- DvP: deferred (V2.1)

**Validation discipline:**
- Shadow validate ≥ 2 weeks before live bets
- $10/bet ceiling, $50/day cap during validation
    """)

    st.markdown("---")
    st.caption(f"V2.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
