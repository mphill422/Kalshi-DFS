import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import requests
import pytz
import json
from supabase import create_client

st.set_page_config(page_title="MPH DFS Optimizer", page_icon="🏆", layout="wide", initial_sidebar_state="expanded")
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
.hdr{background:linear-gradient(135deg,#1a1a2e,#0f0f1f);border-bottom:2px solid #00d4ff;padding:0.9rem 1.2rem;margin-bottom:1rem;border-radius:8px;}
.hdr-mlb{background:linear-gradient(135deg,#1a2e1a,#0f1f0f);border-bottom:2px solid #52b788;}
.hdr h1{font-size:1.9rem;font-weight:800;color:#00d4ff;margin:0;text-transform:uppercase;}
.hdr-mlb h1{color:#52b788;}
.hdr .sub{font-size:0.82rem;color:#8892a4;margin-top:2px;}
.t1{color:#f5a623;border-left:4px solid #f5a623;padding-left:8px;}
.t2{color:#4fc3f7;border-left:4px solid #4fc3f7;padding-left:8px;}
.t3{color:#81c784;border-left:4px solid #81c784;padding-left:8px;}
.t4{color:#ce93d8;border-left:4px solid #ce93d8;padding-left:8px;}
.t5{color:#ffb74d;border-left:4px solid #ffb74d;padding-left:8px;}
.t6{color:#f48fb1;border-left:4px solid #f48fb1;padding-left:8px;}
.pick-cash{background:#0a1a0a;border:1px solid #1a3a1a;border-left:3px solid #52b788;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;}
.pick-gpp{background:#1a0a2a;border:1px solid #3a1a5a;border-left:3px solid #ce93d8;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;}
.pick-nba{background:#0a1a2a;border:1px solid #1a3a5a;border-left:3px solid #00d4ff;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;}
.pick-out{background:#2a0a0a;border:1px solid #f87171;border-left:3px solid #f87171;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;opacity:0.6;}
.pick-pitcher{background:#0a1a2a;border:1px solid #1a3a5a;border-left:3px solid #f5a623;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;}
.lbl-cash{font-size:0.65rem;font-weight:700;color:#52b788;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;}
.lbl-gpp{font-size:0.65rem;font-weight:700;color:#ce93d8;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;}
.lbl-nba{font-size:0.65rem;font-weight:700;color:#00d4ff;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;}
.lbl-pitcher{font-size:0.65rem;font-weight:700;color:#f5a623;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;}
.pname{font-family:'Barlow Condensed',sans-serif;font-size:1.05rem;font-weight:700;color:#fff;}
.pmeta{font-size:0.75rem;color:#8892a4;margin-top:1px;}
.preason{font-size:0.74rem;color:#b0bec5;margin-top:2px;}
.badge{display:inline-block;padding:2px 7px;border-radius:3px;font-size:0.66rem;font-weight:700;text-transform:uppercase;margin-right:3px;}
.b-red{background:#4a0e0e;color:#f87171;}
.b-yellow{background:#3d2c00;color:#f5a623;}
.b-green{background:#1b4332;color:#52b788;}
.b-blue{background:#0a2540;color:#4fc3f7;}
.b-cyan{background:#0a2a2a;color:#00d4ff;}
.b-purple{background:#2d1040;color:#ce93d8;}
.b-orange{background:#3d1f00;color:#ffb74d;}
.b-teal{background:#0a2a2a;color:#4dd0e1;}
.metric-card{background:#161b27;border:1px solid #252d3d;border-radius:8px;padding:0.7rem 0.9rem;text-align:center;}
.metric-val{font-family:'Barlow Condensed',sans-serif;font-size:1.7rem;font-weight:700;color:#52b788;}
.metric-val-nba{color:#00d4ff;}
.metric-lbl{font-size:0.68rem;color:#8892a4;text-transform:uppercase;letter-spacing:0.05em;}
.stack-card{background:#0a1f0a;border:1px solid #1a4a1a;border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.5rem;}
.stack-card-nba{background:#0a1a2a;border:1px solid #1a3a5a;border-radius:8px;padding:0.8rem 1rem;margin-bottom:0.5rem;}
.lock-bar{background:#161b27;border:1px solid #252d3d;border-radius:6px;padding:0.4rem 0.8rem;margin-bottom:0.3rem;display:flex;justify-content:space-between;align-items:center;}
.alert-lock{background:#2a1200;border:1px solid #f5a623;border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.8rem;}
.lineup-slot{background:#0d1424;border:1px solid #1e2d45;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:0.4rem;display:flex;justify-content:space-between;align-items:center;}
.slot-label{font-size:0.7rem;font-weight:700;color:#00d4ff;text-transform:uppercase;width:40px;}
.salary-bar{height:6px;border-radius:3px;background:#1e2d45;margin-top:8px;overflow:hidden;}
.salary-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,#52b788,#00d4ff);transition:width 0.4s;}
div[data-testid="stSidebar"]{background:#0f1420 !important;border-right:1px solid #252d3d;}
.stButton>button{background:#00d4ff !important;color:#0d0f14 !important;font-family:'Barlow Condensed',sans-serif !important;font-weight:700 !important;font-size:0.9rem !important;text-transform:uppercase !important;letter-spacing:0.06em !important;border:none !important;border-radius:6px !important;}
.stButton>button.mlb-btn{background:#52b788 !important;}
@media(max-width:768px){
  .hdr h1{font-size:1.5rem !important;}
  .pname{font-size:1rem !important;}
  .pmeta,.preason{font-size:0.78rem !important;}
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── SHARED CONSTANTS & HELPERS ────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

# ── NBA DK Roster Slots ───────────────────────────────────────────────────────
NBA_ROSTER = [
    {"slot": "PG",   "positions": ["PG"]},
    {"slot": "SG",   "positions": ["SG"]},
    {"slot": "SF",   "positions": ["SF"]},
    {"slot": "PF",   "positions": ["PF"]},
    {"slot": "C",    "positions": ["C"]},
    {"slot": "G",    "positions": ["PG", "SG"]},
    {"slot": "F",    "positions": ["SF", "PF"]},
    {"slot": "UTIL", "positions": ["PG", "SG", "SF", "PF", "C"]},
]
NBA_SALARY_CAP = 50000

# ── Park Factors ──────────────────────────────────────────────────────────────
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

TEAM_ALIASES = {
    "ATH": "OAK", "TBR": "TB", "TBD": "TB",
    "SFG": "SF", "SDG": "SD", "SDP": "SD", "KCR": "KC",
    "WSN": "WSH", "WAS": "WSH", "CHW": "CWS",
}

TEAM_NAME_TO_ABBREV = {
    "arizona diamondbacks": "ARI", "atlanta braves": "ATL",
    "baltimore orioles": "BAL", "boston red sox": "BOS",
    "chicago cubs": "CHC", "chicago white sox": "CWS",
    "cincinnati reds": "CIN", "cleveland guardians": "CLE",
    "colorado rockies": "COL", "detroit tigers": "DET",
    "houston astros": "HOU", "kansas city royals": "KC",
    "los angeles angels": "LAA", "los angeles dodgers": "LAD",
    "miami marlins": "MIA", "milwaukee brewers": "MIL",
    "minnesota twins": "MIN", "new york mets": "NYM",
    "new york yankees": "NYY", "oakland athletics": "OAK",
    "athletics": "OAK", "philadelphia phillies": "PHI",
    "pittsburgh pirates": "PIT", "san diego padres": "SD",
    "san francisco giants": "SF", "seattle mariners": "SEA",
    "st. louis cardinals": "STL", "tampa bay rays": "TB",
    "texas rangers": "TEX", "toronto blue jays": "TOR",
    "washington nationals": "WSH",
}

PITCHER_ERA = {
    "Max Fried": 3.15, "Logan Webb": 3.15, "Michael Wacha": 1.50,
    "Erick Fedde": 4.09, "Ranger Suarez": 4.10, "Kyle Leahy": 4.60,
    "Jacob Lopez": 6.48, "Lance McCullers": 3.20, "Chris Bassitt": 3.85,
    "Freddy Peralta": 3.40, "Matthew Liberatore": 4.21, "Sandy Alcantara": 3.88,
    "Tarik Skubal": 2.60, "Zack Gallen": 4.20, "Garrett Crochet": 2.90,
    "Paul Skenes": 2.50, "Chris Sale": 3.01, "Nathan Eovaldi": 3.20,
    "Jacob deGrom": 3.00, "Luis Severino": 3.80, "Kevin Gausman": 3.55,
    "Kyle Freeland": 4.80, "Zack Wheeler": 2.95, "Corbin Burnes": 2.94,
    "Kodai Senga": 3.10, "Dylan Cease": 3.20, "Pablo Lopez": 3.25,
    "Framber Valdez": 3.28, "Spencer Strider": 3.30, "Gerrit Cole": 3.35,
    "Shane Bieber": 3.40, "Hunter Brown": 3.42, "Luis Castillo": 3.50,
    "Sonny Gray": 3.52, "Aaron Nola": 3.58, "Nestor Cortes": 3.60,
    "Carlos Rodon": 3.65, "Robbie Ray": 3.70, "Marcus Stroman": 3.72,
    "Taj Bradley": 3.78, "Brandon Williamson": 3.80, "Joe Ryan": 3.95,
    "Kyle Harrison": 3.90, "George Kirby": 3.70, "Bryan Woo": 3.85,
    "Michael King": 3.90, "MacKenzie Gore": 3.95, "Bailey Ober": 4.00,
    "Kyle Hendricks": 4.10, "Jake Irvin": 4.15, "Edward Cabrera": 4.20,
    "Casey Mize": 4.40, "Nick Martinez": 4.35, "Eric Lauer": 4.50,
    "Jameson Taillon": 3.68, "George Klassen": 4.80, "Braxton Ashcraft": 5.10,
    "Foster Griffin": 4.60, "Janson Junk": 4.70,
}

DOMED_STADIUMS = {"HOU", "MIA", "TB", "TOR", "ARI", "MIL", "SEA", "MIN", "ATH", "OAK"}

STADIUM_COORDS = {
    "NYY": (40.8296, -73.9262, "Bronx, NY"), "NYM": (40.7571, -73.8458, "Queens, NY"),
    "BOS": (42.3467, -71.0972, "Boston, MA"), "PHI": (39.9061, -75.1665, "Philadelphia, PA"),
    "ATL": (33.8911, -84.4681, "Cumberland, GA"), "MIA": (25.7781, -80.2197, "Miami, FL"),
    "WSH": (38.8730, -77.0074, "Washington, DC"), "PIT": (40.4469, -80.0057, "Pittsburgh, PA"),
    "CHC": (41.9484, -87.6553, "Chicago, IL"), "CWS": (41.8299, -87.6338, "Chicago, IL"),
    "MIL": (43.0283, -87.9712, "Milwaukee, WI"), "STL": (38.6226, -90.1928, "St. Louis, MO"),
    "CIN": (39.0979, -84.5082, "Cincinnati, OH"), "CLE": (41.4962, -81.6852, "Cleveland, OH"),
    "DET": (42.3390, -83.0485, "Detroit, MI"), "MIN": (44.9817, -93.2776, "Minneapolis, MN"),
    "KC":  (39.0517, -94.4803, "Kansas City, MO"), "TEX": (32.7512, -97.0832, "Arlington, TX"),
    "HOU": (29.7573, -95.3555, "Houston, TX"), "LAA": (33.8003, -117.8827, "Anaheim, CA"),
    "LAD": (34.0739, -118.2400, "Los Angeles, CA"), "SF":  (37.7786, -122.3893, "San Francisco, CA"),
    "SD":  (32.7076, -117.1570, "San Diego, CA"), "COL": (39.7559, -104.9942, "Denver, CO"),
    "ARI": (33.4453, -112.0667, "Phoenix, AZ"), "SEA": (47.5914, -122.3326, "Seattle, WA"),
    "OAK": (37.7516, -122.2005, "Oakland, CA"), "ATH": (37.7516, -122.2005, "Oakland, CA"),
    "TB":  (27.7683, -82.6534, "St. Petersburg, FL"), "BAL": (39.2838, -76.6218, "Baltimore, MD"),
    "TOR": (43.6414, -79.3894, "Toronto, ON"),
}

def get_park(team):
    t = TEAM_ALIASES.get(team, team)
    return PARK_FACTORS.get(t, {"factor": 1.0, "name": "Unknown", "type": "neutral"})

def get_pitcher_era(name):
    if not name or name == "TBD": return 4.50
    name_lower = name.lower().strip()
    for key, era in PITCHER_ERA.items():
        if name_lower == key.lower(): return era
    for key, era in PITCHER_ERA.items():
        if name_lower in key.lower() or key.lower() in name_lower: return era
    name_parts = name_lower.split()
    if name_parts:
        last = name_parts[-1]
        for key, era in PITCHER_ERA.items():
            if last in key.lower().split(): return era
    return 4.50

def pitcher_grade(era):
    if era <= 2.75: return "ACE+", "#f5a623"
    if era <= 3.20: return "ACE", "#f5a623"
    if era <= 3.60: return "A", "#52b788"
    if era <= 4.00: return "B+", "#4fc3f7"
    if era <= 4.50: return "B", "#8892a4"
    if era <= 5.00: return "C", "#ffb74d"
    return "D", "#f87171"

def get_vegas(team, vegas_lines):
    t = TEAM_ALIASES.get(team, team)
    for key in [team, t]:
        if key in vegas_lines: return vegas_lines[key]
    for full_name, abbrev in TEAM_NAME_TO_ABBREV.items():
        if abbrev == t or abbrev == team:
            if full_name in vegas_lines: return vegas_lines[full_name]
            if full_name.title() in vegas_lines: return vegas_lines[full_name.title()]
    for k, v in vegas_lines.items():
        if team.lower() in k.lower() or k.lower() in team.lower(): return v
    return {"spread": None, "total": None}

def implied_total(spread, total):
    if spread is None or total is None: return None
    return round((total / 2) - (spread / 2), 2)

def b(text, color): return f'<span class="badge b-{color}">{text}</span>'

# ══════════════════════════════════════════════════════════════════════════════
# ── SHARED API FETCHERS ───────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def fetch_vegas_lines(sport="mlb"):
    lines = {}
    try:
        try: api_key = st.secrets["odds"]["api_key"]
        except: return lines
        if not api_key: return lines
        sport_key = "baseball_mlb" if sport == "mlb" else "basketball_nba"
        resp = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
            params={"apiKey": api_key, "regions": "us", "markets": "spreads,totals", "oddsFormat": "american"},
            timeout=12
        )
        if resp.status_code == 200:
            data = resp.json()
            for game in data:
                home = game.get("home_team", ""); away = game.get("away_team", "")
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
    except: pass
    return lines

@st.cache_data(ttl=600)
def fetch_injuries(sport="mlb"):
    injuries = {}
    try:
        if sport == "mlb":
            url = "https://www.rotowire.com/baseball/tables/injury-report.php?team=ALL&pos=ALL"
        else:
            url = "https://www.rotowire.com/basketball/tables/injury-report.php?team=ALL&pos=ALL"
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
    except: pass
    return injuries

@st.cache_data(ttl=600)
def fetch_real_ownership(sport="mlb"):
    ownership = {}
    try:
        url = f"https://fantasyteamadvice.com/ownerships?sport={sport}"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200: return ownership
        from bs4 import BeautifulSoup
        import re
        soup = BeautifulSoup(resp.text, "html.parser")
        sport_path = f"/{sport}/players/"
        for link in soup.find_all("a", href=lambda h: h and sport_path in h):
            name = link.get_text(strip=True)
            if not name: continue
            parent = link.find_parent()
            if not parent: continue
            text = parent.get_text(" ", strip=True)
            pct_match = re.search(r'(\d+\.?\d*)%', text)
            if pct_match:
                pct = float(pct_match.group(1))
                ownership[name.lower()] = pct
                parts = name.lower().split()
                if parts: ownership[parts[-1]] = pct
    except: pass
    return ownership

@st.cache_data(ttl=1800)
def fetch_weather_for_game(home_team):
    if home_team in DOMED_STADIUMS: return None
    coords = STADIUM_COORDS.get(home_team)
    if not coords: return None
    lat, lon, city = coords
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&hourly=temperature_2m,windspeed_10m,winddirection_10m,weathercode"
               f"&temperature_unit=fahrenheit&windspeed_unit=mph&timezone=auto&forecast_days=1")
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200: return None
        data = resp.json()
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        winds = hourly.get("windspeed_10m", [])
        dirs  = hourly.get("winddirection_10m", [])
        codes = hourly.get("weathercode", [])
        if not times: return None
        now_str = datetime.now().strftime("%Y-%m-%dT%H:00")
        idx = 0
        for i, t in enumerate(times):
            if t >= now_str: idx = i; break
        temp = temps[idx] if temps else 72
        wind_mph = winds[idx] if winds else 0
        wind_deg = dirs[idx] if dirs else 0
        wcode = codes[idx] if codes else 0
        dirs_map = ["N","NE","E","SE","S","SW","W","NW"]
        wind_dir = dirs_map[int((wind_deg + 22.5) / 45) % 8]
        if wcode == 0: desc = "Clear"
        elif wcode <= 3: desc = "Partly cloudy"
        elif wcode <= 48: desc = "Foggy"
        elif wcode <= 67: desc = "Rain"
        elif wcode <= 77: desc = "Snow"
        elif wcode <= 82: desc = "Showers"
        elif wcode <= 99: desc = "Thunderstorm"
        else: desc = "Unknown"
        return {"temp": round(temp), "wind_speed": f"{round(wind_mph)} mph",
                "wind_dir": wind_dir, "description": desc, "city": city, "wind_deg": wind_deg}
    except: return None

def weather_impact(weather, park_name):
    if not weather: return 0, ""
    temp = weather.get("temp", 72)
    wind_str = weather.get("wind_speed", "0 mph")
    wind_dir = weather.get("wind_dir", "")
    try: wind_mph = int(wind_str.split(" ")[0])
    except: wind_mph = 0
    adj = 0; reasons = []
    if temp >= 85: adj += 4; reasons.append(f"Hot {temp}°F 🔥")
    elif temp >= 75: adj += 2
    elif temp <= 50: adj -= 4; reasons.append(f"Cold {temp}°F ❄️")
    elif temp <= 60: adj -= 2
    if wind_mph >= 15:
        if any(d in wind_dir for d in ["S","SE","SW","E","W"]): adj += 6; reasons.append(f"Wind out {wind_mph}mph 🔥")
        elif any(d in wind_dir for d in ["N","NE","NW"]): adj -= 5; reasons.append(f"Wind in {wind_mph}mph ❄️")
        else: adj += 2; reasons.append(f"Wind {wind_mph}mph")
    return adj, " · ".join(reasons)

def get_inj(name, injuries):
    nl = name.lower()
    if nl in injuries: return injuries[nl]
    for k, v in injuries.items():
        if nl in k or k in nl: return v
    return {"status": "", "note": ""}

def batting_order_score(pos):
    if pos == 0: return 0, 0, ""
    if pos == 3: return 14, 10, "3-hole 🔥"
    if pos == 4: return 16, 12, "Cleanup 🔥"
    if pos == 5: return 12, 9, "5-hole"
    if pos == 2: return 8, 6, "2-hole"
    if pos == 1: return 6, 5, "Leadoff"
    if pos == 6: return 3, 2, "6-hole"
    if pos == 7: return -3, -2, "7-hole"
    if pos == 8: return -6, -4, "8-hole"
    if pos == 9: return -8, -5, "9-hole"
    return 0, 0, ""

@st.cache_data(ttl=900)
def fetch_batting_orders():
    orders = {}
    try:
        today = date.today().strftime("%Y-%m-%d")
        resp = requests.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=lineups", timeout=12)
        if resp.status_code != 200: return orders
        data = resp.json()
        for game_date in data.get("dates", []):
            for game in game_date.get("games", []):
                lineups = game.get("lineups", {})
                for side in ["homePlayers", "awayPlayers"]:
                    for idx, player in enumerate(lineups.get(side, [])):
                        full_name = player.get("fullName", "").lower().strip()
                        last_name = full_name.split()[-1] if full_name else ""
                        pos = idx + 1
                        if full_name: orders[full_name] = pos
                        if last_name: orders[last_name] = pos
    except: pass
    return orders

@st.cache_data(ttl=1800)
def fetch_probable_pitchers():
    starters = {}
    try:
        today = date.today().strftime("%Y-%m-%d")
        resp = requests.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=probablePitcher", timeout=12)
        if resp.status_code != 200: return starters
        MLB_ID_TO_ABBREV = {
            108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",
            115:"COL",116:"DET",117:"HOU",118:"KC",119:"LAD",120:"WSH",121:"NYM",
            133:"OAK",134:"PIT",135:"SD",136:"SEA",137:"SF",138:"STL",139:"TB",
            140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CWS",146:"MIA",
            147:"NYY",158:"MIL",
        }
        for game_date in resp.json().get("dates", []):
            for game in game_date.get("games", []):
                for side in ["home", "away"]:
                    team_id = game.get(f"{side}Team", {}).get("id")
                    pitcher = game.get(f"{side}ProbablePitcher", {})
                    if not pitcher or not team_id: continue
                    abbrev = MLB_ID_TO_ABBREV.get(team_id)
                    if not abbrev: continue
                    name = pitcher.get("fullName", "")
                    starters[abbrev] = {"name": name, "era": get_pitcher_era(name)}
    except: pass
    return starters

def monte_carlo_simulate(players, sport="mlb", n_sims=1000):
    rng = np.random.default_rng(42)
    for p in players:
        proj = p.get("dk_projection", p.get("proj", 0))
        if proj <= 0:
            p["sim_floor"] = 0; p["sim_median"] = 0; p["sim_ceiling"] = 0
            p["sim_cash_score"] = 0; p["sim_gpp_score"] = 0
            continue
        if sport == "nba":
            # NBA variance model
            pos = p.get("pos", p.get("position", ""))
            if pos == "C": std = proj * 0.30  # Centers more predictable
            elif pos in ["PG", "SG"]: std = proj * 0.40  # Guards volatile
            else: std = proj * 0.35
            # High O/U = more scoring = more variance
            total = p.get("vegas_total", 220) or 220
            if total >= 230: std *= 1.15
            elif total <= 210: std *= 0.85
        else:
            # MLB variance model
            if p.get("is_pitcher", False): std = proj * 0.25
            else:
                std = proj * 0.45 * (1 + (p.get("park_factor", 1.0) - 1.0) * 0.5)
                total = p.get("vegas_total", 8.5) or 8.5
                if total >= 10: std *= 1.15
                elif total <= 7: std *= 0.85

        sims = np.maximum(rng.normal(loc=proj, scale=std, size=n_sims), 0)
        own = p.get("ownership_pct", 20) or 20
        own_factor = 1.0 - (own / 100) * 0.3

        p["sim_floor"]   = round(float(np.percentile(sims, 10)), 1)
        p["sim_median"]  = round(float(np.percentile(sims, 50)), 1)
        p["sim_ceiling"] = round(float(np.percentile(sims, 90)), 1)
        p["sim_cash_score"] = round(float(
            np.percentile(sims,10)*0.4 + np.percentile(sims,50)*0.5 + np.percentile(sims,90)*0.1), 1)
        p["sim_gpp_score"] = round(float(
            np.percentile(sims,10)*0.1 + np.percentile(sims,50)*0.3 + np.percentile(sims,90)*0.6) * own_factor, 1)
    return players

def get_game_locks(players, sport="mlb"):
    now_et = datetime.now(ET); games = {}
    team_key = "team" if sport == "mlb" else "team"
    opp_key = "opponent" if sport == "mlb" else "opp"
    time_key = "game_time_str" if sport == "mlb" else "game_time_str"
    for p in players:
        opp = p.get(opp_key, ""); team = p.get(team_key, ""); gt = p.get(time_key, "")
        if not opp or not gt: continue
        matchup = "-".join(sorted([team, opp]))
        if matchup not in games:
            try:
                gt_clean = gt.replace(" ET","").strip()
                t = datetime.strptime(gt_clean, "%I:%M%p")
                lock_dt = now_et.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
                if lock_dt < now_et: lock_dt += timedelta(days=1)
                mins = int((lock_dt - now_et).total_seconds() / 60)
                games[matchup] = {"matchup": f"{team} vs {opp}", "teams": [team, opp],
                                  "lock_time_str": gt, "minutes_until_lock": mins}
            except: pass
    return sorted(games.values(), key=lambda x: x.get("minutes_until_lock", 9999))

# ══════════════════════════════════════════════════════════════════════════════
# ── NBA CLASSIC DFS ───────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def parse_nba_csv(uploaded_file):
    """Parse RotoWire NBA CSV for DraftKings classic format."""
    try:
        df = pd.read_csv(uploaded_file)
        players = []
        for _, row in df.iterrows():
            # RotoWire columns: Name, Position, Team, Opp, Game, Salary, FPPG, Proj Own%
            name = str(row.get("Name", row.get("Player", "")) or "").strip()
            if not name: continue
            pos_raw = str(row.get("Position", row.get("Pos", "")) or "").strip().upper()
            pos = pos_raw.split("/")[0].split("-")[0]  # Take first position
            team = str(row.get("Team", row.get("TeamAbbrev", "")) or "").strip()
            opp  = str(row.get("Opp", row.get("Opponent", "")) or "").strip().lstrip("@v")
            game_info = str(row.get("Game", row.get("Game Info", "")) or "")
            salary = float(str(row.get("Salary", row.get("Sal", 0)) or "0").replace("$","").replace(",","") or 0)
            proj   = float(row.get("FPPG", row.get("Proj", row.get("FPts", 0))) or 0)
            own    = float(row.get("Proj Own%", row.get("Own%", row.get("Own", 15))) or 15)
            if isinstance(own, str): own = float(own.replace("%","") or 15)

            # Parse game time
            game_time_str = ""
            if game_info:
                parts = game_info.split()
                for part in parts:
                    if "PM" in part.upper() or "AM" in part.upper():
                        game_time_str = part.upper()
                        break

            # Validate position for DK NBA
            valid_pos = ["PG","SG","SF","PF","C"]
            if pos not in valid_pos: continue
            if salary < 3000 or proj <= 0: continue

            players.append({
                "name": name, "pos": pos, "team": team, "opp": opp,
                "salary": salary, "proj": proj, "own": own,
                "dk_projection": proj, "ownership_pct": own,
                "game_time_str": game_time_str, "game_info": game_info,
                "inj_status": "", "inj_note": "",
                "vegas_total": None, "vegas_spread": None,
                "sim_floor": 0, "sim_median": 0, "sim_ceiling": 0,
                "sim_cash_score": 0, "sim_gpp_score": 0,
                "locked": False, "excluded": False,
            })
        return players
    except Exception as e:
        st.error(f"NBA CSV parse error: {e}")
        return []

def nba_gpp_score(player, own_weight=0.6):
    """Pure GPP scoring: ceiling × (1 - ownership) with salary value bonus."""
    ceiling = player.get("sim_ceiling", player["proj"] * 1.5)
    own = (player.get("ownership_pct", 20) or 20) / 100
    own_factor = 1.0 - (own * own_weight)
    # Value bonus — players who return good value on salary
    value = player["proj"] / (player["salary"] / 1000)
    value_bonus = 1.05 if value >= 5.0 else (1.0 if value >= 4.0 else 0.95)
    return ceiling * own_factor * value_bonus

def nba_cash_score(player):
    """Cash scoring: weighted toward floor and median (consistency)."""
    return player.get("sim_cash_score", player["proj"])

def optimize_nba_lineup(players, mode="gpp", locked_names=set(), excluded_names=set(), stack_team=None):
    """
    Build optimal NBA DK lineup using greedy algorithm.
    mode: 'gpp' or 'cash'
    """
    # Filter excluded
    pool = [p for p in players
            if p["name"] not in excluded_names
            and "OUT" not in p.get("inj_status","").upper()
            and p["salary"] > 0
            and p["proj"] > 0]

    # Score each player
    for p in pool:
        p["_score"] = nba_gpp_score(p) if mode == "gpp" else nba_cash_score(p)

    # Sort by score
    pool_sorted = sorted(pool, key=lambda x: x["_score"], reverse=True)

    lineup = [None] * 8
    used_names = set()
    total_salary = 0

    # 1. Place locked players first
    for p in pool_sorted:
        if p["name"] not in locked_names: continue
        for i, slot in enumerate(NBA_ROSTER):
            if lineup[i] is None and p["pos"] in slot["positions"]:
                lineup[i] = p; used_names.add(p["name"]); total_salary += p["salary"]; break

    # 2. Stack team players if specified
    if stack_team:
        stack_pool = [p for p in pool_sorted if p["team"] == stack_team and p["name"] not in used_names]
        stack_count = 0
        for p in stack_pool:
            if stack_count >= 3: break
            for i, slot in enumerate(NBA_ROSTER):
                if lineup[i] is None and p["pos"] in slot["positions"]:
                    remaining = sum(1 for x in lineup if x is None) - 1
                    min_remaining = remaining * 3500
                    if total_salary + p["salary"] + min_remaining <= NBA_SALARY_CAP:
                        lineup[i] = p; used_names.add(p["name"])
                        total_salary += p["salary"]; stack_count += 1; break

    # 3. Fill remaining slots greedily
    for i, slot in enumerate(NBA_ROSTER):
        if lineup[i] is not None: continue
        for p in pool_sorted:
            if p["name"] in used_names: continue
            if p["pos"] not in slot["positions"]: continue
            remaining_slots = sum(1 for j, x in enumerate(lineup) if x is None and j > i)
            min_remaining = remaining_slots * 3500
            if total_salary + p["salary"] + min_remaining > NBA_SALARY_CAP: continue
            lineup[i] = p; used_names.add(p["name"]); total_salary += p["salary"]; break

    return lineup, total_salary

def auto_detect_stack_team(players, vegas_lines):
    """Find best game stack for NBA — highest total game, target both teams."""
    team_scores = {}
    for p in players:
        if "OUT" in p.get("inj_status","").upper(): continue
        team = p["team"]
        veg = get_vegas(team, vegas_lines)
        total = veg.get("total", 220) or 220
        score = p.get("sim_ceiling", p["proj"] * 1.5) + (total - 220) * 0.5
        team_scores[team] = team_scores.get(team, 0) + score
    if not team_scores: return None
    return max(team_scores, key=team_scores.get)

def render_nba_lineup(lineup, total_salary, mode="gpp"):
    """Render a built NBA lineup."""
    if not any(lineup):
        st.warning("Could not build valid lineup. Check CSV and settings.")
        return

    total_proj = sum(p["proj"] for p in lineup if p)
    total_ceil = sum(p.get("sim_ceiling", p["proj"]) for p in lineup if p)
    avg_own = sum(p.get("ownership_pct", 20) for p in lineup if p) / len([p for p in lineup if p])
    sal_pct = (total_salary / NBA_SALARY_CAP) * 100

    color = "#00d4ff" if mode == "gpp" else "#52b788"
    mode_label = "🏆 GPP Lineup" if mode == "gpp" else "💵 Cash Lineup"

    st.markdown(f"""
    <div style='background:#0d1424;border:1px solid #1e2d45;border-radius:10px;padding:1rem;margin-bottom:1rem'>
    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>
      <div style='font-family:Barlow Condensed,sans-serif;font-size:1.2rem;font-weight:700;color:{color}'>{mode_label}</div>
      <div style='display:flex;gap:16px;font-size:0.82rem;color:#8892a4'>
        <span>Salary <b style='color:#e8eaf0'>${total_salary:,}</b></span>
        <span>Proj <b style='color:#52b788'>{total_proj:.1f}</b></span>
        <span>Ceil <b style='color:{color}'>{total_ceil:.1f}</b></span>
        <span>Avg Own <b style='color:{"#f87171" if avg_own>30 else "#52b788"}'>{avg_own:.1f}%</b></span>
      </div>
    </div>
    <div class='salary-bar'><div class='salary-fill' style='width:{sal_pct:.0f}%'></div></div>
    </div>
    """, unsafe_allow_html=True)

    for i, p in enumerate(lineup):
        slot = NBA_ROSTER[i]["slot"]
        if not p:
            st.markdown(f"<div class='lineup-slot'><span class='slot-label'>{slot}</span><span style='color:#f87171'>⚠ Empty</span></div>", unsafe_allow_html=True)
            continue
        own = p.get("ownership_pct", 20) or 20
        own_color = "#f87171" if own >= 35 else ("#f5a623" if own >= 20 else "#52b788")
        ceil = p.get("sim_ceiling", p["proj"])
        floor = p.get("sim_floor", 0)
        veg_total = p.get("vegas_total", "")
        total_str = f"O/U {veg_total}" if veg_total else ""
        st.markdown(f"""
        <div class='lineup-slot'>
          <span class='slot-label'>{slot}</span>
          <div style='flex:1;margin-left:8px'>
            <span style='font-family:Barlow Condensed,sans-serif;font-weight:700;font-size:1rem'>{p['name']}</span>
            <span style='color:#8892a4;font-size:0.78rem;margin-left:6px'>{p['pos']} · {p['team']} vs {p['opp']} {total_str}</span>
          </div>
          <span style='color:#8892a4;font-size:0.8rem;margin-right:12px'>${p['salary']:,}</span>
          <span style='color:#52b788;font-weight:700;font-size:0.9rem;margin-right:8px'>{p['proj']:.1f}</span>
          <span style='font-size:0.75rem;color:{color}'>↑{ceil:.0f}</span>
          <span style='font-size:0.75rem;color:#8892a4;margin-left:4px'>↓{floor:.0f}</span>
          <span style='font-size:0.75rem;color:{own_color};margin-left:8px'>{own:.0f}%</span>
        </div>
        """, unsafe_allow_html=True)

def render_nba_player_card(p, mode="gpp"):
    own = p.get("ownership_pct", 20) or 20
    own_color = "#f87171" if own >= 35 else ("#f5a623" if own >= 20 else "#52b788")
    ceil = p.get("sim_ceiling", p["proj"] * 1.5)
    floor = p.get("sim_floor", 0)
    median = p.get("sim_median", p["proj"])
    color = "#00d4ff" if mode == "gpp" else "#52b788"
    css = "pick-nba" if mode == "gpp" else "pick-cash"
    inj = p.get("inj_status","")
    if "OUT" in inj.upper(): css = "pick-out"
    veg_total = p.get("vegas_total","")
    total_str = f"O/U {veg_total}" if veg_total else ""
    inj_badge = f"<span class='badge b-red'>OUT</span>" if "OUT" in inj.upper() else (f"<span class='badge b-yellow'>GTD</span>" if "GTD" in inj.upper() else "")
    own_badge = f"<span class='badge b-{'red' if own>=35 else ('yellow' if own>=20 else 'green')}'>{own:.0f}% OWN</span>"

    return f"""
    <div class='{css}'>
    <div style='display:flex;justify-content:space-between;align-items:flex-start'>
      <div style='flex:1'>
        <div class='pname'>{p['name']} <span style='color:#8892a4;font-size:0.8rem'>{p['pos']}</span></div>
        <div class='pmeta'>{p['team']} vs {p['opp']} · ${p['salary']:,} · Proj {p['proj']:.1f} {total_str}</div>
        <div style='margin-top:4px'>{inj_badge}{own_badge}</div>
      </div>
      <div style='text-align:center;min-width:60px;margin-left:8px'>
        <div style='font-size:0.58rem;color:#8892a4'>CEIL</div>
        <div style='font-family:Barlow Condensed,sans-serif;font-size:0.95rem;font-weight:700;color:{color}'>{ceil:.0f}</div>
        <div style='font-size:0.58rem;color:#8892a4'>MED</div>
        <div style='font-family:Barlow Condensed,sans-serif;font-size:1.1rem;font-weight:800;color:{color}'>{median:.0f}</div>
        <div style='font-size:0.58rem;color:#8892a4'>FLOR</div>
        <div style='font-family:Barlow Condensed,sans-serif;font-size:0.85rem;font-weight:700;color:#8892a4'>{floor:.0f}</div>
      </div>
    </div>
    </div>
    """

# ══════════════════════════════════════════════════════════════════════════════
# ── MLB TIERS (existing logic preserved) ─────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def parse_mlb_csv(uploaded_file):
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
            if tier is None: continue
            name = str(row.get("Name", "") or "").strip()
            if not name:
                nid = str(row.get("Name + ID", "") or "")
                name = nid.split("(")[0].strip() if "(" in nid else nid.strip()
            team      = str(row.get("TeamAbbrev", "") or "").strip()
            avg_pts   = float(row.get("AvgPointsPerGame", 0) or 0)
            game_info = str(row.get("Game Info", "") or "")
            salary    = float(str(row.get("Salary", 0) or "0").replace("$","").replace(",","") or 0)
            opponent = ""; game_time_str = ""; is_home = False
            if "@" in game_info:
                parts = game_info.split(" ")
                matchup = parts[0] if parts else ""
                teams = matchup.split("@")
                if len(teams) == 2:
                    away_t, home_t = teams[0].strip(), teams[1].strip()
                    opponent = home_t if team == away_t else away_t
                    is_home = team == home_t
                try:
                    game_time_str = " ".join(parts[1:3]) if len(parts) >= 3 else ""
                    game_time_str = game_time_str.replace(" ET","").strip()
                except: pass
            home_team = team if is_home else opponent
            players.append({
                "name": name, "team": team, "position": position, "tier": tier,
                "dk_projection": avg_pts, "salary": salary, "opponent": opponent,
                "home_team": home_team, "game_time_str": game_time_str, "is_home": is_home,
                "inj_status": "", "inj_note": "", "vegas_spread": None, "vegas_total": None,
                "opp_pitcher": "", "opp_pitcher_era": 4.50, "park_factor": 1.0, "park_name": "",
                "ownership_pct": None, "ownership_proxy": 0.5, "cash_score": 0, "gpp_score": 0,
                "cash_reasons": [], "gpp_reasons": [], "spike_boost": 0, "spike_reason": "",
                "is_pitcher": position == "P", "stack_team": "", "batting_order": 0,
            })
        return players
    except Exception as e:
        st.error(f"CSV parse error: {e}")
        return []

def assign_opp_pitchers(players, probable_pitchers={}):
    pitcher_map = {}
    for p in players:
        if p["is_pitcher"]:
            era = get_pitcher_era(p["name"])
            team = p["team"]; team_resolved = TEAM_ALIASES.get(team, team)
            pitcher_map[team] = {"name": p["name"], "era": era}
            pitcher_map[team_resolved] = {"name": p["name"], "era": era}
    for abbrev, data in probable_pitchers.items():
        if abbrev not in pitcher_map: pitcher_map[abbrev] = data
    for p in players:
        if not p["is_pitcher"]:
            opp = p["opponent"]; opp_resolved = TEAM_ALIASES.get(opp, opp)
            found = pitcher_map.get(opp) or pitcher_map.get(opp_resolved)
            if found: p["opp_pitcher"] = found["name"]; p["opp_pitcher_era"] = found["era"]
            else: p["opp_pitcher"] = ""; p["opp_pitcher_era"] = 4.50
    return players

def assign_batting_orders_to_players(players, batting_orders):
    for p in players:
        if p["is_pitcher"]: p["batting_order"] = 0; continue
        name_lower = p["name"].lower().strip()
        last_name = name_lower.split()[-1] if name_lower else ""
        p["batting_order"] = batting_orders.get(name_lower) or batting_orders.get(last_name) or 0
    return players

def estimate_ownership(players):
    for tier_num in range(1, 7):
        tier_ps = [p for p in players if p["tier"] == tier_num and "OUT" not in p.get("inj_status","").upper()]
        if not tier_ps: continue
        tier_ps.sort(key=lambda x: x["dk_projection"], reverse=True)
        base_owns = [45, 28, 15, 7, 3, 2]
        for idx, p in enumerate(tier_ps):
            base = base_owns[idx] if idx < len(base_owns) else 1
            if not p["is_pitcher"]:
                if p.get("park_factor",1.0) >= 1.10: base += 5
                if p.get("opp_pitcher_era",4.50) >= 4.5: base += 5
            p["ownership_pct"] = min(max(base, 1), 70)
    return players

def score_mlb_players(players, injuries, vegas_lines, manual_out=set(), manual_gtd=set(), weather_cache={}):
    for tier_num in range(1, 7):
        tier_ps = [p for p in players if p["tier"] == tier_num]
        if not tier_ps: continue
        max_proj = max(p["dk_projection"] for p in tier_ps) or 1
        for p in tier_ps: p["ownership_proxy"] = p["dk_projection"] / max_proj

    for p in players:
        if p["name"] in manual_out: p["inj_status"] = "OUT"; p["inj_note"] = "Manually marked OUT"
        elif p["name"] in manual_gtd: p["inj_status"] = "GTD"; p["inj_note"] = "Manually marked GTD"
        else:
            inj = get_inj(p["name"], injuries)
            p["inj_status"] = inj.get("status",""); p["inj_note"] = inj.get("note","")

        veg = get_vegas(p["team"], vegas_lines)
        p["vegas_spread"] = veg.get("spread"); p["vegas_total"] = veg.get("total")
        park = get_park(p["home_team"])
        p["park_factor"] = park["factor"]; p["park_name"] = park["name"]
        weather = weather_cache.get(p.get("home_team",""))
        w_adj, w_reason = weather_impact(weather, p["park_name"])
        p["weather"] = weather; p["weather_adj"] = w_adj; p["weather_reason"] = w_reason

        status = p["inj_status"].upper()
        if "OUT" in status:
            p["cash_score"] = 0; p["gpp_score"] = 0
            p["cash_reasons"] = ["OUT — do not play"]; p["gpp_reasons"] = ["OUT — do not play"]
            continue

        proj = p["dk_projection"]; spread = p["vegas_spread"]; total = p["vegas_total"]
        pf = p["park_factor"]; own = p["ownership_proxy"]; is_p = p["is_pitcher"]
        cash = 50.0; gpp = 50.0; cr = []; gr = []

        if "GTD" in status or "QUESTIONABLE" in status:
            cash -= 20; gpp -= 8; cr.append("GTD — risky for cash")

        if is_p:
            era = get_pitcher_era(p["name"]); p["opp_pitcher_era"] = era
            if era <= 2.75: cash += 30; gpp += 25; cr.append(f"Ace+ ERA {era:.2f}")
            elif era <= 3.20: cash += 25; gpp += 20; cr.append(f"Ace ERA {era:.2f}")
            elif era <= 3.60: cash += 18; gpp += 15; cr.append(f"Elite SP ERA {era:.2f}")
            elif era <= 4.00: cash += 10; gpp += 8; cr.append(f"Good SP ERA {era:.2f}")
            elif era >= 6.00: cash -= 20; gpp -= 15; cr.append(f"Struggling SP ERA {era:.2f}")
            elif era >= 5.00: cash -= 15; gpp -= 10; cr.append(f"Weak SP ERA {era:.2f}")
            elif era >= 4.50: cash -= 8; gpp -= 5; cr.append(f"Below avg SP ERA {era:.2f}")
            if pf <= 0.95: cash += 8; gpp += 6; cr.append("Pitcher's park ✅")
            elif pf >= 1.10: cash -= 10; gpp -= 8; cr.append("Hitter's park ⚠️")
            if total:
                if total <= 7.5: cash += 10; gpp += 8; cr.append(f"Low O/U {total}")
                elif total >= 10: cash -= 12; gpp -= 8; cr.append(f"High O/U {total}")
            cash += min(proj * 0.8, 20); gpp += min(proj * 0.6, 15)
        else:
            opp_era = p.get("opp_pitcher_era", 4.50)
            if opp_era >= 6.00: cash += 25; gpp += 20; cr.append(f"Struggling opp SP {opp_era:.2f} 🔥")
            elif opp_era >= 5.00: cash += 18; gpp += 15; cr.append(f"Weak opp SP {opp_era:.2f}")
            elif opp_era >= 4.50: cash += 12; gpp += 10; cr.append(f"Below avg SP {opp_era:.2f}")
            elif opp_era >= 4.00: cash += 6; gpp += 5
            elif opp_era <= 2.75: cash -= 20; gpp -= 15; cr.append(f"Facing ace+ {opp_era:.2f} ⚠️")
            elif opp_era <= 3.20: cash -= 15; gpp -= 10; cr.append(f"Facing ace {opp_era:.2f}")
            elif opp_era <= 3.60: cash -= 8; gpp -= 5; cr.append(f"Tough SP {opp_era:.2f}")
            if pf >= 1.15: cash += 12; gpp += 10; cr.append("Extreme hitter's park 🔥")
            elif pf >= 1.05: cash += 7; gpp += 6; cr.append(f"Hitter's park")
            elif pf <= 0.95: cash -= 8; gpp -= 5; cr.append("Pitcher's park")
            if total:
                if total >= 10: cash += 10; gpp += 8; cr.append(f"High O/U {total}")
                elif total >= 9: cash += 6; gpp += 5
                elif total <= 7: cash -= 8; gpp -= 5; cr.append(f"Low O/U {total}")
            if spread is not None:
                if spread <= -1.5: cash += 6; gpp += 3; cr.append("Team favored")
                elif spread >= 1.5: cash -= 5; gpp -= 3; cr.append("Team underdog")
            proj_bonus = min((proj - 5) * 1.2, 25)
            cash += proj_bonus; gpp += proj_bonus * 0.7
            w_adj = p.get("weather_adj", 0)
            if w_adj != 0 and p.get("home_team","") not in DOMED_STADIUMS:
                cash += w_adj; gpp += w_adj * 0.8
                if p.get("weather_reason",""): cr.append(p["weather_reason"])
            tier_ps_floor = [x for x in players if x["tier"] == p["tier"] and not x["is_pitcher"]]
            tier_projs = sorted([x["dk_projection"] for x in tier_ps_floor], reverse=True)
            proj_floor = tier_projs[int(len(tier_projs)*0.50)] if tier_projs else 0
            above_floor = proj >= proj_floor
            is_chalk_top = bool(tier_projs and proj >= tier_projs[0] * 0.98)
            if own < 0.4:
                if above_floor and not is_chalk_top: gpp += 18; gr.append("Low own + upside 🎯")
                elif above_floor: gpp += 6; gr.append("Top proj low own")
                else: gpp -= 10; gr.append("Low own weak proj — trap")
            elif own < 0.6:
                if above_floor and not is_chalk_top: gpp += 10
                elif above_floor: gpp += 4
                else: gpp -= 3
            else:
                if is_chalk_top: gpp -= 12; gr.append("Chalk #1 — fade in GPP")
                else: gpp -= 6; gr.append("High chalk")
            bat_pos = p.get("batting_order", 0)
            bo_cash, bo_gpp, bo_label = batting_order_score(bat_pos)
            if bo_cash != 0:
                cash += bo_cash; gpp += bo_gpp
                if bo_label: cr.append(f"Bats {bat_pos} ({bo_label})")

        p["cash_score"] = max(round(cash, 1), 0)
        p["gpp_score"]  = max(round(gpp, 1), 0)
        p["cash_reasons"] = cr[:3]; p["gpp_reasons"] = (gr + cr)[:3]
    return players

def mlb_badges(p):
    html = ""
    status = p.get("inj_status","").upper()
    if "OUT" in status: html += b("OUT","red")
    elif "GTD" in status or "QUESTIONABLE" in status: html += b("GTD","yellow")
    pf = p.get("park_factor",1.0)
    if pf >= 1.10: html += b("HITTER'S PARK","orange")
    elif pf <= 0.95: html += b("PITCHER'S PARK","teal")
    total = p.get("vegas_total")
    if total:
        if total >= 10: html += b(f"O/U {total}","blue")
        elif total <= 7: html += b(f"O/U {total}","teal")
        else: html += b(f"O/U {total}","purple")
    if p.get("is_pitcher"):
        era = get_pitcher_era(p["name"]); grade, _ = pitcher_grade(era)
        html += b(f"ERA {era:.2f} {grade}","orange")
    else:
        opp_era = p.get("opp_pitcher_era",4.50)
        if opp_era >= 4.50: html += b(f"OPP ERA {opp_era:.2f}","green")
        elif opp_era <= 3.20: html += b(f"OPP ERA {opp_era:.2f}","red")
        elif opp_era <= 3.60: html += b(f"OPP ERA {opp_era:.2f}","yellow")
    own = p.get("ownership_pct")
    if own:
        color = "red" if own >= 35 else ("yellow" if own >= 20 else "green")
        html += b(f"~{own:.0f}% OWN",color)
    bat_pos = p.get("batting_order",0)
    if bat_pos > 0 and not p.get("is_pitcher"):
        _, _, bo_label = batting_order_score(bat_pos)
        bc = "blue" if bat_pos <= 2 else ("green" if bat_pos <= 5 else ("purple" if bat_pos <= 6 else "teal"))
        html += b(f"BAT {bat_pos} {bo_label if bo_label else ''}",bc)
    return html

def make_mlb_card(p, mode="cash"):
    proj = p["dk_projection"]; spread = p.get("vegas_spread"); total = p.get("vegas_total")
    vegas_str = ""
    if spread is not None: vegas_str = f"Run line {spread:+.1f}"
    if total: vegas_str += f" · O/U {total}"
    reasons = p.get("cash_reasons" if mode=="cash" else "gpp_reasons",[])
    reasons_html = "".join(f"<div class='preason'>• {r}</div>" for r in reasons[:3])
    b_html = mlb_badges(p)
    opp_p = p.get("opp_pitcher","")
    opp_line = f"vs {opp_p}" if opp_p and not p["is_pitcher"] else ""
    sal = p.get("salary",0); sal_str = f"${sal:,.0f}" if sal else ""
    weather = p.get("weather")
    weather_str = ""
    if weather and p.get("home_team","") not in DOMED_STADIUMS:
        temp = weather.get("temp",""); wind = weather.get("wind_speed","")
        wdir = weather.get("wind_dir",""); desc = weather.get("description","")
        weather_str = f"{temp}°F · {wind} {wdir} · {desc}" if temp else ""
    if p["is_pitcher"]: css="pick-pitcher"; sc_col="#f5a623"
    elif mode=="cash": css="pick-cash"; sc_col="#52b788"
    else: css="pick-gpp"; sc_col="#ce93d8"
    if "OUT" in p.get("inj_status","").upper(): css="pick-out"
    floor=p.get("sim_floor",0); median=p.get("sim_median",0); ceiling=p.get("sim_ceiling",0)
    has_mc = floor > 0 or ceiling > 0
    score_html = (
        f"<div style='text-align:center;min-width:60px;margin-left:8px'>"
        f"<div style='font-size:0.58rem;color:#8892a4'>CEIL</div>"
        f"<div style='font-family:Barlow Condensed,sans-serif;font-size:0.95rem;font-weight:700;color:{sc_col}'>{ceiling:.0f}</div>"
        f"<div style='font-size:0.58rem;color:#8892a4'>MED</div>"
        f"<div style='font-family:Barlow Condensed,sans-serif;font-size:1.1rem;font-weight:800;color:{sc_col}'>{median:.0f}</div>"
        f"<div style='font-size:0.58rem;color:#8892a4'>FLOR</div>"
        f"<div style='font-family:Barlow Condensed,sans-serif;font-size:0.85rem;font-weight:700;color:#8892a4'>{floor:.0f}</div>"
        f"</div>"
    ) if has_mc else f"<div style='min-width:48px;margin-left:8px'></div>"
    bat_pos = p.get("batting_order",0)
    bat_html = f'<span style="color:#f5a623;font-size:0.9rem;margin-right:4px">#{bat_pos}</span>' if bat_pos > 0 and not p["is_pitcher"] else ""
    return (
        f"<div class='{css}'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
        f"<div style='flex:1'>"
        f"<div class='pname'>{bat_html}{p['name']} <span style='color:#8892a4;font-size:0.8rem'>{p['position']}</span></div>"
        f"<div class='pmeta'>{p['team']} vs {p['opponent']} {opp_line} · Proj: {proj:.1f} {sal_str}</div>"
        f"<div class='pmeta'>{vegas_str} · {p.get('park_name','')}</div>"
        f"{'<div class=\"pmeta\">🌤 ' + weather_str + '</div>' if weather_str else ''}"
        f"<div style='margin-top:5px'>{b_html}</div>"
        f"{reasons_html}"
        f"</div>{score_html}</div></div>"
    )

def save_mlb_slate(players):
    if not supabase: return False
    try:
        today = date.today().isoformat()
        supabase.table("dfs_slate").delete().eq("slate_date", today).execute()
        records = [{"slate_date":today,"name":p["name"],"team":p["team"],"position":p["position"],
                    "tier":p["tier"],"dk_projection":p["dk_projection"],"opponent":p["opponent"],
                    "game_time_str":p.get("game_time_str","")} for p in players]
        for i in range(0, len(records), 10):
            supabase.table("dfs_slate").insert(records[i:i+10]).execute()
        return True
    except: return False

def load_mlb_slate():
    if not supabase: return []
    try:
        today = date.today().isoformat()
        resp = supabase.table("dfs_slate").select("*").eq("slate_date", today).execute()
        if not resp.data: return []
        players = []
        for row in resp.data:
            pos = row.get("position",""); opp = row.get("opponent",""); team = row.get("team","")
            players.append({
                "name":row["name"],"team":team,"position":pos,"tier":row["tier"],
                "dk_projection":float(row.get("dk_projection",0) or 0),"salary":0,
                "opponent":opp,"home_team":opp,"game_time_str":row.get("game_time_str",""),
                "is_home":False,"inj_status":"","inj_note":"","vegas_spread":None,"vegas_total":None,
                "opp_pitcher":"","opp_pitcher_era":4.50,"park_factor":1.0,"park_name":"",
                "ownership_pct":None,"ownership_proxy":0.5,"cash_score":0,"gpp_score":0,
                "cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"",
                "is_pitcher":pos=="P","stack_team":"","batting_order":0,
            })
        return players
    except: return []

# ══════════════════════════════════════════════════════════════════════════════
# ── SESSION STATE ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
if "sport_mode" not in st.session_state: st.session_state.sport_mode = "🏀 NBA Classic"
if "nba_players" not in st.session_state: st.session_state.nba_players = []
if "nba_locked" not in st.session_state: st.session_state.nba_locked = set()
if "nba_excluded" not in st.session_state: st.session_state.nba_excluded = set()
if "nba_lineup_gpp" not in st.session_state: st.session_state.nba_lineup_gpp = []
if "nba_lineup_cash" not in st.session_state: st.session_state.nba_lineup_cash = []
if "mlb_players" not in st.session_state: st.session_state.mlb_players = []
if "manual_out" not in st.session_state: st.session_state.manual_out = set()
if "manual_gtd" not in st.session_state: st.session_state.manual_gtd = set()
if "picks_cash" not in st.session_state: st.session_state.picks_cash = {}
if "picks_gpp" not in st.session_state: st.session_state.picks_gpp = {}

# ── Sidebar ───────────────────────────────────────────────────────────────────
now_et = datetime.now(ET)
with st.sidebar:
    st.markdown("### 🏆 MPH DFS Optimizer")
    sport_mode = st.radio("Sport", ["🏀 NBA Classic", "⚾ MLB Tiers"], index=0)
    st.session_state.sport_mode = sport_mode
    st.markdown("---")

    try: odds_key = st.secrets["odds"]["api_key"]
    except: odds_key = ""

    st.markdown("### 🔑 API Status")
    st.markdown(f"**Odds API:** {'✅' if odds_key else '⚠️ No key'}")
    st.markdown(f"**Injury Feed:** ✅ Rotowire")
    st.markdown(f"**Weather:** ✅ Open-Meteo")
    st.markdown(f"**Ownership:** ✅ FTA Projections")
    if sport_mode == "⚾ MLB Tiers":
        st.markdown(f"**Batting Orders:** ✅ MLB Stats API")
    st.markdown(f"**Supabase:** {'✅' if supabase else '❌'}")
    st.markdown("---")

    if sport_mode == "🏀 NBA Classic":
        st.markdown("### ⚙️ NBA Settings")
        nba_stack_auto = st.toggle("Auto-detect stack game", value=True)
        nba_stack_team = ""
        if not nba_stack_auto and st.session_state.nba_players:
            teams = sorted(set(p["team"] for p in st.session_state.nba_players))
            nba_stack_team = st.selectbox("Force stack team", ["Auto"] + teams)
            if nba_stack_team == "Auto": nba_stack_team = ""
        st.markdown("---")
        st.markdown("### 🔒 Locked Players")
        if st.session_state.nba_locked:
            for name in list(st.session_state.nba_locked):
                if st.button(f"🔓 {name}", key=f"unlock_{name}"):
                    st.session_state.nba_locked.discard(name); st.rerun()
        else:
            st.caption("No locked players")
        st.markdown("### 🚫 Excluded Players")
        if st.session_state.nba_excluded:
            for name in list(st.session_state.nba_excluded):
                if st.button(f"↩ {name}", key=f"include_{name}"):
                    st.session_state.nba_excluded.discard(name); st.rerun()
        else:
            st.caption("No excluded players")
    else:
        st.markdown("### ⚙️ MLB Options")
        show_all = st.toggle("Show All Players Per Tier", value=False)

# ══════════════════════════════════════════════════════════════════════════════
# ── HEADER ────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
if sport_mode == "🏀 NBA Classic":
    st.markdown(f"""
    <div class="hdr">
      <h1>🏀 NBA Classic DFS Optimizer</h1>
      <div class="sub">NBA Playoffs · DraftKings Classic · {now_et.strftime('%A %b %d, %Y')} · {now_et.strftime('%I:%M %p ET')} · Single Entry GPP</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class="hdr hdr-mlb">
      <h1>⚾ MLB Tier Optimizer</h1>
      <div class="sub">MLB · DraftKings Tiers · {now_et.strftime('%A %b %d, %Y')} · {now_et.strftime('%I:%M %p ET')}</div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── NBA CLASSIC MODE ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
if sport_mode == "🏀 NBA Classic":
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Optimizer", "👥 Player Pool", "🏆 My Lineups", "🔄 Late Swap"])

    with tab1:
        # CSV Upload
        if not st.session_state.nba_players:
            st.markdown("""
            <div style="background:#0a1a2a;border:1px solid #00d4ff;border-radius:8px;padding:0.8rem 1rem;margin-bottom:1rem">
            <b style="color:#00d4ff">📂 How to get your RotoWire NBA CSV</b><br>
            <span style="color:#8892a4;font-size:0.82rem">
            RotoWire → DFS → NBA → DraftKings → Export CSV → save to OneDrive
            </span>
            </div>
            """, unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload RotoWire NBA CSV", type=["csv"], label_visibility="collapsed")
            if uploaded:
                players = parse_nba_csv(uploaded)
                if players:
                    st.session_state.nba_players = players
                    st.success(f"✅ {len(players)} players loaded")
                    st.rerun()
                else:
                    st.error("❌ Could not parse CSV. Check format.")
            else:
                st.info("👆 Upload your RotoWire NBA CSV to get started.")
                st.stop()
        else:
            col_reload, col_info = st.columns([1, 3])
            with col_reload:
                if st.button("📂 New CSV"):
                    st.session_state.nba_players = []
                    st.session_state.nba_lineup_gpp = []
                    st.session_state.nba_lineup_cash = []
                    st.rerun()
            with col_info:
                st.success(f"✅ {len(st.session_state.nba_players)} players loaded · {len(st.session_state.nba_locked)} locked · {len(st.session_state.nba_excluded)} excluded")

        nba_players = st.session_state.nba_players
        if not nba_players: st.stop()

        # Load all data
        with st.spinner("Loading injuries, Vegas lines, ownership, simulating..."):
            vegas_lines = fetch_vegas_lines("nba")
            injuries    = fetch_injuries("nba")
            ownership   = fetch_real_ownership("nba")

            # Apply injuries, Vegas, ownership to players
            for p in nba_players:
                inj = get_inj(p["name"], injuries)
                if p["name"] not in st.session_state.nba_locked:
                    p["inj_status"] = inj.get("status",""); p["inj_note"] = inj.get("note","")
                # Vegas
                veg = get_vegas(p["team"], vegas_lines)
                p["vegas_total"] = veg.get("total"); p["vegas_spread"] = veg.get("spread")
                # Real ownership
                name_lower = p["name"].lower()
                last = name_lower.split()[-1]
                real_own = ownership.get(name_lower) or ownership.get(last)
                if real_own is not None: p["ownership_pct"] = real_own

            # Monte Carlo
            nba_players = monte_carlo_simulate(nba_players, sport="nba")

            # Auto stack
            if nba_stack_auto or not nba_stack_team:
                stack_team = auto_detect_stack_team(nba_players, vegas_lines)
            else:
                stack_team = nba_stack_team if nba_stack_team else None

        # Metrics
        out_count = sum(1 for p in nba_players if "OUT" in p.get("inj_status","").upper())
        gtd_count = sum(1 for p in nba_players if "GTD" in p.get("inj_status","").upper())
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.markdown(f'<div class="metric-card"><div class="metric-val metric-val-nba">{len(nba_players)}</div><div class="metric-lbl">Players</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f87171">{out_count}</div><div class="metric-lbl">Out</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f5a623">{gtd_count}</div><div class="metric-lbl">GTD</div></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="metric-card"><div class="metric-val metric-val-nba">{stack_team or "Auto"}</div><div class="metric-lbl">Stack Team</div></div>', unsafe_allow_html=True)

        # Game locks
        game_locks = get_game_locks(nba_players, "nba")
        if game_locks:
            st.markdown("**⏱ Game Locks**")
            for gl in game_locks:
                mins = gl["minutes_until_lock"]
                if mins < 0: icon="🔒"; color="#8892a4"; txt="LOCKED"
                elif mins <= 15: icon="🔴"; color="#f87171"; txt=f"LOCKS IN {mins}m"
                elif mins <= 45: icon="🟡"; color="#f5a623"; txt=f"Locks in {mins}m"
                else:
                    h,m = divmod(mins,60); txt=f"Locks in {h}h {m}m" if h else f"Locks in {m}m"
                    icon="🟢"; color="#52b788"
                st.markdown(f'<div class="lock-bar"><span style="color:#e8eaf0;font-size:0.85rem">{gl["matchup"]}</span><span style="color:{color};font-weight:700">{icon} {txt}</span></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Generate lineups button
        col_g, col_c = st.columns(2)
        with col_g:
            if st.button("⚡ Generate GPP Lineup", use_container_width=True):
                lineup, sal = optimize_nba_lineup(
                    nba_players, mode="gpp",
                    locked_names=st.session_state.nba_locked,
                    excluded_names=st.session_state.nba_excluded,
                    stack_team=stack_team
                )
                st.session_state.nba_lineup_gpp = lineup
                st.session_state.nba_lineup_cash_sal = sal
        with col_c:
            if st.button("💵 Generate Cash Lineup", use_container_width=True):
                lineup, sal = optimize_nba_lineup(
                    nba_players, mode="cash",
                    locked_names=st.session_state.nba_locked,
                    excluded_names=st.session_state.nba_excluded,
                    stack_team=None
                )
                st.session_state.nba_lineup_cash = lineup
                st.session_state.nba_lineup_cash_sal2 = sal

        # Show built lineups
        if st.session_state.nba_lineup_gpp:
            render_nba_lineup(st.session_state.nba_lineup_gpp,
                              getattr(st.session_state, "nba_lineup_cash_sal", 50000), "gpp")
        if st.session_state.nba_lineup_cash:
            render_nba_lineup(st.session_state.nba_lineup_cash,
                              getattr(st.session_state, "nba_lineup_cash_sal2", 50000), "cash")

        # Top picks by position
        st.markdown("---")
        st.markdown("### 🎯 Top GPP Plays by Position")
        positions = ["PG","SG","SF","PF","C"]
        for pos in positions:
            pos_players = [p for p in nba_players
                          if p["pos"] == pos
                          and "OUT" not in p.get("inj_status","").upper()
                          and p["name"] not in st.session_state.nba_excluded]
            if not pos_players: continue
            pos_sorted = sorted(pos_players, key=lambda x: nba_gpp_score(x), reverse=True)
            with st.expander(f"{pos} — Top Plays", expanded=False):
                st.markdown(f"<div class='lbl-nba'>🏆 GPP</div>", unsafe_allow_html=True)
                for p in pos_sorted[:3]:
                    st.markdown(render_nba_player_card(p, "gpp"), unsafe_allow_html=True)
                cash_sorted = sorted(pos_players, key=lambda x: nba_cash_score(x), reverse=True)
                st.markdown(f"<div class='lbl-cash'>💵 CASH</div>", unsafe_allow_html=True)
                for p in cash_sorted[:2]:
                    st.markdown(render_nba_player_card(p, "cash"), unsafe_allow_html=True)

    with tab2:
        st.markdown("### 👥 Player Pool")
        if not st.session_state.nba_players:
            st.info("Upload CSV first.")
        else:
            search = st.text_input("Search player or team...", "")
            pos_filter = st.multiselect("Filter position", ["PG","SG","SF","PF","C"], default=[])
            filtered = [p for p in st.session_state.nba_players
                       if (search.lower() in p["name"].lower() or search.lower() in p["team"].lower())
                       and (not pos_filter or p["pos"] in pos_filter)]
            filtered.sort(key=lambda x: x["proj"], reverse=True)

            rows = []
            for p in filtered[:100]:
                rows.append({
                    "Player": p["name"],
                    "Pos": p["pos"],
                    "Team": p["team"],
                    "vs": p["opp"],
                    "Salary": f"${p['salary']:,}",
                    "Proj": p["proj"],
                    "Floor": p.get("sim_floor",0),
                    "Median": p.get("sim_median",0),
                    "Ceiling": p.get("sim_ceiling",0),
                    "Own%": p.get("ownership_pct",0),
                    "O/U": p.get("vegas_total",""),
                    "Status": p.get("inj_status",""),
                    "Lock": "🔒" if p["name"] in st.session_state.nba_locked else "",
                    "Out": "🚫" if p["name"] in st.session_state.nba_excluded else "",
                })
            df_display = pd.DataFrame(rows)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            st.markdown("---")
            col_lock, col_excl = st.columns(2)
            with col_lock:
                st.markdown("**Lock a player:**")
                all_names = [p["name"] for p in st.session_state.nba_players]
                lock_name = st.selectbox("Select to lock", [""] + all_names, key="lock_select")
                if lock_name and st.button("🔒 Lock"):
                    st.session_state.nba_locked.add(lock_name)
                    st.session_state.nba_excluded.discard(lock_name)
                    st.rerun()
            with col_excl:
                st.markdown("**Exclude a player:**")
                excl_name = st.selectbox("Select to exclude", [""] + all_names, key="excl_select")
                if excl_name and st.button("🚫 Exclude"):
                    st.session_state.nba_excluded.add(excl_name)
                    st.session_state.nba_locked.discard(excl_name)
                    st.rerun()

    with tab3:
        st.markdown("### 🏆 My Lineups")
        if st.session_state.nba_lineup_gpp:
            render_nba_lineup(st.session_state.nba_lineup_gpp,
                              getattr(st.session_state,"nba_lineup_cash_sal",50000), "gpp")
            # Export
            if all(st.session_state.nba_lineup_gpp):
                names = [p["name"] for p in st.session_state.nba_lineup_gpp if p]
                st.code(", ".join(names), language=None)
        else:
            st.info("Generate a lineup in the Optimizer tab.")
        if st.session_state.nba_lineup_cash:
            render_nba_lineup(st.session_state.nba_lineup_cash,
                              getattr(st.session_state,"nba_lineup_cash_sal2",50000), "cash")

    with tab4:
        st.markdown("### 🔄 Late Swap — Injury Monitor")
        if not st.session_state.nba_players:
            st.info("Upload CSV first.")
        else:
            injuries_nba = fetch_injuries("nba")
            injured = [(p["name"], get_inj(p["name"], injuries_nba))
                      for p in st.session_state.nba_players
                      if get_inj(p["name"], injuries_nba).get("status","")]
            if injured:
                st.markdown("**⚠️ Injury Report:**")
                for name, inj in injured:
                    status = inj.get("status",""); note = inj.get("note","")
                    color = "#f87171" if "OUT" in status.upper() else "#f5a623"
                    st.markdown(f'<div style="background:#1a0a0a;border-left:3px solid {color};border-radius:6px;padding:0.5rem 0.8rem;margin-bottom:0.3rem"><b style="color:{color}">{name}</b> — {status} · {note}</div>', unsafe_allow_html=True)
            else:
                st.success("✅ No injury concerns found")

            # Lineup alerts
            if st.session_state.nba_lineup_gpp:
                st.markdown("---")
                st.markdown("**GPP Lineup Status:**")
                for p in st.session_state.nba_lineup_gpp:
                    if not p: continue
                    inj = get_inj(p["name"], injuries_nba)
                    status = inj.get("status","")
                    if "OUT" in status.upper():
                        st.markdown(f'<div style="background:#2a0a0a;border:1px solid #f87171;border-radius:6px;padding:0.5rem 0.8rem;margin-bottom:0.3rem;color:#f87171">🔴 <b>{p["name"]}</b> — OUT · Swap needed</div>', unsafe_allow_html=True)
                    elif status:
                        st.markdown(f'<div style="background:#2a1a00;border:1px solid #f5a623;border-radius:6px;padding:0.5rem 0.8rem;margin-bottom:0.3rem;color:#f5a623">🟡 <b>{p["name"]}</b> — {status} · Monitor</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── MLB TIERS MODE ────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["⚾ Today's Slate", "🏟️ Game Environment", "🎯 Best Bets", "🔄 Late Swap", "📋 My Lineup"])

    # Load slate
    mlb_players = []
    with tab1:
        if not st.session_state.mlb_players:
            saved = load_mlb_slate()
            if saved: st.session_state.mlb_players = saved
        if st.session_state.mlb_players:
            mlb_players = st.session_state.mlb_players
            st.success(f"✅ {len(mlb_players)} players loaded for {date.today().strftime('%B %d')} — slate persisted")
            if st.button("📂 Upload New CSV", type="primary"):
                st.session_state.mlb_players = []
                if supabase:
                    try: supabase.table("dfs_slate").delete().eq("slate_date", date.today().isoformat()).execute()
                    except: pass
                st.rerun()
        else:
            st.markdown("""
            <div style="background:#1a2e1a;border:1px solid #52b788;border-radius:8px;padding:0.8rem 1rem;margin-bottom:1rem">
            <b style="color:#52b788">📂 How to get your DK MLB CSV</b><br>
            <span style="color:#8892a4;font-size:0.82rem">
            DraftKings → MLB → Tiers → any contest → Draft Team → scroll bottom → Export to CSV → save to OneDrive
            </span>
            </div>
            """, unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload DK MLB Tier CSV", type=["csv"], label_visibility="collapsed")
            if uploaded:
                mlb_players = parse_mlb_csv(uploaded)
                if mlb_players:
                    st.session_state.mlb_players = mlb_players
                    saved_ok = save_mlb_slate(mlb_players)
                    st.success(f"✅ {len(mlb_players)} players loaded{' · Saved ☁️' if saved_ok else ''}")
                else:
                    st.error("❌ Could not parse CSV.")
            else:
                st.info("👆 Upload your DK MLB CSV to load today's slate.")

    if not st.session_state.mlb_players:
        st.stop()

    mlb_players = st.session_state.mlb_players

    # Score MLB players
    with st.spinner("Loading injuries, Vegas lines, weather, scoring..."):
        injuries_mlb    = fetch_injuries("mlb")
        vegas_lines_mlb = fetch_vegas_lines("mlb")
        batting_orders  = fetch_batting_orders()
        probable_pitchers = fetch_probable_pitchers()
        real_own_mlb    = fetch_real_ownership("mlb")
        weather_cache   = {}
        for p in mlb_players:
            ht = p.get("home_team","")
            if ht and ht not in weather_cache:
                weather_cache[ht] = fetch_weather_for_game(ht)
        mlb_players = assign_opp_pitchers(mlb_players, probable_pitchers)
        mlb_players = assign_batting_orders_to_players(mlb_players, batting_orders)
        for p in mlb_players:
            name_lower = p["name"].lower(); last = name_lower.split()[-1]
            own_pct = real_own_mlb.get(name_lower) or real_own_mlb.get(last)
            if own_pct is not None: p["ownership_pct"] = own_pct
        mlb_players = score_mlb_players(mlb_players, injuries_mlb, vegas_lines_mlb,
                                        st.session_state.manual_out, st.session_state.manual_gtd,
                                        weather_cache)
        mlb_players = monte_carlo_simulate(mlb_players, sport="mlb")
        mlb_players = estimate_ownership(mlb_players)
        for p in mlb_players:
            name_lower = p["name"].lower(); last = name_lower.split()[-1]
            own_pct = real_own_mlb.get(name_lower) or real_own_mlb.get(last)
            if own_pct is not None: p["ownership_pct"] = own_pct
        game_locks = get_game_locks(mlb_players, "mlb")

    TIER_LABELS = {1:"Tier 1 — Elite",2:"Tier 2 — Star",3:"Tier 3 — Premium",
                   4:"Tier 4 — Mid",5:"Tier 5 — Value",6:"Tier 6 — Dart"}

    with tab1:
        for gl in [g for g in game_locks if 0 <= g["minutes_until_lock"] <= 30]:
            st.markdown(f'<div class="alert-lock">⏰ <b style="color:#f5a623">LOCK IN {gl["minutes_until_lock"]} MIN</b> — {gl["matchup"]}</div>', unsafe_allow_html=True)

        out_count = sum(1 for p in mlb_players if "OUT" in p.get("inj_status","").upper())
        gtd_count = sum(1 for p in mlb_players if any(x in p.get("inj_status","").upper() for x in ["GTD","QUESTIONABLE"]))
        pitcher_count = sum(1 for p in mlb_players if p["is_pitcher"])
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.markdown(f'<div class="metric-card"><div class="metric-val">{len(mlb_players)}</div><div class="metric-lbl">Players</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f87171">{out_count}</div><div class="metric-lbl">Out</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f5a623">{gtd_count}</div><div class="metric-lbl">GTD</div></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#4fc3f7">{pitcher_count}</div><div class="metric-lbl">Pitchers</div></div>', unsafe_allow_html=True)

        if game_locks:
            st.markdown("**⏱ Game Locks**")
            for gl in game_locks:
                mins = gl["minutes_until_lock"]
                if mins < 0: icon="🔒"; color="#8892a4"; txt="LOCKED"
                elif mins <= 15: icon="🔴"; color="#f87171"; txt=f"LOCKS IN {mins}m"
                elif mins <= 45: icon="🟡"; color="#f5a623"; txt=f"Locks in {mins}m"
                else:
                    h,m = divmod(mins,60); txt=f"Locks in {h}h {m}m" if h else f"Locks in {m}m"
                    icon="🟢"; color="#52b788"
                st.markdown(f'<div class="lock-bar"><span style="color:#e8eaf0;font-size:0.85rem">{gl["matchup"]}</span><span style="color:{color};font-weight:700">{icon} {txt}</span></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        for tier_num in range(1, 7):
            tier_ps = [p for p in mlb_players if p["tier"] == tier_num]
            if not tier_ps: continue
            cash_s = sorted(tier_ps, key=lambda x: x.get("sim_cash_score", x["cash_score"]), reverse=True)

            def gpp_rank(p, tier_ps=tier_ps):
                if p["is_pitcher"]: return p.get("sim_gpp_score", p["gpp_score"])
                ceiling = p.get("sim_ceiling", p["dk_projection"] * 1.5)
                own = (p.get("ownership_pct") or 30) / 100
                own_factor = 1.0 - (own * 0.6)
                bat_pos = p.get("batting_order", 0)
                bat_bonus = 1.10 if bat_pos in [3,4] else (1.07 if bat_pos in [1,2,5] else 1.0)
                tier_batters = [x for x in tier_ps if not x["is_pitcher"]]
                tier_projs = sorted([x["dk_projection"] for x in tier_batters], reverse=True)
                proj_median = tier_projs[len(tier_projs)//2] if tier_projs else 0
                if p["dk_projection"] < proj_median: return ceiling * own_factor * bat_bonus * 0.5
                return ceiling * own_factor * bat_bonus

            gpp_s = sorted(tier_ps, key=gpp_rank, reverse=True)

            with st.expander(f"{TIER_LABELS[tier_num]}", expanded=True):
                pitchers     = [p for p in tier_ps if p["is_pitcher"]]
                batters_cash = [p for p in cash_s if not p["is_pitcher"]]
                batters_gpp  = [p for p in gpp_s  if not p["is_pitcher"]]
                if pitchers:
                    st.markdown("<div class='lbl-pitcher'>⚾ PITCHER PICKS</div>", unsafe_allow_html=True)
                    for p in pitchers[:2]: st.markdown(make_mlb_card(p,"cash"), unsafe_allow_html=True)
                    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                if batters_cash:
                    st.markdown("<div class='lbl-cash'>💵 CASH — BATTER</div>", unsafe_allow_html=True)
                    for p in batters_cash[:2]: st.markdown(make_mlb_card(p,"cash"), unsafe_allow_html=True)
                    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                if batters_gpp:
                    st.markdown("<div class='lbl-gpp'>🏆 GPP — BATTER</div>", unsafe_allow_html=True)
                    shown = set()
                    for p in batters_gpp:
                        if p["name"] not in shown:
                            st.markdown(make_mlb_card(p,"gpp"), unsafe_allow_html=True)
                            shown.add(p["name"])
                        if len(shown) >= 2: break
                if show_all:
                    rows = [{"Player":p["name"],"Bat#":p.get("batting_order","") or "","Pos":p["position"],
                             "Team":p["team"],"vs":p["opponent"],"Proj":p["dk_projection"],
                             "Floor":p.get("sim_floor",""),"Median":p.get("sim_median",""),"Ceiling":p.get("sim_ceiling",""),
                             "Cash":p.get("sim_cash_score",p["cash_score"]),"GPP":p.get("sim_gpp_score",p["gpp_score"]),
                             "Park PF":p.get("park_factor",""),"Opp ERA":p.get("opp_pitcher_era",""),
                             "O/U":p.get("vegas_total","") or "N/A","Own%":p.get("ownership_pct",""),
                             "Inj":p.get("inj_status","")} for p in cash_s]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab2:
        st.markdown("### 🏟️ Game Environment")
        st.caption("Best run environments — ranked by implied total, park, pitcher quality")
        games_seen = {}
        for p in mlb_players:
            if not p.get("opponent"): continue
            matchup = "-".join(sorted([p["team"], p["opponent"]]))
            if matchup not in games_seen:
                home = p["home_team"]; park = get_park(home)
                total = p.get("vegas_total"); spread = p.get("vegas_spread")
                imp = implied_total(spread, total) if total and spread is not None else None
                games_seen[matchup] = {"teams":f"{p['team']} vs {p['opponent']}","home":home,
                                       "park":park,"total":total,"spread":spread,"implied":imp,
                                       "lock":p.get("game_time_str","")}
        if not games_seen:
            st.info("Upload your CSV to see game environments.")
        else:
            game_envs = []
            for key, g in games_seen.items():
                score = 50.0; tags = []
                total = g["total"]; imp = g["implied"]; pf = g["park"]["factor"]
                if imp is not None:
                    if imp >= 5.5: score += 25; tags.append(f"Implied {imp:.1f} runs 🔥")
                    elif imp >= 5.0: score += 18; tags.append(f"Implied {imp:.1f} runs")
                    elif imp >= 4.5: score += 10; tags.append(f"Implied {imp:.1f} runs")
                    elif imp <= 3.5: score -= 15; tags.append(f"Low implied {imp:.1f} runs ❄️")
                elif total:
                    if total >= 10: score += 20; tags.append(f"O/U {total} 🔥")
                    elif total >= 9: score += 12; tags.append(f"O/U {total}")
                    elif total >= 8: score += 5; tags.append(f"O/U {total}")
                    elif total <= 7: score -= 12; tags.append(f"Low O/U {total} ❄️")
                if pf >= 1.15: score += 15; tags.append(f"Extreme hitter's park ({g['park']['name']})")
                elif pf >= 1.05: score += 8; tags.append(f"Hitter's park ({g['park']['name']})")
                elif pf <= 0.95: score -= 10; tags.append(f"Pitcher's park ({g['park']['name']})")
                if g["home"] in DOMED_STADIUMS: tags.append("🏟️ Domed")
                g["env_score"] = round(score,1); g["tags"] = tags; game_envs.append(g)
            game_envs.sort(key=lambda x: x["env_score"], reverse=True)
            for idx, g in enumerate(game_envs):
                score = g["env_score"]
                color = "#52b788" if score >= 65 else ("#f5a623" if score >= 55 else ("#8892a4" if score >= 45 else "#f87171"))
                rank = "🔥 BEST ENVIRONMENT" if idx == 0 else (f"#{idx+1}" if idx < 3 else f"#{idx+1} — avoid batters")
                total_str = f"O/U {g['total']}" if g["total"] else "O/U N/A"
                imp_str = f"Implied {g['implied']:.1f}" if g["implied"] is not None else "Implied N/A"
                st.markdown(f"""
                <div class="stack-card">
                <div style='display:flex;justify-content:space-between;align-items:center'>
                  <div>
                    <div style='font-family:Barlow Condensed,sans-serif;font-size:1.15rem;font-weight:700;color:#fff'>{g["teams"]} · {rank}</div>
                    <div class='pmeta'>{total_str} · {imp_str} · {g["park"]["name"]} (PF {g["park"]["factor"]:.2f}) · {g["lock"]}</div>
                    <div class='pmeta' style='margin-top:3px'>{" · ".join(g["tags"][:3])}</div>
                  </div>
                  <div style='text-align:center;min-width:52px'>
                    <div style='background:#1a2a1a;border-radius:8px;padding:6px 10px;font-family:Barlow Condensed,sans-serif;font-size:1.3rem;font-weight:700;color:{color}'>{score:.0f}</div>
                    <div style='font-size:0.6rem;color:#8892a4;margin-top:2px'>ENV SCORE</div>
                  </div>
                </div>
                </div>
                """, unsafe_allow_html=True)

    with tab3:
        st.markdown("### 🎯 Tier Best Bets")
        st.caption("One clear recommendation per tier for cash and GPP")
        if not any(p["cash_score"] > 0 for p in mlb_players):
            st.info("Upload your CSV to see best bets.")
        else:
            pitchers_in_pool = {p["team"]: p["name"] for p in mlb_players if p["is_pitcher"]}
            for tier_num in range(1, 7):
                tier_ps = [p for p in mlb_players if p["tier"] == tier_num]
                if not tier_ps: continue
                pitchers_t = [p for p in tier_ps if p["is_pitcher"]]
                batters_t  = [p for p in tier_ps if not p["is_pitcher"] and "OUT" not in p.get("inj_status","").upper()]
                if not batters_t and not pitchers_t: continue
                st.markdown(f"<div class='t{tier_num}'><b>{TIER_LABELS[tier_num]}</b></div>", unsafe_allow_html=True)
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                col_c, col_g = st.columns(2)
                with col_c:
                    st.markdown("<div class='lbl-cash'>💵 CASH PICK</div>", unsafe_allow_html=True)
                    best = sorted(pitchers_t, key=lambda x: x["cash_score"], reverse=True)[0] if pitchers_t else (sorted(batters_t, key=lambda x: x["cash_score"], reverse=True)[0] if batters_t else None)
                    if best:
                        era = get_pitcher_era(best["name"]) if best["is_pitcher"] else best.get("opp_pitcher_era",4.50)
                        era_label = f"ERA {era:.2f}" if best["is_pitcher"] else f"Opp ERA {era:.2f}"
                        bat_str = f" · Bats #{best.get('batting_order',0)}" if best.get("batting_order",0) > 0 else ""
                        total_str = f" · O/U {best['vegas_total']}" if best.get("vegas_total") else ""
                        reasons = " · ".join(best.get("cash_reasons",[])[:2])
                        st.markdown(f"""<div class='pick-cash'>
                        <div class='pname'>{best['name']} <span style='color:#8892a4;font-size:0.8rem'>{best['position']}</span></div>
                        <div class='pmeta'>{best['team']} vs {best['opponent']}{bat_str}{total_str}</div>
                        <div class='pmeta'>{era_label} · {best.get('park_name','')}</div>
                        <div class='preason' style='margin-top:4px;color:#52b788'>{reasons}</div>
                        </div>""", unsafe_allow_html=True)
                with col_g:
                    st.markdown("<div class='lbl-gpp'>🏆 GPP PICK</div>", unsafe_allow_html=True)
                    best_gpp = sorted(batters_t, key=lambda x: x["gpp_score"], reverse=True)[0] if batters_t else (sorted(pitchers_t, key=lambda x: x["gpp_score"], reverse=True)[0] if pitchers_t else None)
                    if best_gpp:
                        era_gpp = best_gpp.get("opp_pitcher_era",4.50)
                        bat_str_g = f" · Bats #{best_gpp.get('batting_order',0)}" if best_gpp.get("batting_order",0) > 0 else ""
                        total_str_g = f" · O/U {best_gpp['vegas_total']}" if best_gpp.get("vegas_total") else ""
                        own = best_gpp.get("ownership_pct",0) or 0
                        reasons_g = " · ".join(best_gpp.get("gpp_reasons",[])[:2])
                        st.markdown(f"""<div class='pick-gpp'>
                        <div class='pname'>{best_gpp['name']} <span style='color:#8892a4;font-size:0.8rem'>{best_gpp['position']}</span></div>
                        <div class='pmeta'>{best_gpp['team']} vs {best_gpp['opponent']}{bat_str_g}{total_str_g} · ~{own:.0f}% own</div>
                        <div class='pmeta'>Opp ERA {era_gpp:.2f} · {best_gpp.get('park_name','')}</div>
                        <div class='preason' style='margin-top:4px;color:#ce93d8'>{reasons_g}</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("---")
            st.markdown("### ⛔ Pitcher Avoid List")
            if pitchers_in_pool:
                for team, pitcher_name in pitchers_in_pool.items():
                    era = get_pitcher_era(pitcher_name); grade, color = pitcher_grade(era)
                    affected = [p for p in mlb_players if not p["is_pitcher"] and p["opponent"] == team]
                    affected_names = ", ".join(p["name"] for p in affected[:4])
                    st.markdown(f"""<div style='background:#1a0a0a;border:1px solid #3a1a1a;border-left:3px solid #f87171;border-radius:8px;padding:0.6rem 0.9rem;margin-bottom:0.4rem'>
                    <div class='pname' style='color:#f87171'>⛔ {pitcher_name} ({team}) — ERA {era:.2f} {grade}</div>
                    <div class='pmeta'>Avoid batters facing {team}: <b style='color:#e8eaf0'>{affected_names or "none in pool"}</b></div>
                    </div>""", unsafe_allow_html=True)

    with tab4:
        st.markdown("### 🔄 Late Swap & Injury Manager")
        all_names = sorted(set(p["name"] for p in mlb_players))
        col_out, col_gtd = st.columns(2)
        with col_out:
            st.markdown("**Mark as OUT:**")
            for name in all_names:
                is_out = name in st.session_state.manual_out
                if st.checkbox(f"🔴 {name}", value=is_out, key=f"out_{name}"):
                    st.session_state.manual_out.add(name); st.session_state.manual_gtd.discard(name)
                else: st.session_state.manual_out.discard(name)
        with col_gtd:
            st.markdown("**Mark as GTD:**")
            for name in all_names:
                if name in st.session_state.manual_out: continue
                is_gtd = name in st.session_state.manual_gtd
                if st.checkbox(f"🟡 {name}", value=is_gtd, key=f"gtd_{name}"):
                    st.session_state.manual_gtd.add(name)
                else: st.session_state.manual_gtd.discard(name)
        if st.session_state.manual_out:
            st.markdown("---")
            st.markdown("#### ⚡ Replacement Suggestions")
            for out_name in st.session_state.manual_out:
                out_p = next((p for p in mlb_players if p["name"]==out_name), None)
                if not out_p: continue
                tier_num = out_p["tier"]
                reps = [p for p in mlb_players if p["tier"]==tier_num and p["name"]!=out_name
                        and "OUT" not in p.get("inj_status","").upper()
                        and p["name"] not in st.session_state.manual_out]
                st.markdown(f"**🔴 {out_name} OUT — Tier {tier_num} replacements:**")
                rc, rg = st.columns(2)
                with rc:
                    st.markdown("💵 Cash:")
                    for p in sorted(reps, key=lambda x: x["cash_score"], reverse=True)[:3]:
                        era_str = f" · ERA {p.get('opp_pitcher_era',4.5):.2f}" if not p["is_pitcher"] else ""
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
                h,m = divmod(mins,60); txt=f"Locks in {h}h {m}m" if h else f"Locks in {m}m"
                icon="🟢"; color="#52b788"
            st.markdown(f"{icon} **{gl['matchup']}** — <span style='color:{color}'>{txt}</span>", unsafe_allow_html=True)

    with tab5:
        st.markdown("### 📋 My Lineup")
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### 💵 Cash (Triple Up)")
            for tier_num in range(1, 7):
                tier_ps = sorted([p for p in mlb_players if p["tier"]==tier_num],
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
                tier_ps = sorted([p for p in mlb_players if p["tier"]==tier_num],
                                 key=lambda x: x["gpp_score"], reverse=True)
                active = [p for p in tier_ps if "OUT" not in p.get("inj_status","").upper()
                          and p["name"] not in st.session_state.manual_out]
                if not active: continue
                options = [p["name"] for p in active[:2]] + ["Other..."]
                choice = st.selectbox(f"T{tier_num}", options=options, key=f"gpp_t{tier_num}")
                if choice == "Other...":
                    choice = st.selectbox(f"T{tier_num} full", [p["name"] for p in active], key=f"gpp_full_t{tier_num}")
                st.session_state.picks_gpp[tier_num] = choice
        st.markdown("---")
        cash_alerts = []; gpp_alerts = []
        for t in range(1, 7):
            for pick, alist in [(st.session_state.picks_cash.get(t,""), cash_alerts),
                                (st.session_state.picks_gpp.get(t,""), gpp_alerts)]:
                if not pick: continue
                p = next((x for x in mlb_players if x["name"]==pick), None)
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
        else:
            if st.session_state.picks_cash or st.session_state.picks_gpp:
                st.success("✅ All your picks are healthy")
        if len(st.session_state.picks_cash) == 6 and len(st.session_state.picks_gpp) == 6:
            lc, rg = st.columns(2)
            with lc:
                st.markdown("**💵 Cash Lineup**")
                st.code("\n".join([f"T{t}: {st.session_state.picks_cash.get(t,'')}" for t in range(1,7)]), language=None)
            with rg:
                st.markdown("**🏆 GPP Lineup**")
                st.code("\n".join([f"T{t}: {st.session_state.picks_gpp.get(t,'')}" for t in range(1,7)]), language=None)
