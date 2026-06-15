"""
PropLine Soft-Line Edge Test — V1
==================================
THE definitive test: does the CALIBRATED model beat the soft pick'em lines
(PrizePicks / Underdog) by enough to clear their house edge?

All prior validation scored the model against DraftKings/FanDuel (sharp) lines
and found ~zero edge once calibration removed the model's overconfidence. But
the platforms actually bet are PrizePicks/Underdog, which are SOFTER. This job
measures the model against THOSE lines using PropLine's no-vig fair line as the
honest benchmark.

What it does each run:
1. Pull today's + tomorrow's MLB events from PropLine.
2. For each event, pull PrizePicks + Underdog + Pinnacle lines for the target
   markets (RBI, Runs, Total Bases, Strikeouts).
3. For each player line, compute the model's CALIBRATED probability (same
   calibration curve as the app — the model is overconfident, so we correct it).
4. Compare calibrated prob to the platform's NO-VIG implied prob.
   - If PropLine provides a no-vig/fair field, use it.
   - Otherwise fall back to Pinnacle's line as the sharp no-vig reference,
     or de-vig the platform's own over/under pair.
5. Log every candidate where calibrated_prob - novig_implied >= EDGE_MARGIN
   into Supabase table `propline_edge_test` for later settlement + analysis.

This does NOT place bets and does NOT touch the existing model/snapshot. It
accumulates candidate edges so that, after ~2 weeks of settled results, we can
answer definitively whether real edge exists on the soft platforms.

Required GitHub secrets:
- PROPLINE_API_KEY
- SUPABASE_URL
- SUPABASE_KEY   (service_role)

NOTE ON FIRST RUN: PropLine claims the-odds-api-compatible shape. If the odds
payload differs, this script prints the raw structure of the first event's
bookmakers array to the Action log and exits gracefully, so we can adapt the
parser in one more pass without guessing.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta, date, timezone

import numpy as np
import pandas as pd
import requests

# ============================================================
# CONFIG
# ============================================================

PROPLINE_API_KEY = os.environ.get("PROPLINE_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

missing = [k for k, v in {
    "PROPLINE_API_KEY": PROPLINE_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
}.items() if not v]
if missing:
    print(f"❌ Missing secrets: {', '.join(missing)}")
    sys.exit(1)

PROPLINE_BASE = "https://api.prop-line.com/v1"
MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"

# Target markets — PropLine market keys (the-odds-api compatible)
TARGET_MARKETS = {
    "batter_rbis": "RBI",
    "batter_runs_scored": "Runs",
    "batter_total_bases": "Total Bases",
    "pitcher_strikeouts": "Strikeouts",
}

SOFT_BOOKS = ["prizepicks", "underdog"]
SHARP_BOOK = "pinnacle"

# Minimum honest edge (calibrated prob - no-vig implied, in pp) to log a
# candidate. Set conservatively: soft-book house edge means small gaps aren't
# real. We log anything >= this so we can study the distribution; we are NOT
# betting these, just measuring.
EDGE_MARGIN = 3.0

N_SIMULATIONS = 10_000
L25_WINDOW = 25
L10_WEIGHT = 0.70

# ---- Calibration curve (claimed % -> honest %), fit via isotonic regression
# on ~9,000 settled picks. MUST match the app's CALIB_* values. ----
CALIB_CLAIMED = [0, 10, 20, 30, 40, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
CALIB_HONEST = [26.0, 26.0, 26.0, 26.0, 28.6, 37.5, 43.0, 48.1, 53.0, 56.7,
                60.4, 64.3, 68.0, 70.1, 71.2, 71.2]


def calibrate_prob(claimed_pct):
    if claimed_pct is None:
        return None
    c = max(0.0, min(100.0, float(claimed_pct)))
    return float(np.interp(c, CALIB_CLAIMED, CALIB_HONEST))


# ============================================================
# SUPABASE
# ============================================================

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }


def sb_upsert(table, rows, on_conflict):
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    written = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        try:
            r = requests.post(url, headers=sb_headers(), json=chunk, timeout=30)
            if r.status_code in (200, 201, 204):
                written += len(chunk)
            else:
                print(f"⚠️  upsert failed {r.status_code}: {r.text[:300]}")
        except Exception as e:
            print(f"⚠️  upsert exception: {e}")
    return written


# ============================================================
# PROPLINE
# ============================================================

def pl_get(path, params=None):
    p = {"apiKey": PROPLINE_API_KEY}
    if params:
        p.update(params)
    r = requests.get(f"{PROPLINE_BASE}/{path}", params=p, timeout=25)
    return r


def pl_events(sport="baseball_mlb"):
    r = pl_get(f"sports/{sport}/events")
    if r.status_code != 200:
        print(f"❌ events {r.status_code}: {r.text[:200]}")
        return []
    evs = r.json()
    today = datetime.utcnow().date()
    keep = []
    for e in evs:
        try:
            d = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")).date()
            if today <= d <= today + timedelta(days=1):
                keep.append(e)
        except Exception:
            continue
    return keep


def pl_event_odds(event_id, sport="baseball_mlb"):
    r = pl_get(f"sports/{sport}/events/{event_id}/odds",
               params={
                   "regions": "us_dfs",
                   "markets": ",".join(TARGET_MARKETS.keys()),
                   "bookmakers": ",".join(SOFT_BOOKS + [SHARP_BOOK]),
               })
    if r.status_code != 200:
        return None, f"{r.status_code}: {r.text[:200]}"
    return r.json(), None


# ============================================================
# PARSING (defensive — adapts to the-odds-api-style shape)
# ============================================================

def american_to_prob(odds):
    if odds is None:
        return None
    try:
        o = float(odds)
    except Exception:
        return None
    return 100.0 / (o + 100.0) if o > 0 else -o / (-o + 100.0)


def devig_pair(p_over, p_under):
    """Remove vig from an over/under implied-prob pair (proportional)."""
    if p_over is None or p_under is None:
        return p_over, p_under
    s = p_over + p_under
    if s <= 0:
        return p_over, p_under
    return p_over / s, p_under / s


def parse_event_odds(data):
    """
    Convert a PropLine odds payload into normalized rows:
      {market_key, stat, player, line, book, over_odds, under_odds,
       over_prob_novig, under_prob_novig}
    Built defensively for the-odds-api-style shape:
      data['bookmakers'] = [ {key, markets:[ {key, outcomes:[
          {name:'Over'/'Under', description:player, point:line, price:odds,
           ... possibly 'fair'/'no_vig' fields} ]} ]} ]
    Returns (rows, raw_sample_for_debug).
    """
    rows = []
    bms = data.get("bookmakers")
    if not bms:
        return rows, None

    for bm in bms:
        book = bm.get("key", "")
        for m in bm.get("markets", []):
            mkey = m.get("key", "")
            stat = TARGET_MARKETS.get(mkey)
            if stat is None:
                continue
            # group outcomes by player+line
            bykey = {}
            for o in m.get("outcomes", []):
                player = o.get("description") or o.get("participant") or o.get("name_player")
                point = o.get("point")
                side = (o.get("name") or "").lower()
                price = o.get("price")
                # capture any fair/no-vig field if present
                fair = o.get("fair_price") or o.get("no_vig_price") or o.get("fair")
                k = (player, point)
                bykey.setdefault(k, {})[side] = {"price": price, "fair": fair}
            for (player, point), sides in bykey.items():
                over = sides.get("over", {})
                under = sides.get("under", {})
                po = american_to_prob(over.get("price"))
                pu = american_to_prob(under.get("price"))
                # Prefer explicit fair/no-vig if PropLine provides it
                po_fair = american_to_prob(over.get("fair")) if over.get("fair") else None
                pu_fair = american_to_prob(under.get("fair")) if under.get("fair") else None
                if po_fair is None or pu_fair is None:
                    po_fair, pu_fair = devig_pair(po, pu)
                rows.append({
                    "market_key": mkey, "stat": stat, "player": player,
                    "line": point, "book": book,
                    "over_odds": over.get("price"), "under_odds": under.get("price"),
                    "over_prob_novig": po_fair, "under_prob_novig": pu_fair,
                })
    return rows, None


# ============================================================
# MLB HISTORY + MODEL (mirrors snapshot logic)
# ============================================================

_id_cache = {}

def mlb_player_id(name):
    if name in _id_cache:
        return _id_cache[name]
    season = date.today().year
    try:
        r = requests.get(f"{MLB_STATS_BASE}/sports/1/players",
                         params={"season": season}, timeout=20)
        if r.status_code != 200:
            return None
        target = (name or "").lower().strip()
        people = r.json().get("people", [])
        for p in people:
            if p.get("fullName", "").lower() == target:
                _id_cache[name] = p["id"]; return p["id"]
        last = target.split()[-1] if target else ""
        for p in people:
            if p.get("fullName", "").lower().endswith(last):
                _id_cache[name] = p["id"]; return p["id"]
    except Exception:
        pass
    _id_cache[name] = None
    return None


def mlb_game_log(player_id, group):
    if player_id is None:
        return pd.DataFrame()
    season = date.today().year
    try:
        r = requests.get(f"{MLB_STATS_BASE}/people/{player_id}/stats",
                         params={"stats": "gameLog", "group": group,
                                 "season": season, "sportId": 1}, timeout=20)
        if r.status_code != 200:
            return pd.DataFrame()
        arr = r.json().get("stats", [])
        if not arr:
            return pd.DataFrame()
        rows = []
        for s in arr[0].get("splits", []):
            st = s.get("stat", {})
            rows.append({
                "rbi": st.get("rbi", 0), "runs": st.get("runs", 0),
                "totalBases": st.get("totalBases", 0),
                "strikeouts": st.get("strikeOuts", 0),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


STAT_FIELD = {"RBI": "rbi", "Runs": "runs", "Total Bases": "totalBases",
              "Strikeouts": "strikeouts"}
PITCHER_STATS = {"Strikeouts"}


def model_prob_over(player, stat, line):
    """Raw model probability the player goes OVER the line (Monte Carlo)."""
    pid = mlb_player_id(player)
    if pid is None:
        return None, 0
    group = "pitching" if stat in PITCHER_STATS else "hitting"
    log = mlb_game_log(pid, group)
    field = STAT_FIELD.get(stat)
    if log.empty or field not in log.columns:
        return None, 0
    vals = log[field].astype(float).values
    vals = vals[~np.isnan(vals)]
    n = len(vals)
    if n == 0:
        return None, 0
    # distribution
    if n < 5:
        sims = np.random.poisson(max(np.mean(vals), 0.1), N_SIMULATIONS)
    elif n < 10:
        mean = np.mean(vals); var = np.var(vals, ddof=1)
        if var > mean and mean > 0:
            p = mean / var; nb = mean * p / (1 - p)
            sims = (np.random.negative_binomial(nb, p, N_SIMULATIONS)
                    if nb > 0 and np.isfinite(nb)
                    else np.random.poisson(max(mean, 0.1), N_SIMULATIONS))
        else:
            sims = np.random.poisson(max(mean, 0.1), N_SIMULATIONS)
    else:
        l10 = vals[:min(10, n)]; older = vals[10:min(L25_WINDOW, n)]
        if len(older) > 0:
            n10 = int(N_SIMULATIONS * L10_WEIGHT)
            sims = np.concatenate([np.random.choice(l10, n10, replace=True),
                                   np.random.choice(older, N_SIMULATIONS - n10, replace=True)])
        else:
            sims = np.random.choice(l10, N_SIMULATIONS, replace=True)
        sims = np.round(sims).clip(min=0)
    return float(np.mean(sims > line)), n


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"=== PropLine Edge Test — {datetime.now(timezone.utc).isoformat()} ===")
    events = pl_events()
    print(f"MLB events today/tomorrow: {len(events)}")
    if not events:
        print("No events. Exiting clean.")
        return

    candidates = []
    debug_printed = False
    processed = 0

    for ev in events:
        odds, err = pl_event_odds(ev["id"])
        if err:
            print(f"  odds err {ev['id']}: {err}")
            continue
        rows, _ = parse_event_odds(odds)

        # First-run safety: if we got bookmakers but parsed nothing, dump shape
        if not rows and odds.get("bookmakers") and not debug_printed:
            print("⚠️  Got bookmakers but parsed 0 rows. Raw shape of first book:")
            print(json.dumps(odds["bookmakers"][0], indent=2)[:2000])
            debug_printed = True
            continue

        for row in rows:
            if row["book"] not in SOFT_BOOKS:
                continue  # only score soft-book lines
            if row["line"] is None or row["player"] is None:
                continue
            raw_over, n = model_prob_over(row["player"], row["stat"], row["line"])
            if raw_over is None or n < 10:
                continue
            processed += 1
            cal_over = calibrate_prob(raw_over * 100) / 100.0
            cal_under = calibrate_prob((1 - raw_over) * 100) / 100.0

            # Compare each side's calibrated prob to its no-vig implied
            for side, cal_p, novig in [
                ("Over", cal_over, row["over_prob_novig"]),
                ("Under", cal_under, row["under_prob_novig"]),
            ]:
                if novig is None:
                    continue
                edge_pp = (cal_p - novig) * 100
                if edge_pp >= EDGE_MARGIN:
                    candidates.append({
                        "test_date": date.today().isoformat(),
                        "commence_time": ev.get("commence_time"),
                        "home_team": ev.get("home_team"),
                        "away_team": ev.get("away_team"),
                        "book": row["book"],
                        "player": row["player"],
                        "stat": row["stat"],
                        "line": float(row["line"]),
                        "side": side,
                        "model_prob_raw": round(raw_over * 100 if side == "Over"
                                                else (1 - raw_over) * 100, 1),
                        "model_prob_cal": round(cal_p * 100, 1),
                        "novig_implied": round(novig * 100, 1),
                        "edge_pp": round(edge_pp, 1),
                        "sample_size": n,
                        "outcome": None,
                        "actual_value": None,
                    })
        time.sleep(0.15)

    print(f"Lines scored: {processed}")
    print(f"Candidate edges (>= {EDGE_MARGIN}pp): {len(candidates)}")
    if candidates:
        # quick summary
        df = pd.DataFrame(candidates)
        print(df.groupby(["stat", "side"]).size().to_string())
        written = sb_upsert("propline_edge_test", candidates,
                            on_conflict="test_date,book,player,stat,line,side")
        print(f"Written to Supabase: {written}")
    else:
        print("No candidate edges this run (this is itself a meaningful result).")

    print("=== Done ===")


if __name__ == "__main__":
    main()
