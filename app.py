import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import requests
import time
from supabase import create_client
import pytz

st.set_page_config(
    page_title="DK Tier Optimizer",
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

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Barlow', sans-serif;
    background-color: #0d0f14;
    color: #e8eaf0;
}
h1,h2,h3 { font-family: 'Barlow Condensed', sans-serif; letter-spacing: 0.04em; }

.main-header {
    background: linear-gradient(135deg, #1a1e2e 0%, #0f1420 100%);
    border-bottom: 2px solid #f5a623;
    padding: 1rem 1.5rem; margin-bottom: 1rem; border-radius: 8px;
}
.main-header h1 { font-size: 2rem; font-weight: 800; color: #f5a623; margin: 0; text-transform: uppercase; }
.main-header .subtitle { font-size: 0.85rem; color: #8892a4; margin-top: 2px; }

.tier-header { font-family: 'Barlow Condensed', sans-serif; font-size: 1.4rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.08em; margin: 1rem 0 0.5rem 0; padding-left: 10px; }
.t1 { color: #f5a623; border-left: 4px solid #f5a623; }
.t2 { color: #4fc3f7; border-left: 4px solid #4fc3f7; }
.t3 { color: #81c784; border-left: 4px solid #81c784; }
.t4 { color: #ce93d8; border-left: 4px solid #ce93d8; }
.t5 { color: #ffb74d; border-left: 4px solid #ffb74d; }
.t6 { color: #f48fb1; border-left: 4px solid #f48fb1; }

.pick-cash { background: #0a1a2a; border: 1px solid #1a3a5a; border-left: 3px solid #4fc3f7;
    border-radius: 8px; padding: 0.7rem 0.9rem; margin-bottom: 0.4rem; }
.pick-gpp  { background: #1a0a2a; border: 1px solid #3a1a5a; border-left: 3px solid #ce93d8;
    border-radius: 8px; padding: 0.7rem 0.9rem; margin-bottom: 0.4rem; }
.pick-swap { background: #2a1500; border: 1px solid #f5a623; border-left: 3px solid #f5a623;
    border-radius: 8px; padding: 0.7rem 0.9rem; margin-bottom: 0.4rem; }

.label-cash { font-size: 0.65rem; font-weight: 700; color: #4fc3f7; text-transform: uppercase; letter-spacing: 0.1em; }
.label-gpp  { font-size: 0.65rem; font-weight: 700; color: #ce93d8; text-transform: uppercase; letter-spacing: 0.1em; }
.label-swap { font-size: 0.65rem; font-weight: 700; color: #f5a623; text-transform: uppercase; letter-spacing: 0.1em; }

.pname { font-family: 'Barlow Condensed', sans-serif; font-size: 1.05rem; font-weight: 700; color: #fff; }
.pmeta { font-size: 0.75rem; color: #8892a4; margin-top: 1px; }
.preason { font-size: 0.75rem; color: #b0bec5; margin-top: 3px; font-style: italic; }

.badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 0.65rem;
    font-weight: 700; text-transform: uppercase; margin-right: 3px; }
.b-red    { background: #4a0e0e; color: #f87171; }
.b-yellow { background: #3d2c00; color: #f5a623; }
.b-green  { background: #1b4332; color: #52b788; }
.b-blue   { background: #0a2540; color: #4fc3f7; }
.b-purple { background: #2d1040; color: #ce93d8; }
.b-gray   { background: #252d3d; color: #8892a4; }

.metric-card { background: #161b27; border: 1px solid #252d3d; border-radius: 8px;
    padding: 0.7rem 0.9rem; text-align: center; }
.metric-val { font-family: 'Barlow Condensed', sans-serif; font-size: 1.7rem; font-weight: 700; color: #f5a623; }
.metric-lbl { font-size: 0.68rem; color: #8892a4; text-transform: uppercase; letter-spacing: 0.05em; }

.alert-lock { background: #2a1200; border: 1px solid #f5a623; border-radius: 8px;
    padding: 0.6rem 1rem; margin-bottom: 0.8rem; }
.alert-out  { background: #2a0a0a; border: 1px solid #f87171; border-radius: 8px;
    padding: 0.5rem 0.8rem; margin-bottom: 0.4rem; color: #f87171; font-size: 0.85rem; }
.alert-gtd  { background: #2a1f00; border: 1px solid #f5a623; border-radius: 8px;
    padding: 0.5rem 0.8rem; margin-bottom: 0.4rem; color: #f5a623; font-size: 0.85rem; }

.countdown { font-family: 'Barlow Condensed', sans-serif; font-size: 1.1rem; font-weight: 700; }
.countdown-urgent { color: #f87171; }
.countdown-warn   { color: #f5a623; }
.countdown-ok     { color: #52b788; }

.game-lock-bar { background: #161b27; border: 1px solid #252d3d; border-radius: 6px;
    padding: 0.4rem 0.8rem; margin-bottom: 0.3rem; display: flex; justify-content: space-between; }

div[data-testid="stSidebar"] { background: #0f1420 !important; border-right: 1px solid #252d3d; }
.stButton > button { background: #f5a623 !important; color: #0d0f14 !important;
    font-family: 'Barlow Condensed', sans-serif !important; font-weight: 700 !important;
    font-size: 0.95rem !important; text-transform: uppercase !important;
    letter-spacing: 0.06em !important; border: none !important; border-radius: 6px !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
ET = pytz.timezone("America/New_York")

TIER_LABELS = {
    1: "Tier 1 — Elite",
    2: "Tier 2 — Star",
    3: "Tier 3 — Premium",
    4: "Tier 4 — Mid",
    5: "Tier 5 — Value",
    6: "Tier 6 — Dart"
}
TIER_CLASSES = {1: "t1", 2: "t2", 3: "t3", 4: "t4", 5: "t5", 6: "t6"}

# DK team abbrev → full name (for Vegas line matching)
DK_TEAM_MAP = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards"
}

# ── Data Fetchers ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def fetch_injuries():
    """Fetch NBA injury report from Rotowire."""
    injuries = {}
    try:
        url = "https://www.rotowire.com/basketball/tables/injury-report.php?team=ALL&pos=ALL"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            dfs = pd.read_html(resp.text)
            if dfs:
                df = dfs[0]
                for _, row in df.iterrows():
                    name = str(row.get("Player", "") or "").strip()
                    status = str(row.get("Status", "") or "").strip().upper()
                    injury = str(row.get("Injury", "") or "").strip()
                    if name and name.lower() != "nan":
                        injuries[name.lower()] = {"status": status, "note": injury}
    except:
        pass

    # Fallback: NBA Stats
    try:
        url = "https://stats.nba.com/stats/leagueinjuriesv2?LeagueID=00&Season=2025-26"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.nba.com",
            "x-nba-stats-origin": "stats",
            "x-nba-stats-token": "true"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get("resultSets", [{}])[0].get("rowSet", [])
            hdrs = data.get("resultSets", [{}])[0].get("headers", [])
            for row in rows:
                r = dict(zip(hdrs, row))
                name = str(r.get("PLAYER_NAME", "") or "").strip().lower()
                if name and name not in injuries:
                    injuries[name] = {"status": "OUT", "note": r.get("INJURY_DESCRIPTION", "")}
    except:
        pass

    return injuries

@st.cache_data(ttl=600)
def fetch_vegas_lines():
    """Fetch NBA Vegas lines from The Odds API."""
    lines = {}
    try:
        api_key = st.secrets.get("ODDS_API_KEY", "")
        if not api_key:
            return lines
        url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
        params = {"apiKey": api_key, "regions": "us", "markets": "spreads,totals", "oddsFormat": "american"}
        resp = requests.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            for game in resp.json():
                home = game.get("home_team", "")
                away = game.get("away_team", "")
                spread, total = None, None
                for bm in game.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market["key"] == "spreads":
                            for o in market.get("outcomes", []):
                                if o["name"] == home:
                                    spread = o.get("point", 0)
                        if market["key"] == "totals":
                            for o in market.get("outcomes", []):
                                if o["name"] == "Over":
                                    total = o.get("point", 0)
                    break
                lines[home] = {"spread": spread, "total": total, "opponent": away}
                lines[away] = {"spread": -spread if spread else None, "total": total, "opponent": home}
    except:
        pass
    return lines

@st.cache_data(ttl=1800)
def fetch_recent_form(player_name):
    """Fetch last 10 game DK FPTS average from NBA Stats API."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.nba.com",
            "x-nba-stats-origin": "stats",
            "x-nba-stats-token": "true",
            "Accept": "application/json"
        }
        # Find player ID
        resp = requests.get(
            "https://stats.nba.com/stats/commonallplayers",
            headers=headers,
            params={"LeagueID": "00", "Season": "2025-26", "IsOnlyCurrentSeason": "1"},
            timeout=15
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        rows = data["resultSets"][0]["rowSet"]
        hdrs = data["resultSets"][0]["headers"]
        player_id = None
        name_lower = player_name.lower()
        for row in rows:
            p = dict(zip(hdrs, row))
            full = p.get("DISPLAY_FIRST_LAST", "").lower()
            if name_lower in full or full in name_lower:
                player_id = p.get("PERSON_ID")
                break

        if not player_id:
            return None

        # Get game log
        resp = requests.get(
            "https://stats.nba.com/stats/playergamelog",
            headers=headers,
            params={"PlayerID": player_id, "Season": "2025-26", "SeasonType": "Regular Season", "LeagueID": "00"},
            timeout=15
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        rows = data["resultSets"][0]["rowSet"]
        hdrs = data["resultSets"][0]["headers"]
        if not rows:
            return None

        fpts_list = []
        for row in rows[:10]:
            g = dict(zip(hdrs, row))
            try:
                fpts = (
                    float(g.get("PTS", 0) or 0) +
                    float(g.get("REB", 0) or 0) * 1.25 +
                    float(g.get("AST", 0) or 0) * 1.5 +
                    float(g.get("STL", 0) or 0) * 2.0 +
                    float(g.get("BLK", 0) or 0) * 2.0 +
                    float(g.get("TOV", 0) or 0) * -0.5 +
                    float(g.get("FG3M", 0) or 0) * 0.5
                )
                fpts_list.append(fpts)
            except:
                pass

        return round(np.mean(fpts_list), 1) if fpts_list else None
    except:
        return None

# ── CSV Parser ────────────────────────────────────────────────────────────────
def parse_dk_csv(uploaded_file):
    """Parse DraftKings tier contest CSV. Returns list of player dicts."""
    try:
        df = pd.read_csv(uploaded_file)
        players = []
        for _, row in df.iterrows():
            roster_pos = str(row.get("Roster Position", "") or "").strip()
            position   = str(row.get("Position", "") or "").strip()

            tier = None
            if roster_pos.startswith("T") and len(roster_pos) == 2:
                try:
                    tier = int(roster_pos[1])
                except:
                    pass
            if tier is None:
                continue

            name = str(row.get("Name", "") or "").strip()
            if not name:
                nid = str(row.get("Name + ID", "") or "")
                name = nid.split("(")[0].strip() if "(" in nid else nid.strip()

            team      = str(row.get("TeamAbbrev", "") or "").strip()
            avg_pts   = float(row.get("AvgPointsPerGame", 0) or 0)
            game_info = str(row.get("Game Info", "") or "")

            # Parse opponent
            opponent = ""
            game_time_str = ""
            if "@" in game_info:
                parts = game_info.split(" ")
                matchup = parts[0] if parts else ""
                teams = matchup.split("@")
                if len(teams) == 2:
                    away_t, home_t = teams[0].strip(), teams[1].strip()
                    opponent = home_t if team == away_t else away_t
                # Try to parse game time: "NYK@ATL 07:30PM ET"
                try:
                    time_part = " ".join(parts[1:3]) if len(parts) >= 3 else ""
                    game_time_str = time_part.replace(" ET", "").strip()
                except:
                    pass

            players.append({
                "name": name,
                "team": team,
                "position": position,
                "tier": tier,
                "dk_projection": avg_pts,
                "status": "",
                "opponent": opponent,
                "game_time_str": game_time_str,
                # Will be filled in by scoring
                "inj_status": "",
                "inj_note": "",
                "recent_form": None,
                "vegas_spread": None,
                "vegas_total": None,
                "cash_score": 0,
                "gpp_score": 0,
                "cash_reasons": [],
                "gpp_reasons": [],
            })
        return players
    except Exception as e:
        st.error(f"CSV parse error: {e}")
        return []

# ── Scoring Engine ────────────────────────────────────────────────────────────
def get_inj_status(player_name, injuries):
    """Look up injury status for a player."""
    name_lower = player_name.lower()
    # Exact match
    if name_lower in injuries:
        return injuries[name_lower]
    # Partial match
    for key, val in injuries.items():
        if name_lower in key or key in name_lower:
            return val
    return {"status": "", "note": ""}

def get_vegas(team, vegas_lines):
    """Look up Vegas spread/total for a team."""
    full_name = DK_TEAM_MAP.get(team, team)
    for key in [team, full_name]:
        if key in vegas_lines:
            return vegas_lines[key]
    return {"spread": None, "total": None}

def score_players(players, injuries, vegas_lines, load_recent_form=False):
    """
    Score each player for cash and GPP separately.
    Cash score = maximize floor (safe picks)
    GPP score  = maximize ceiling + ownership leverage
    """
    # Build ownership proxy — players higher in tier list = higher ownership
    # We use DK projection as ownership proxy (higher proj = more chalk)
    for tier_num in range(1, 7):
        tier_players = [p for p in players if p["tier"] == tier_num]
        if not tier_players:
            continue
        max_proj = max(p["dk_projection"] for p in tier_players) or 1
        for p in tier_players:
            p["ownership_proxy"] = p["dk_projection"] / max_proj  # 0-1, higher = more chalk

    for p in players:
        inj = get_inj_status(p["name"], injuries)
        veg = get_vegas(p["team"], vegas_lines)

        p["inj_status"] = inj.get("status", "")
        p["inj_note"]   = inj.get("note", "")
        p["vegas_spread"] = veg.get("spread")
        p["vegas_total"]  = veg.get("total")

        # Optional: fetch recent form (slow — only if requested)
        if load_recent_form and p["recent_form"] is None:
            p["recent_form"] = fetch_recent_form(p["name"])

        proj   = p["dk_projection"]
        spread = p["vegas_spread"]
        total  = p["vegas_total"]
        status = p["inj_status"].upper()
        ownership = p.get("ownership_proxy", 0.5)

        cash_score = 50.0
        gpp_score  = 50.0
        cash_reasons = []
        gpp_reasons  = []

        # ── Injury ────────────────────────────────────────────────────────────
        if "OUT" in status:
            p["cash_score"] = 0
            p["gpp_score"]  = 0
            p["cash_reasons"] = ["OUT — do not play"]
            p["gpp_reasons"]  = ["OUT — do not play"]
            continue

        if "QUESTIONABLE" in status or "GTD" in status or "DOUBTFUL" in status:
            cash_score -= 25
            gpp_score  -= 10  # GPP: risky but if plays = low ownership boom
            cash_reasons.append("GTD — risky for cash")
            gpp_reasons.append("GTD — if confirmed, low ownership upside")

        # ── Projection ───────────────────────────────────────────────────────
        proj_bonus = min((proj - 20) * 0.8, 30)
        cash_score += proj_bonus
        gpp_score  += proj_bonus * 0.7  # GPP cares less about raw proj

        # ── Recent form ──────────────────────────────────────────────────────
        if p["recent_form"] is not None:
            form_diff = p["recent_form"] - proj
            if form_diff > 5:
                cash_score += 8
                gpp_score  += 6
                cash_reasons.append(f"Hot — L10 avg {p['recent_form']:.1f} (+{form_diff:.0f} vs proj)")
                gpp_reasons.append(f"Hot streak — L10 avg {p['recent_form']:.1f}")
            elif form_diff < -5:
                cash_score -= 6
                gpp_score  -= 4
                cash_reasons.append(f"Cold — L10 avg {p['recent_form']:.1f} ({form_diff:.0f} vs proj)")

        # ── Vegas spread ─────────────────────────────────────────────────────
        if spread is not None:
            if spread <= -10:
                cash_score += 10
                gpp_score  += 5
                cash_reasons.append(f"Heavy fav ({spread:+.1f}) — safe floor")
                gpp_reasons.append(f"Fav {spread:+.1f} — chalk, lower GPP value")
            elif spread <= -5:
                cash_score += 6
                gpp_score  += 4
                cash_reasons.append(f"Favored ({spread:+.1f})")
            elif spread >= 10:
                cash_score -= 15
                gpp_score  -= 8
                cash_reasons.append(f"Big underdog ({spread:+.1f}) — blowout risk")
                gpp_reasons.append(f"Underdog {spread:+.1f} — blowout risk")
            elif spread >= 5:
                cash_score -= 6
                gpp_score  -= 3
            elif abs(spread) <= 3:
                cash_score += 4
                gpp_score  += 9  # Close games = more GPP variance/upside
                gpp_reasons.append(f"Close game ({spread:+.1f}) — GPP upside")

        # ── Vegas total ──────────────────────────────────────────────────────
        if total is not None:
            if total >= 230:
                cash_score += 6
                gpp_score  += 8
                cash_reasons.append(f"High O/U {total}")
                gpp_reasons.append(f"High O/U {total} — pace up")
            elif total >= 224:
                cash_score += 3
                gpp_score  += 4
            elif total <= 210:
                cash_score -= 5
                gpp_score  -= 4
                cash_reasons.append(f"Low O/U {total} — slow game")

        # ── GPP ownership leverage ────────────────────────────────────────────
        # Low ownership = GPP bonus, high ownership = GPP penalty
        if ownership < 0.5:
            gpp_score += 12
            gpp_reasons.append("Low ownership — GPP differentiator")
        elif ownership < 0.7:
            gpp_score += 5
            gpp_reasons.append("Moderate ownership")
        else:
            gpp_score -= 5
            gpp_reasons.append("High chalk — fading in GPP has merit")

        # Floor for cash: penalize high-variance players more
        # (players with huge upside but inconsistent = bad for cash)
        if proj > 45 and spread is not None and spread >= 5:
            cash_score -= 8
            cash_reasons.append("High proj but wrong side — floor risk")

        p["cash_score"]    = max(round(cash_score, 1), 0)
        p["gpp_score"]     = max(round(gpp_score, 1), 0)
        p["cash_reasons"]  = cash_reasons[:3]
        p["gpp_reasons"]   = gpp_reasons[:3]

    return players

# ── Game Lock Detection ───────────────────────────────────────────────────────
def get_game_locks(players):
    """
    Build a list of unique games with their lock times from the slate.
    Returns list of {matchup, teams, lock_time_str, minutes_until_lock}
    """
    now_et = datetime.now(ET)
    games = {}
    for p in players:
        opp = p.get("opponent", "")
        team = p.get("team", "")
        gt = p.get("game_time_str", "")
        if not opp or not gt:
            continue
        matchup = "-".join(sorted([team, opp]))
        if matchup not in games:
            # Parse time string e.g. "07:30PM" or "07:30PM ET"
            try:
                gt_clean = gt.replace(" ET", "").strip()
                t = datetime.strptime(gt_clean, "%I:%M%p")
                lock_dt = now_et.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
                if lock_dt < now_et:
                    lock_dt += timedelta(days=1)
                mins = int((lock_dt - now_et).total_seconds() / 60)
                games[matchup] = {
                    "matchup": f"{team} vs {opp}",
                    "teams": [team, opp],
                    "lock_time_str": gt,
                    "lock_dt": lock_dt,
                    "minutes_until_lock": mins
                }
            except:
                pass

    return sorted(games.values(), key=lambda x: x.get("minutes_until_lock", 9999))

# ── Late Swap Detection ───────────────────────────────────────────────────────
def check_late_swap_alerts(picks, players, injuries):
    """
    Check if any picked players have injury issues.
    Returns list of alert dicts.
    """
    alerts = []
    for tier_num, player_name in picks.items():
        player = next((p for p in players if p["name"] == player_name), None)
        if not player:
            continue
        inj = get_inj_status(player_name, injuries)
        status = inj.get("status", "").upper()
        if "OUT" in status:
            alerts.append({
                "tier": tier_num,
                "player": player_name,
                "status": "OUT",
                "note": inj.get("note", ""),
                "severity": "red"
            })
        elif "GTD" in status or "QUESTIONABLE" in status or "DOUBTFUL" in status:
            alerts.append({
                "tier": tier_num,
                "player": player_name,
                "status": status,
                "note": inj.get("note", ""),
                "severity": "yellow"
            })
    return alerts

# ── Save/Load Lineup ──────────────────────────────────────────────────────────
def save_lineup(picks, contest_date, contest_type="TIER"):
    if not supabase:
        return False
    try:
        record = {
            "contest_date": contest_date,
            "sport": "NBA",
            "contest_type": contest_type,
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
        st.error(f"Save error: {e}")
        return False

def load_history():
    if not supabase:
        return pd.DataFrame()
    try:
        resp = supabase.table("dfs_lineups").select("*").order("contest_date", desc=True).limit(30).execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except:
        return pd.DataFrame()

# ── Badge HTML ────────────────────────────────────────────────────────────────
def badge(text, color):
    return f'<span class="badge b-{color}">{text}</span>'

def player_badges(p):
    html = ""
    status = p.get("inj_status", "").upper()
    if "OUT" in status:
        html += badge("OUT", "red")
    elif "GTD" in status or "QUESTIONABLE" in status:
        html += badge("GTD", "yellow")
    elif "PROBABLE" in status:
        html += badge("PROB", "yellow")

    spread = p.get("vegas_spread")
    total  = p.get("vegas_total")
    if spread is not None:
        if spread <= -8:
            html += badge(f"FAV {spread:+.0f}", "green")
        elif spread >= 8:
            html += badge(f"DOG {spread:+.0f}", "red")
        elif abs(spread) <= 3:
            html += badge("CLOSE GAME", "blue")
    if total and total >= 228:
        html += badge(f"O/U {total}", "blue")
    if p.get("recent_form"):
        html += badge(f"L10: {p['recent_form']:.0f}", "purple")
    return html

# ── Main UI ───────────────────────────────────────────────────────────────────

# Header
now_et = datetime.now(ET)
st.markdown(f"""
<div class="main-header">
  <h1>🏀 DK Tier Optimizer</h1>
  <div class="subtitle">NBA · DraftKings Tier Contests · {now_et.strftime('%A, %B %d, %Y')} · {now_et.strftime('%I:%M %p ET')}</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")

    slate_mode = st.radio("Slate Source", ["📂 Upload DK CSV", "🔶 Demo Slate"], index=0)

    st.markdown("---")
    st.markdown("### 🔄 Auto Refresh")
    auto_refresh = st.toggle("Auto-Refresh", value=False)
    refresh_interval = st.select_slider(
        "Interval",
        options=[5, 10, 15, 30],
        value=15,
        format_func=lambda x: f"{x} min"
    )

    st.markdown("---")
    st.markdown("### 📊 Options")
    load_form = st.toggle("Load Recent Form (L10)", value=False,
                          help="Fetches last 10 game averages from NBA Stats API — slower but more accurate")
    show_all  = st.toggle("Show All Players Per Tier", value=False)

    st.markdown("---")
    st.markdown("### 🔑 API Status")
    odds_key = st.secrets.get("ODDS_API_KEY", "")
    st.markdown(f"**Supabase:** {'✅' if SUPABASE_URL else '❌'}")
    st.markdown(f"**Odds API:** {'✅' if odds_key else '⚠️ No key'}")
    st.markdown(f"**Injury Feed:** ✅ Rotowire")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["🏀 Today's Slate", "📋 My Lineup", "🔄 Late Swap", "📊 History"])

# ── Load Data ─────────────────────────────────────────────────────────────────
with tab1:
    players = []

    if slate_mode == "📂 Upload DK CSV":
        st.markdown("""
        <div style="background:#1a1e2e; border:1px solid #f5a623; border-radius:8px; padding:0.8rem 1rem; margin-bottom:1rem">
        <b style="color:#f5a623">📂 How to get your DK CSV</b><br>
        <span style="color:#8892a4; font-size:0.82rem">
        DraftKings → NBA → Tiers → any contest → <b>Draft Team</b> → scroll bottom → <b>Export to CSV</b>
        </span>
        </div>
        """, unsafe_allow_html=True)

        uploaded = st.file_uploader("Upload DK Tier CSV", type=["csv"], label_visibility="collapsed")
        if uploaded:
            players = parse_dk_csv(uploaded)
            if players:
                st.success(f"✅ {len(players)} players loaded across {len(set(p['tier'] for p in players))} tiers")
            else:
                st.error("❌ Could not parse CSV — make sure it's a DK tier contest export.")
        else:
            st.info("👆 Upload your DK CSV to load tonight's real slate.")
    else:
        # Demo slate
        players = [
            {"name": "Victor Wembanyama", "team": "SAS", "position": "C", "tier": 1, "dk_projection": 54.2, "status": "", "opponent": "LAC", "game_time_str": "08:30PM"},
            {"name": "Giannis Antetokounmpo", "team": "MIL", "position": "PF", "tier": 1, "dk_projection": 58.1, "status": "", "opponent": "CHI", "game_time_str": "07:00PM"},
            {"name": "Nikola Jokic", "team": "DEN", "position": "C", "tier": 1, "dk_projection": 62.5, "status": "", "opponent": "UTA", "game_time_str": "09:00PM"},
            {"name": "Anthony Edwards", "team": "MIN", "position": "SG", "tier": 2, "dk_projection": 46.3, "status": "GTD", "opponent": "DET", "game_time_str": "07:00PM"},
            {"name": "Donovan Mitchell", "team": "CLE", "position": "SG", "tier": 2, "dk_projection": 44.6, "status": "", "opponent": "GSW", "game_time_str": "10:00PM"},
            {"name": "Deni Avdija", "team": "POR", "position": "SF", "tier": 2, "dk_projection": 43.8, "status": "", "opponent": "NOP", "game_time_str": "10:00PM"},
            {"name": "James Harden", "team": "CLE", "position": "PG", "tier": 3, "dk_projection": 45.4, "status": "", "opponent": "GSW", "game_time_str": "10:00PM"},
            {"name": "LeBron James", "team": "LAL", "position": "PF", "tier": 3, "dk_projection": 40.9, "status": "", "opponent": "OKC", "game_time_str": "09:30PM"},
            {"name": "Evan Mobley", "team": "CLE", "position": "PF", "tier": 3, "dk_projection": 40.1, "status": "", "opponent": "GSW", "game_time_str": "10:00PM"},
            {"name": "Austin Reaves", "team": "LAL", "position": "SG", "tier": 4, "dk_projection": 39.4, "status": "", "opponent": "OKC", "game_time_str": "09:30PM"},
            {"name": "Chet Holmgren", "team": "OKC", "position": "PF", "tier": 4, "dk_projection": 35.0, "status": "", "opponent": "LAL", "game_time_str": "09:30PM"},
            {"name": "Dejounte Murray", "team": "NOP", "position": "PG", "tier": 4, "dk_projection": 35.5, "status": "", "opponent": "POR", "game_time_str": "10:00PM"},
            {"name": "Stephon Castle", "team": "SAS", "position": "SG", "tier": 5, "dk_projection": 36.7, "status": "", "opponent": "LAC", "game_time_str": "10:30PM"},
            {"name": "Rudy Gobert", "team": "MIN", "position": "C", "tier": 5, "dk_projection": 32.9, "status": "", "opponent": "DET", "game_time_str": "07:00PM"},
            {"name": "Brandon Miller", "team": "CHA", "position": "SF", "tier": 5, "dk_projection": 35.6, "status": "", "opponent": "PHX", "game_time_str": "07:00PM"},
            {"name": "De'Aaron Fox", "team": "SAS", "position": "PG", "tier": 6, "dk_projection": 34.4, "status": "", "opponent": "LAC", "game_time_str": "10:30PM"},
            {"name": "Kobe Knueppel", "team": "CHA", "position": "SG", "tier": 6, "dk_projection": 33.4, "status": "", "opponent": "PHX", "game_time_str": "07:00PM"},
            {"name": "Draymond Green", "team": "GSW", "position": "PF", "tier": 6, "dk_projection": 31.2, "status": "", "opponent": "CLE", "game_time_str": "10:00PM"},
        ]
        # Add missing keys
        for p in players:
            p.update({"inj_status": "", "inj_note": "", "recent_form": None,
                      "vegas_spread": None, "vegas_total": None,
                      "cash_score": 0, "gpp_score": 0,
                      "cash_reasons": [], "gpp_reasons": [], "ownership_proxy": 0.5})
        st.info("📌 Demo mode — showing sample slate.")

    if not players:
        st.stop()

    # Score players
    with st.spinner("Loading injuries, Vegas lines, scoring players..."):
        injuries    = fetch_injuries()
        vegas_lines = fetch_vegas_lines()
        players     = score_players(players, injuries, vegas_lines, load_recent_form=load_form)

    # Game lock status
    game_locks = get_game_locks(players)

    # ── Lock Alerts ───────────────────────────────────────────────────────────
    urgent_locks = [g for g in game_locks if 0 <= g["minutes_until_lock"] <= 30]
    if urgent_locks:
        for gl in urgent_locks:
            mins = gl["minutes_until_lock"]
            color = "urgent" if mins <= 10 else "warn"
            st.markdown(f"""
            <div class="alert-lock">
            ⏰ <span class="countdown countdown-{color}">LOCK IN {mins} MIN</span>
            — {gl['matchup']} locks at {gl['lock_time_str']}
            </div>
            """, unsafe_allow_html=True)

    # ── Slate Metrics ─────────────────────────────────────────────────────────
    out_count  = sum(1 for p in players if "OUT" in p.get("inj_status", "").upper())
    gtd_count  = sum(1 for p in players if any(x in p.get("inj_status", "").upper() for x in ["GTD", "QUESTIONABLE", "DOUBTFUL"]))
    fav_count  = sum(1 for p in players if p.get("vegas_spread") is not None and p["vegas_spread"] <= -5)
    games_count = len(set(f"{p['team']}-{p['opponent']}" for p in players if p.get("opponent")))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{len(players)}</div><div class="metric-lbl">Players</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f87171">{out_count}</div><div class="metric-lbl">Out</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f5a623">{gtd_count}</div><div class="metric-lbl">GTD</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#4fc3f7">{games_count}</div><div class="metric-lbl">Games</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Game Lock Countdown Bar ───────────────────────────────────────────────
    if game_locks:
        st.markdown("**⏱ Game Locks**")
        for gl in game_locks:
            mins = gl["minutes_until_lock"]
            if mins < 0:
                color = "#f87171"; status_txt = "LOCKED"
            elif mins <= 15:
                color = "#f87171"; status_txt = f"🔴 {mins}m"
            elif mins <= 45:
                color = "#f5a623"; status_txt = f"🟡 {mins}m"
            else:
                h, m = divmod(mins, 60)
                status_txt = f"🟢 {h}h {m}m" if h else f"🟢 {m}m"
                color = "#52b788"
            st.markdown(f"""
            <div class="game-lock-bar">
              <span style="color:#e8eaf0; font-size:0.85rem">{gl['matchup']}</span>
              <span style="color:{color}; font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:0.9rem">{status_txt}</span>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Tier Panels ───────────────────────────────────────────────────────────
    if "picks_cash" not in st.session_state:
        st.session_state.picks_cash = {}
    if "picks_gpp" not in st.session_state:
        st.session_state.picks_gpp = {}

    for tier_num in range(1, 7):
        tier_players = [p for p in players if p["tier"] == tier_num]
        if not tier_players:
            continue

        # Sort for cash (floor) and GPP (ceiling) separately
        cash_sorted = sorted(tier_players, key=lambda x: x["cash_score"], reverse=True)
        gpp_sorted  = sorted(tier_players, key=lambda x: x["gpp_score"],  reverse=True)

        tc = TIER_CLASSES[tier_num]
        st.markdown(f'<div class="tier-header {tc}">{TIER_LABELS[tier_num]}</div>', unsafe_allow_html=True)

        col_cash, col_gpp = st.columns(2)

        # ── Cash picks ────────────────────────────────────────────────────────
        with col_cash:
            st.markdown(f'<div class="label-cash">💵 Triple Up / Cash</div>', unsafe_allow_html=True)
            for idx, p in enumerate(cash_sorted[:2]):
                rank = "🥇 TOP CASH PICK" if idx == 0 else "2nd CASH OPTION"
                proj = p["dk_projection"]
                spread = p.get("vegas_spread")
                total  = p.get("vegas_total")
                vegas_str = ""
                if spread is not None:
                    vegas_str = f"Spread {spread:+.1f}"
                    if total:
                        vegas_str += f" · O/U {total}"

                reasons_list = p.get("cash_reasons", [])
                reasons_html = "".join(f"<div class='preason'>• {r}</div>" for r in reasons_list)
                badges_html = player_badges(p)
                name_safe = p["name"]
                pos_safe = p["position"]
                team_safe = p["team"]
                opp_safe = p["opponent"]
                score_val = int(p["cash_score"])

                card_html = (
                    f"<div class='pick-cash'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
                    f"<div>"
                    f"<div class='pname'>{name_safe}</div>"
                    f"<div class='pmeta'>{pos_safe} &middot; {team_safe} vs {opp_safe} &middot; Proj: {proj:.1f}</div>"
                    f"<div class='pmeta'>{vegas_str}</div>"
                    f"<div style='margin-top:4px'>{badges_html}</div>"
                    f"{reasons_html}"
                    f"</div>"
                    f"<div style='text-align:center;min-width:44px'>"
                    f"<div style='background:#0a2540;border-radius:50%;width:40px;height:40px;display:flex;align-items:center;justify-content:center;font-family:Barlow Condensed,sans-serif;font-size:1rem;font-weight:700;color:#4fc3f7'>{score_val}</div>"
                    f"<div style='font-size:0.6rem;color:#8892a4;margin-top:2px'>CASH</div>"
                    f"</div></div>"
                    f"<div style='font-size:0.68rem;color:#4fc3f7;margin-top:5px'>{rank}</div>"
                    f"</div>"
                )
                st.markdown(card_html, unsafe_allow_html=True)

        # ── GPP picks ─────────────────────────────────────────────────────────
        with col_gpp:
            st.markdown(f'<div class="label-gpp">🏆 GPP / Tournament</div>', unsafe_allow_html=True)
            for idx, p in enumerate(gpp_sorted[:2]):
                rank = "🥇 TOP GPP PICK" if idx == 0 else "2nd GPP OPTION"
                proj = p["dk_projection"]
                spread = p.get("vegas_spread")
                total  = p.get("vegas_total")
                vegas_str = ""
                if spread is not None:
                    vegas_str = f"Spread {spread:+.1f}"
                    if total:
                        vegas_str += f" · O/U {total}"

                reasons_list = p.get("gpp_reasons", [])
                reasons_html = "".join(f"<div class='preason'>• {r}</div>" for r in reasons_list)
                badges_html = player_badges(p)
                name_safe = p["name"]
                pos_safe = p["position"]
                team_safe = p["team"]
                opp_safe = p["opponent"]
                score_val = int(p["gpp_score"])

                gpp_card = (
                    f"<div class='pick-gpp'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
                    f"<div>"
                    f"<div class='pname'>{name_safe}</div>"
                    f"<div class='pmeta'>{pos_safe} &middot; {team_safe} vs {opp_safe} &middot; Proj: {proj:.1f}</div>"
                    f"<div class='pmeta'>{vegas_str}</div>"
                    f"<div style='margin-top:4px'>{badges_html}</div>"
                    f"{reasons_html}"
                    f"</div>"
                    f"<div style='text-align:center;min-width:44px'>"
                    f"<div style='background:#2d1040;border-radius:50%;width:40px;height:40px;display:flex;align-items:center;justify-content:center;font-family:Barlow Condensed,sans-serif;font-size:1rem;font-weight:700;color:#ce93d8'>{score_val}</div>"
                    f"<div style='font-size:0.6rem;color:#8892a4;margin-top:2px'>GPP</div>"
                    f"</div></div>"
                    f"<div style='font-size:0.68rem;color:#ce93d8;margin-top:5px'>{rank}</div>"
                    f"</div>"
                )
                st.markdown(gpp_card, unsafe_allow_html=True)

        # Show all players in expander
        if show_all and len(tier_players) > 2:
            with st.expander(f"All {len(tier_players)} Tier {tier_num} players"):
                rows = []
                for p in cash_sorted:
                    rows.append({
                        "Player": p["name"],
                        "Team": p["team"],
                        "vs": p["opponent"],
                        "Proj": p["dk_projection"],
                        "Cash Score": p["cash_score"],
                        "GPP Score": p["gpp_score"],
                        "Spread": p.get("vegas_spread", ""),
                        "O/U": p.get("vegas_total", ""),
                        "Injury": p.get("inj_status", ""),
                        "L10": p.get("recent_form", "")
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)

# ── My Lineup Tab ─────────────────────────────────────────────────────────────
with tab2:
    st.markdown("### 📋 Build Your Lineup")

    if not players:
        st.info("Upload your DK CSV in the Today's Slate tab first.")
        st.stop()

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 💵 Cash Lineup (Triple Up)")
        for tier_num in range(1, 7):
            tier_players = sorted(
                [p for p in players if p["tier"] == tier_num],
                key=lambda x: x["cash_score"], reverse=True
            )
            if not tier_players:
                continue
            top2 = [p["name"] for p in tier_players[:2]]
            options = top2 + ["Other..."]
            choice = st.selectbox(
                f"Tier {tier_num}",
                options=options,
                key=f"cash_t{tier_num}"
            )
            if choice == "Other...":
                choice = st.selectbox(
                    f"Tier {tier_num} — full list",
                    [p["name"] for p in tier_players],
                    key=f"cash_full_t{tier_num}"
                )
            st.session_state.picks_cash[tier_num] = choice

    with col_right:
        st.markdown("#### 🏆 GPP Lineup")
        for tier_num in range(1, 7):
            tier_players = sorted(
                [p for p in players if p["tier"] == tier_num],
                key=lambda x: x["gpp_score"], reverse=True
            )
            if not tier_players:
                continue
            top2 = [p["name"] for p in tier_players[:2]]
            options = top2 + ["Other..."]
            choice = st.selectbox(
                f"Tier {tier_num}",
                options=options,
                key=f"gpp_t{tier_num}"
            )
            if choice == "Other...":
                choice = st.selectbox(
                    f"Tier {tier_num} — full list",
                    [p["name"] for p in tier_players],
                    key=f"gpp_full_t{tier_num}"
                )
            st.session_state.picks_gpp[tier_num] = choice

    st.markdown("---")

    # Show lineups side by side
    if len(st.session_state.picks_cash) == 6 and len(st.session_state.picks_gpp) == 6:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**💵 Your Cash Lineup**")
            for t in range(1, 7):
                name = st.session_state.picks_cash.get(t, "—")
                st.markdown(f"**T{t}:** {name}")
            cash_text = "\n".join([f"T{t}: {st.session_state.picks_cash.get(t,'')}" for t in range(1,7)])
            st.code(cash_text, language=None)
            if st.button("💾 Save Cash Lineup"):
                if save_lineup(st.session_state.picks_cash, date.today().isoformat(), "TIER-CASH"):
                    st.success("Cash lineup saved!")

        with c2:
            st.markdown("**🏆 Your GPP Lineup**")
            for t in range(1, 7):
                name = st.session_state.picks_gpp.get(t, "—")
                st.markdown(f"**T{t}:** {name}")
            gpp_text = "\n".join([f"T{t}: {st.session_state.picks_gpp.get(t,'')}" for t in range(1,7)])
            st.code(gpp_text, language=None)
            if st.button("💾 Save GPP Lineup"):
                if save_lineup(st.session_state.picks_gpp, date.today().isoformat(), "TIER-GPP"):
                    st.success("GPP lineup saved!")

# ── Late Swap Tab ─────────────────────────────────────────────────────────────
with tab3:
    st.markdown("### 🔄 Late Swap Monitor")

    if not players:
        st.info("Upload your DK CSV first.")
    else:
        # Show game lock countdowns
        st.markdown("#### ⏱ Game Lock Status")
        game_locks = get_game_locks(players)
        if game_locks:
            for gl in game_locks:
                mins = gl["minutes_until_lock"]
                if mins < 0:
                    icon = "🔒"; color = "#8892a4"; txt = "LOCKED"
                elif mins <= 15:
                    icon = "🔴"; color = "#f87171"; txt = f"LOCKS IN {mins} MIN"
                elif mins <= 45:
                    icon = "🟡"; color = "#f5a623"; txt = f"Locks in {mins} min"
                else:
                    h, m = divmod(mins, 60)
                    txt = f"Locks in {h}h {m}m" if h else f"Locks in {m}m"
                    icon = "🟢"; color = "#52b788"
                st.markdown(f"{icon} **{gl['matchup']}** — <span style='color:{color}'>{txt}</span> ({gl['lock_time_str']})", unsafe_allow_html=True)
        else:
            st.info("No game times found — make sure your CSV includes Game Info column.")

        st.markdown("---")
        st.markdown("#### 🚨 Pick Alerts")

        all_picks = {}
        all_picks.update(st.session_state.picks_cash)
        all_picks.update(st.session_state.picks_gpp)

        if not all_picks:
            st.info("Build your lineup in the 'My Lineup' tab first to monitor your picks.")
        else:
            alerts = check_late_swap_alerts(all_picks, players, injuries)
            if not alerts:
                st.success("✅ All your picks look healthy — no injury alerts.")
            else:
                for alert in alerts:
                    css = "alert-out" if alert["severity"] == "red" else "alert-gtd"
                    icon = "🔴" if alert["severity"] == "red" else "🟡"
                    st.markdown(f"""
                    <div class="{css}">
                    {icon} <b>Tier {alert['tier']} — {alert['player']}</b> is <b>{alert['status']}</b>
                    {f"({alert['note']})" if alert['note'] else ""}
                    </div>
                    """, unsafe_allow_html=True)

                    # Show replacement options
                    tier_num = alert["tier"]
                    tier_players = [p for p in players
                                    if p["tier"] == tier_num
                                    and p["name"] != alert["player"]
                                    and "OUT" not in p.get("inj_status", "").upper()]

                    cash_replacements = sorted(tier_players, key=lambda x: x["cash_score"], reverse=True)[:3]
                    gpp_replacements  = sorted(tier_players, key=lambda x: x["gpp_score"],  reverse=True)[:3]

                    rc, rg = st.columns(2)
                    with rc:
                        st.markdown(f"**💵 Cash replacements — T{tier_num}:**")
                        for p in cash_replacements:
                            spread = p.get("vegas_spread")
                            spread_str = f" · {spread:+.0f}" if spread is not None else ""
                            st.markdown(f"• **{p['name']}** ({p['team']} vs {p['opponent']}{spread_str}) — Score: {p['cash_score']:.0f}")
                    with rg:
                        st.markdown(f"**🏆 GPP replacements — T{tier_num}:**")
                        for p in gpp_replacements:
                            spread = p.get("vegas_spread")
                            spread_str = f" · {spread:+.0f}" if spread is not None else ""
                            st.markdown(f"• **{p['name']}** ({p['team']} vs {p['opponent']}{spread_str}) — Score: {p['gpp_score']:.0f}")

                    st.markdown("---")

# ── History Tab ───────────────────────────────────────────────────────────────
with tab4:
    st.markdown("### 📊 Lineup History")
    history = load_history()
    if history.empty:
        st.info("No lineups saved yet.")
    else:
        st.dataframe(history, use_container_width=True, hide_index=True)
        st.markdown(f"**{len(history)} lineups saved**")

# ── Auto Refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    interval_sec = refresh_interval * 60
    # Smart refresh: faster if games locking soon
    if game_locks:
        min_lock = min(g["minutes_until_lock"] for g in game_locks if g["minutes_until_lock"] >= 0) if any(g["minutes_until_lock"] >= 0 for g in game_locks) else 999
        if min_lock <= 15:
            interval_sec = 120  # 2 min when locking soon
        elif min_lock <= 30:
            interval_sec = 300  # 5 min when 30 min out
    time.sleep(interval_sec)
    st.rerun()
