import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import requests
import json
import time
from supabase import create_client
import os

st.set_page_config(
    page_title="DFS Tier Optimizer",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def get_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

supabase = get_supabase()

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Barlow', sans-serif;
    background-color: #0d0f14;
    color: #e8eaf0;
}
h1, h2, h3 {
    font-family: 'Barlow Condensed', sans-serif;
    letter-spacing: 0.04em;
}
.main-header {
    background: linear-gradient(135deg, #1a1e2e 0%, #0f1420 100%);
    border-bottom: 2px solid #f5a623;
    padding: 1rem 1.5rem;
    margin-bottom: 1.5rem;
    border-radius: 8px;
}
.main-header h1 {
    font-size: 2.2rem;
    font-weight: 800;
    color: #f5a623;
    margin: 0;
    text-transform: uppercase;
}
.main-header .subtitle {
    font-size: 0.9rem;
    color: #8892a4;
    margin-top: 2px;
}
.tier-card {
    background: #161b27;
    border: 1px solid #252d3d;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 1rem;
}
.tier-label {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 1.4rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.6rem;
}
.t1 { color: #f5a623; border-left: 4px solid #f5a623; padding-left: 10px; }
.t2 { color: #4fc3f7; border-left: 4px solid #4fc3f7; padding-left: 10px; }
.t3 { color: #81c784; border-left: 4px solid #81c784; padding-left: 10px; }
.t4 { color: #ce93d8; border-left: 4px solid #ce93d8; padding-left: 10px; }
.t5 { color: #ffb74d; border-left: 4px solid #ffb74d; padding-left: 10px; }
.t6 { color: #f48fb1; border-left: 4px solid #f48fb1; padding-left: 10px; }
.player-row {
    background: #1e2535;
    border-radius: 6px;
    padding: 0.6rem 0.8rem;
    margin-bottom: 0.5rem;
    border: 1px solid #2a3347;
}
.player-name {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: #ffffff;
}
.player-meta {
    font-size: 0.78rem;
    color: #8892a4;
}
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    margin-right: 4px;
}
.badge-green { background: #1b4332; color: #52b788; }
.badge-red { background: #4a0e0e; color: #f87171; }
.badge-yellow { background: #3d2c00; color: #f5a623; }
.badge-blue { background: #0a2540; color: #4fc3f7; }
.score-circle {
    background: #252d3d;
    border-radius: 50%;
    width: 42px;
    height: 42px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
}
.lineup-box {
    background: #161b27;
    border: 2px solid #f5a623;
    border-radius: 10px;
    padding: 1.2rem;
}
.lineup-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid #252d3d;
}
.metric-card {
    background: #161b27;
    border: 1px solid #252d3d;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    text-align: center;
}
.metric-value {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 1.8rem;
    font-weight: 700;
    color: #f5a623;
}
.metric-label {
    font-size: 0.75rem;
    color: #8892a4;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.stButton > button {
    background: #f5a623 !important;
    color: #0d0f14 !important;
    font-family: 'Barlow Condensed', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.4rem 1.2rem !important;
}
.stSelectbox label, .stRadio label {
    color: #8892a4 !important;
    font-size: 0.82rem !important;
}
div[data-testid="stSidebar"] {
    background: #0f1420 !important;
    border-right: 1px solid #252d3d;
}
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
}
.dot-green { background: #52b788; }
.dot-red { background: #f87171; }
.dot-yellow { background: #f5a623; }
</style>
""", unsafe_allow_html=True)

# ── Data Fetchers ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch_dk_tier_contest_id():
    """
    Find today NBA Tier draft group ID using confirmed contestTypeId=73.
    rosterSlotId 415-420 = Tiers 1-6 (confirmed via DevTools inspection).
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        # contestTypeId=73 confirmed as NBA Tiers via Chrome DevTools
        url = "https://api.draftkings.com/lineups/v1/draftgroups?sport=NBA&contestTypeId=73&includeSecondaryDraftablePlayers=false"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()
        draft_groups = data.get("draftGroups", [])
        today = date.today().isoformat()

        for dg in draft_groups:
            start = dg.get("startDateEst", "")
            state = dg.get("draftGroupState", "")
            suffix = dg.get("startTimeSuffix", "")
            if today in start and state != "Closed":
                return dg.get("draftGroupId")

        # Fallback: return any result
        if draft_groups:
            return draft_groups[0].get("draftGroupId")

        return None

    except Exception as e:
        return None

@st.cache_data(ttl=300)
def fetch_dk_tier_players(draft_group_id):
    """Fetch players and tier assignments for a given DK draft group."""
    try:
        url = f"https://api.draftkings.com/lineups/v1/draftgroups/{draft_group_id}/draftables"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []

        data = resp.json()
        players = []

        for p in data.get("draftables", []):
            roster_slot = p.get("rosterSlotId", 0)

            # Tier mapping confirmed via Chrome DevTools 2026-04-06
            # rosterSlotId 415=T1, 416=T2, 417=T3, 418=T4, 419=T5, 420=T6
            tier = None
            position = p.get("position", "")
            tier_map = {415: 1, 416: 2, 417: 3, 418: 4, 419: 5, 420: 6}
            tier = tier_map.get(roster_slot)
            if tier is None and position.startswith("T"):
                try:
                    tier = int(position[1])
                except:
                    pass

            if tier is None:
                continue

            # Get projection from draftStatAttributes
            proj = 0
            for attr in p.get("draftStatAttributes", []):
                if attr.get("id") in [110, 111, 112]:  # FPPG attribute IDs
                    try:
                        proj = float(attr.get("value", 0))
                    except:
                        pass
                    break
            if proj == 0:
                try:
                    proj = float(p.get("draftStatAttributes", [{}])[0].get("value", 0) or 0)
                except:
                    proj = 0

            # Get opponent
            comp = p.get("competition", {})
            home = comp.get("homeTeam", {}).get("abbreviation", "")
            away = comp.get("awayTeam", {}).get("abbreviation", "")
            team = p.get("teamAbbreviation", "")
            opponent = away if team == home else home

            players.append({
                "player_id": p.get("playerId"),
                "name": p.get("displayName", ""),
                "team": team,
                "position": p.get("playerPosition", position),
                "tier": tier,
                "dk_projection": proj,
                "status": p.get("playerGameAttribute", {}).get("label", ""),
                "opponent": opponent,
                "roster_slot_id": roster_slot  # keep for debugging
            })

        return players

    except Exception as e:
        return []

@st.cache_data(ttl=300)
def fetch_dk_nba_slate():
    """
    Main slate fetcher — tries multiple DK endpoints to find tier contest.
    Returns (players list, draft_group_id or None, method used)
    """
    dg_id = fetch_dk_tier_contest_id()

    if dg_id:
        players = fetch_dk_tier_players(dg_id)
        if players:
            return players, dg_id, "live"

    return [], None, "failed"

@st.cache_data(ttl=600)
def fetch_nba_player_stats(player_name):
    """Fetch player recent stats from NBA Stats API."""
    try:
        search_url = "https://stats.nba.com/stats/commonallplayers"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.nba.com",
            "Accept": "application/json",
            "x-nba-stats-origin": "stats",
            "x-nba-stats-token": "true"
        }
        params = {"LeagueID": "00", "Season": "2024-25", "IsOnlyCurrentSeason": "1"}
        resp = requests.get(search_url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            rows = data["resultSets"][0]["rowSet"]
            headers_list = data["resultSets"][0]["headers"]
            for row in rows:
                player = dict(zip(headers_list, row))
                if player_name.lower() in player.get("DISPLAY_FIRST_LAST", "").lower():
                    return player
    except:
        pass
    return {}

@st.cache_data(ttl=600)
def fetch_vegas_lines():
    """Fetch NBA Vegas lines from The Odds API (free tier)."""
    try:
        # Uses oddsapi.io free tier — user needs API key in secrets
        api_key = st.secrets.get("ODDS_API_KEY", "")
        if not api_key:
            return {}
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
        params = {
            "apiKey": api_key,
            "regions": "us",
            "markets": "spreads,totals",
            "oddsFormat": "american"
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            games = resp.json()
            lines = {}
            for game in games:
                home = game.get("home_team", "")
                away = game.get("away_team", "")
                spread = None
                total = None
                for bm in game.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market["key"] == "spreads":
                            for outcome in market.get("outcomes", []):
                                if outcome["name"] == home:
                                    spread = outcome.get("point", 0)
                        if market["key"] == "totals":
                            for outcome in market.get("outcomes", []):
                                if outcome["name"] == "Over":
                                    total = outcome.get("point", 0)
                    break  # first bookmaker only
                lines[home] = {"spread": spread, "total": total, "opponent": away}
                lines[away] = {"spread": -spread if spread else None, "total": total, "opponent": home}
            return lines
        return {}
    except:
        return {}

@st.cache_data(ttl=300)
def fetch_injury_report():
    """Fetch NBA injury report from NBA Stats API."""
    try:
        url = "https://stats.nba.com/stats/leaguedashplayerstats"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.nba.com",
            "x-nba-stats-origin": "stats",
            "x-nba-stats-token": "true"
        }
        # Simplified — pull from rotowire injury feed (no auth needed)
        inj_url = "https://www.rotowire.com/basketball/tables/injury-report.php?team=ALL&pos=ALL"
        resp = requests.get(inj_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code == 200:
            # Parse injury table
            df = pd.read_html(resp.text)[0]
            injured = {}
            for _, row in df.iterrows():
                name = str(row.get("Player", ""))
                status = str(row.get("Status", ""))
                injured[name] = status
            return injured
    except:
        pass
    return {}

# ── Scoring Engine ─────────────────────────────────────────────────────────────

def score_player(player, vegas_lines, injuries):
    """
    Score a player 0-100 for tier recommendation.
    Combines: DK projection, matchup, blowout risk, injury status.
    """
    score = 50.0
    flags = []

    # Base: DK projection (normalized)
    proj = float(player.get("dk_projection", 0) or 0)
    score += min(proj * 1.2, 25)

    # Vegas blowout risk
    team = player.get("team", "")
    line_data = vegas_lines.get(team, {})
    spread = line_data.get("spread")
    total = line_data.get("total")

    if spread is not None:
        if abs(spread) >= 12:
            if spread > 0:  # underdog — blowout victim risk
                score -= 15
                flags.append(("BLOWOUT RISK", "red"))
            else:  # heavy favorite — could have garbage time
                score += 5
                flags.append(("FAV", "green"))
        elif abs(spread) <= 4:
            score += 8
            flags.append(("CLOSE GAME", "blue"))

    if total is not None:
        if total >= 230:
            score += 6
            flags.append(("HIGH O/U", "blue"))
        elif total <= 210:
            score -= 5

    # Injury check
    name = player.get("name", "")
    inj_status = injuries.get(name, "")
    status_field = player.get("status", "")

    if "OUT" in inj_status.upper() or "OUT" in status_field.upper():
        score = 0
        flags = [("OUT", "red")]
    elif "QUESTIONABLE" in inj_status.upper() or "GTD" in status_field.upper():
        score -= 20
        flags.append(("GTD", "yellow"))
    elif "PROBABLE" in inj_status.upper():
        score -= 5
        flags.append(("PROB", "yellow"))

    return round(max(score, 0), 1), flags

def get_matchup_grade(player, vegas_lines):
    """Return A/B/C/D matchup grade based on spread and total."""
    team = player.get("team", "")
    line_data = vegas_lines.get(team, {})
    spread = line_data.get("spread")
    total = line_data.get("total", 220)

    if spread is None:
        return "N/A", "#8892a4"

    score = 0
    if spread <= -6: score += 2
    elif spread <= -3: score += 1
    elif spread >= 10: score -= 3
    elif spread >= 6: score -= 1

    if total >= 228: score += 2
    elif total >= 222: score += 1
    elif total <= 212: score -= 2

    if score >= 3: return "A+", "#52b788"
    elif score >= 2: return "A", "#52b788"
    elif score >= 1: return "B", "#4fc3f7"
    elif score == 0: return "C", "#f5a623"
    else: return "D", "#f87171"

# ── Demo / Fallback Data ───────────────────────────────────────────────────────

def get_demo_slate():
    """Returns a realistic demo slate when DK API is unavailable."""
    return [
        # Tier 1
        {"name": "Nikola Jokic", "team": "DEN", "position": "C", "tier": 1, "dk_projection": 62.5, "status": "", "opponent": "LAL"},
        {"name": "Giannis Antetokounmpo", "team": "MIL", "position": "PF", "tier": 1, "dk_projection": 58.2, "status": "", "opponent": "CHI"},
        {"name": "Luka Doncic", "team": "DAL", "position": "PG", "tier": 1, "dk_projection": 57.8, "status": "GTD", "opponent": "PHX"},
        # Tier 2
        {"name": "Anthony Edwards", "team": "MIN", "position": "SG", "tier": 2, "dk_projection": 48.3, "status": "", "opponent": "UTA"},
        {"name": "Joel Embiid", "team": "PHI", "position": "C", "tier": 2, "dk_projection": 46.9, "status": "", "opponent": "ATL"},
        {"name": "Jayson Tatum", "team": "BOS", "position": "SF", "tier": 2, "dk_projection": 45.1, "status": "", "opponent": "MIA"},
        # Tier 3
        {"name": "Tyrese Haliburton", "team": "IND", "position": "PG", "tier": 3, "dk_projection": 39.4, "status": "", "opponent": "ORL"},
        {"name": "Donovan Mitchell", "team": "CLE", "position": "SG", "tier": 3, "dk_projection": 38.7, "status": "", "opponent": "DET"},
        {"name": "Paolo Banchero", "team": "ORL", "position": "PF", "tier": 3, "dk_projection": 37.2, "status": "GTD", "opponent": "IND"},
        # Tier 4
        {"name": "Darius Garland", "team": "CLE", "position": "PG", "tier": 4, "dk_projection": 31.8, "status": "", "opponent": "DET"},
        {"name": "Tyler Herro", "team": "MIA", "position": "SG", "tier": 4, "dk_projection": 30.5, "status": "", "opponent": "BOS"},
        {"name": "Zach LaVine", "team": "CHI", "position": "SG", "tier": 4, "dk_projection": 29.9, "status": "", "opponent": "MIL"},
        # Tier 5
        {"name": "Bogdan Bogdanovic", "team": "ATL", "position": "SG", "tier": 5, "dk_projection": 24.1, "status": "", "opponent": "PHI"},
        {"name": "Alperen Sengun", "team": "HOU", "position": "C", "tier": 5, "dk_projection": 23.7, "status": "", "opponent": "SAS"},
        {"name": "Dereck Lively II", "team": "DAL", "position": "C", "tier": 5, "dk_projection": 22.4, "status": "", "opponent": "PHX"},
        # Tier 6
        {"name": "Bones Hyland", "team": "LAC", "position": "PG", "tier": 6, "dk_projection": 17.3, "status": "", "opponent": "GSW"},
        {"name": "Tre Jones", "team": "SAS", "position": "PG", "tier": 6, "dk_projection": 16.8, "status": "", "opponent": "HOU"},
        {"name": "Bol Bol", "team": "PHX", "position": "C", "tier": 6, "dk_projection": 15.9, "status": "", "opponent": "DAL"},
    ]


def parse_dk_csv(uploaded_file):
    """
    Parse a DraftKings tier contest CSV export into player list.
    DK CSV columns: Position, Name + ID, Name, ID, Roster Position,
    Salary, Game Info, TeamAbbrev, AvgPointsPerGame
    For tier contests, Position field is T1-T6.
    """
    try:
        df = pd.read_csv(uploaded_file)
        players = []

        for _, row in df.iterrows():
            position = str(row.get("Position", "") or row.get("Roster Position", "")).strip()

            # Tier contests: position is T1, T2, T3, T4, T5, T6
            tier = None
            if position.startswith("T") and len(position) == 2:
                try:
                    tier = int(position[1])
                except:
                    pass

            if tier is None:
                continue

            name = str(row.get("Name", "") or "").strip()
            if not name:
                # Try Name + ID column
                name_id = str(row.get("Name + ID", "") or "")
                name = name_id.split("(")[0].strip() if "(" in name_id else name_id.strip()

            team = str(row.get("TeamAbbrev", "") or "").strip()
            avg_pts = float(row.get("AvgPointsPerGame", 0) or 0)
            game_info = str(row.get("Game Info", "") or "")

            # Parse opponent from game info (e.g. "NYK@ATL 07:30PM ET")
            opponent = ""
            if "@" in game_info:
                teams_part = game_info.split(" ")[0]
                parts = teams_part.split("@")
                if len(parts) == 2:
                    away_team = parts[0].strip()
                    home_team = parts[1].strip()
                    opponent = home_team if team == away_team else away_team

            players.append({
                "name": name,
                "team": team,
                "position": position,
                "tier": tier,
                "dk_projection": avg_pts,
                "status": "",
                "opponent": opponent,
            })

        return players
    except Exception as e:
        st.error(f"CSV parse error: {e}")
        return []

# ── Save to Supabase ───────────────────────────────────────────────────────────

def save_lineup(picks, contest_date):
    """Save today's tier picks to Supabase dfs_lineups table."""
    if not supabase:
        return False
    try:
        record = {
            "contest_date": contest_date,
            "sport": "NBA",
            "contest_type": "TIER",
            "tier_1": picks.get(1, ""),
            "tier_2": picks.get(2, ""),
            "tier_3": picks.get(3, ""),
            "tier_4": picks.get(4, ""),
            "tier_5": picks.get(5, ""),
            "tier_6": picks.get(6, ""),
            "saved_at": datetime.utcnow().isoformat()
        }
        supabase.table("dfs_lineups").insert(record).execute()
        return True
    except Exception as e:
        st.error(f"Supabase save error: {e}")
        return False

def load_lineup_history():
    """Load past lineups from Supabase."""
    if not supabase:
        return pd.DataFrame()
    try:
        resp = supabase.table("dfs_lineups").select("*").order("contest_date", desc=True).limit(30).execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except:
        return pd.DataFrame()

# ── UI ────────────────────────────────────────────────────────────────────────

# Header
st.markdown(f"""
<div class="main-header">
  <h1>🏀 DK Tier Optimizer</h1>
  <div class="subtitle">NBA · DraftKings Tier Contests · {date.today().strftime('%A, %B %d, %Y')}</div>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    slate_mode = st.radio("Slate Source", ["📂 Upload DK CSV", "🔶 Demo Slate"], index=0)
    auto_refresh = st.toggle("Auto-Refresh (5 min)", value=False)
    st.markdown("---")
    st.markdown("### 🔑 API Status")

    odds_key = st.secrets.get("ODDS_API_KEY", "")
    sb_status = "✅ Connected" if SUPABASE_URL else "❌ Not configured"
    odds_status = "✅ Configured" if odds_key else "⚠️ No key (Vegas disabled)"

    st.markdown(f"**Supabase:** {sb_status}")
    st.markdown(f"**Odds API:** {odds_status}")
    st.markdown("---")
    st.markdown("### 📋 Scoring Weights")
    proj_weight = st.slider("Projection Weight", 0.5, 2.0, 1.2, 0.1)
    blowout_penalty = st.slider("Blowout Penalty", 5, 25, 15, 5)
    gtd_penalty = st.slider("GTD Penalty", 5, 30, 20, 5)

# Tabs
tab1, tab2, tab3 = st.tabs(["🏀 Today's Slate", "📋 My Lineup", "📊 History"])

with tab1:
    # CSV Upload mode
    players = []
    if slate_mode == "📂 Upload DK CSV":
        st.markdown("""
        <div style="background:#1e2535; border:1px solid #f5a623; border-radius:8px; padding:0.8rem 1rem; margin-bottom:1rem">
        <b style="color:#f5a623">📂 How to get your DK CSV:</b><br>
        <span style="color:#8892a4; font-size:0.85rem">
        1. Open DraftKings → NBA → Tiers → click any contest → <b>Draft Team</b><br>
        2. Scroll to bottom → click <b>Export to CSV</b><br>
        3. Upload that file below ⬇️
        </span>
        </div>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader("Upload DK Tier CSV", type=["csv"], label_visibility="collapsed")

        if uploaded_file:
            players = parse_dk_csv(uploaded_file)
            if players:
                st.success(f"✅ Loaded {len(players)} players from DK CSV across {len(set(p['tier'] for p in players))} tiers")
            else:
                st.error("❌ Could not parse CSV. Make sure it's a DraftKings tier contest export.")
                players = get_demo_slate()
        else:
            st.info("👆 Upload your DK CSV to load tonight's real slate.")
            players = get_demo_slate()
    else:
        players = get_demo_slate()
        st.info("📌 Demo mode — showing sample slate.")

    with st.spinner("Scoring players..."):
        vegas_lines = fetch_vegas_lines()
        injuries = fetch_injury_report()

    # Score all players
    for p in players:
        p["score"], p["flags"] = score_player(p, vegas_lines, injuries)
        p["matchup_grade"], p["grade_color"] = get_matchup_grade(p, vegas_lines)

    # Summary metrics
    total_players = len(players)
    gtd_count = sum(1 for p in players if any(f[0] == "GTD" for f in p["flags"]))
    out_count = sum(1 for p in players if any(f[0] == "OUT" for f in p["flags"]))
    close_games = sum(1 for p in players if any(f[0] == "CLOSE GAME" for f in p["flags"]))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total_players}</div><div class="metric-label">Players in Slate</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#f5a623">{gtd_count}</div><div class="metric-label">GTD / Questionable</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#f87171">{out_count}</div><div class="metric-label">Out</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#4fc3f7">{close_games}</div><div class="metric-label">Close Game Spots</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tier_colors = {1: "t1", 2: "t2", 3: "t3", 4: "t4", 5: "t5", 6: "t6"}
    tier_labels = {1: "Tier 1 — Elite", 2: "Tier 2 — Star", 3: "Tier 3 — Premium", 4: "Tier 4 — Mid", 5: "Tier 5 — Value", 6: "Tier 6 — Dart"}

    # Initialize picks in session state
    if "picks" not in st.session_state:
        st.session_state.picks = {}

    for tier_num in range(1, 7):
        tier_players = [p for p in players if p["tier"] == tier_num]
        tier_players.sort(key=lambda x: x["score"], reverse=True)
        top2 = tier_players[:2]
        rest = tier_players[2:]

        color_class = tier_colors[tier_num]
        label = tier_labels[tier_num]

        st.markdown(f'<div class="tier-label {color_class}">{label}</div>', unsafe_allow_html=True)

        if not top2:
            st.markdown("_No players found for this tier._")
            continue

        cols = st.columns(len(top2))
        for idx, (col, player) in enumerate(zip(cols, top2)):
            with col:
                score = player["score"]
                flags = player["flags"]
                grade = player["matchup_grade"]
                grade_color = player["grade_color"]
                proj = player.get("dk_projection", 0)
                opp = player.get("opponent", "")
                pos = player.get("position", "")
                team = player.get("team", "")

                # Rank badge
                rank_label = "🥇 TOP PICK" if idx == 0 else "2nd OPTION"

                # Build flag HTML
                flag_html = ""
                for flag_text, flag_color in flags:
                    flag_html += f'<span class="badge badge-{flag_color}">{flag_text}</span>'

                # Vegas info
                line_data = vegas_lines.get(team, {})
                spread = line_data.get("spread")
                total = line_data.get("total")
                vegas_str = ""
                if spread is not None:
                    sign = "+" if spread > 0 else ""
                    vegas_str = f"Spread: {sign}{spread} | O/U: {total}"

                st.markdown(f"""
                <div class="player-row">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                      <div class="player-name">{player['name']}</div>
                      <div class="player-meta">{pos} · {team} vs {opp} · Proj: {proj:.1f} pts</div>
                      <div style="margin-top:4px">{flag_html}<span class="badge badge-blue">MU: {grade}</span></div>
                      <div class="player-meta" style="margin-top:4px">{vegas_str}</div>
                    </div>
                    <div style="text-align:center">
                      <div class="score-circle" style="background:#252d3d; color:#f5a623">{score:.0f}</div>
                      <div style="font-size:0.65rem; color:#8892a4; margin-top:3px">SCORE</div>
                    </div>
                  </div>
                  <div style="margin-top:6px; font-size:0.72rem; color:#8892a4">{rank_label}</div>
                </div>
                """, unsafe_allow_html=True)

        # Show rest of tier in expander
        if rest:
            with st.expander(f"Show all {len(rest) + len(top2)} Tier {tier_num} players"):
                all_players_df = pd.DataFrame([{
                    "Player": p["name"],
                    "Team": p["team"],
                    "Pos": p["position"],
                    "vs": p["opponent"],
                    "Projection": p["dk_projection"],
                    "Score": p["score"],
                    "Matchup": p["matchup_grade"],
                    "Flags": ", ".join(f[0] for f in p["flags"])
                } for p in tier_players])
                st.dataframe(all_players_df, use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)

with tab2:
    st.markdown("### 📋 Build Your Lineup")
    st.markdown("Select your final pick for each tier. Model recommends top 2 — you make the call.")

    if not players:
        st.warning("Load the slate in the Today's Slate tab first.")
    else:
        # Re-score (in case weights changed)
        for p in players:
            p["score"], p["flags"] = score_player(p, vegas_lines, injuries)

        lineup_complete = True
        for tier_num in range(1, 7):
            tier_players = [p for p in players if p["tier"] == tier_num]
            tier_players.sort(key=lambda x: x["score"], reverse=True)

            if not tier_players:
                lineup_complete = False
                continue

            top2 = tier_players[:2]
            options = [p["name"] for p in top2]
            # Add "Other..." option
            options_display = options + ["Other (see full list)"]

            col_a, col_b = st.columns([1, 2])
            with col_a:
                label = tier_labels.get(tier_num, f"Tier {tier_num}")
                choice = st.selectbox(
                    f"**{label}**",
                    options=options_display,
                    key=f"tier_pick_{tier_num}"
                )
            with col_b:
                if choice == "Other (see full list)":
                    all_names = [p["name"] for p in tier_players]
                    choice = st.selectbox("Select from full tier:", all_names, key=f"tier_full_{tier_num}")

                # Show chosen player info
                chosen = next((p for p in tier_players if p["name"] == choice), None)
                if chosen:
                    proj = chosen.get("dk_projection", 0)
                    score = chosen.get("score", 0)
                    flags_str = " ".join(f[0] for f in chosen.get("flags", []))
                    st.markdown(f"**{chosen['name']}** · {chosen['team']} vs {chosen['opponent']} · Proj: {proj:.1f} · Score: {score:.0f} {flags_str}")
                    st.session_state.picks[tier_num] = choice

        st.markdown("---")

        # Lineup summary box
        all_picked = all(t in st.session_state.picks for t in range(1, 7))
        if all_picked:
            st.markdown("### ✅ Your Final Lineup")
            lineup_md = ""
            for t in range(1, 7):
                name = st.session_state.picks.get(t, "—")
                player_data = next((p for p in players if p["name"] == name), {})
                proj = player_data.get("dk_projection", 0)
                lineup_md += f"**Tier {t}:** {name} _(Proj: {proj:.1f})_\n\n"
            st.markdown(lineup_md)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Lineup to Supabase"):
                    saved = save_lineup(st.session_state.picks, date.today().isoformat())
                    if saved:
                        st.success("Lineup saved!")
                    else:
                        st.error("Save failed — check Supabase connection.")
            with col2:
                # Copy-friendly format
                lineup_text = "\n".join([f"T{t}: {st.session_state.picks.get(t, '')}" for t in range(1, 7)])
                st.code(lineup_text, language=None)
        else:
            st.info("Complete all 6 tiers to see your final lineup.")

with tab3:
    st.markdown("### 📊 Lineup History")
    history_df = load_lineup_history()
    if history_df.empty:
        st.info("No lineups saved yet. Build and save your first lineup in the 'My Lineup' tab.")
    else:
        st.dataframe(history_df, use_container_width=True, hide_index=True)
        st.markdown(f"**{len(history_df)} lineups saved**")

# Auto-refresh
if auto_refresh:
    time.sleep(300)
    st.rerun()
