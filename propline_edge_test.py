"""
PropLine Soft-Line Edge Test — V2
==================================
THE definitive test: does the CALIBRATED model beat the soft pick'em lines
by enough to clear the REAL bar you must beat on each platform?

WHAT CHANGED FROM V1 (and why):
-------------------------------
V1 had a fatal benchmark bug. Pick'em platforms (PrizePicks, ParlayPlay)
carry NO real odds, so V1 fell back to a 50% coin-flip and flagged a fake
"edge" on ~70% of all lines. The 308 rows it logged were almost entirely
garbage (model vs 50%, not vs anything real).

V2 fixes the benchmark honestly, three ways:
  1. PICK'EM PLATFORMS (no odds) are now scored against the REAL per-leg
     BREAKEVEN you must clear to be profitable — not 50%. PrizePicks 2-pick
     power pays 3x, so each leg needs ~57.7% to break even. A model leg at
     60% vs a 57.7% bar is a real +2.3pp edge. A leg at 66% vs 50% was a
     fake +16pp. This collapses the fake candidates and shows real ones.
  2. REAL-ODDS PLATFORMS (Underdog carries real implied values) are still
     scored against their de-vigged no-vig line — the honest comparison
     that already worked in V1.
  3. PARLAYPLAY added to the soft-book list. Research flag: ParlayPlay is
     reported to run SOFTER, slower-updating MLB lines than PrizePicks /
     Underdog — the most likely place a real edge exists, if one does.

Also fixed: the 500 "ON CONFLICT DO UPDATE cannot affect row a second time"
error. V1 sent duplicate (player, stat, line, side) rows in one batch. V2
de-dupes before upsert (keeps the highest-edge row per key), so all rows
write cleanly.

This does NOT place bets and does NOT touch the model/snapshot. It logs
candidates so that, after ~2 weeks of settled results, we run one query:
did the flagged edges actually win vs their benchmark? Honest prior: edge
is thin (this is the 4th efficient-market test). The data decides.

ONE-TIME SETUP (run once in Supabase SQL Editor before first V2 run):
  alter table propline_edge_test
    add column if not exists benchmark_type text;

Required GitHub secrets:
- PROPLINE_API_KEY
- SUPABASE_URL
- SUPABASE_KEY   (service_role)
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

# Soft pick'em platforms we score. ParlayPlay added (softest MLB lines).
SOFT_BOOKS = ["prizepicks", "underdog", "parlayplay"]
SHARP_BOOK = "pinnacle"

# ---- PER-PLATFORM PICK'EM BREAKEVENS ----
# For platforms that carry NO real odds, this is the per-leg win probability
# a pick must clear to be profitable, given the contest's payout multiplier.
# Formula: breakeven = (1 / payout_multiplier) ** (1 / n_picks)
#
#   PrizePicks 2-pick power (3.0x):  (1/3)  ** (1/2) = 0.577   <- CONFIRMED
#   PrizePicks 3-pick power (6.0x):  (1/6)  ** (1/3) = 0.550
#   Underdog   2-pick std   (3.5x):  (1/3.5)** (1/2) = 0.535   <- CONFIRMED
#   Underdog   3-pick std   (6.0x):  (1/6)  ** (1/3) = 0.550
#
# We score against the 2-PICK bar by default (the realistic, strictest
# common play). Underdog usually delivers REAL odds via PropLine, so its
# breakeven here is only a fallback if odds are missing.
#
# ParlayPlay multiplier is NOT yet confirmed — using PrizePicks' 2-pick bar
# (0.577) as a conservative placeholder. ⚠️ CONFIRM PARLAYPLAY 2-PICK PAYOUT
# and update this number before trusting ParlayPlay candidates.
PICKEM_BREAKEVEN = {
    "prizepicks": 0.577,
    "parlayplay": 0.577,   # ⚠️ placeholder — confirm real multiplier
    "underdog": 0.535,     # fallback only; real odds preferred when present
}
DEFAULT_PICKEM_BREAKEVEN = 0.577

# Minimum honest edge (calibrated prob - real benchmark, in pp) to log a
# candidate. Now measured against a REAL bar, so 3pp is meaningful.
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
    over_prob_novig / under_prob_novig are None when the book carries no
    real odds (pick'em platforms) — those get scored against breakeven.
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
                fair = o.get("fair_price") or o.get("no_vig_price") or o.get("fair")
                k = (player, point)
                bykey.setdefault(k, {})[side] = {"price": price, "fair": fair}
            for (player, point), sides in bykey.items():
                over = sides.get("over", {})
                under = sides.get("under", {})
                po = american_to_prob(over.get("price"))
                pu = american_to_prob(under.get("price"))
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
# MLB HISTORY + MODEL (mirrors snapshot logic — UNCHANGED)
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
# BENCHMARK SELECTION
# ============================================================

def benchmark_for(book, side_novig):
    """
    Decide what real bar this leg is judged against.
      - If the book gave a real no-vig implied prob -> use it (real_novig).
      - Else if the book is a known pick'em platform -> use its breakeven.
      - Else -> None (skip; unknown book with no odds).
    Returns (benchmark_prob, benchmark_type) or (None, None).
    """
    if side_novig is not None:
        return side_novig, "real_novig"
    if book in PICKEM_BREAKEVEN:
        return PICKEM_BREAKEVEN[book], "pickem_breakeven"
    if book in SOFT_BOOKS:
        return DEFAULT_PICKEM_BREAKEVEN, "pickem_breakeven"
    return None, None


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"=== PropLine Edge Test V2 — {datetime.now(timezone.utc).isoformat()} ===")
    events = pl_events()
    print(f"MLB events today/tomorrow: {len(events)}")
    if not events:
        print("No events. Exiting clean.")
        return

    # De-dupe candidates by conflict key; keep the highest-edge row per key.
    cand_by_key = {}
    debug_printed = False
    processed = 0

    for ev in events:
        odds, err = pl_event_odds(ev["id"])
        if err:
            print(f"  odds err {ev['id']}: {err}")
            continue
        rows, _ = parse_event_odds(odds)

        if not rows and odds.get("bookmakers") and not debug_printed:
            print("⚠️  Got bookmakers but parsed 0 rows. Raw shape of first book:")
            print(json.dumps(odds["bookmakers"][0], indent=2)[:2000])
            debug_printed = True
            continue

        for row in rows:
            if row["book"] not in SOFT_BOOKS:
                continue
            if row["line"] is None or row["player"] is None:
                continue
            raw_over, n = model_prob_over(row["player"], row["stat"], row["line"])
            if raw_over is None or n < 10:
                continue
            processed += 1
            cal_over = calibrate_prob(raw_over * 100) / 100.0
            cal_under = calibrate_prob((1 - raw_over) * 100) / 100.0

            for side, cal_p, side_novig in [
                ("Over", cal_over, row["over_prob_novig"]),
                ("Under", cal_under, row["under_prob_novig"]),
            ]:
                benchmark, btype = benchmark_for(row["book"], side_novig)
                if benchmark is None:
                    continue
                edge_pp = (cal_p - benchmark) * 100
                if edge_pp < EDGE_MARGIN:
                    continue
                key = (date.today().isoformat(), row["book"], row["player"],
                       row["stat"], float(row["line"]), side)
                cand = {
                    "test_date": key[0],
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
                    "novig_implied": round(benchmark * 100, 1),
                    "benchmark_type": btype,
                    "edge_pp": round(edge_pp, 1),
                    "sample_size": n,
                    "outcome": None,
                    "actual_value": None,
                }
                prev = cand_by_key.get(key)
                if prev is None or cand["edge_pp"] > prev["edge_pp"]:
                    cand_by_key[key] = cand
        time.sleep(0.15)

    candidates = list(cand_by_key.values())
    print(f"Lines scored: {processed}")
    print(f"Candidate edges (>= {EDGE_MARGIN}pp vs REAL benchmark): {len(candidates)}")
    if candidates:
        df = pd.DataFrame(candidates)
        # show breakdown by book + benchmark type so fakes can't hide
        print(df.groupby(["book", "benchmark_type", "stat", "side"]).size().to_string())
        written = sb_upsert("propline_edge_test", candidates,
                            on_conflict="test_date,book,player,stat,line,side")
        print(f"Written to Supabase: {written}")
    else:
        print("No candidate edges this run (this is itself a meaningful result).")

    print("=== Done ===")


if __name__ == "__main__":
    main()
