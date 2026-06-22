"""
PropLine Settlement — grades logged candidates against actual MLB results
=========================================================================
THE MISSING HALF. The edge-test script logs candidates but never checks whether
they WON. This script fills the `outcome` column so we can finally answer:
did the flagged picks actually beat their real breakeven?

WHAT IT DOES
------------
1. Pull every unsettled row from `propline_edge_test` (outcome IS NULL) whose
   game date is in the past (so a result exists).
2. For each player, pull their MLB game log and find the actual stat value on
   that game's date.
3. Grade:  Over  -> win if actual > line
           Under -> win if actual < line
           actual == line -> push (void, not counted)
4. Write `outcome` ('win'/'loss'/'push'/'dnp') and `actual_value` back.

HONEST NOTES
------------
- Most of the 7,735 rows are from the OLD V1 script (flagged vs a fake 50%
  benchmark). That doesn't matter for grading — win/loss is real either way.
  The analysis we run AFTER this asks "did flagged picks win above breakeven,"
  which is benchmark-independent.
- Doubleheaders: stats for the same date are summed (approximate — pick'em props
  are usually single-game, but this CSV has no game_id to disambiguate). Flagged
  as a known limitation.
- A player who didn't play that day is marked 'dnp' and excluded from win-rate.
- ⚠️ UNTESTED against live MLB/Supabase from the build env (network-blocked).
  Verify the first run's printed summary before trusting the numbers.

Required GitHub secrets:
- SUPABASE_URL
- SUPABASE_KEY  (service_role)
"""

import os
import sys
import time
from datetime import datetime, date, timezone
from collections import defaultdict

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing SUPABASE_URL / SUPABASE_KEY")
    sys.exit(1)

STAT_FIELD = {"RBI": "rbi", "Runs": "runs", "Total Bases": "totalBases",
              "Strikeouts": "strikeOuts"}
PITCHER_STATS = {"Strikeouts"}


# ============================================================
# SUPABASE (read unsettled, write outcomes)
# ============================================================
def sb_headers(extra=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def fetch_unsettled():
    """Get all rows with outcome IS NULL, paginated."""
    rows = []
    step = 1000
    offset = 0
    while True:
        url = (f"{SUPABASE_URL}/rest/v1/propline_edge_test"
               f"?outcome=is.null&select=*&order=test_date.asc"
               f"&limit={step}&offset={offset}")
        try:
            r = requests.get(url, headers=sb_headers(), timeout=30)
        except Exception as e:
            print(f"⚠️ fetch exception: {e}")
            break
        if r.status_code != 200:
            print(f"⚠️ fetch failed {r.status_code}: {r.text[:200]}")
            break
        batch = r.json()
        rows.extend(batch)
        if len(batch) < step:
            break
        offset += step
    return rows


def update_outcome(row_id_filter, outcome, actual_value):
    """PATCH a single row's outcome + actual_value.
    row_id_filter is a dict of the conflict-key columns identifying the row."""
    # build filter querystring from the natural key
    q = "&".join(f"{k}=eq.{requests.utils.quote(str(v))}"
                 for k, v in row_id_filter.items())
    url = f"{SUPABASE_URL}/rest/v1/propline_edge_test?{q}"
    payload = {"outcome": outcome, "actual_value": actual_value}
    try:
        r = requests.patch(url, headers=sb_headers({"Prefer": "return=minimal"}),
                           json=payload, timeout=30)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"⚠️ update exception: {e}")
        return False


# ============================================================
# MLB STATS
# ============================================================
_id_cache = {}
_log_cache = {}


def mlb_player_id(name, season):
    key = (name, season)
    if key in _id_cache:
        return _id_cache[key]
    try:
        r = requests.get(f"{MLB_STATS_BASE}/sports/1/players",
                         params={"season": season}, timeout=20)
        if r.status_code != 200:
            _id_cache[key] = None
            return None
        target = (name or "").lower().strip()
        people = r.json().get("people", [])
        for p in people:
            if p.get("fullName", "").lower() == target:
                _id_cache[key] = p["id"]
                return p["id"]
        last = target.split()[-1] if target else ""
        for p in people:
            if p.get("fullName", "").lower().endswith(last):
                _id_cache[key] = p["id"]
                return p["id"]
    except Exception:
        pass
    _id_cache[key] = None
    return None


