"""
MPH Underdog Ladders Model — V1.0
==================================
Monte Carlo prop modeling for Underdog Ladders (NBA + MLB)

Architecture:
- Tab 1: NBA Props (Blocks / Steals / 3PM) — auto from Odds API
- Tab 2: MLB Props (Ks / Hits / TB / RBI / Runs) — auto from Odds API
- Tab 3: Underdog Overlay — manual rung entry, full MC analysis
- Tab 4: Settings — API status, cache controls

Methodology:
- Bootstrap Monte Carlo (10,000 sims) from empirical game logs
- L25 game window with L10 weighting for recency
- Adjustments: minutes projection, opponent defense, pace factor
- Joint probability for ladder rungs (captures within-game correlation)
- Edge = Model Hit Prob − Implied Prob (from sportsbook odds or UD payout)
- Fallback to Poisson with shrinkage when sample size <10 games

Repo: mphill422/Kalshi-DFS
Replaces: DK Tier optimizer (deprecated)
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta, date
from scipy import stats
import time

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="MPH Underdog Ladders",
    page_icon="🪜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
# Read Odds API key from [odds] section in secrets, with fallback
try:
    ODDS_API_KEY = st.secrets["odds"]["api_key"]
except (KeyError, FileNotFoundError):
    ODDS_API_KEY = st.secrets.get("ODDS_API_KEY", "")
    if not ODDS_API_KEY:
        st.error("⚠️ ODDS_API_KEY not found in Streamlit secrets. Add [odds] section with api_key.")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

NBA_STATS_BASE = "https://stats.nba.com/stats"
NBA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
}

MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"

ESPN_NBA_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
ESPN_MLB_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/injuries"

# MC config
N_SIMULATIONS = 10_000
L25_WINDOW = 25
L10_WEIGHT = 0.70  # 70% weight on L10, 30% on games 11-25

# NBA stat keys (Odds API)
NBA_STAT_MARKETS = {
    "Blocks": "player_blocks",
    "Steals": "player_steals",
    "3PM": "player_threes",
}

# MLB stat keys (Odds API)
MLB_STAT_MARKETS = {
    "Strikeouts": "pitcher_strikeouts",
    "Hits": "batter_hits",
    "Total Bases": "batter_total_bases",
    "RBI": "batter_rbis",
    "Runs": "batter_runs_scored",
}

# Stat-to-NBA-Stats-API column mapping
NBA_STAT_COLUMNS = {
    "Blocks": "BLK",
    "Steals": "STL",
    "3PM": "FG3M",
}

# League averages for opponent adjustment normalization
NBA_LEAGUE_AVG = {
    "Blocks": 5.0,   # team blocks allowed per game
    "Steals": 7.5,
    "3PM": 12.5,
}

MLB_LEAGUE_AVG = {
    "Strikeouts": 8.5,  # team Ks per game
    "Hits": 8.5,
    "Total Bases": 14.0,
    "RBI": 4.3,
    "Runs": 4.3,
}


# ============================================================
# DATA FETCHERS — ODDS API
# ============================================================

@st.cache_data(ttl=300)  # 5 min cache
def fetch_odds_api_props(sport: str, markets: list, regions: str = "us"):
    """
    Pull player props from The Odds API.
    sport: 'basketball_nba' or 'baseball_mlb'
    markets: list of market keys like ['player_blocks', 'player_steals']
    """
    # First get today's events
    events_url = f"{ODDS_API_BASE}/sports/{sport}/events"
    events_params = {"apiKey": ODDS_API_KEY, "dateFormat": "iso"}

    try:
        resp = requests.get(events_url, params=events_params, timeout=15)
        if resp.status_code != 200:
            return [], f"Events API error {resp.status_code}: {resp.text[:200]}"
        events = resp.json()
    except Exception as e:
        return [], f"Events fetch failed: {e}"

    if not events:
        return [], "No events scheduled today"

    # Filter to today's games only
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

    # Pull props per event
    all_props = []
    markets_str = ",".join(markets)

    for ev in today_events:
        event_id = ev["id"]
        odds_url = f"{ODDS_API_BASE}/sports/{sport}/events/{event_id}/odds"
        odds_params = {
            "apiKey": ODDS_API_KEY,
            "regions": regions,
            "markets": markets_str,
            "oddsFormat": "american",
            "bookmakers": "draftkings,fanduel",
        }

        try:
            r = requests.get(odds_url, params=odds_params, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()

            home = data.get("home_team", "")
            away = data.get("away_team", "")

            for book in data.get("bookmakers", []):
                book_key = book.get("key", "")
                for market in book.get("markets", []):
                    market_key = market.get("key", "")
                    for outcome in market.get("outcomes", []):
                        all_props.append({
                            "event_id": event_id,
                            "home": home,
                            "away": away,
                            "commence_time": data.get("commence_time"),
                            "book": book_key,
                            "market": market_key,
                            "player": outcome.get("description", ""),
                            "side": outcome.get("name", ""),  # "Over" or "Under"
                            "line": outcome.get("point"),
                            "odds": outcome.get("price"),
                        })
        except Exception:
            continue

    if not all_props:
        return [], f"No props returned for {len(today_events)} events"

    return all_props, None


def consolidate_props_to_lines(props: list, market_label_map: dict) -> pd.DataFrame:
    """
    Collapse Over/Under outcomes per player+line into one row.
    Returns DataFrame with: player, market_label, line, over_odds, under_odds, book.
    """
    if not props:
        return pd.DataFrame()

    df = pd.DataFrame(props)
    if df.empty:
        return df

    # Reverse map: market_key -> label (e.g. 'player_blocks' -> 'Blocks')
    rev_map = {v: k for k, v in market_label_map.items()}
    df["stat"] = df["market"].map(rev_map)
    df = df[df["stat"].notna()]

    # Pivot Over/Under into columns
    pivot_rows = []
    for (player, stat, line, book, home, away, commence), grp in df.groupby(
        ["player", "stat", "line", "book", "home", "away", "commence_time"]
    ):
        over_odds = grp[grp["side"] == "Over"]["odds"].values
        under_odds = grp[grp["side"] == "Under"]["odds"].values
        pivot_rows.append({
            "player": player,
            "stat": stat,
            "line": line,
            "book": book,
            "home": home,
            "away": away,
            "commence_time": commence,
            "over_odds": float(over_odds[0]) if len(over_odds) else None,
            "under_odds": float(under_odds[0]) if len(under_odds) else None,
        })

    return pd.DataFrame(pivot_rows)


# ============================================================
# DATA FETCHERS — NBA STATS API
# ============================================================

@st.cache_data(ttl=1800)  # 30 min
def fetch_nba_player_id(player_name: str):
    """Get NBA player ID from name. Uses commonallplayers endpoint."""
    url = f"{NBA_STATS_BASE}/commonallplayers"
    params = {
        "LeagueID": "00",
        "Season": _current_nba_season(),
        "IsOnlyCurrentSeason": "1",
    }
    try:
        r = requests.get(url, params=params, headers=NBA_HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        rs = data["resultSets"][0]
        headers = rs["headers"]
        rows = rs["rowSet"]
        df = pd.DataFrame(rows, columns=headers)
        # Match on display first/last
        df["full_name"] = df["DISPLAY_FIRST_LAST"].str.lower()
        match = df[df["full_name"] == player_name.lower()]
        if match.empty:
            # Fuzzy fallback — last name match
            last = player_name.split()[-1].lower()
            match = df[df["full_name"].str.endswith(last)]
        if not match.empty:
            return int(match.iloc[0]["PERSON_ID"])
    except Exception:
        return None
    return None


@st.cache_data(ttl=1800)
def fetch_nba_game_log(player_id: int, season: str = None):
    """Fetch player game log for current season."""
    if season is None:
        season = _current_nba_season()
    url = f"{NBA_STATS_BASE}/playergamelog"
    params = {
        "PlayerID": player_id,
        "Season": season,
        "SeasonType": "Regular Season",
    }
    try:
        r = requests.get(url, params=params, headers=NBA_HEADERS, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        rs = data["resultSets"][0]
        df = pd.DataFrame(rs["rowSet"], columns=rs["headers"])
        # Sort newest first
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
        df = df.sort_values("GAME_DATE", ascending=False).reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


def _current_nba_season() -> str:
    """Return current NBA season string like '2025-26'."""
    today = date.today()
    if today.month >= 10:  # Oct-Dec = start of new season
        start = today.year
    else:
        start = today.year - 1
    end_short = str(start + 1)[-2:]
    return f"{start}-{end_short}"


# ============================================================
# DATA FETCHERS — MLB STATS API
# ============================================================

@st.cache_data(ttl=1800)
def fetch_mlb_player_id(player_name: str):
    """Look up MLB player ID by name."""
    url = f"{MLB_STATS_BASE}/people/search"
    params = {"names": player_name}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            # Fallback: people endpoint
            return _mlb_fuzzy_lookup(player_name)
        data = r.json()
        people = data.get("people", [])
        if people:
            return people[0]["id"]
    except Exception:
        pass
    return _mlb_fuzzy_lookup(player_name)


def _mlb_fuzzy_lookup(player_name: str):
    """Fallback MLB lookup via sports/1/players endpoint."""
    season = date.today().year
    url = f"{MLB_STATS_BASE}/sports/1/players"
    params = {"season": season}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        for p in data.get("people", []):
            full = p.get("fullName", "").lower()
            if full == player_name.lower():
                return p["id"]
        # Last-name fallback
        last = player_name.split()[-1].lower()
        for p in data.get("people", []):
            if p.get("fullName", "").lower().endswith(last):
                return p["id"]
    except Exception:
        return None
    return None


@st.cache_data(ttl=1800)
def fetch_mlb_game_log(player_id: int, stat_type: str):
    """
    Fetch player game log. stat_type: 'pitching' or 'hitting'
    """
    season = date.today().year
    group = "pitching" if stat_type == "pitching" else "hitting"
    url = f"{MLB_STATS_BASE}/people/{player_id}/stats"
    params = {
        "stats": "gameLog",
        "group": group,
        "season": season,
        "sportId": 1,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        stats_arr = data.get("stats", [])
        if not stats_arr:
            return pd.DataFrame()
        splits = stats_arr[0].get("splits", [])
        if not splits:
            return pd.DataFrame()
        rows = []
        for s in splits:
            stat = s.get("stat", {})
            row = {
                "date": s.get("date"),
                "opponent": s.get("opponent", {}).get("name", ""),
                "strikeouts": stat.get("strikeOuts", 0),
                "hits": stat.get("hits", 0),
                "totalBases": stat.get("totalBases", 0),
                "rbi": stat.get("rbi", 0),
                "runs": stat.get("runs", 0),
                "atBats": stat.get("atBats", 0),
                "inningsPitched": float(stat.get("inningsPitched", 0) or 0),
            }
            rows.append(row)
        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date", ascending=False).reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


# ============================================================
# INJURY FEEDS — ESPN
# ============================================================

@st.cache_data(ttl=900)  # 15 min
def fetch_espn_injuries(league: str):
    """league: 'nba' or 'mlb'"""
    url = ESPN_NBA_INJURIES if league == "nba" else ESPN_MLB_INJURIES
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return {}
        data = r.json()
        injuries = {}
        for team in data.get("injuries", []):
            for inj in team.get("injuries", []):
                athlete = inj.get("athlete", {})
                name = athlete.get("displayName", "")
                if not name:
                    continue
                injuries[name.lower()] = {
                    "status": inj.get("status", "Unknown"),
                    "type": inj.get("type", ""),
                    "detail": inj.get("details", {}).get("detail", ""),
                }
        return injuries
    except Exception:
        return {}


def get_injury_status(player_name: str, injury_dict: dict):
    """Return (emoji, status_text) for a player."""
    status = injury_dict.get(player_name.lower(), {}).get("status", "")
    if not status:
        return "✅", "Active"
    s = status.lower()
    if "out" in s or "ir" in s:
        return "❌", status
    if "doubtful" in s or "questionable" in s or "day-to-day" in s or "probable" in s:
        return "⚠️", status
    return "✅", status


# ============================================================
# MONTE CARLO ENGINE
# ============================================================

def build_player_distribution(game_log_values: np.ndarray, n_sims: int = N_SIMULATIONS) -> np.ndarray:
    """
    Build MC distribution from empirical game log.
    - Uses L25 with L10 recency weighting (70/30)
    - Bootstrap with replacement
    - Falls back to Poisson if sample <10
    """
    vals = np.array(game_log_values, dtype=float)
    vals = vals[~np.isnan(vals)]

    if len(vals) == 0:
        return np.zeros(n_sims)

    if len(vals) < 10:
        # Small-sample fallback: Poisson with shrinkage toward sample mean
        mean = max(np.mean(vals), 0.1)
        return np.random.poisson(lam=mean, size=n_sims).astype(float)

    # Split into L10 (most recent) and L11-25 (older)
    l10 = vals[: min(10, len(vals))]
    l_older = vals[10: min(L25_WINDOW, len(vals))]

    # Sample 70% from L10, 30% from older window (if exists)
    if len(l_older) > 0:
        n_l10 = int(n_sims * L10_WEIGHT)
        n_older = n_sims - n_l10
        sims_l10 = np.random.choice(l10, size=n_l10, replace=True)
        sims_older = np.random.choice(l_older, size=n_older, replace=True)
        sims = np.concatenate([sims_l10, sims_older])
        np.random.shuffle(sims)
    else:
        sims = np.random.choice(l10, size=n_sims, replace=True)

    return sims


def apply_adjustments(
    sims: np.ndarray,
    minutes_mult: float = 1.0,
    opp_mult: float = 1.0,
    pace_mult: float = 1.0,
) -> np.ndarray:
    """
    Apply multiplicative adjustments to simulation array.
    minutes_mult: projected_minutes / season_avg_minutes
    opp_mult: opp_stat_allowed / league_avg
    pace_mult: game_pace / player_avg_pace
    """
    combined = minutes_mult * opp_mult * pace_mult
    adjusted = sims * combined
    # Round to nearest integer for counting stats (MC works on continuous, but stats are discrete)
    return np.round(adjusted).astype(int).clip(min=0)


def hit_probability(sims: np.ndarray, line: float, side: str = "Over") -> float:
    """Compute probability of going Over/Under a given line."""
    if len(sims) == 0:
        return 0.5
    if side.lower() == "over":
        # Underdog/sportsbook convention: "Over 1.5" means stat >= 2 (since lines are .5)
        # If line is integer, "Over X" means stat > X. We use strict > for safety.
        return float(np.mean(sims > line))
    else:
        return float(np.mean(sims < line + 0.5))


def ladder_joint_probability(sims: np.ndarray, rungs: list) -> dict:
    """
    For Underdog ladders: rungs are sorted ascending (e.g. [1.5, 2.5, 3.5]).
    Returns dict mapping each rung to P(stat >= rung) — NOT independent product,
    actual joint prob from same sims.
    """
    out = {}
    for r in sorted(rungs):
        out[r] = float(np.mean(sims > r))
    return out


def implied_prob_from_american(odds: float) -> float:
    """Convert American odds to implied probability."""
    if odds is None or pd.isna(odds):
        return None
    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return -odds / (-odds + 100.0)


def implied_prob_from_payout(payout_multiplier: float) -> float:
    """Underdog ladder payout (e.g. 3x = 0.333 implied prob)."""
    if not payout_multiplier or payout_multiplier <= 0:
        return None
    return 1.0 / payout_multiplier


def signal_emoji(edge_pct: float) -> str:
    """Edge in percentage points (0-100 scale)."""
    if edge_pct is None or pd.isna(edge_pct):
        return "⚪"
    if edge_pct >= 8:
        return "🟢"
    if edge_pct >= 3:
        return "🎯"
    if edge_pct < 0:
        return "🔴"
    return "🟡"


# ============================================================
# STAT-SPECIFIC PIPELINES
# ============================================================

def get_nba_player_stat_history(player_name: str, stat: str) -> tuple:
    """
    Returns (sims_array, sample_size, season_avg, l10_avg) or (None, 0, None, None).
    """
    pid = fetch_nba_player_id(player_name)
    if pid is None:
        return None, 0, None, None
    log = fetch_nba_game_log(pid)
    if log.empty:
        return None, 0, None, None
    col = NBA_STAT_COLUMNS.get(stat)
    if col is None or col not in log.columns:
        return None, 0, None, None
    values = log[col].astype(float).values
    sims = build_player_distribution(values)
    season_avg = float(np.mean(values)) if len(values) else None
    l10_avg = float(np.mean(values[:10])) if len(values) >= 1 else None
    return sims, len(values), season_avg, l10_avg


def get_mlb_player_stat_history(player_name: str, stat: str) -> tuple:
    """
    Returns (sims_array, sample_size, season_avg, l10_avg).
    """
    pid = fetch_mlb_player_id(player_name)
    if pid is None:
        return None, 0, None, None

    if stat == "Strikeouts":
        log = fetch_mlb_game_log(pid, "pitching")
        if log.empty:
            return None, 0, None, None
        values = log["strikeouts"].astype(float).values
    elif stat == "Hits":
        log = fetch_mlb_game_log(pid, "hitting")
        if log.empty:
            return None, 0, None, None
        values = log["hits"].astype(float).values
    elif stat == "Total Bases":
        log = fetch_mlb_game_log(pid, "hitting")
        if log.empty:
            return None, 0, None, None
        values = log["totalBases"].astype(float).values
    elif stat == "RBI":
        log = fetch_mlb_game_log(pid, "hitting")
        if log.empty:
            return None, 0, None, None
        values = log["rbi"].astype(float).values
    elif stat == "Runs":
        log = fetch_mlb_game_log(pid, "hitting")
        if log.empty:
            return None, 0, None, None
        values = log["runs"].astype(float).values
    else:
        return None, 0, None, None

    sims = build_player_distribution(values)
    season_avg = float(np.mean(values)) if len(values) else None
    l10_avg = float(np.mean(values[:10])) if len(values) >= 1 else None
    return sims, len(values), season_avg, l10_avg


# ============================================================
# ANALYSIS — PROPS TAB ROW BUILDER
# ============================================================

def analyze_prop_row(player: str, stat: str, line: float, over_odds: float,
                     under_odds: float, league: str, injuries: dict) -> dict:
    """Build full analysis row for one prop."""
    if league == "nba":
        sims, n_games, season_avg, l10_avg = get_nba_player_stat_history(player, stat)
    else:
        sims, n_games, season_avg, l10_avg = get_mlb_player_stat_history(player, stat)

    inj_emoji, inj_status = get_injury_status(player, injuries)

    if sims is None:
        return {
            "Signal": "⚪",
            "Player": player,
            "Status": f"{inj_emoji} {inj_status}",
            "Stat": stat,
            "Line": line,
            "L10 Avg": None,
            "Season Avg": None,
            "Sample": 0,
            "Model P(Over)": None,
            "Implied (Over)": None,
            "Edge (Over)": None,
            "Model P(Under)": None,
            "Implied (Under)": None,
            "Edge (Under)": None,
            "Over Odds": over_odds,
            "Under Odds": under_odds,
            "Note": "No game log",
        }

    p_over = hit_probability(sims, line, "Over")
    p_under = 1.0 - p_over

    imp_over = implied_prob_from_american(over_odds)
    imp_under = implied_prob_from_american(under_odds)

    edge_over = (p_over - imp_over) * 100 if imp_over is not None else None
    edge_under = (p_under - imp_under) * 100 if imp_under is not None else None

    # Pick best side for signal
    best_edge = max(
        e for e in [edge_over, edge_under] if e is not None
    ) if (edge_over is not None or edge_under is not None) else None
    sig = signal_emoji(best_edge if best_edge is not None else 0)

    note = ""
    if n_games < 10:
        note = "⚠️ Limited sample (Poisson fallback)"
    elif n_games < 15:
        note = "Small sample"

    return {
        "Signal": sig,
        "Player": player,
        "Status": f"{inj_emoji} {inj_status}",
        "Stat": stat,
        "Line": line,
        "L10 Avg": round(l10_avg, 2) if l10_avg is not None else None,
        "Season Avg": round(season_avg, 2) if season_avg is not None else None,
        "Sample": n_games,
        "Model P(Over)": round(p_over * 100, 1),
        "Implied (Over)": round(imp_over * 100, 1) if imp_over is not None else None,
        "Edge (Over)": round(edge_over, 1) if edge_over is not None else None,
        "Model P(Under)": round(p_under * 100, 1),
        "Implied (Under)": round(imp_under * 100, 1) if imp_under is not None else None,
        "Edge (Under)": round(edge_under, 1) if edge_under is not None else None,
        "Over Odds": over_odds,
        "Under Odds": under_odds,
        "Note": note,
    }


# ============================================================
# UI — HEADER
# ============================================================

st.title("🪜 MPH Underdog Ladders Model")
st.caption("V1.0 — Monte Carlo prop modeling for NBA + MLB | Bootstrap simulation, L25 with L10 recency weighting")

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Controls")
    refresh = st.button("🔄 Force refresh data", use_container_width=True)
    if refresh:
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.markdown("### 📊 Model Config")
    st.markdown(f"- **Sims/player:** {N_SIMULATIONS:,}")
    st.markdown(f"- **L25 window:** L10 weighted {int(L10_WEIGHT*100)}%")
    st.markdown("- **Books:** DraftKings + FanDuel")
    st.markdown("---")
    st.markdown("### 🎯 Signal Legend")
    st.markdown("- 🟢 Edge ≥ 8% (strong)")
    st.markdown("- 🎯 Edge 3–8% (marginal)")
    st.markdown("- 🟡 Edge 0–3% (thin)")
    st.markdown("- 🔴 Edge < 0% (fade)")
    st.markdown("- ⚪ No data")

# ============================================================
# UI — TABS
# ============================================================

tab_nba, tab_mlb, tab_overlay, tab_settings = st.tabs([
    "🏀 NBA Props",
    "⚾ MLB Props",
    "🪜 Underdog Overlay",
    "📊 Settings",
])


# ============================================================
# TAB 1 — NBA PROPS
# ============================================================

with tab_nba:
    st.subheader("🏀 NBA Player Props — Blocks / Steals / 3PM")
    st.caption(f"Today's slate · DraftKings + FanDuel · MC sims = {N_SIMULATIONS:,}")

    selected_stats_nba = st.multiselect(
        "Stats to analyze",
        list(NBA_STAT_MARKETS.keys()),
        default=list(NBA_STAT_MARKETS.keys()),
        key="nba_stats",
    )

    if not selected_stats_nba:
        st.info("Select at least one stat above.")
    else:
        with st.spinner("Fetching NBA props..."):
            markets = [NBA_STAT_MARKETS[s] for s in selected_stats_nba]
            props, err = fetch_odds_api_props("basketball_nba", markets)

        if err:
            st.error(f"⚠️ Odds API: {err}")
        elif not props:
            st.warning("No NBA props returned. Could be off-day or API limit reached.")
        else:
            df_props = consolidate_props_to_lines(props, NBA_STAT_MARKETS)
            st.success(f"✅ {len(df_props)} prop lines pulled across {df_props['player'].nunique()} players")

            with st.spinner("Loading injury feed..."):
                inj = fetch_espn_injuries("nba")

            with st.spinner(f"Running Monte Carlo on {df_props['player'].nunique()} players..."):
                rows = []
                for _, p in df_props.iterrows():
                    rows.append(analyze_prop_row(
                        player=p["player"],
                        stat=p["stat"],
                        line=p["line"],
                        over_odds=p["over_odds"],
                        under_odds=p["under_odds"],
                        league="nba",
                        injuries=inj,
                    ))
                df_out = pd.DataFrame(rows)

            # Sort by best edge descending
            df_out["best_edge"] = df_out[["Edge (Over)", "Edge (Under)"]].max(axis=1)
            df_out = df_out.sort_values("best_edge", ascending=False, na_position="last").drop(columns=["best_edge"])

            st.dataframe(df_out, use_container_width=True, hide_index=True)

            st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')} | Cache TTL: 5 min props, 30 min stats")


# ============================================================
# TAB 2 — MLB PROPS
# ============================================================

with tab_mlb:
    st.subheader("⚾ MLB Player Props — Ks / Hits / TB / RBI / Runs")
    st.caption(f"Today's slate · DraftKings + FanDuel · MC sims = {N_SIMULATIONS:,}")

    selected_stats_mlb = st.multiselect(
        "Stats to analyze",
        list(MLB_STAT_MARKETS.keys()),
        default=list(MLB_STAT_MARKETS.keys()),
        key="mlb_stats",
    )

    if not selected_stats_mlb:
        st.info("Select at least one stat above.")
    else:
        with st.spinner("Fetching MLB props..."):
            markets = [MLB_STAT_MARKETS[s] for s in selected_stats_mlb]
            props, err = fetch_odds_api_props("baseball_mlb", markets)

        if err:
            st.error(f"⚠️ Odds API: {err}")
        elif not props:
            st.warning("No MLB props returned. Could be off-day or API limit reached.")
        else:
            df_props = consolidate_props_to_lines(props, MLB_STAT_MARKETS)
            st.success(f"✅ {len(df_props)} prop lines pulled across {df_props['player'].nunique()} players")

            with st.spinner("Loading injury feed..."):
                inj = fetch_espn_injuries("mlb")

            with st.spinner(f"Running Monte Carlo on {df_props['player'].nunique()} players..."):
                rows = []
                for _, p in df_props.iterrows():
                    rows.append(analyze_prop_row(
                        player=p["player"],
                        stat=p["stat"],
                        line=p["line"],
                        over_odds=p["over_odds"],
                        under_odds=p["under_odds"],
                        league="mlb",
                        injuries=inj,
                    ))
                df_out = pd.DataFrame(rows)

            df_out["best_edge"] = df_out[["Edge (Over)", "Edge (Under)"]].max(axis=1)
            df_out = df_out.sort_values("best_edge", ascending=False, na_position="last").drop(columns=["best_edge"])

            st.dataframe(df_out, use_container_width=True, hide_index=True)

            st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')} | Cache TTL: 5 min props, 30 min stats")


# ============================================================
# TAB 3 — UNDERDOG OVERLAY (manual rung entry)
# ============================================================

with tab_overlay:
    st.subheader("🪜 Underdog Ladder Overlay")
    st.caption("Enter Underdog ladder rungs manually. Model auto-pulls L10/season + runs MC simulation per rung.")

    with st.form("ladder_form"):
        col1, col2 = st.columns(2)
        with col1:
            ud_league = st.selectbox("League", ["NBA", "MLB"], key="ud_league")
            ud_player = st.text_input("Player name", placeholder="e.g. Anthony Davis", key="ud_player")
        with col2:
            if ud_league == "NBA":
                ud_stat = st.selectbox("Stat", list(NBA_STAT_MARKETS.keys()), key="ud_stat_nba")
            else:
                ud_stat = st.selectbox("Stat", list(MLB_STAT_MARKETS.keys()), key="ud_stat_mlb")

        st.markdown("**Ladder rungs (Underdog thresholds):**")
        rcol1, rcol2, rcol3, rcol4 = st.columns(4)
        with rcol1:
            r1 = st.number_input("Rung 1 line", min_value=0.0, value=1.5, step=0.5, key="r1")
            r1_pay = st.number_input("R1 payout (e.g. 1.5x)", min_value=1.0, value=1.5, step=0.1, key="r1p")
        with rcol2:
            r2 = st.number_input("Rung 2 line", min_value=0.0, value=2.5, step=0.5, key="r2")
            r2_pay = st.number_input("R2 payout (e.g. 3x)", min_value=1.0, value=3.0, step=0.1, key="r2p")
        with rcol3:
            r3 = st.number_input("Rung 3 line", min_value=0.0, value=3.5, step=0.5, key="r3")
            r3_pay = st.number_input("R3 payout (e.g. 6x)", min_value=1.0, value=6.0, step=0.1, key="r3p")
        with rcol4:
            r4 = st.number_input("Rung 4 line (optional)", min_value=0.0, value=0.0, step=0.5, key="r4")
            r4_pay = st.number_input("R4 payout (0 if none)", min_value=0.0, value=0.0, step=0.1, key="r4p")

        submitted = st.form_submit_button("🪜 Analyze ladder", use_container_width=True)

    if submitted:
        if not ud_player.strip():
            st.error("Enter a player name.")
        else:
            with st.spinner(f"Running MC for {ud_player}..."):
                if ud_league == "NBA":
                    sims, n_games, season_avg, l10_avg = get_nba_player_stat_history(ud_player, ud_stat)
                    inj = fetch_espn_injuries("nba")
                else:
                    sims, n_games, season_avg, l10_avg = get_mlb_player_stat_history(ud_player, ud_stat)
                    inj = fetch_espn_injuries("mlb")

            if sims is None:
                st.error(f"❌ Could not find game log for {ud_player}. Check spelling.")
            else:
                inj_emoji, inj_status = get_injury_status(ud_player, inj)
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("L10 Avg", f"{l10_avg:.2f}" if l10_avg is not None else "—")
                col_b.metric("Season Avg", f"{season_avg:.2f}" if season_avg is not None else "—")
                col_c.metric("Sample", f"{n_games} games")
                col_d.metric("Status", f"{inj_emoji} {inj_status}")

                if n_games < 10:
                    st.warning("⚠️ Limited sample — Poisson fallback used. Treat output as low-confidence.")

                # Build rung table
                rungs = [(1, r1, r1_pay), (2, r2, r2_pay), (3, r3, r3_pay)]
                if r4 > 0 and r4_pay > 0:
                    rungs.append((4, r4, r4_pay))

                rows = []
                for rn, line, pay in rungs:
                    p_hit = hit_probability(sims, line, "Over")
                    imp = implied_prob_from_payout(pay)
                    edge = (p_hit - imp) * 100 if imp is not None else None
                    rec = ""
                    if edge is not None:
                        if edge >= 8 and p_hit >= 0.5:
                            rec = "🟢 STRONG TARGET"
                        elif edge >= 3 and p_hit >= 0.5:
                            rec = "🎯 PLAY"
                        elif edge < 0:
                            rec = "🔴 FADE"
                        elif p_hit < 0.5:
                            rec = "⚠️ Coin flip — skip"
                        else:
                            rec = "🟡 Thin edge"
                    rows.append({
                        "Rung": f"R{rn}",
                        "Line": line,
                        "Payout": f"{pay}x",
                        "Model P(Hit)": f"{p_hit*100:.1f}%",
                        "Implied (UD)": f"{imp*100:.1f}%" if imp is not None else "—",
                        "Edge": f"{edge:+.1f}%" if edge is not None else "—",
                        "Recommendation": rec,
                    })

                st.markdown(f"### {ud_player} — {ud_stat} ladder")
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                # Best rung pick
                best_rec = None
                best_edge_val = -999
                for rn, line, pay in rungs:
                    p_hit = hit_probability(sims, line, "Over")
                    imp = implied_prob_from_payout(pay)
                    if imp is None or p_hit < 0.5:
                        continue
                    edge = (p_hit - imp) * 100
                    if edge > best_edge_val:
                        best_edge_val = edge
                        best_rec = (rn, line, pay, p_hit, edge)

                if best_rec and best_edge_val >= 3:
                    rn, line, pay, p_hit, edge = best_rec
                    st.success(
                        f"🎯 **TARGET R{rn}: Over {line} @ {pay}x** — "
                        f"Model {p_hit*100:.1f}% | Edge +{edge:.1f}% | "
                        f"L10 avg {l10_avg:.2f}, Season avg {season_avg:.2f}"
                    )
                elif best_rec:
                    rn, line, pay, p_hit, edge = best_rec
                    st.info(f"Best available: R{rn} (edge {edge:+.1f}%) — too thin to recommend")
                else:
                    st.warning("No rung clears 50% hit prob. Skip this player tonight.")


# ============================================================
# TAB 4 — SETTINGS
# ============================================================

with tab_settings:
    st.subheader("📊 Settings & Diagnostics")

    st.markdown("### API Status")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**The Odds API**")
        try:
            r = requests.get(
                f"{ODDS_API_BASE}/sports",
                params={"apiKey": ODDS_API_KEY},
                timeout=10,
            )
            if r.status_code == 200:
                remaining = r.headers.get("x-requests-remaining", "?")
                used = r.headers.get("x-requests-used", "?")
                st.success(f"✅ Connected\nUsed: {used} | Remaining: {remaining}")
            else:
                st.error(f"❌ Status {r.status_code}")
        except Exception as e:
            st.error(f"❌ {e}")

    with col2:
        st.markdown("**NBA Stats API**")
        try:
            r = requests.get(
                f"{NBA_STATS_BASE}/scoreboardv2",
                params={"DayOffset": 0, "GameDate": date.today().strftime("%m/%d/%Y"), "LeagueID": "00"},
                headers=NBA_HEADERS,
                timeout=10,
            )
            if r.status_code == 200:
                st.success("✅ Connected")
            else:
                st.warning(f"⚠️ Status {r.status_code}")
        except Exception as e:
            st.error(f"❌ {e}")

    with col3:
        st.markdown("**MLB Stats API**")
        try:
            r = requests.get(f"{MLB_STATS_BASE}/sports/1", timeout=10)
            if r.status_code == 200:
                st.success("✅ Connected")
            else:
                st.warning(f"⚠️ Status {r.status_code}")
        except Exception as e:
            st.error(f"❌ {e}")

    st.markdown("---")
    st.markdown("### Cache Management")
    if st.button("🗑️ Clear all caches"):
        st.cache_data.clear()
        st.success("Caches cleared. Refresh tabs to repopulate.")

    st.markdown("---")
    st.markdown("### Methodology Notes")
    st.markdown("""
    **Monte Carlo Engine:**
    - 10,000 sims per player per stat
    - Bootstrap from L25 game log with replacement
    - L10 weighted 70%, games 11-25 weighted 30%
    - Falls back to Poisson with shrinkage if sample < 10 games

    **Hit Probability:**
    - P(Over X) = fraction of sims where stat > X
    - For ladders, joint probabilities computed from same simulation set (captures within-game correlation)

    **Edge Calculation:**
    - Sportsbook props: Edge = Model P(Over) − Implied P from American odds
    - Underdog ladders: Edge = Model P(Hit) − (1 / payout multiplier)

    **Known V1.0 Limitations:**
    - No live minutes projections (uses season avg) — V1.1 adds Rotowire scrape
    - No pace/opponent adjustments wired in (engine supports it, UI inputs deferred to V1.1)
    - No Vegas total / blowout detection (V1.1)
    - No multi-player Pick-N correlation modeling (V1.2)

    **Validation Discipline:**
    - Shadow validation only for first 2 weeks
    - No live betting until calibration data shows model edges materializing
    """)

    st.markdown("---")
    st.caption(f"App version: V1.0 | Last code refresh: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
