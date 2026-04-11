import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import requests
import pytz
import json
from supabase import create_client

st.set_page_config(page_title="DK MLB Tier Optimizer", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")
ET = pytz.timezone("America/New_York")

# ── Supabase ──────────────────────────────────────────────────────────────────
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except:
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
html,body,[class*="css"]{font-family:'Barlow',sans-serif;background-color:#0d0f14;color:#e8eaf0;}
h1,h2,h3{font-family:'Barlow Condensed',sans-serif;letter-spacing:0.04em;}
.hdr{background:linear-gradient(135deg,#1a2e1a,#0f1f0f);border-bottom:2px solid #52b788;padding:0.9rem 1.2rem;margin-bottom:1rem;border-radius:8px;}
.hdr h1{font-size:1.9rem;font-weight:800;color:#52b788;margin:0;text-transform:uppercase;}
.hdr .sub{font-size:0.82rem;color:#8892a4;margin-top:2px;}
.t1{color:#f5a623;border-left:4px solid #f5a623;padding-left:8px;}
.t2{color:#4fc3f7;border-left:4px solid #4fc3f7;padding-left:8px;}
.t3{color:#81c784;border-left:4px solid #81c784;padding-left:8px;}
.t4{color:#ce93d8;border-left:4px solid #ce93d8;padding-left:8px;}
.t5{color:#ffb74d;border-left:4px solid #ffb74d;padding-left:8px;}
.t6{color:#f48fb1;border-left:4px solid #f48fb1;padding-left:8px;}
.pick-cash{background:#0a1a0a;border:1px solid #1a3a1a;border-left:3px solid #52b788;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;}
.pick-gpp{background:#1a0a2a;border:1px solid #3a1a5a;border-left:3px solid #ce93d8;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;}
.pick-out{background:#2a0a0a;border:1px solid #f87171;border-left:3px solid #f87171;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;opacity:0.6;}
.pick-pitcher{background:#0a1a2a;border:1px solid #1a3a5a;border-left:3px solid #f5a623;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;}
.lbl-cash{font-size:0.65rem;font-weight:700;color:#52b788;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;}
.lbl-gpp{font-size:0.65rem;font-weight:700;color:#ce93d8;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;}
.lbl-pitcher{font-size:0.65rem;font-weight:700;color:#f5a623;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;}
.pname{font-family:'Barlow Condensed',sans-serif;font-size:1.05rem;font-weight:700;color:#fff;}
.pmeta{font-size:0.75rem;color:#8892a4;margin-top:1px;}
.preason{font-size:0.74rem;color:#b0bec5;margin-top:2px;}
.badge{display:inline-block;padding:2px 7px;border-radius:3px;font-size:0.66rem;font-weight:700;text-transform:uppercase;margin-right:3px;}
.b-red{background:#4a0e0e;color:#f87171;}
.b-yellow{background:#3d2c00;color:#f5a623;}
.b-green{background:#1b4332;color:#52b788;}
.b-blue{background:#0a2540;color:#4fc3f7;}
.b-purple{background:#2d1040;color:#ce93d8;}
.b-orange{background:#3d1f00;color:#ffb74d;}
.b-teal{background:#0a2a2a;color:#4dd0e1;}
.metric-card{background:#161b27;border:1px solid #252d3d;border-radius:8px;padding:0.7rem 0.9rem;text-align:center;}
.metric-val{font-family:'Barlow Condensed',sans-serif;font-size:1.7rem;font-weight:700;color:#52b788;}
.metric-lbl{font-size:0.68rem;color:#8892a4;text-transform:uppercase;letter-spacing:0.05em;}
.stack-card{background:#0a1f0a;border:1px solid #1a4a1a;border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.5rem;}
.lock-bar{background:#161b27;border:1px solid #252d3d;border-radius:6px;padding:0.4rem 0.8rem;margin-bottom:0.3rem;display:flex;justify-content:space-between;align-items:center;}
.alert-lock{background:#2a1200;border:1px solid #f5a623;border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.8rem;}
.spike-alert{background:#0a1a0a;border:1px solid #52b788;border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.5rem;color:#c8f0c8;font-size:0.85rem;}
.weather-card{background:#0a1a2a;border:1px solid #1a3a5a;border-radius:8px;padding:0.7rem 1rem;margin-bottom:0.5rem;}
div[data-testid="stSidebar"]{background:#0f1420 !important;border-right:1px solid #252d3d;}
.stButton>button{background:#52b788 !important;color:#0d0f14 !important;font-family:'Barlow Condensed',sans-serif !important;font-weight:700 !important;font-size:0.9rem !important;text-transform:uppercase !important;letter-spacing:0.06em !important;border:none !important;border-radius:6px !important;}
@media(max-width:768px){
  .hdr h1{font-size:1.5rem !important;}
  .pname{font-size:1rem !important;}
  .pmeta,.preason{font-size:0.78rem !important;}
  .pick-cash,.pick-gpp,.pick-out,.pick-pitcher{padding:0.8rem !important;}
  .badge{font-size:0.7rem !important;padding:3px 8px !important;}
}
</style>
""", unsafe_allow_html=True)

# ── Park Factors (all 30 stadiums) ────────────────────────────────────────────
PARK_FACTORS = {
    "COL": {"factor": 1.38, "name": "Coors Field", "type": "extreme hitter"},
    "CIN": {"factor": 1.07, "name": "Great American Ball Park", "type": "hitter"},
    "TEX": {"factor": 1.06, "name": "Globe Life Field", "type": "hitter"},
    "BOS": {"factor": 1.05, "name": "Fenway Park", "type": "hitter"},
    "PHI": {"factor": 1.04, "name": "Citizens Bank Park", "type": "hitter"},
    "MIL": {"factor": 1.03, "name": "American Family Field", "type": "slight hitter"},
    "BAL": {"factor": 1.03, "name": "Camden Yards", "type": "slight hitter"},
    "TOR": {"factor": 1.02, "name": "Rogers Centre", "type": "slight hitter"},
    "CHC": {"factor": 1.02, "name": "Wrigley Field", "type": "slight hitter"},
    "NYY": {"factor": 1.02, "name": "Yankee Stadium", "type": "slight hitter"},
    "HOU": {"factor": 1.01, "name": "Minute Maid Park", "type": "neutral"},
    "ARI": {"factor": 1.01, "name": "Chase Field", "type": "neutral"},
    "DET": {"factor": 1.00, "name": "Comerica Park", "type": "neutral"},
    "MIN": {"factor": 1.00, "name": "Target Field", "type": "neutral"},
    "LAA": {"factor": 1.00, "name": "Angel Stadium", "type": "neutral"},
    "ATL": {"factor": 0.99, "name": "Truist Park", "type": "neutral"},
    "TB":  {"factor": 0.99, "name": "Tropicana Field", "type": "neutral"},
    "CWS": {"factor": 0.99, "name": "Guaranteed Rate Field", "type": "neutral"},
    "STL": {"factor": 0.98, "name": "Busch Stadium", "type": "slight pitcher"},
    "PIT": {"factor": 0.98, "name": "PNC Park", "type": "slight pitcher"},
    "KC":  {"factor": 0.98, "name": "Kauffman Stadium", "type": "slight pitcher"},
    "CLE": {"factor": 0.97, "name": "Progressive Field", "type": "slight pitcher"},
    "LAD": {"factor": 0.97, "name": "Dodger Stadium", "type": "slight pitcher"},
    "NYM": {"factor": 0.97, "name": "Citi Field", "type": "pitcher"},
    "SF":  {"factor": 0.96, "name": "Oracle Park", "type": "pitcher"},
    "SEA": {"factor": 0.96, "name": "T-Mobile Park", "type": "pitcher"},
    "MIA": {"factor": 0.95, "name": "loanDepot park", "type": "pitcher"},
    "OAK": {"factor": 0.95, "name": "Oakland Coliseum", "type": "pitcher"},
    "SD":  {"factor": 0.94, "name": "Petco Park", "type": "pitcher"},
    "WSH": {"factor": 0.94, "name": "Nationals Park", "type": "pitcher"},
}

# Team abbrev aliases (DK uses different codes sometimes)
TEAM_ALIASES = {
    "ATH": "OAK", "ARI": "ARI", "TBR": "TB", "TBD": "TB",
    "SFG": "SF", "SDG": "SD", "SDP": "SD", "KCR": "KC",
    "WSN": "WSH", "WAS": "WSH", "CHW": "CWS", "CHC": "CHC",
    "LAA": "LAA", "LAD": "LAD", "NYY": "NYY", "NYM": "NYM",
}

def get_park(team):
    t = TEAM_ALIASES.get(team, team)
    return PARK_FACTORS.get(t, {"factor": 1.0, "name": "Unknown", "type": "neutral"})

# ── Pitcher ERA Dictionary (from existing MLB model) ──────────────────────────
PITCHER_ERA = {
    # Elite
    "Zack Wheeler": 2.95, "Corbin Burnes": 2.94, "Chris Sale": 3.01,
    "Kodai Senga": 3.10, "Logan Webb": 3.15, "Dylan Cease": 3.20,
    "Pablo Lopez": 3.25, "Framber Valdez": 3.28, "Spencer Strider": 3.30,
    "Gerrit Cole": 3.35, "Shane Bieber": 3.40, "Hunter Brown": 3.42,
    # Good
    "Luis Castillo": 3.50, "Sonny Gray": 3.52, "Kevin Gausman": 3.55,
    "Aaron Nola": 3.58, "Nestor Cortes": 3.60, "Carlos Rodon": 3.65,
    "Max Fried": 3.68, "Robbie Ray": 3.70, "Marcus Stroman": 3.72,
    "Michael Wacha": 3.75, "Taj Bradley": 3.78, "Brandon Williamson": 3.80,
    # Average
    "Kyle Hendricks": 4.10, "Jake Irvin": 4.15, "Edward Cabrera": 4.20,
    "Ranger Suarez": 4.25, "Kyle Leahy": 4.30, "Nick Martinez": 4.35,
    "George Klassen": 4.80, "Jacob Lopez": 4.85, "Erick Fedde": 4.90,
    "Braxton Ashcraft": 5.10, "Joe Ryan": 3.95, "Foster Griffin": 4.60,
    "Casey Mize": 4.40, "Janson Junk": 4.70, "Chris Bassitt": 3.85,
    "Eric Lauer": 4.50, "Kyle Harrison": 3.90,
}

def get_pitcher_era(name):
    """Look up pitcher ERA — partial name match."""
    if not name or name == "TBD":
        return 4.50  # League average
    name_lower = name.lower()
    for key, era in PITCHER_ERA.items():
        if name_lower in key.lower() or key.lower() in name_lower:
            return era
    return 4.50

def pitcher_grade(era):
    """Return letter grade and color for pitcher ERA."""
    if era <= 3.00: return "ACE", "#f5a623"
    if era <= 3.50: return "A", "#52b788"
    if era <= 4.00: return "B+", "#4fc3f7"
    if era <= 4.50: return "B", "#8892a4"
    if era <= 5.00: return "C", "#ffb74d"
    return "D", "#f87171"

# ── Vegas Lines ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def fetch_vegas_lines():
    lines = {}
    try:
        api_key = st.secrets.get("ODDS_API_KEY", "")
        if not api_key:
            return lines
        resp = requests.get(
            "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
            params={"apiKey": api_key, "regions": "us", "markets": "spreads,totals", "oddsFormat": "american"},
            timeout=12
        )
        if resp.status_code == 200:
            for game in resp.json():
                home = game.get("home_team", "")
                away = game.get("away_team", "")
                spread, total = None, None
                for bm in game.get("bookmakers", []):
                    for m in bm.get("markets", []):
                        if m["key"] == "spreads":
                            for o in m.get("outcomes", []):
                                if o["name"] == home: spread = o.get("point", 0)
                        if m["key"] == "totals":
                            for o in m.get("outcomes", []):
                                if o["name"] == "Over": total = o.get("point", 0)
                    break
                lines[home] = {"spread": spread, "total": total, "opponent": away}
                lines[away] = {"spread": -spread if spread else None, "total": total, "opponent": home}
    except:
        pass
    return lines

@st.cache_data(ttl=600)
def fetch_mlb_injuries():
    injuries = {}
    try:
        url = "https://www.rotowire.com/baseball/tables/injury-report.php?team=ALL&pos=ALL"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if resp.status_code == 200:
            dfs = pd.read_html(resp.text)
            if dfs:
                for _, row in dfs[0].iterrows():
                    name = str(row.get("Player", "") or "").strip()
                    status = str(row.get("Status", "") or "").strip().upper()
                    note = str(row.get("Injury", "") or "").strip()
                    if name and name.lower() != "nan":
                        injuries[name.lower()] = {"status": status, "note": note}
    except:
        pass
    return injuries

# ── CSV Parser ────────────────────────────────────────────────────────────────
def parse_mlb_csv(uploaded_file):
    """
    Parse DraftKings MLB tier contest CSV.
    MLB CSV columns: Position, Name+ID, Name, ID, Roster Position,
    Salary, Game Info, TeamAbbrev, AvgPointsPerGame
    Positions: P, C, 1B, 2B, 3B, SS, OF
    Tier contests: Roster Position = T1-T6
    """
    try:
        df = pd.read_csv(uploaded_file)
        players = []
        for _, row in df.iterrows():
            roster_pos = str(row.get("Roster Position", "") or "").strip()
            position   = str(row.get("Position", "") or "").strip()

            tier = None
            if roster_pos.startswith("T") and len(roster_pos) == 2:
                try: tier = int(roster_pos[1])
                except: pass
            if tier is None:
                continue

            name = str(row.get("Name", "") or "").strip()
            if not name:
                nid = str(row.get("Name + ID", "") or "")
                name = nid.split("(")[0].strip() if "(" in nid else nid.strip()

            team      = str(row.get("TeamAbbrev", "") or "").strip()
            avg_pts   = float(row.get("AvgPointsPerGame", 0) or 0)
            game_info = str(row.get("Game Info", "") or "")
            salary    = float(str(row.get("Salary", 0) or "0").replace("$", "").replace(",", "") or 0)

            opponent = ""
            game_time_str = ""
            if "@" in game_info:
                parts = game_info.split(" ")
                matchup = parts[0] if parts else ""
                teams = matchup.split("@")
                if len(teams) == 2:
                    away_t, home_t = teams[0].strip(), teams[1].strip()
                    opponent = home_t if team == away_t else away_t
                    is_home = team == home_t
                else:
                    is_home = False
                try:
                    game_time_str = " ".join(parts[1:3]) if len(parts) >= 3 else ""
                    game_time_str = game_time_str.replace(" ET", "").strip()
                except: pass
            else:
                is_home = False

            # Determine home team for park factor
            home_team = opponent if not is_home else team

            players.append({
                "name": name,
                "team": team,
                "position": position,
                "tier": tier,
                "dk_projection": avg_pts,
                "salary": salary,
                "opponent": opponent,
                "home_team": home_team,
                "game_time_str": game_time_str,
                "is_home": is_home,
                # Filled by scoring
                "inj_status": "", "inj_note": "",
                "vegas_spread": None, "vegas_total": None,
                "opp_pitcher": "", "opp_pitcher_era": 4.50,
                "park_factor": 1.0, "park_name": "",
                "ownership_pct": None, "ownership_proxy": 0.5,
                "cash_score": 0, "gpp_score": 0,
                "cash_reasons": [], "gpp_reasons": [],
                "spike_boost": 0, "spike_reason": "",
                "is_pitcher": position == "P",
                "stack_team": "",
            })
        return players
    except Exception as e:
        st.error(f"CSV parse error: {e}")
        return []

# ── Injury Lookup ─────────────────────────────────────────────────────────────
def get_inj(name, injuries):
    nl = name.lower()
    if nl in injuries: return injuries[nl]
    for k, v in injuries.items():
        if nl in k or k in nl: return v
    return {"status": "", "note": ""}

def get_vegas(team, vegas_lines):
    aliases = TEAM_ALIASES.get(team, team)
    for t in [team, aliases]:
        if t in vegas_lines: return vegas_lines[t]
    # Try partial match on team name
    for k, v in vegas_lines.items():
        if team.lower() in k.lower() or k.lower() in team.lower():
            return v
    return {"spread": None, "total": None}

# ── Implied Team Total ────────────────────────────────────────────────────────
def implied_total(spread, total):
    """
    Calculate implied team run total from spread and O/U.
    Formula: implied = (total / 2) - (spread / 2)
    e.g. O/U 9, spread -1.5 -> implied = 4.5 + 0.75 = 5.25 runs
    """
    if spread is None or total is None:
        return None
    return round((total / 2) - (spread / 2), 2)

# ── Weather Fetch (from NWS API) ──────────────────────────────────────────────
# MLB stadium coordinates for weather lookup
STADIUM_COORDS = {
    "NYY": (40.8296, -73.9262, "Bronx, NY"),
    "NYM": (40.7571, -73.8458, "Queens, NY"),
    "BOS": (42.3467, -71.0972, "Boston, MA"),
    "PHI": (39.9061, -75.1665, "Philadelphia, PA"),
    "ATL": (33.8911, -84.4681, "Cumberland, GA"),
    "MIA": (25.7781, -80.2197, "Miami, FL"),
    "WSH": (38.8730, -77.0074, "Washington, DC"),
    "PIT": (40.4469, -80.0057, "Pittsburgh, PA"),
    "CHC": (41.9484, -87.6553, "Chicago, IL"),
    "CWS": (41.8299, -87.6338, "Chicago, IL"),
    "MIL": (43.0283, -87.9712, "Milwaukee, WI"),
    "STL": (38.6226, -90.1928, "St. Louis, MO"),
    "CIN": (39.0979, -84.5082, "Cincinnati, OH"),
    "CLE": (41.4962, -81.6852, "Cleveland, OH"),
    "DET": (42.3390, -83.0485, "Detroit, MI"),
    "MIN": (44.9817, -93.2776, "Minneapolis, MN"),
    "KC":  (39.0517, -94.4803, "Kansas City, MO"),
    "TEX": (32.7512, -97.0832, "Arlington, TX"),
    "HOU": (29.7573, -95.3555, "Houston, TX"),
    "LAA": (33.8003, -117.8827, "Anaheim, CA"),
    "LAD": (34.0739, -118.2400, "Los Angeles, CA"),
    "SF":  (37.7786, -122.3893, "San Francisco, CA"),
    "SD":  (32.7076, -117.1570, "San Diego, CA"),
    "COL": (39.7559, -104.9942, "Denver, CO"),
    "ARI": (33.4453, -112.0667, "Phoenix, AZ"),
    "SEA": (47.5914, -122.3326, "Seattle, WA"),
    "OAK": (37.7516, -122.2005, "Oakland, CA"),
    "ATH": (37.7516, -122.2005, "Oakland, CA"),
    "TB":  (27.7683, -82.6534, "St. Petersburg, FL"),
    "BAL": (39.2838, -76.6218, "Baltimore, MD"),
    "TOR": (43.6414, -79.3894, "Toronto, ON"),
}

@st.cache_data(ttl=1800)
def fetch_weather_for_game(home_team):
    """Fetch current weather for a stadium using NWS API."""
    coords = STADIUM_COORDS.get(home_team)
    if not coords:
        return None
    lat, lon, city = coords
    try:
        # NWS points endpoint
        points_url = f"https://api.weather.gov/points/{lat},{lon}"
        resp = requests.get(points_url, headers={"User-Agent": "DFSTierOptimizer/1.0"}, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        forecast_url = data["properties"]["forecastHourly"]
        resp2 = requests.get(forecast_url, headers={"User-Agent": "DFSTierOptimizer/1.0"}, timeout=10)
        if resp2.status_code != 200:
            return None
        periods = resp2.json()["properties"]["periods"]
        if not periods:
            return None
        p = periods[0]
        return {
            "temp": p.get("temperature", 0),
            "wind_speed": p.get("windSpeed", "0 mph"),
            "wind_dir": p.get("windDirection", ""),
            "description": p.get("shortForecast", ""),
            "city": city,
        }
    except:
        return None

def weather_impact(weather, park_name):
    """
    Assess weather impact on scoring.
    Returns (score_adjustment, reason)
    """
    if not weather:
        return 0, ""
    
    temp = weather.get("temp", 72)
    wind_str = weather.get("wind_speed", "0 mph")
    wind_dir = weather.get("wind_dir", "")
    
    try:
        wind_mph = int(wind_str.split(" ")[0])
    except:
        wind_mph = 0
    
    adj = 0
    reasons = []
    
    # Temperature
    if temp >= 85:
        adj += 4; reasons.append(f"Hot {temp}°F — ball carries")
    elif temp >= 75:
        adj += 2
    elif temp <= 50:
        adj -= 4; reasons.append(f"Cold {temp}°F — ball dies")
    elif temp <= 60:
        adj -= 2; reasons.append(f"Cool {temp}°F")
    
    # Wind — out = hitter boost, in = pitcher boost
    if wind_mph >= 15:
        out_dirs = ["Out", "S", "SE", "SW", "E", "W"]
        in_dirs = ["In", "N", "NE", "NW"]
        if any(d in wind_dir for d in out_dirs):
            adj += 6; reasons.append(f"Wind out {wind_mph}mph 🔥")
        elif any(d in wind_dir for d in in_dirs):
            adj -= 5; reasons.append(f"Wind in {wind_mph}mph ❄️")
        else:
            adj += 2; reasons.append(f"Wind {wind_mph}mph")
    elif wind_mph >= 10:
        adj += 2 if "S" in wind_dir or "E" in wind_dir else -1
    
    return adj, " · ".join(reasons)

# ── Stack Detection ───────────────────────────────────────────────────────────
def detect_stacks(players, vegas_lines):
    """
    Identify best stacking opportunities by team.
    Returns dict of team -> stack score.
    """
    teams = set(p["team"] for p in players if not p["is_pitcher"])
    stack_scores = {}

    for team in teams:
        team_players = [p for p in players if p["team"] == team and not p["is_pitcher"]]
        if len(team_players) < 3:
            continue

        # Get opposing pitcher
        opp = team_players[0]["opponent"] if team_players else ""
        opp_pitcher_era = team_players[0].get("opp_pitcher_era", 4.50) if team_players else 4.50

        # Vegas
        veg = get_vegas(team, vegas_lines)
        total = veg.get("total", 8.5)
        spread = veg.get("spread")

        # Park factor
        home = team_players[0].get("home_team", team) if team_players else team
        park = get_park(home)

        score = 50.0
        reasons = []

        # Opposing pitcher quality (higher ERA = better for batters)
        if opp_pitcher_era >= 5.0:
            score += 20; reasons.append(f"Weak SP (ERA {opp_pitcher_era:.2f})")
        elif opp_pitcher_era >= 4.5:
            score += 12; reasons.append(f"Below avg SP (ERA {opp_pitcher_era:.2f})")
        elif opp_pitcher_era >= 4.0:
            score += 6; reasons.append(f"Average SP (ERA {opp_pitcher_era:.2f})")
        elif opp_pitcher_era <= 3.0:
            score -= 15; reasons.append(f"Ace pitcher (ERA {opp_pitcher_era:.2f}) — avoid stack")
        elif opp_pitcher_era <= 3.5:
            score -= 8; reasons.append(f"Good SP (ERA {opp_pitcher_era:.2f})")

        # Implied team total (most important factor)
        imp = implied_total(spread, total) if total else None
        if imp is not None:
            if imp >= 5.5: score += 20; reasons.append(f"Implied {imp:.1f} runs — elite stack spot")
            elif imp >= 4.5: score += 12; reasons.append(f"Implied {imp:.1f} runs")
            elif imp >= 4.0: score += 5
            elif imp <= 3.0: score -= 15; reasons.append(f"Implied {imp:.1f} runs — avoid")
            elif imp <= 3.5: score -= 8; reasons.append(f"Low implied {imp:.1f} runs")
        elif total:
            if total >= 10: score += 15; reasons.append(f"High O/U {total}")
            elif total >= 9: score += 10; reasons.append(f"O/U {total}")
            elif total >= 8: score += 5
            elif total <= 7: score -= 10; reasons.append(f"Low O/U {total}")

        # Spread
        if spread is not None:
            if spread <= -1.5: score += 8; reasons.append("Favored")
            elif spread >= 1.5: score -= 5; reasons.append("Underdog")

        # Park factor
        pf = park["factor"]
        if pf >= 1.10: score += 12; reasons.append(f"Hitter's park ({park['name']})")
        elif pf >= 1.05: score += 7; reasons.append(f"Slight hitter's park")
        elif pf <= 0.95: score -= 8; reasons.append(f"Pitcher's park ({park['name']})")

        stack_scores[team] = {
            "score": round(score, 1),
            "reasons": reasons[:3],
            "opp": opp,
            "opp_era": opp_pitcher_era,
            "total": total,
            "spread": spread,
            "park": park,
            "player_count": len(team_players)
        }

    return dict(sorted(stack_scores.items(), key=lambda x: x[1]["score"], reverse=True))

# ── Scoring Engine ────────────────────────────────────────────────────────────
def score_players(players, injuries, vegas_lines, manual_out=set(), manual_gtd=set()):
    """Score each player for cash and GPP — MLB specific."""

    # Set ownership proxy by projection rank within tier
    for tier_num in range(1, 7):
        tier_ps = [p for p in players if p["tier"] == tier_num]
        if not tier_ps: continue
        max_proj = max(p["dk_projection"] for p in tier_ps) or 1
        for p in tier_ps:
            p["ownership_proxy"] = p["dk_projection"] / max_proj

    for p in players:
        # Manual overrides
        if p["name"] in manual_out:
            p["inj_status"] = "OUT"; p["inj_note"] = "Manually marked OUT"
        elif p["name"] in manual_gtd:
            p["inj_status"] = "GTD"; p["inj_note"] = "Manually marked GTD"
        else:
            inj = get_inj(p["name"], injuries)
            p["inj_status"] = inj.get("status", "")
            p["inj_note"] = inj.get("note", "")

        # Vegas
        veg = get_vegas(p["team"], vegas_lines)
        p["vegas_spread"] = veg.get("spread")
        p["vegas_total"] = veg.get("total")

        # Park factor
        park = get_park(p["home_team"])
        p["park_factor"] = park["factor"]
        p["park_name"] = park["name"]

        status = p["inj_status"].upper()
        if "OUT" in status:
            p["cash_score"] = 0; p["gpp_score"] = 0
            p["cash_reasons"] = ["OUT — do not play"]
            p["gpp_reasons"] = ["OUT — do not play"]
            continue

        proj = p["dk_projection"]
        spread = p["vegas_spread"]
        total = p["vegas_total"]
        pf = p["park_factor"]
        own = p["ownership_proxy"]
        is_p = p["is_pitcher"]

        cash = 50.0; gpp = 50.0
        cr = []; gr = []

        # GTD
        if "GTD" in status or "QUESTIONABLE" in status:
            cash -= 20; gpp -= 8
            cr.append("GTD — risky for cash")
            gr.append("GTD — low ownership if confirmed")

        # ── PITCHER scoring ───────────────────────────────────────────────────
        if is_p:
            era = get_pitcher_era(p["name"])
            p["opp_pitcher_era"] = era  # self ERA for pitchers
            grade, _ = pitcher_grade(era)

            # Pitcher quality
            if era <= 3.0: cash += 25; gpp += 20; cr.append(f"Ace — ERA {era:.2f}")
            elif era <= 3.5: cash += 18; gpp += 15; cr.append(f"Elite SP — ERA {era:.2f}")
            elif era <= 4.0: cash += 10; gpp += 8; cr.append(f"Good SP — ERA {era:.2f}")
            elif era >= 5.0: cash -= 15; gpp -= 10; cr.append(f"Weak SP — ERA {era:.2f} — fade")
            elif era >= 4.5: cash -= 8; gpp -= 5; cr.append(f"Below avg SP — ERA {era:.2f}")

            # Pitching park — inverse (pitcher's park = good for pitcher)
            if pf <= 0.95: cash += 8; gpp += 6; cr.append(f"Pitcher's park ✅")
            elif pf >= 1.10: cash -= 10; gpp -= 8; cr.append(f"Hitter's park ⚠️")

            # Vegas total for pitchers — low total = good
            if total:
                if total <= 7.5: cash += 10; gpp += 8; cr.append(f"Low O/U {total} — pitcher spot")
                elif total >= 10: cash -= 12; gpp -= 8; cr.append(f"High O/U {total} — risky for SP")

            # Projection
            cash += min(proj * 0.8, 20); gpp += min(proj * 0.6, 15)

        # ── BATTER scoring ────────────────────────────────────────────────────
        else:
            # Opposing pitcher ERA (higher = better for batter)
            opp_era = p.get("opp_pitcher_era", 4.50)
            if opp_era >= 5.0: cash += 18; gpp += 15; cr.append(f"Weak opp SP (ERA {opp_era:.2f})")
            elif opp_era >= 4.5: cash += 12; gpp += 10; cr.append(f"Below avg SP (ERA {opp_era:.2f})")
            elif opp_era >= 4.0: cash += 6; gpp += 5
            elif opp_era <= 3.0: cash -= 15; gpp -= 10; cr.append(f"Facing ace (ERA {opp_era:.2f})")
            elif opp_era <= 3.5: cash -= 8; gpp -= 5; cr.append(f"Tough SP (ERA {opp_era:.2f})")

            # Park factor for batters
            if pf >= 1.15: cash += 12; gpp += 10; cr.append(f"Extreme hitter's park 🔥")
            elif pf >= 1.05: cash += 7; gpp += 6; cr.append(f"Hitter's park ({p['park_name']})")
            elif pf <= 0.95: cash -= 8; gpp -= 5; cr.append(f"Pitcher's park ({p['park_name']})")

            # Vegas total
            if total:
                if total >= 10: cash += 10; gpp += 8; cr.append(f"High O/U {total} — run environment")
                elif total >= 9: cash += 6; gpp += 5
                elif total <= 7: cash -= 8; gpp -= 5; cr.append(f"Low O/U {total} — slow game")

            # Spread
            if spread is not None:
                if spread <= -1.5: cash += 6; gpp += 3; cr.append("Team favored")
                elif spread >= 1.5: cash -= 5; gpp -= 3; cr.append("Team underdog")

            # Projection
            proj_bonus = min((proj - 5) * 1.2, 25)
            cash += proj_bonus; gpp += proj_bonus * 0.7

            # GPP ownership lever
            if own < 0.4: gpp += 14; gr.append("Low ownership — GPP leverage")
            elif own < 0.6: gpp += 5
            else: gpp -= 6; gr.append("High chalk — fade has GPP merit")

        p["cash_score"] = max(round(cash, 1), 0)
        p["gpp_score"]  = max(round(gpp, 1), 0)
        p["cash_reasons"] = cr[:3]
        p["gpp_reasons"]  = (gr + cr)[:3]

    return players

def assign_opp_pitchers(players):
    """
    Try to assign opposing pitcher ERA to each batter.
    Pitchers in the pool face the opposing team's batters.
    """
    # Build pitcher -> team map from player pool
    pitcher_map = {}
    for p in players:
        if p["is_pitcher"]:
            era = get_pitcher_era(p["name"])
            # This pitcher pitches for their team against opponent
            pitcher_map[p["team"]] = {"name": p["name"], "era": era}

    # Assign to batters
    for p in players:
        if not p["is_pitcher"]:
            opp = p["opponent"]
            if opp in pitcher_map:
                p["opp_pitcher"] = pitcher_map[opp]["name"]
                p["opp_pitcher_era"] = pitcher_map[opp]["era"]
            else:
                p["opp_pitcher_era"] = 4.50

    return players

# ── Ownership Estimates ───────────────────────────────────────────────────────
def estimate_ownership(players):
    for tier_num in range(1, 7):
        tier_ps = [p for p in players if p["tier"] == tier_num
                   and "OUT" not in p.get("inj_status", "").upper()]
        if not tier_ps: continue
        tier_ps.sort(key=lambda x: x["dk_projection"], reverse=True)
        base_owns = [45, 28, 15, 7, 3, 2]
        for idx, p in enumerate(tier_ps):
            base = base_owns[idx] if idx < len(base_owns) else 1
            pf = p.get("park_factor", 1.0)
            era = p.get("opp_pitcher_era", 4.50)
            if not p["is_pitcher"]:
                if pf >= 1.10: base += 5
                if era >= 4.5: base += 5
            p["ownership_pct"] = min(max(base, 1), 70)
    return players

# ── Game Locks ────────────────────────────────────────────────────────────────
def get_game_locks(players):
    now_et = datetime.now(ET)
    games = {}
    for p in players:
        opp = p.get("opponent", ""); team = p.get("team", ""); gt = p.get("game_time_str", "")
        if not opp or not gt: continue
        matchup = "-".join(sorted([team, opp]))
        if matchup not in games:
            try:
                gt_clean = gt.replace(" ET", "").strip()
                t = datetime.strptime(gt_clean, "%I:%M%p")
                lock_dt = now_et.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
                if lock_dt < now_et: lock_dt += timedelta(days=1)
                mins = int((lock_dt - now_et).total_seconds() / 60)
                games[matchup] = {"matchup": f"{team} vs {opp}", "teams": [team, opp],
                                  "lock_time_str": gt, "lock_dt": lock_dt, "minutes_until_lock": mins}
            except: pass
    return sorted(games.values(), key=lambda x: x.get("minutes_until_lock", 9999))

# ── Supabase Slate Save/Load ──────────────────────────────────────────────────
def save_slate(players):
    if not supabase: return False
    try:
        today = date.today().isoformat()
        supabase.table("dfs_slate").delete().eq("slate_date", today).execute()
        records = []
        for p in players:
            records.append({
                "slate_date": today, "name": p["name"], "team": p["team"],
                "position": p["position"], "tier": p["tier"],
                "dk_projection": p["dk_projection"], "opponent": p["opponent"],
                "game_time_str": p.get("game_time_str", ""),
            })
        for i in range(0, len(records), 10):
            supabase.table("dfs_slate").insert(records[i:i+10]).execute()
        return True
    except: return False

def load_slate():
    if not supabase: return []
    try:
        today = date.today().isoformat()
        resp = supabase.table("dfs_slate").select("*").eq("slate_date", today).execute()
        if not resp.data: return []
        players = []
        for row in resp.data:
            pos = row.get("position", "")
            game_info = row.get("game_time_str", "")
            opp = row.get("opponent", "")
            team = row.get("team", "")
            players.append({
                "name": row["name"], "team": team, "position": pos,
                "tier": row["tier"], "dk_projection": float(row.get("dk_projection", 0) or 0),
                "salary": 0, "opponent": opp, "home_team": opp,
                "game_time_str": game_info, "is_home": False,
                "inj_status": "", "inj_note": "", "vegas_spread": None, "vegas_total": None,
                "opp_pitcher": "", "opp_pitcher_era": 4.50,
                "park_factor": 1.0, "park_name": "", "ownership_pct": None, "ownership_proxy": 0.5,
                "cash_score": 0, "gpp_score": 0, "cash_reasons": [], "gpp_reasons": [],
                "spike_boost": 0, "spike_reason": "", "is_pitcher": pos == "P", "stack_team": "",
            })
        return players
    except: return []

# ── Badge HTML ────────────────────────────────────────────────────────────────
def b(text, color): return f'<span class="badge b-{color}">{text}</span>'

def badges(p):
    html = ""
    status = p.get("inj_status", "").upper()
    if "OUT" in status: html += b("OUT", "red")
    elif "GTD" in status or "QUESTIONABLE" in status: html += b("GTD", "yellow")
    pf = p.get("park_factor", 1.0)
    if pf >= 1.10: html += b(f"HITTER'S PARK", "orange")
    elif pf <= 0.95: html += b("PITCHER'S PARK", "teal")
    total = p.get("vegas_total")
    if total:
        if total >= 10: html += b(f"O/U {total}", "blue")
        elif total <= 7: html += b(f"O/U {total}", "teal")
    if p.get("is_pitcher"):
        era = get_pitcher_era(p["name"])
        grade, _ = pitcher_grade(era)
        html += b(f"ERA {era:.2f} {grade}", "orange")
    else:
        opp_era = p.get("opp_pitcher_era", 4.50)
        if opp_era >= 4.5: html += b(f"OPP ERA {opp_era:.2f}", "green")
        elif opp_era <= 3.5: html += b(f"OPP ERA {opp_era:.2f}", "red")
    own = p.get("ownership_pct")
    if own: color = "red" if own >= 35 else ("yellow" if own >= 20 else "green")
    return html

def own_html(p):
    own = p.get("ownership_pct")
    if not own: return ""
    color = "#f87171" if own >= 35 else ("#f5a623" if own >= 20 else "#52b788")
    return f'<span class="pmeta">Est. ownership: <b style="color:{color}">{own:.0f}%</b></span>'

def make_card(p, mode="cash"):
    proj = p["dk_projection"]
    spread = p.get("vegas_spread"); total = p.get("vegas_total")
    vegas_str = ""
    if spread is not None: vegas_str = f"Run line {spread:+.1f}"
    if total: vegas_str += f" · O/U {total}"
    score_key = "cash_score" if mode == "cash" else "gpp_score"
    reasons_key = "cash_reasons" if mode == "cash" else "gpp_reasons"
    score = int(p.get(score_key, 0))
    reasons = p.get(reasons_key, [])
    reasons_html = "".join(f"<div class='preason'>• {r}</div>" for r in reasons[:3])
    b_html = badges(p)
    o_html = own_html(p)
    park = p.get("park_name", "")
    opp_p = p.get("opp_pitcher", "")
    opp_line = f"vs {opp_p}" if opp_p and not p["is_pitcher"] else ""
    sal = p.get("salary", 0)
    sal_str = f"${sal:,.0f}" if sal else ""

    if p["is_pitcher"]:
        css = "pick-pitcher"
        sc_bg = "#1a1a0a"; sc_col = "#f5a623"
    elif mode == "cash":
        css = "pick-cash"
        sc_bg = "#0a2a0a"; sc_col = "#52b788"
    else:
        css = "pick-gpp"
        sc_bg = "#2d1040"; sc_col = "#ce93d8"

    if "OUT" in p.get("inj_status", "").upper(): css = "pick-out"

    return (
        f"<div class='{css}'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
        f"<div style='flex:1'>"
        f"<div class='pname'>{p['name']} <span style='color:#8892a4;font-size:0.8rem'>{p['position']}</span></div>"
        f"<div class='pmeta'>{p['team']} vs {p['opponent']} {opp_line} · Proj: {proj:.1f} {sal_str}</div>"
        f"<div class='pmeta'>{vegas_str} · {park}</div>"
        f"<div style='margin-top:5px'>{b_html}</div>"
        f"{o_html}"
        f"{reasons_html}"
        f"</div>"
        f"<div style='text-align:center;min-width:48px;margin-left:8px'>"
        f"<div style='background:{sc_bg};border-radius:50%;width:44px;height:44px;display:flex;align-items:center;justify-content:center;font-family:Barlow Condensed,sans-serif;font-size:1.1rem;font-weight:700;color:{sc_col}'>{score}</div>"
        f"<div style='font-size:0.6rem;color:#8892a4;margin-top:2px'>{mode.upper()}</div>"
        f"</div></div>"
        f"</div>"
    )

# ── Session State ─────────────────────────────────────────────────────────────
if "players" not in st.session_state: st.session_state.players = []
if "manual_out" not in st.session_state: st.session_state.manual_out = set()
if "manual_gtd" not in st.session_state: st.session_state.manual_gtd = set()
if "picks_cash" not in st.session_state: st.session_state.picks_cash = {}
if "picks_gpp" not in st.session_state: st.session_state.picks_gpp = {}

# ── Header ────────────────────────────────────────────────────────────────────
now_et = datetime.now(ET)
st.markdown(f"""
<div class="hdr">
  <h1>⚾ DK MLB Tier Optimizer</h1>
  <div class="sub">MLB · DraftKings Tiers · {now_et.strftime('%A %b %d, %Y')} · {now_et.strftime('%I:%M %p ET')}</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    slate_mode = st.radio("Slate Source", ["📂 Upload DK CSV", "🔶 Demo Slate"], index=0)
    st.markdown("---")
    st.markdown("### 📊 Options")
    show_stacks = st.toggle("Show Stack Recommendations", value=True)
    show_all = st.toggle("Show All Players Per Tier", value=False)
    st.markdown("---")
    st.markdown("### 🔑 API Status")
    odds_key = st.secrets.get("ODDS_API_KEY", "")
    st.markdown(f"**Odds API:** {'✅' if odds_key else '⚠️ No key'}")
    st.markdown(f"**Injury Feed:** ✅ Rotowire")
    st.markdown(f"**Supabase:** {'✅' if supabase else '❌'}")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["⚾ Today's Slate", "📊 Stack Advisor", "🔄 Late Swap", "📋 My Lineup"])

# ── Load Slate ────────────────────────────────────────────────────────────────
players = []

if slate_mode == "📂 Upload DK CSV":
    with tab1:
        if not st.session_state.players:
            saved = load_slate()
            if saved: st.session_state.players = saved

        if st.session_state.players:
            players = st.session_state.players
            today = date.today().strftime("%B %d")
            st.success(f"✅ {len(players)} players loaded for {today} — slate persisted")
            if st.button("📂 Upload New CSV", type="primary"):
                st.session_state.players = []
                if supabase:
                    try: supabase.table("dfs_slate").delete().eq("slate_date", date.today().isoformat()).execute()
                    except: pass
                st.rerun()
        else:
            st.markdown("""
            <div style="background:#1a2e1a;border:1px solid #52b788;border-radius:8px;padding:0.8rem 1rem;margin-bottom:1rem">
            <b style="color:#52b788">📂 How to get your DK MLB CSV</b><br>
            <span style="color:#8892a4;font-size:0.82rem">
            DraftKings → MLB → Tiers → any contest → <b>Draft Team</b> → scroll bottom → <b>Export to CSV</b> → save to OneDrive
            </span>
            </div>
            """, unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload DK MLB Tier CSV", type=["csv"], label_visibility="collapsed")
            if uploaded:
                players = parse_mlb_csv(uploaded)
                if players:
                    st.session_state.players = players
                    saved_ok = save_slate(players)
                    sb_msg = " · Saved to cloud ☁️" if saved_ok else ""
                    st.success(f"✅ {len(players)} players loaded across {len(set(p['tier'] for p in players))} tiers{sb_msg}")
                else:
                    st.error("❌ Could not parse CSV.")
            else:
                st.info("👆 Upload your DK MLB CSV to load today's slate.")
else:
    # Demo slate
    players = [
        {"name":"Kodai Senga","team":"NYM","position":"P","tier":1,"dk_projection":22.8,"salary":9200,"opponent":"ATH","home_team":"NYM","game_time_str":"04:10PM","is_home":True,"inj_status":"","inj_note":"","vegas_spread":-1.5,"vegas_total":4.0,"opp_pitcher":"Jacob Lopez","opp_pitcher_era":4.85,"park_factor":0.97,"park_name":"Citi Field","ownership_pct":None,"ownership_proxy":1.0,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":True,"stack_team":""},
        {"name":"Michael Wacha","team":"KC","position":"P","tier":1,"dk_projection":17.2,"salary":8500,"opponent":"CWS","home_team":"KC","game_time_str":"04:10PM","is_home":True,"inj_status":"","inj_note":"","vegas_spread":-1.5,"vegas_total":5.0,"opp_pitcher":"Erick Fedde","opp_pitcher_era":4.90,"park_factor":0.98,"park_name":"Kauffman Stadium","ownership_pct":None,"ownership_proxy":0.9,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":True,"stack_team":""},
        {"name":"Sal Stewart","team":"CIN","position":"1B","tier":2,"dk_projection":11.4,"salary":4500,"opponent":"LAA","home_team":"CIN","game_time_str":"04:10PM","is_home":True,"inj_status":"","inj_note":"","vegas_spread":-0.5,"vegas_total":5.0,"opp_pitcher":"George Klassen","opp_pitcher_era":4.80,"park_factor":1.07,"park_name":"Great American Ball Park","ownership_pct":None,"ownership_proxy":0.85,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"CIN"},
        {"name":"Matt McLain","team":"CIN","position":"2B","tier":2,"dk_projection":10.8,"salary":3900,"opponent":"LAA","home_team":"CIN","game_time_str":"04:10PM","is_home":True,"inj_status":"","inj_note":"","vegas_spread":-0.5,"vegas_total":5.0,"opp_pitcher":"George Klassen","opp_pitcher_era":4.80,"park_factor":1.07,"park_name":"Great American Ball Park","ownership_pct":None,"ownership_proxy":0.8,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"CIN"},
        {"name":"Eugenio Suarez","team":"CIN","position":"3B","tier":3,"dk_projection":11.1,"salary":4700,"opponent":"LAA","home_team":"CIN","game_time_str":"04:10PM","is_home":True,"inj_status":"","inj_note":"","vegas_spread":-0.5,"vegas_total":5.0,"opp_pitcher":"George Klassen","opp_pitcher_era":4.80,"park_factor":1.07,"park_name":"Great American Ball Park","ownership_pct":None,"ownership_proxy":0.9,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"CIN"},
        {"name":"Zach Neto","team":"LAA","position":"SS","tier":3,"dk_projection":12.9,"salary":4700,"opponent":"CIN","home_team":"CIN","game_time_str":"04:10PM","is_home":False,"inj_status":"","inj_note":"","vegas_spread":0.5,"vegas_total":5.0,"opp_pitcher":"Brandon Williamson","opp_pitcher_era":3.80,"park_factor":1.07,"park_name":"Great American Ball Park","ownership_pct":None,"ownership_proxy":0.85,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"LAA"},
        {"name":"Spencer Steer","team":"CIN","position":"OF","tier":4,"dk_projection":11.6,"salary":3000,"opponent":"LAA","home_team":"CIN","game_time_str":"04:10PM","is_home":True,"inj_status":"","inj_note":"","vegas_spread":-0.5,"vegas_total":5.0,"opp_pitcher":"George Klassen","opp_pitcher_era":4.80,"park_factor":1.07,"park_name":"Great American Ball Park","ownership_pct":None,"ownership_proxy":0.8,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"CIN"},
        {"name":"Jo Adell","team":"LAA","position":"OF","tier":4,"dk_projection":10.8,"salary":3900,"opponent":"CIN","home_team":"CIN","game_time_str":"04:10PM","is_home":False,"inj_status":"","inj_note":"","vegas_spread":0.5,"vegas_total":5.0,"opp_pitcher":"Brandon Williamson","opp_pitcher_era":3.80,"park_factor":1.07,"park_name":"Great American Ball Park","ownership_pct":None,"ownership_proxy":0.7,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"LAA"},
        {"name":"TJ Friedl","team":"CIN","position":"OF","tier":5,"dk_projection":9.8,"salary":3600,"opponent":"LAA","home_team":"CIN","game_time_str":"04:10PM","is_home":True,"inj_status":"","inj_note":"","vegas_spread":-0.5,"vegas_total":5.0,"opp_pitcher":"George Klassen","opp_pitcher_era":4.80,"park_factor":1.07,"park_name":"Great American Ball Park","ownership_pct":None,"ownership_proxy":0.75,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"CIN"},
        {"name":"Will Benson","team":"CIN","position":"OF","tier":5,"dk_projection":8.9,"salary":3100,"opponent":"LAA","home_team":"CIN","game_time_str":"04:10PM","is_home":True,"inj_status":"","inj_note":"","vegas_spread":-0.5,"vegas_total":5.0,"opp_pitcher":"George Klassen","opp_pitcher_era":4.80,"park_factor":1.07,"park_name":"Great American Ball Park","ownership_pct":None,"ownership_proxy":0.65,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"CIN"},
        {"name":"Carter Jensen","team":"KC","position":"C","tier":6,"dk_projection":9.6,"salary":4000,"opponent":"CWS","home_team":"KC","game_time_str":"04:10PM","is_home":True,"inj_status":"","inj_note":"","vegas_spread":-1.5,"vegas_total":5.0,"opp_pitcher":"Erick Fedde","opp_pitcher_era":4.90,"park_factor":0.98,"park_name":"Kauffman Stadium","ownership_pct":None,"ownership_proxy":0.8,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"KC"},
        {"name":"Jorge Soler","team":"LAA","position":"OF","tier":6,"dk_projection":10.8,"salary":3200,"opponent":"CIN","home_team":"CIN","game_time_str":"04:10PM","is_home":False,"inj_status":"","inj_note":"","vegas_spread":0.5,"vegas_total":5.0,"opp_pitcher":"Brandon Williamson","opp_pitcher_era":3.80,"park_factor":1.07,"park_name":"Great American Ball Park","ownership_pct":None,"ownership_proxy":0.7,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","is_pitcher":False,"stack_team":"LAA"},
    ]
    with tab1:
        st.info("📌 Demo mode — upload a real DK MLB CSV to get started.")

if not players:
    st.stop()

# ── Score ─────────────────────────────────────────────────────────────────────
with st.spinner("Loading injuries, Vegas lines, scoring..."):
    injuries    = fetch_mlb_injuries()
    vegas_lines = fetch_vegas_lines()
    players     = assign_opp_pitchers(players)
    players     = score_players(players, injuries, vegas_lines,
                                st.session_state.manual_out, st.session_state.manual_gtd)
    players     = estimate_ownership(players)
    stacks      = detect_stacks(players, vegas_lines)
    game_locks  = get_game_locks(players)

TIER_LABELS  = {1:"Tier 1 — Elite",2:"Tier 2 — Star",3:"Tier 3 — Premium",4:"Tier 4 — Mid",5:"Tier 5 — Value",6:"Tier 6 — Dart"}
TIER_CLASSES = {1:"t1",2:"t2",3:"t3",4:"t4",5:"t5",6:"t6"}

# ── TAB 1: Today's Slate ──────────────────────────────────────────────────────
with tab1:
    # Urgent locks
    for gl in [g for g in game_locks if 0 <= g["minutes_until_lock"] <= 30]:
        st.markdown(f'<div class="alert-lock">⏰ <b style="color:#f5a623">LOCK IN {gl["minutes_until_lock"]} MIN</b> — {gl["matchup"]}</div>', unsafe_allow_html=True)

    # Metrics
    out_count = sum(1 for p in players if "OUT" in p.get("inj_status","").upper())
    gtd_count = sum(1 for p in players if any(x in p.get("inj_status","").upper() for x in ["GTD","QUESTIONABLE"]))
    pitcher_count = sum(1 for p in players if p["is_pitcher"])

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><div class="metric-val">{len(players)}</div><div class="metric-lbl">Players</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f87171">{out_count}</div><div class="metric-lbl">Out</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f5a623">{gtd_count}</div><div class="metric-lbl">GTD</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#4fc3f7">{pitcher_count}</div><div class="metric-lbl">Pitchers</div></div>', unsafe_allow_html=True)

    # Game locks
    if game_locks:
        st.markdown("**⏱ Game Locks**")
        for gl in game_locks:
            mins = gl["minutes_until_lock"]
            if mins < 0: icon="🔒"; color="#8892a4"; txt="LOCKED"
            elif mins <= 15: icon="🔴"; color="#f87171"; txt=f"LOCKS IN {mins}m"
            elif mins <= 45: icon="🟡"; color="#f5a623"; txt=f"Locks in {mins}m"
            else:
                h,m = divmod(mins,60)
                txt = f"Locks in {h}h {m}m" if h else f"Locks in {m}m"
                icon="🟢"; color="#52b788"
            st.markdown(f'<div class="lock-bar"><span style="color:#e8eaf0;font-size:0.85rem">{gl["matchup"]}</span><span style="color:{color};font-weight:700">{icon} {txt}</span></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tier panels
    for tier_num in range(1, 7):
        tier_ps = [p for p in players if p["tier"] == tier_num]
        if not tier_ps: continue
        cash_s = sorted(tier_ps, key=lambda x: x["cash_score"], reverse=True)
        gpp_s  = sorted(tier_ps, key=lambda x: x["gpp_score"],  reverse=True)

        with st.expander(f"{TIER_LABELS[tier_num]}", expanded=True):
            # Pitchers get their own section
            pitchers = [p for p in tier_ps if p["is_pitcher"]]
            batters_cash = [p for p in cash_s if not p["is_pitcher"]]
            batters_gpp  = [p for p in gpp_s  if not p["is_pitcher"]]

            if pitchers:
                st.markdown("<div class='lbl-pitcher'>⚾ PITCHER PICKS</div>", unsafe_allow_html=True)
                for p in pitchers[:2]:
                    st.markdown(make_card(p, "cash"), unsafe_allow_html=True)
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

            if batters_cash:
                st.markdown("<div class='lbl-cash'>💵 CASH — BATTER</div>", unsafe_allow_html=True)
                for p in batters_cash[:2]:
                    st.markdown(make_card(p, "cash"), unsafe_allow_html=True)
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

            if batters_gpp:
                st.markdown("<div class='lbl-gpp'>🏆 GPP — BATTER</div>", unsafe_allow_html=True)
                shown = set()
                for p in batters_gpp:
                    if p["name"] not in shown:
                        st.markdown(make_card(p, "gpp"), unsafe_allow_html=True)
                        shown.add(p["name"])
                    if len(shown) >= 2: break

            if show_all:
                rows = []
                for p in cash_s:
                    rows.append({"Player":p["name"],"Pos":p["position"],"Team":p["team"],"vs":p["opponent"],
                                 "Proj":p["dk_projection"],"Sal":p.get("salary",0),"Cash":p["cash_score"],
                                 "GPP":p["gpp_score"],"Park PF":p.get("park_factor",""),
                                 "Opp ERA":p.get("opp_pitcher_era",""),"O/U":p.get("vegas_total",""),
                                 "Own%":p.get("ownership_pct",""),"Inj":p.get("inj_status","")})
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── TAB 2: Stack Advisor ──────────────────────────────────────────────────────
with tab2:
    st.markdown("### 📊 Stack Advisor")
    st.caption("Ranks teams by stacking opportunity based on opposing pitcher, park factor, and Vegas lines")

    if not stacks:
        st.info("Upload your CSV to see stack recommendations.")
    else:
        for idx, (team, data) in enumerate(list(stacks.items())[:6]):
            score = data["score"]
            color = "#52b788" if score >= 65 else ("#f5a623" if score >= 50 else "#f87171")
            rank_label = "🥇 TOP STACK" if idx == 0 else (f"#{idx+1}" if idx < 3 else f"#{idx+1} — avoid")
            park = data["park"]
            era_grade, era_color = pitcher_grade(data["opp_era"])

            st.markdown(f"""
            <div class="stack-card">
            <div style='display:flex;justify-content:space-between;align-items:center'>
              <div>
                <div style='font-family:Barlow Condensed,sans-serif;font-size:1.2rem;font-weight:700;color:#fff'>{team} vs {data["opp"]} · {rank_label}</div>
                <div class='pmeta'>Opp SP ERA: <b style='color:{era_color}'>{data["opp_era"]:.2f} ({era_grade})</b> · O/U: {data["total"] or "N/A"} · Implied: {f'{implied_total(data["spread"], data["total"]):.1f} runs' if data["total"] else "N/A"} · Park: {park["name"]} ({park["factor"]:.2f})</div>
                <div class='pmeta'>{" · ".join(data["reasons"])}</div>
                <div class='pmeta'>{data["player_count"]} players available in pool</div>
              </div>
              <div style='text-align:center;min-width:52px'>
                <div style='background:#1a2a1a;border-radius:8px;padding:6px 10px;font-family:Barlow Condensed,sans-serif;font-size:1.3rem;font-weight:700;color:{color}'>{score:.0f}</div>
                <div style='font-size:0.6rem;color:#8892a4;margin-top:2px'>STACK SCORE</div>
              </div>
            </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**💡 Stack Rules for MLB Tiers:**")
        st.markdown("- Stack 3-4 batters from your top team against the weakest pitcher")
        st.markdown("- Add 1-2 batters from a second game as bring-back")
        st.markdown("- Never roster a pitcher AND stack batters against them")
        st.markdown("- Hitter's park + weak SP + high O/U = premium stack spot")

# ── TAB 3: Late Swap ──────────────────────────────────────────────────────────
with tab3:
    st.markdown("### 🔄 Late Swap & Injury Manager")
    st.markdown("#### 🩺 Manual Injury Overrides")
    st.caption("Mark players OUT or GTD — overrides auto feed instantly")

    all_names = sorted(set(p["name"] for p in players))
    col_out, col_gtd = st.columns(2)
    with col_out:
        st.markdown("**Mark as OUT:**")
        for name in all_names:
            is_out = name in st.session_state.manual_out
            if st.checkbox(f"🔴 {name}", value=is_out, key=f"out_{name}"):
                st.session_state.manual_out.add(name)
                st.session_state.manual_gtd.discard(name)
            else:
                st.session_state.manual_out.discard(name)

    with col_gtd:
        st.markdown("**Mark as GTD:**")
        for name in all_names:
            if name in st.session_state.manual_out: continue
            is_gtd = name in st.session_state.manual_gtd
            if st.checkbox(f"🟡 {name}", value=is_gtd, key=f"gtd_{name}"):
                st.session_state.manual_gtd.add(name)
            else:
                st.session_state.manual_gtd.discard(name)

    if st.session_state.manual_out:
        st.markdown("---")
        st.markdown("#### ⚡ Replacement Suggestions")
        for out_name in st.session_state.manual_out:
            out_p = next((p for p in players if p["name"] == out_name), None)
            if not out_p: continue
            tier_num = out_p["tier"]
            reps = [p for p in players if p["tier"] == tier_num and p["name"] != out_name
                    and "OUT" not in p.get("inj_status","").upper()
                    and p["name"] not in st.session_state.manual_out]
            st.markdown(f"**🔴 {out_name} OUT — Tier {tier_num} replacements:**")
            rc, rg = st.columns(2)
            with rc:
                st.markdown("💵 Cash:")
                for p in sorted(reps, key=lambda x: x["cash_score"], reverse=True)[:3]:
                    era_str = f" · Opp ERA {p.get('opp_pitcher_era',4.5):.2f}" if not p["is_pitcher"] else ""
                    st.markdown(f"• **{p['name']}** ({p['team']}{era_str}) — {p['cash_score']:.0f}")
            with rg:
                st.markdown("🏆 GPP:")
                for p in sorted(reps, key=lambda x: x["gpp_score"], reverse=True)[:3]:
                    own = p.get("ownership_pct","")
                    own_str = f" · {own:.0f}% own" if own else ""
                    st.markdown(f"• **{p['name']}** ({p['team']}{own_str}) — {p['gpp_score']:.0f}")

    st.markdown("---")
    st.markdown("#### ⏱ Game Lock Status")
    for gl in game_locks:
        mins = gl["minutes_until_lock"]
        if mins < 0: icon="🔒"; color="#8892a4"; txt="LOCKED"
        elif mins <= 15: icon="🔴"; color="#f87171"; txt=f"LOCKS IN {mins} MIN"
        elif mins <= 45: icon="🟡"; color="#f5a623"; txt=f"Locks in {mins}m"
        else:
            h,m = divmod(mins,60)
            txt = f"Locks in {h}h {m}m" if h else f"Locks in {m}m"
            icon="🟢"; color="#52b788"
        st.markdown(f"{icon} **{gl['matchup']}** — <span style='color:{color}'>{txt}</span>", unsafe_allow_html=True)

# ── TAB 4: My Lineup ──────────────────────────────────────────────────────────
with tab4:
    st.markdown("### 📋 My Lineup")

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("#### 💵 Cash (Triple Up)")
        for tier_num in range(1, 7):
            tier_ps = sorted([p for p in players if p["tier"] == tier_num],
                             key=lambda x: x["cash_score"], reverse=True)
            active = [p for p in tier_ps if "OUT" not in p.get("inj_status","").upper()
                      and p["name"] not in st.session_state.manual_out]
            if not active: continue
            options = [p["name"] for p in active[:2]] + ["Other..."]
            choice = st.selectbox(f"T{tier_num}", options=options, key=f"cash_t{tier_num}")
            if choice == "Other...":
                choice = st.selectbox(f"T{tier_num} full", [p["name"] for p in active], key=f"cash_full_t{tier_num}")
            st.session_state.picks_cash[tier_num] = choice

    with col_r:
        st.markdown("#### 🏆 GPP")
        for tier_num in range(1, 7):
            tier_ps = sorted([p for p in players if p["tier"] == tier_num],
                             key=lambda x: x["gpp_score"], reverse=True)
            active = [p for p in tier_ps if "OUT" not in p.get("inj_status","").upper()
                      and p["name"] not in st.session_state.manual_out]
            if not active: continue
            options = [p["name"] for p in active[:2]] + ["Other..."]
            choice = st.selectbox(f"T{tier_num}", options=options, key=f"gpp_t{tier_num}")
            if choice == "Other...":
                choice = st.selectbox(f"T{tier_num} full", [p["name"] for p in active], key=f"gpp_full_t{tier_num}")
            st.session_state.picks_gpp[tier_num] = choice

    # Injury alerts
    st.markdown("---")
    cash_alerts = []; gpp_alerts = []
    for t in range(1, 7):
        for pick, alist, label in [(st.session_state.picks_cash.get(t,""), cash_alerts, "Cash"),
                                    (st.session_state.picks_gpp.get(t,""), gpp_alerts, "GPP")]:
            if not pick: continue
            p = next((x for x in players if x["name"]==pick), None)
            if not p: continue
            status = p.get("inj_status","").upper()
            if "OUT" in status or pick in st.session_state.manual_out:
                alist.append((t, pick, "🔴 OUT — swap immediately"))
            elif any(x in status for x in ["GTD","QUESTIONABLE"]) or pick in st.session_state.manual_gtd:
                alist.append((t, pick, "🟡 GTD — monitor before lock"))

    if cash_alerts or gpp_alerts:
        st.markdown("### ⚠️ Lineup Alerts")
        for t, name, msg in cash_alerts:
            st.markdown(f'<div style="background:#2a0a0a;border:1px solid #f87171;border-radius:8px;padding:0.5rem 0.8rem;margin-bottom:0.4rem;color:#f87171">💵 <b>Cash T{t}: {name}</b> — {msg}</div>', unsafe_allow_html=True)
        for t, name, msg in gpp_alerts:
            st.markdown(f'<div style="background:#2a1f00;border:1px solid #f5a623;border-radius:8px;padding:0.5rem 0.8rem;margin-bottom:0.4rem;color:#f5a623">🏆 <b>GPP T{t}: {name}</b> — {msg}</div>', unsafe_allow_html=True)
        st.caption("Go to Late Swap tab for replacements")
    else:
        if st.session_state.picks_cash or st.session_state.picks_gpp:
            st.success("✅ All your picks are healthy")

    # Final lineups
    if len(st.session_state.picks_cash) == 6 and len(st.session_state.picks_gpp) == 6:
        lc, rg = st.columns(2)
        with lc:
            st.markdown("**💵 Cash Lineup**")
            st.code("\n".join([f"T{t}: {st.session_state.picks_cash.get(t,'')}" for t in range(1,7)]), language=None)
        with rg:
            st.markdown("**🏆 GPP Lineup**")
            st.code("\n".join([f"T{t}: {st.session_state.picks_gpp.get(t,'')}" for t in range(1,7)]), language=None)