def mlb_game_log_by_date(player_id, group, season):
    """Return {date_str: {stat_field: value}} summed per date (doubleheaders)."""
    key = (player_id, group, season)
    if key in _log_cache:
        return _log_cache[key]
    out = defaultdict(lambda: defaultdict(float))
    try:
        r = requests.get(f"{MLB_STATS_BASE}/people/{player_id}/stats",
                         params={"stats": "gameLog", "group": group,
                                 "season": season, "sportId": 1}, timeout=20)
        if r.status_code == 200:
            arr = r.json().get("stats", [])
            if arr:
                for s in arr[0].get("splits", []):
                    d = s.get("date")
                    st = s.get("stat", {})
                    if not d:
                        continue
                    for fld in ("rbi", "runs", "totalBases", "strikeOuts"):
                        try:
                            out[d][fld] += float(st.get(fld, 0) or 0)
                        except (TypeError, ValueError):
                            pass
    except Exception:
        pass
    _log_cache[key] = out
    return out


# ============================================================
# GRADE
# ============================================================
def game_date_of(row):
    """Extract YYYY-MM-DD of the game from commence_time, fallback test_date."""
    ct = row.get("commence_time")
    if ct:
        try:
            return datetime.fromisoformat(ct.replace("Z", "+00:00")).date().isoformat()
        except Exception:
            pass
    return row.get("test_date")


def grade(side, actual, line):
    if actual is None:
        return "dnp", None
    if actual > line:
        res = "win" if side == "Over" else "loss"
    elif actual < line:
        res = "win" if side == "Under" else "loss"
    else:
        res = "push"
    return res, actual


# ============================================================
# MAIN
# ============================================================
def main():
    print(f"=== PropLine Settlement — {datetime.now(timezone.utc).isoformat()} ===")
    rows = fetch_unsettled()
    print(f"Unsettled rows fetched: {len(rows)}")
    if not rows:
        print("Nothing to settle. Exiting.")
        return

    today = date.today().isoformat()
    counts = defaultdict(int)
    updated = 0
    skipped_future = 0

    # group by (player, season, group) to minimize API calls
    for row in rows:
        gdate = game_date_of(row)
        if not gdate or gdate >= today:
            skipped_future += 1
            continue
        player = row.get("player")
        stat = row.get("stat")
        line = row.get("line")
        side = row.get("side")
        if player is None or stat not in STAT_FIELD or line is None:
            continue
        season = int(gdate[:4])
        pid = mlb_player_id(player, season)
        if pid is None:
            counts["no_player_id"] += 1
            continue
        group = "pitching" if stat in PITCHER_STATS else "hitting"
        logs = mlb_game_log_by_date(pid, group, season)
        fld = STAT_FIELD[stat]
        day = logs.get(gdate)
        actual = day.get(fld) if day else None
        outcome, actual_val = grade(side, actual, float(line))
        counts[outcome] += 1

        key = {"test_date": row["test_date"], "book": row["book"],
               "player": row["player"], "stat": row["stat"],
               "line": row["line"], "side": row["side"]}
        if update_outcome(key, outcome, actual_val):
            updated += 1
        time.sleep(0.05)

    print(f"Skipped (future/no date): {skipped_future}")
    print(f"Updated in Supabase: {updated}")
    print("Outcome breakdown:")
    for k in ("win", "loss", "push", "dnp", "no_player_id"):
        if counts[k]:
            print(f"  {k}: {counts[k]}")
    graded = counts["win"] + counts["loss"]
    if graded:
        print(f"Raw win rate (excl push/dnp): {counts['win']/graded*100:.1f}% "
              f"({counts['win']}/{graded})")
    print("=== Done ===")


if __name__ == "__main__":
    main()
