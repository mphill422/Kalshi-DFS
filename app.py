import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import requests
import time
import pytz
import json
from supabase import create_client

st.set_page_config(page_title="DK Tier Optimizer", page_icon="🏀", layout="wide", initial_sidebar_state="expanded")
ET = pytz.timezone("America/New_York")

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def get_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

supabase = get_supabase()

def save_slate_to_supabase(players):
    """Save today's slate to Supabase so it persists across sessions."""
    if not supabase:
        return False
    try:
        today = date.today().isoformat()
        # Delete old slate for today first
        supabase.table("dfs_slate").delete().eq("slate_date", today).execute()
        # Save each player
        records = []
        for p in players:
            records.append({
                "slate_date": today,
                "name": p["name"],
                "team": p["team"],
                "position": p["position"],
                "tier": p["tier"],
                "dk_projection": p["dk_projection"],
                "opponent": p["opponent"],
                "game_time_str": p.get("game_time_str", ""),
            })
        # Batch insert
        for i in range(0, len(records), 10):
            supabase.table("dfs_slate").insert(records[i:i+10]).execute()
        return True
    except Exception as e:
        return False

def load_slate_from_supabase():
    """Load today's slate from Supabase if it exists."""
    if not supabase:
        return []
    try:
        today = date.today().isoformat()
        resp = supabase.table("dfs_slate").select("*").eq("slate_date", today).execute()
        if not resp.data:
            return []
        players = []
        for row in resp.data:
            players.append({
                "name": row["name"],
                "team": row["team"],
                "position": row.get("position", ""),
                "tier": row["tier"],
                "dk_projection": float(row.get("dk_projection", 0) or 0),
                "opponent": row.get("opponent", ""),
                "game_time_str": row.get("game_time_str", ""),
                "inj_status": "", "inj_note": "", "recent_form": None, "form_trend": None,
                "vegas_spread": None, "vegas_total": None, "ownership_pct": None,
                "cash_score": 0, "gpp_score": 0, "cash_reasons": [], "gpp_reasons": [],
                "spike_boost": 0, "spike_reason": "", "ownership_proxy": 0.5,
            })
        return players
    except:
        return []

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@400;500;600&display=swap');
html,body,[class*="css"]{font-family:'Barlow',sans-serif;background-color:#0d0f14;color:#e8eaf0;}
h1,h2,h3{font-family:'Barlow Condensed',sans-serif;letter-spacing:0.04em;}
.hdr{background:linear-gradient(135deg,#1a1e2e,#0f1420);border-bottom:2px solid #f5a623;padding:0.9rem 1.2rem;margin-bottom:1rem;border-radius:8px;}
.hdr h1{font-size:1.9rem;font-weight:800;color:#f5a623;margin:0;text-transform:uppercase;}
.hdr .sub{font-size:0.82rem;color:#8892a4;margin-top:2px;}
.t1{color:#f5a623;border-left:4px solid #f5a623;padding-left:8px;}
.t2{color:#4fc3f7;border-left:4px solid #4fc3f7;padding-left:8px;}
.t3{color:#81c784;border-left:4px solid #81c784;padding-left:8px;}
.t4{color:#ce93d8;border-left:4px solid #ce93d8;padding-left:8px;}
.t5{color:#ffb74d;border-left:4px solid #ffb74d;padding-left:8px;}
.t6{color:#f48fb1;border-left:4px solid #f48fb1;padding-left:8px;}
.tier-hdr{font-family:'Barlow Condensed',sans-serif;font-size:1.35rem;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;margin:0.8rem 0 0.4rem 0;}
.pick-cash{background:#0a1a2a;border:1px solid #1a3a5a;border-left:3px solid #4fc3f7;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;}
.pick-gpp{background:#1a0a2a;border:1px solid #3a1a5a;border-left:3px solid #ce93d8;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;}
.pick-out{background:#2a0a0a;border:1px solid #f87171;border-left:3px solid #f87171;border-radius:8px;padding:0.75rem 0.9rem;margin-bottom:0.5rem;opacity:0.6;}
.lbl-cash{font-size:0.65rem;font-weight:700;color:#4fc3f7;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;}
.lbl-gpp{font-size:0.65rem;font-weight:700;color:#ce93d8;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;}
.pname{font-family:'Barlow Condensed',sans-serif;font-size:1.05rem;font-weight:700;color:#fff;}
.pmeta{font-size:0.75rem;color:#8892a4;margin-top:1px;}
.preason{font-size:0.74rem;color:#b0bec5;margin-top:2px;}
.pown{font-size:0.72rem;color:#8892a4;}
.badge{display:inline-block;padding:2px 7px;border-radius:3px;font-size:0.66rem;font-weight:700;text-transform:uppercase;margin-right:3px;}
.b-red{background:#4a0e0e;color:#f87171;}
.b-yellow{background:#3d2c00;color:#f5a623;}
.b-green{background:#1b4332;color:#52b788;}
.b-blue{background:#0a2540;color:#4fc3f7;}
.b-purple{background:#2d1040;color:#ce93d8;}
.b-orange{background:#3d1f00;color:#ffb74d;}
.metric-card{background:#161b27;border:1px solid #252d3d;border-radius:8px;padding:0.7rem 0.9rem;text-align:center;}
.metric-val{font-family:'Barlow Condensed',sans-serif;font-size:1.7rem;font-weight:700;color:#f5a623;}
.metric-lbl{font-size:0.68rem;color:#8892a4;text-transform:uppercase;letter-spacing:0.05em;}
.lock-bar{background:#161b27;border:1px solid #252d3d;border-radius:6px;padding:0.4rem 0.8rem;margin-bottom:0.3rem;display:flex;justify-content:space-between;align-items:center;}
.alert-lock{background:#2a1200;border:1px solid #f5a623;border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.8rem;}
.spike-alert{background:#1a2a0a;border:1px solid #81c784;border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.5rem;}
div[data-testid="stSidebar"]{background:#0f1420 !important;border-right:1px solid #252d3d;}
.stButton>button{background:#f5a623 !important;color:#0d0f14 !important;font-family:'Barlow Condensed',sans-serif !important;font-weight:700 !important;font-size:0.9rem !important;text-transform:uppercase !important;letter-spacing:0.06em !important;border:none !important;border-radius:6px !important;}
@media(max-width:768px){
  .hdr h1{font-size:1.5rem !important;}
  .pname{font-size:1rem !important;}
  .pmeta,.preason,.pown{font-size:0.78rem !important;}
  .pick-cash,.pick-gpp,.pick-out{padding:0.8rem !important;}
  .badge{font-size:0.7rem !important;padding:3px 8px !important;}
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
TIER_LABELS  = {1:"Tier 1 — Elite",2:"Tier 2 — Star",3:"Tier 3 — Premium",4:"Tier 4 — Mid",5:"Tier 5 — Value",6:"Tier 6 — Dart"}
TIER_CLASSES = {1:"t1",2:"t2",3:"t3",4:"t4",5:"t5",6:"t6"}
DK_TEAM_MAP  = {
    "ATL":"Atlanta Hawks","BOS":"Boston Celtics","BKN":"Brooklyn Nets","CHA":"Charlotte Hornets",
    "CHI":"Chicago Bulls","CLE":"Cleveland Cavaliers","DAL":"Dallas Mavericks","DEN":"Denver Nuggets",
    "DET":"Detroit Pistons","GSW":"Golden State Warriors","HOU":"Houston Rockets","IND":"Indiana Pacers",
    "LAC":"LA Clippers","LAL":"Los Angeles Lakers","MEM":"Memphis Grizzlies","MIA":"Miami Heat",
    "MIL":"Milwaukee Bucks","MIN":"Minnesota Timberwolves","NOP":"New Orleans Pelicans","NYK":"New York Knicks",
    "OKC":"Oklahoma City Thunder","ORL":"Orlando Magic","PHI":"Philadelphia 76ers","PHX":"Phoenix Suns",
    "POR":"Portland Trail Blazers","SAC":"Sacramento Kings","SAS":"San Antonio Spurs","TOR":"Toronto Raptors",
    "UTA":"Utah Jazz","WAS":"Washington Wizards"
}

# ── Session State Init ────────────────────────────────────────────────────────
if "manual_out" not in st.session_state:
    st.session_state.manual_out = set()
if "manual_gtd" not in st.session_state:
    st.session_state.manual_gtd = set()
if "players" not in st.session_state:
    st.session_state.players = []
if "picks_cash" not in st.session_state:
    st.session_state.picks_cash = {}
if "picks_gpp" not in st.session_state:
    st.session_state.picks_gpp = {}

# ── Data Fetchers ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def fetch_injuries():
    injuries = {}
    try:
        url = "https://www.rotowire.com/basketball/tables/injury-report.php?team=ALL&pos=ALL"
        resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=12)
        if resp.status_code == 200:
            dfs = pd.read_html(resp.text)
            if dfs:
                for _, row in dfs[0].iterrows():
                    name = str(row.get("Player","") or "").strip()
                    status = str(row.get("Status","") or "").strip().upper()
                    note = str(row.get("Injury","") or "").strip()
                    if name and name.lower() != "nan":
                        injuries[name.lower()] = {"status": status, "note": note}
    except:
        pass
    return injuries

@st.cache_data(ttl=600)
def fetch_vegas_lines():
    lines = {}
    try:
        api_key = st.secrets.get("ODDS_API_KEY","")
        if not api_key:
            return lines
        resp = requests.get(
            "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/",
            params={"apiKey":api_key,"regions":"us","markets":"spreads,totals","oddsFormat":"american"},
            timeout=12
        )
        if resp.status_code == 200:
            for game in resp.json():
                home, away = game.get("home_team",""), game.get("away_team","")
                spread, total = None, None
                for bm in game.get("bookmakers",[]):
                    for m in bm.get("markets",[]):
                        if m["key"]=="spreads":
                            for o in m.get("outcomes",[]):
                                if o["name"]==home: spread=o.get("point",0)
                        if m["key"]=="totals":
                            for o in m.get("outcomes",[]):
                                if o["name"]=="Over": total=o.get("point",0)
                    break
                lines[home] = {"spread":spread,"total":total,"opponent":away}
                lines[away] = {"spread":-spread if spread else None,"total":total,"opponent":home}
    except:
        pass
    return lines

@st.cache_data(ttl=1800)
def fetch_recent_form(player_name):
    try:
        hdrs = {"User-Agent":"Mozilla/5.0","Referer":"https://www.nba.com","x-nba-stats-origin":"stats","x-nba-stats-token":"true","Accept":"application/json"}
        resp = requests.get("https://stats.nba.com/stats/commonallplayers",headers=hdrs,params={"LeagueID":"00","Season":"2025-26","IsOnlyCurrentSeason":"1"},timeout=15)
        if resp.status_code!=200: return None, None
        rows=resp.json()["resultSets"][0]["rowSet"]
        hdrs2=resp.json()["resultSets"][0]["headers"]
        player_id=None
        nl=player_name.lower()
        for row in rows:
            p=dict(zip(hdrs2,row))
            fl=p.get("DISPLAY_FIRST_LAST","").lower()
            if nl in fl or fl in nl:
                player_id=p.get("PERSON_ID"); break
        if not player_id: return None, None
        resp2=requests.get("https://stats.nba.com/stats/playergamelog",headers=hdrs,params={"PlayerID":player_id,"Season":"2025-26","SeasonType":"Regular Season","LeagueID":"00"},timeout=15)
        if resp2.status_code!=200: return None, None
        rows2=resp2.json()["resultSets"][0]["rowSet"]
        hdrs3=resp2.json()["resultSets"][0]["headers"]
        if not rows2: return None, None
        fpts=[]
        for row in rows2[:10]:
            g=dict(zip(hdrs3,row))
            try:
                f=(float(g.get("PTS",0) or 0)+float(g.get("REB",0) or 0)*1.25+float(g.get("AST",0) or 0)*1.5+
                   float(g.get("STL",0) or 0)*2+float(g.get("BLK",0) or 0)*2+float(g.get("TOV",0) or 0)*-0.5+
                   float(g.get("FG3M",0) or 0)*0.5)
                fpts.append(f)
            except: pass
        if not fpts: return None, None
        avg=round(np.mean(fpts),1)
        # trend: compare last 3 vs last 10
        recent3=round(np.mean(fpts[:3]),1) if len(fpts)>=3 else avg
        trend = "up" if recent3 > avg+3 else ("down" if recent3 < avg-3 else "flat")
        return avg, trend
    except:
        return None, None

# ── CSV Parser ────────────────────────────────────────────────────────────────
def parse_dk_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        players = []
        for _, row in df.iterrows():
            roster_pos = str(row.get("Roster Position","") or "").strip()
            position   = str(row.get("Position","") or "").strip()
            tier = None
            if roster_pos.startswith("T") and len(roster_pos)==2:
                try: tier=int(roster_pos[1])
                except: pass
            if tier is None: continue
            name = str(row.get("Name","") or "").strip()
            if not name:
                nid=str(row.get("Name + ID","") or "")
                name=nid.split("(")[0].strip() if "(" in nid else nid.strip()
            team      = str(row.get("TeamAbbrev","") or "").strip()
            avg_pts   = float(row.get("AvgPointsPerGame",0) or 0)
            game_info = str(row.get("Game Info","") or "")
            opponent, game_time_str = "", ""
            if "@" in game_info:
                parts=game_info.split(" ")
                matchup=parts[0] if parts else ""
                teams=matchup.split("@")
                if len(teams)==2:
                    away_t,home_t=teams[0].strip(),teams[1].strip()
                    opponent=home_t if team==away_t else away_t
                try:
                    game_time_str=" ".join(parts[1:3]) if len(parts)>=3 else ""
                    game_time_str=game_time_str.replace(" ET","").strip()
                except: pass
            players.append({
                "name":name,"team":team,"position":position,"tier":tier,
                "dk_projection":avg_pts,"opponent":opponent,"game_time_str":game_time_str,
                "inj_status":"","inj_note":"","recent_form":None,"form_trend":None,
                "vegas_spread":None,"vegas_total":None,"ownership_pct":None,
                "cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],
                "spike_boost":0,"spike_reason":"",
            })
        return players
    except Exception as e:
        st.error(f"CSV parse error: {e}")
        return []

# ── Injury Lookup ─────────────────────────────────────────────────────────────
def get_inj(name, injuries):
    nl=name.lower()
    if nl in injuries: return injuries[nl]
    for k,v in injuries.items():
        if nl in k or k in nl: return v
    return {"status":"","note":""}

def get_vegas(team, vegas_lines):
    full=DK_TEAM_MAP.get(team,team)
    for k in [team,full]:
        if k in vegas_lines: return vegas_lines[k]
    return {"spread":None,"total":None}

# ── Usage Spike Detection ─────────────────────────────────────────────────────
def detect_usage_spikes(players):
    """
    When a star player is OUT, boost teammates on same team.
    Boost scales with the OUT player's projection.
    """
    out_players = [p for p in players if "OUT" in p.get("inj_status","").upper() or p["name"] in st.session_state.manual_out]

    for out_p in out_players:
        out_proj = out_p["dk_projection"]
        out_team = out_p["team"]
        out_tier = out_p["tier"]

        # Boost teammates — higher boost for same/adjacent tiers
        for p in players:
            if p["team"] != out_team: continue
            if p["name"] == out_p["name"]: continue
            if "OUT" in p.get("inj_status","").upper(): continue

            tier_diff = abs(p["tier"] - out_tier)
            if tier_diff == 0:
                boost = min(out_proj * 0.25, 15)  # Same tier: big boost
                reason = f"Usage spike — {out_p['name']} OUT (same tier)"
            elif tier_diff == 1:
                boost = min(out_proj * 0.15, 10)  # Adjacent tier: medium boost
                reason = f"Usage spike — {out_p['name']} OUT"
            elif tier_diff == 2:
                boost = min(out_proj * 0.08, 6)   # 2 tiers away: small boost
                reason = f"Indirect usage — {out_p['name']} OUT"
            else:
                continue

            p["spike_boost"] += boost
            p["spike_reason"] = reason
            p["cash_score"] += boost
            p["gpp_score"]  += boost * 0.8  # GPP slightly less — ownership will rise

    return players

# ── Ownership Estimate ────────────────────────────────────────────────────────
def estimate_ownership(players):
    """
    Estimate ownership % based on projection rank within tier.
    Top player ~40-55%, drops ~10-15% per rank.
    Adjusted for injury status and chalk factors.
    """
    for tier_num in range(1, 7):
        tier_ps = [p for p in players if p["tier"]==tier_num and "OUT" not in p.get("inj_status","").upper() and p["name"] not in st.session_state.manual_out]
        if not tier_ps: continue
        tier_ps.sort(key=lambda x: x["dk_projection"], reverse=True)
        base_owns = [48, 28, 15, 7, 3, 2]  # Base ownership by rank
        for idx, p in enumerate(tier_ps):
            base = base_owns[idx] if idx < len(base_owns) else 1
            # Adjustments
            spread = p.get("vegas_spread")
            if spread is not None:
                if spread <= -10: base += 8   # Heavy fav = more chalk
                elif spread >= 8: base -= 5   # Underdog = less owned
            if p.get("spike_boost", 0) > 5:
                base += 10  # Usage spike players get more owned
            p["ownership_pct"] = min(max(base, 1), 75)
    return players

# ── Scoring Engine ────────────────────────────────────────────────────────────
def score_players(players, injuries, vegas_lines, load_form=False):
    # Set ownership proxy for later
    for tier_num in range(1,7):
        tier_ps=[p for p in players if p["tier"]==tier_num]
        if not tier_ps: continue
        max_proj=max(p["dk_projection"] for p in tier_ps) or 1
        for p in tier_ps:
            p["ownership_proxy"]=p["dk_projection"]/max_proj

    for p in players:
        # Apply manual overrides first
        if p["name"] in st.session_state.manual_out:
            p["inj_status"]="OUT"; p["inj_note"]="Manually marked OUT"
        elif p["name"] in st.session_state.manual_gtd:
            p["inj_status"]="GTD"; p["inj_note"]="Manually marked GTD"
        else:
            inj=get_inj(p["name"],injuries)
            p["inj_status"]=inj.get("status","")
            p["inj_note"]=inj.get("note","")

        veg=get_vegas(p["team"],vegas_lines)
        p["vegas_spread"]=veg.get("spread")
        p["vegas_total"]=veg.get("total")

        if load_form and p["recent_form"] is None:
            p["recent_form"], p["form_trend"] = fetch_recent_form(p["name"])

        proj=p["dk_projection"]
        spread=p["vegas_spread"]
        total=p["vegas_total"]
        status=p["inj_status"].upper()
        own=p.get("ownership_proxy",0.5)

        if "OUT" in status:
            p["cash_score"]=0; p["gpp_score"]=0
            p["cash_reasons"]=["OUT — do not play"]; p["gpp_reasons"]=["OUT — do not play"]
            continue

        cash=50.0; gpp=50.0
        cr=[]; gr=[]

        if "GTD" in status or "QUESTIONABLE" in status or "DOUBTFUL" in status:
            cash-=25; gpp-=10
            cr.append("GTD — risky for cash"); gr.append("GTD — low ownership if confirmed")

        # Projection
        proj_bonus=min((proj-20)*0.8,30)
        cash+=proj_bonus; gpp+=proj_bonus*0.7

        # Recent form
        if p["recent_form"] is not None:
            diff=p["recent_form"]-proj
            if diff>5:
                cash+=8; gpp+=6
                cr.append(f"🔥 Hot — L10 avg {p['recent_form']:.0f} (+{diff:.0f})")
                gr.append(f"🔥 Hot streak L10: {p['recent_form']:.0f}")
            elif diff<-5:
                cash-=6; gpp-=3
                cr.append(f"❄️ Cold — L10 avg {p['recent_form']:.0f} ({diff:.0f})")

        # Vegas spread
        if spread is not None:
            if spread<=-12:
                cash+=12; gpp+=4
                cr.append(f"Heavy fav ({spread:+.0f}) — safe floor")
                gr.append(f"Heavy fav {spread:+.0f} — chalk")
            elif spread<=-6:
                cash+=7; gpp+=4
                cr.append(f"Favored ({spread:+.0f})")
            elif spread<=-3:
                cash+=3; gpp+=3
            elif spread>=12:
                cash-=18; gpp-=10
                cr.append(f"Big dog ({spread:+.0f}) — blowout risk")
                gr.append(f"Blowout risk {spread:+.0f}")
            elif spread>=6:
                cash-=8; gpp-=4
                cr.append(f"Underdog ({spread:+.0f})")
            elif abs(spread)<=3:
                cash+=3; gpp+=10
                gr.append(f"Close game ({spread:+.0f}) — GPP upside")

        # Vegas total
        if total is not None:
            if total>=232:
                cash+=7; gpp+=9
                cr.append(f"High O/U {total} — pace up")
                gr.append(f"High O/U {total}")
            elif total>=226:
                cash+=3; gpp+=4
            elif total<=212:
                cash-=6; gpp-=4
                cr.append(f"Low O/U {total} — slow game")

        # GPP ownership lever
        if own<0.4:
            gpp+=14; gr.append("Low ownership — strong GPP leverage")
        elif own<0.6:
            gpp+=5
        else:
            gpp-=6; gr.append("High chalk — fade has GPP merit")

        p["cash_score"]=max(round(cash,1),0)
        p["gpp_score"]=max(round(gpp,1),0)
        p["cash_reasons"]=cr[:3]; p["gpp_reasons"]=gr[:3]

    # Usage spikes after individual scoring
    players=detect_usage_spikes(players)
    # Ownership estimates
    players=estimate_ownership(players)
    return players

# ── Game Locks ────────────────────────────────────────────────────────────────
def get_game_locks(players):
    now_et=datetime.now(ET)
    games={}
    for p in players:
        opp=p.get("opponent",""); team=p.get("team",""); gt=p.get("game_time_str","")
        if not opp or not gt: continue
        matchup="-".join(sorted([team,opp]))
        if matchup not in games:
            try:
                gt_clean=gt.replace(" ET","").strip()
                t=datetime.strptime(gt_clean,"%I:%M%p")
                lock_dt=now_et.replace(hour=t.hour,minute=t.minute,second=0,microsecond=0)
                if lock_dt<now_et: lock_dt+=timedelta(days=1)
                mins=int((lock_dt-now_et).total_seconds()/60)
                games[matchup]={"matchup":f"{team} vs {opp}","teams":[team,opp],"lock_time_str":gt,"lock_dt":lock_dt,"minutes_until_lock":mins}
            except: pass
    return sorted(games.values(),key=lambda x:x.get("minutes_until_lock",9999))

# ── Badge HTML ────────────────────────────────────────────────────────────────
def b(text, color):
    return f'<span class="badge b-{color}">{text}</span>'

def badges(p):
    html=""
    status=p.get("inj_status","").upper()
    if "OUT" in status: html+=b("OUT","red")
    elif "GTD" in status or "QUESTIONABLE" in status: html+=b("GTD","yellow")
    elif "PROBABLE" in status: html+=b("PROB","yellow")
    if p["name"] in st.session_state.manual_out: html+=b("MANUAL OUT","red")
    elif p["name"] in st.session_state.manual_gtd: html+=b("MANUAL GTD","yellow")
    spread=p.get("vegas_spread"); total=p.get("vegas_total")
    if spread is not None:
        if spread<=-8: html+=b(f"FAV {spread:+.0f}","green")
        elif spread>=8: html+=b(f"DOG {spread:+.0f}","red")
        elif abs(spread)<=3: html+=b("CLOSE GAME","blue")
    if total and total>=228: html+=b(f"O/U {total}","blue")
    if p.get("spike_boost",0)>3: html+=b("USAGE SPIKE","orange")
    trend=p.get("form_trend")
    if trend=="up": html+=b("🔥 HOT","green")
    elif trend=="down": html+=b("❄️ COLD","red")
    return html

def ownership_bar(pct):
    if pct is None: return ""
    color="#f87171" if pct>=40 else ("#f5a623" if pct>=20 else "#52b788")
    return f'<span class="pown">Est. ownership: <b style="color:{color}">{pct:.0f}%</b></span>'

def make_card(p, mode="cash"):
    proj=p["dk_projection"]
    spread=p.get("vegas_spread"); total=p.get("vegas_total")
    vegas_str=""
    if spread is not None:
        vegas_str=f"Spread {spread:+.1f}"
        if total: vegas_str+=f" · O/U {total}"
    sk="cash_score" if mode=="cash" else "gpp_score"
    rk="cash_reasons" if mode=="cash" else "gpp_reasons"
    score=int(p.get(sk,0))
    reasons=p.get(rk,[])
    if p.get("spike_reason") and p.get("spike_boost",0)>0:
        reasons=list(reasons)+[f"⚡ {p['spike_reason']}"]
    reasons_html="".join(f"<div class='preason'>• {r}</div>" for r in reasons[:3])
    b_html=badges(p)
    own_html=ownership_bar(p.get("ownership_pct"))
    form_str=""
    if p.get("recent_form"): form_str=f" · L10: {p['recent_form']:.0f}"
    css="pick-out" if ("OUT" in p.get("inj_status","").upper() or p["name"] in st.session_state.manual_out) else (f"pick-{mode}")
    sc_bg="#0a2540" if mode=="cash" else "#2d1040"
    sc_col="#4fc3f7" if mode=="cash" else "#ce93d8"
    return (
        f"<div class='{css}'>"
        f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
        f"<div style='flex:1'>"
        f"<div class='pname'>{p['name']}</div>"
        f"<div class='pmeta'>{p['position']} · {p['team']} vs {p['opponent']} · Proj: {proj:.1f}{form_str}</div>"
        f"<div class='pmeta'>{vegas_str}</div>"
        f"<div style='margin-top:5px'>{b_html}</div>"
        f"{own_html}"
        f"{reasons_html}"
        f"</div>"
        f"<div style='text-align:center;min-width:48px;margin-left:8px'>"
        f"<div style='background:{sc_bg};border-radius:50%;width:44px;height:44px;display:flex;align-items:center;justify-content:center;font-family:Barlow Condensed,sans-serif;font-size:1.1rem;font-weight:700;color:{sc_col}'>{score}</div>"
        f"<div style='font-size:0.6rem;color:#8892a4;margin-top:2px'>{mode.upper()}</div>"
        f"</div></div>"
        f"</div>"
    )

# ── Header ────────────────────────────────────────────────────────────────────
now_et=datetime.now(ET)
st.markdown(f"""
<div class="hdr">
  <h1>🏀 DK Tier Optimizer</h1>
  <div class="sub">NBA · DraftKings Tiers · {now_et.strftime('%A %b %d, %Y')} · {now_et.strftime('%I:%M %p ET')}</div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    slate_mode=st.radio("Slate Source",["📂 Upload DK CSV","🔶 Demo Slate"],index=0)
    st.markdown("---")
    st.markdown("### 📊 Options")
    load_form=st.toggle("Load Recent Form (L10)",value=False,help="Fetches NBA Stats API — slower")
    show_all=st.toggle("Show All Players Per Tier",value=False)
    st.markdown("---")
    st.markdown("### 🔑 API Status")
    odds_key=st.secrets.get("ODDS_API_KEY","")
    st.markdown(f"**Odds API:** {'✅' if odds_key else '⚠️ No key'}")
    st.markdown(f"**Injury Feed:** ✅ Rotowire")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🏀 Today's Slate", "🔄 Late Swap / Injuries", "📋 My Lineup"])

# ── Load Slate ────────────────────────────────────────────────────────────────
players = []

if slate_mode == "📂 Upload DK CSV":
    with tab1:
        # Try loading from Supabase first (auto-loads on phone)
        if not st.session_state.players:
            saved = load_slate_from_supabase()
            if saved:
                st.session_state.players = saved

        if st.session_state.players:
            players = st.session_state.players
            today = date.today().strftime("%B %d")
            st.success(f"✅ {len(players)} players loaded for {today} — slate persisted from earlier upload")
            if st.button("🔄 Upload new CSV"):
                st.session_state.players = []
                st.rerun()
        else:
            st.markdown("""
            <div style="background:#1a1e2e;border:1px solid #f5a623;border-radius:8px;padding:0.8rem 1rem;margin-bottom:1rem">
            <b style="color:#f5a623">📂 How to get your DK CSV</b><br>
            <span style="color:#8892a4;font-size:0.82rem">
            DraftKings → NBA → Tiers → any contest → <b>Draft Team</b> → scroll bottom → <b>Export to CSV</b> → save to OneDrive
            </span>
            </div>
            """, unsafe_allow_html=True)
            uploaded=st.file_uploader("Upload DK Tier CSV",type=["csv"],label_visibility="collapsed")
            if uploaded:
                players=parse_dk_csv(uploaded)
                if players:
                    st.session_state.players=players
                    # Save to Supabase for phone persistence
                    saved_ok = save_slate_to_supabase(players)
                    sb_msg = " · Saved to cloud ☁️" if saved_ok else ""
                    st.success(f"✅ {len(players)} players loaded across {len(set(p['tier'] for p in players))} tiers{sb_msg}")
                else:
                    st.error("❌ Could not parse CSV.")
            else:
                st.info("👆 Upload your DK CSV once on Mac — it will load automatically on your phone all night.")
else:
    players=[
        {"name":"Victor Wembanyama","team":"SAS","position":"C","tier":1,"dk_projection":54.2,"opponent":"PHI","game_time_str":"08:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":1.0},
        {"name":"Jalen Johnson","team":"ATL","position":"PF","tier":1,"dk_projection":50.6,"opponent":"NYK","game_time_str":"07:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":0.93},
        {"name":"James Harden","team":"CLE","position":"PG","tier":2,"dk_projection":45.3,"opponent":"MEM","game_time_str":"08:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":1.0},
        {"name":"Donovan Mitchell","team":"CLE","position":"SG","tier":2,"dk_projection":44.8,"opponent":"MEM","game_time_str":"08:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":0.99},
        {"name":"Paolo Banchero","team":"ORL","position":"PF","tier":2,"dk_projection":42.6,"opponent":"DET","game_time_str":"07:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":0.94},
        {"name":"Stephon Castle","team":"SAS","position":"SG","tier":3,"dk_projection":38.7,"opponent":"PHI","game_time_str":"08:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":1.0},
        {"name":"Nickeil Alexander-Walker","team":"PHI","position":"SG","tier":3,"dk_projection":34.8,"opponent":"SAS","game_time_str":"08:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":0.9},
        {"name":"De'Aaron Fox","team":"SAS","position":"PG","tier":4,"dk_projection":34.4,"opponent":"PHI","game_time_str":"08:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":1.0},
        {"name":"Dyson Daniels","team":"ATL","position":"SG","tier":4,"dk_projection":33.2,"opponent":"NYK","game_time_str":"07:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":0.96},
        {"name":"Onyeka Okongwu","team":"ATL","position":"C","tier":5,"dk_projection":28.4,"opponent":"NYK","game_time_str":"07:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":1.0},
        {"name":"Devin Vassell","team":"SAS","position":"SG","tier":6,"dk_projection":26.1,"opponent":"PHI","game_time_str":"08:00PM","inj_status":"","inj_note":"","recent_form":None,"form_trend":None,"vegas_spread":None,"vegas_total":None,"ownership_pct":None,"cash_score":0,"gpp_score":0,"cash_reasons":[],"gpp_reasons":[],"spike_boost":0,"spike_reason":"","ownership_proxy":1.0},
    ]
    with tab1:
        st.info("📌 Demo mode — showing sample slate.")

if not players:
    st.stop()

# ── Score Players ─────────────────────────────────────────────────────────────
with st.spinner("Loading injuries, Vegas lines, scoring..."):
    injuries=fetch_injuries()
    vegas_lines=fetch_vegas_lines()
    players=score_players(players,injuries,vegas_lines,load_form=load_form)
    game_locks=get_game_locks(players)

# ── TAB 1: Today's Slate ──────────────────────────────────────────────────────
with tab1:
    # Urgent lock alerts
    urgent=[g for g in game_locks if 0<=g["minutes_until_lock"]<=30]
    for gl in urgent:
        mins=gl["minutes_until_lock"]
        st.markdown(f"""
        <div class="alert-lock">
        ⏰ <b style="color:#f5a623">LOCK IN {mins} MIN</b> — {gl['matchup']} locks at {gl['lock_time_str']}
        </div>
        """, unsafe_allow_html=True)

    # Usage spike alerts
    spike_players=[p for p in players if p.get("spike_boost",0)>3]
    if spike_players:
        st.markdown("**⚡ Usage Spike Alerts**")
        for p in spike_players:
            st.markdown(f"""
            <div class="spike-alert">
            ⚡ <b>{p['name']}</b> ({p['team']}) — {p['spike_reason']} · Score boost: +{p['spike_boost']:.0f}
            </div>
            """, unsafe_allow_html=True)

    # Metrics
    out_count=sum(1 for p in players if "OUT" in p.get("inj_status","").upper() or p["name"] in st.session_state.manual_out)
    gtd_count=sum(1 for p in players if any(x in p.get("inj_status","").upper() for x in ["GTD","QUESTIONABLE"]) and p["name"] not in st.session_state.manual_out)
    spike_count=len(spike_players)

    c1,c2,c3,c4=st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><div class="metric-val">{len(players)}</div><div class="metric-lbl">Players</div></div>',unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f87171">{out_count}</div><div class="metric-lbl">Out</div></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#f5a623">{gtd_count}</div><div class="metric-lbl">GTD</div></div>',unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#ffb74d">{spike_count}</div><div class="metric-lbl">Spikes</div></div>',unsafe_allow_html=True)

    # Game lock bar
    if game_locks:
        st.markdown("**⏱ Game Locks**")
        for gl in game_locks:
            mins=gl["minutes_until_lock"]
            if mins<0: icon="🔒"; color="#8892a4"; txt="LOCKED"
            elif mins<=15: icon="🔴"; color="#f87171"; txt=f"LOCKS IN {mins}m"
            elif mins<=45: icon="🟡"; color="#f5a623"; txt=f"Locks in {mins}m"
            else:
                h,m=divmod(mins,60)
                txt=f"Locks in {h}h {m}m" if h else f"Locks in {m}m"
                icon="🟢"; color="#52b788"
            st.markdown(f'<div class="lock-bar"><span style="color:#e8eaf0;font-size:0.85rem">{gl["matchup"]}</span><span style="color:{color};font-family:Barlow Condensed,sans-serif;font-weight:700;font-size:0.9rem">{icon} {txt}</span></div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Tier panels
    for tier_num in range(1,7):
        tier_ps=[p for p in players if p["tier"]==tier_num]
        if not tier_ps: continue
        cash_s=sorted(tier_ps,key=lambda x:x["cash_score"],reverse=True)
        gpp_s=sorted(tier_ps,key=lambda x:x["gpp_score"],reverse=True)
        tc=TIER_CLASSES[tier_num]

        with st.expander(f"{TIER_LABELS[tier_num]}",expanded=True):
            # Cash
            st.markdown("<div class='lbl-cash'>💵 TRIPLE UP / CASH</div>",unsafe_allow_html=True)
            for p in cash_s[:2]:
                st.markdown(make_card(p,"cash"),unsafe_allow_html=True)

            st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)

            # GPP
            st.markdown("<div class='lbl-gpp'>🏆 GPP / TOURNAMENT</div>",unsafe_allow_html=True)
            shown_gpp=set()
            for p in gpp_s:
                if p["name"] not in shown_gpp:
                    st.markdown(make_card(p,"gpp"),unsafe_allow_html=True)
                    shown_gpp.add(p["name"])
                if len(shown_gpp)>=2: break

            # Full table
            if show_all:
                rows=[]
                for p in cash_s:
                    rows.append({"Player":p["name"],"Team":p["team"],"vs":p["opponent"],"Proj":p["dk_projection"],"Cash":p["cash_score"],"GPP":p["gpp_score"],"Own%":p.get("ownership_pct",""),"Spread":p.get("vegas_spread",""),"O/U":p.get("vegas_total",""),"Inj":p.get("inj_status",""),"L10":p.get("recent_form","")})
                st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

# ── TAB 2: Late Swap / Injuries ───────────────────────────────────────────────
with tab2:
    st.markdown("### 🔄 Late Swap & Injury Manager")

    # Manual injury toggles
    st.markdown("#### 🩺 Manual Injury Overrides")
    st.caption("Mark players OUT or GTD yourself — overrides the auto feed instantly")

    all_names=sorted(set(p["name"] for p in players))

    col_out, col_gtd = st.columns(2)
    with col_out:
        st.markdown("**Mark as OUT:**")
        for name in all_names:
            is_out=name in st.session_state.manual_out
            if st.checkbox(f"🔴 {name}", value=is_out, key=f"out_{name}"):
                st.session_state.manual_out.add(name)
                st.session_state.manual_gtd.discard(name)
            else:
                st.session_state.manual_out.discard(name)

    with col_gtd:
        st.markdown("**Mark as GTD:**")
        for name in all_names:
            if name in st.session_state.manual_out: continue
            is_gtd=name in st.session_state.manual_gtd
            if st.checkbox(f"🟡 {name}", value=is_gtd, key=f"gtd_{name}"):
                st.session_state.manual_gtd.add(name)
            else:
                st.session_state.manual_gtd.discard(name)

    if st.session_state.manual_out or st.session_state.manual_gtd:
        st.markdown("---")
        st.markdown("#### ⚡ Replacement Suggestions")
        st.caption("Best replacements for players you marked OUT")

        for out_name in st.session_state.manual_out:
            out_player=next((p for p in players if p["name"]==out_name),None)
            if not out_player: continue
            tier_num=out_player["tier"]
            replacements=[p for p in players if p["tier"]==tier_num and p["name"]!=out_name and "OUT" not in p.get("inj_status","").upper() and p["name"] not in st.session_state.manual_out]

            st.markdown(f"**🔴 {out_name} OUT — Tier {tier_num} replacements:**")
            cash_reps=sorted(replacements,key=lambda x:x["cash_score"],reverse=True)[:3]
            gpp_reps=sorted(replacements,key=lambda x:x["gpp_score"],reverse=True)[:3]

            rc,rg=st.columns(2)
            with rc:
                st.markdown("💵 Cash:")
                for p in cash_reps:
                    spike_tag=" ⚡" if p.get("spike_boost",0)>3 else ""
                    spread=p.get("vegas_spread")
                    spread_str=f" · {spread:+.0f}" if spread is not None else ""
                    own=p.get("ownership_pct")
                    own_str=f" · {own:.0f}% own" if own else ""
                    st.markdown(f"• **{p['name']}**{spike_tag} — Score: {p['cash_score']:.0f}{spread_str}{own_str}")
            with rg:
                st.markdown("🏆 GPP:")
                for p in gpp_reps:
                    spike_tag=" ⚡" if p.get("spike_boost",0)>3 else ""
                    spread=p.get("vegas_spread")
                    spread_str=f" · {spread:+.0f}" if spread is not None else ""
                    own=p.get("ownership_pct")
                    own_str=f" · {own:.0f}% own" if own else ""
                    st.markdown(f"• **{p['name']}**{spike_tag} — Score: {p['gpp_score']:.0f}{spread_str}{own_str}")
            st.markdown("---")

    # Game lock status
    st.markdown("#### ⏱ Game Lock Status")
    if game_locks:
        for gl in game_locks:
            mins=gl["minutes_until_lock"]
            if mins<0: icon="🔒"; color="#8892a4"; txt="LOCKED"
            elif mins<=15: icon="🔴"; color="#f87171"; txt=f"LOCKS IN {mins} MIN — SWAP NOW"
            elif mins<=45: icon="🟡"; color="#f5a623"; txt=f"Locks in {mins} min"
            else:
                h,m=divmod(mins,60)
                txt=f"Locks in {h}h {m}m" if h else f"Locks in {m}m"
                icon="🟢"; color="#52b788"
            st.markdown(f"{icon} **{gl['matchup']}** — <span style='color:{color}'>{txt}</span>",unsafe_allow_html=True)
    else:
        st.info("No game times found in slate.")

# ── TAB 3: My Lineup ──────────────────────────────────────────────────────────
with tab3:
    st.markdown("### 📋 My Lineup")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### 💵 Cash (Triple Up)")
        for tier_num in range(1,7):
            tier_ps=sorted([p for p in players if p["tier"]==tier_num],key=lambda x:x["cash_score"],reverse=True)
            if not tier_ps: continue
            active=[p for p in tier_ps if "OUT" not in p.get("inj_status","").upper() and p["name"] not in st.session_state.manual_out]
            options=[p["name"] for p in active[:2]]+["Other..."]
            choice=st.selectbox(f"T{tier_num}",options=options,key=f"cash_t{tier_num}")
            if choice=="Other...":
                choice=st.selectbox(f"T{tier_num} full list",[p["name"] for p in active],key=f"cash_full_t{tier_num}")
            st.session_state.picks_cash[tier_num]=choice

    with col_r:
        st.markdown("#### 🏆 GPP")
        for tier_num in range(1,7):
            tier_ps=sorted([p for p in players if p["tier"]==tier_num],key=lambda x:x["gpp_score"],reverse=True)
            if not tier_ps: continue
            active=[p for p in tier_ps if "OUT" not in p.get("inj_status","").upper() and p["name"] not in st.session_state.manual_out]
            options=[p["name"] for p in active[:2]]+["Other..."]
            choice=st.selectbox(f"T{tier_num}",options=options,key=f"gpp_t{tier_num}")
            if choice=="Other...":
                choice=st.selectbox(f"T{tier_num} full list",[p["name"] for p in active],key=f"gpp_full_t{tier_num}")
            st.session_state.picks_gpp[tier_num]=choice

    # Show lineups
    if len(st.session_state.picks_cash)==6 and len(st.session_state.picks_gpp)==6:
        st.markdown("---")
        lc,rg=st.columns(2)
        with lc:
            st.markdown("**💵 Cash Lineup**")
            cash_text="\n".join([f"T{t}: {st.session_state.picks_cash.get(t,'')}" for t in range(1,7)])
            st.code(cash_text,language=None)
        with rg:
            st.markdown("**🏆 GPP Lineup**")
            gpp_text="\n".join([f"T{t}: {st.session_state.picks_gpp.get(t,'')}" for t in range(1,7)])
            st.code(gpp_text,language=None)
