"""
DFS Shadow Validation — Morning Settlement Job
==============================================
Runs at 11 AM ET via GitHub Actions cron.

Workflow:
1. Pull yesterday's picks from dfs_shadow_picks
2. For each pick, fetch the actual game outcome
3. Mark hit/miss/push/void
4. Write to dfs_settlements table

Required env vars:
- SUPABASE_URL, SUPABASE_KEY
- BDL_API_KEY  (NBA outcomes)
"""

import os
import sys
import time
from datetime import datetime, timedelta, date, timezone

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
BDL_API_KEY = os.environ.get("BDL_API_KEY", "")

missing = [k for k, v in {"SUPABASE_URL": SUPABASE_URL,
                          "SUPABASE_KEY": SUPABASE_KEY,
                          "BDL_API_KEY": BDL_API_KEY}.items() if not v]
if missing:
    print(f"❌ Missing env vars: {', '.join(missing)}")
    sys.exit(1)

BDL_BASE = "https://api.balldontlie.io/v1"
MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"


# ============================================================
# SUPABASE
# ============================================================

def sb_headers():
    return {"apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"}


def fetch_unsettled_picks(target_date: str):
    """Get picks from target_date that don't have settlements yet."""
    url = f"{SUPABASE_URL}/rest/v1/dfs_shadow_picks"
    params = {
        "snapshot_date": f"eq.{target_date}",
        "select": "id,league,player,stat,line,side,commence_time,home_team,away_team",
        "limit": 5000,
    }
    try:
        r = requests.get(url, headers=sb_headers(), params=params, timeout=30)
        if r.status_code != 200:
            print(f"❌ Fetch picks: {r.status_code} {r.text[:200]}")
            return []
        picks = r.json()
        # Filter out already-settled
        ids = [p["id"] for p in picks]
        if not ids:
            return []
        # Get IDs already settled
        settled_url = f"{SUPABASE_URL}/rest/v1/dfs_settlements"
        settled_params = {"pick_id": f"in.({','.join(str(i) for i in ids)})",
                          "select": "pick_id"}
        r2 = requests.get(settled_url, headers=sb_headers(),
                          params=settled_params, timeout=30)
        if r2.status_code == 200:
            settled_ids = {row["pick_id"] for row in r2.json()}
            return [p for p in picks if p["id"] not in settled_ids]
        return picks
    except Exception as e:
        print(f"❌ Exception: {e}")
        return []


def insert_settlements(rows: list):
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/dfs_settlements"
    inserted = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i+500]
        try:
            r = requests.post(url, headers={**sb_headers(),
                                             "Prefer": "return=minimal"},
                              json=chunk, timeout=30)
            if r.status_code in (200, 201, 204):
                inserted += len(chunk)
            else:
                print(f"⚠️  Batch insert failed: {r.status_code} {r.text[:200]}")
                print(f"   Falling back to per-row inserts for this chunk...")
                # Per-row fallback so one bad row doesn't kill the batch
                for single in chunk:
                    try:
                        r2 = requests.post(url, headers={**sb_headers(),
                                                          "Prefer": "return=minimal"},
                                           json=single, timeout=15)
                        if r2.status_code in (200, 201, 204):
                            inserted += 1
                    except Exception:
                        pass
        except Exception as e:
            print(f"⚠️  Insert exception: {e}")
    return inserted


def log_run_start(run_type: str):
    url = f"{SUPABASE_URL}/rest/v1/dfs_run_log"
    headers = {**sb_headers(), "Prefer": "return=representation"}
    row = {"run_type": run_type, "status": "running"}
    try:
        r = requests.post(url, headers=headers, json=row, timeout=15)
        if r.status_code in (200, 201):
            data = r.json()
            return data[0]["id"] if data else None
    except Exception:
        pass
    return None


def log_run_end(run_id, status, processed, written, errors=None):
    if run_id is None:
        return
    url = f"{SUPABASE_URL}/rest/v1/dfs_run_log?id=eq.{run_id}"
    headers = {**sb_headers(), "Prefer": "return=minimal"}
    patch = {"completed_at": datetime.now(timezone.utc).isoformat(),
             "status": status, "rows_processed": processed,
             "rows_written": written, "errors": errors}
    try:
        requests.patch(url, headers=headers, json=patch, timeout=15)
    except Exception:
        pass


# ============================================================
# NBA SETTLEMENT (BallDontLie)
# ============================================================

_bdl_player_cache = {}
_bdl_game_cache = {}


def bdl_player_id(name: str):
    if name in _bdl_player_cache:
        return _bdl_player_cache[name]
    parts = name.strip().split()
    if not parts:
        return None
    try:
        r = requests.get(f"{BDL_BASE}/players",
                         params={"search": parts[-1], "per_page": 25},
                         headers={"Authorization": BDL_API_KEY}, timeout=10)
        if r.status_code != 200:
            return None
        target = name.lower().strip()
        for p in r.json().get("data", []):
            full = f"{p.get('first_name', '')} {p.get('last_name', '')}".lower().strip()
            if full == target:
                _bdl_player_cache[name] = p["id"]
                return p["id"]
        last = parts[-1].lower()
        for p in r.json().get("data", []):
            if p.get("last_name", "").lower() == last:
                _bdl_player_cache[name] = p["id"]
                return p["id"]
    except Exception:
        pass
    _bdl_player_cache[name] = None
    return None


def bdl_box_score(player_id: int, game_date: str):
    """Fetch a player's stats for a specific date."""
    cache_key = (player_id, game_date)
    if cache_key in _bdl_game_cache:
        return _bdl_game_cache[cache_key]
    try:
        r = requests.get(f"{BDL_BASE}/stats",
                         params={"player_ids[]": player_id,
                                 "dates[]": game_date,
                                 "per_page": 10},
                         headers={"Authorization": BDL_API_KEY}, timeout=15)
        if r.status_code != 200:
            _bdl_game_cache[cache_key] = None
            return None
        data = r.json().get("data", [])
        if not data:
            _bdl_game_cache[cache_key] = None
            return None
        # Take first result for that day
        result = data[0]
        _bdl_game_cache[cache_key] = result
        return result
    except Exception:
        _bdl_game_cache[cache_key] = None
        return None


def parse_minutes(m):
    if m is None or m == "":
        return 0.0
    try:
        if isinstance(m, (int, float)):
            return float(m)
        if ":" in str(m):
            parts = str(m).split(":")
            return float(parts[0]) + float(parts[1]) / 60.0
        return float(m)
    except Exception:
        return 0.0


# Canonical schema for every settlement row.
# All settlement dicts MUST have these exact keys before insert,
# otherwise PostgREST rejects the batch with PGRST102.
SETTLEMENT_KEYS = [
    "pick_id", "game_date", "outcome", "actual_value",
    "actual_minutes", "player_played", "game_status",
    "raw_box_score", "notes",
]


def normalize_settlement(row: dict) -> dict:
    """Ensure every settlement row has the same set of keys (fill missing with None)."""
    return {k: row.get(k) for k in SETTLEMENT_KEYS}


def settle_nba_pick(pick: dict, game_date: str) -> dict:
    """Returns settlement row for one NBA pick."""
    player = pick["player"]
    stat = pick["stat"]
    line = pick["line"]
    side = pick["side"]

    pid = bdl_player_id(player)
    if pid is None:
        return {
            "pick_id": pick["id"], "game_date": game_date,
            "outcome": "no_data", "game_status": "player_not_found",
            "player_played": None,
            "notes": f"BDL player lookup failed for {player}",
        }

    box = bdl_box_score(pid, game_date)
    if box is None:
        return {
            "pick_id": pick["id"], "game_date": game_date,
            "outcome": "no_data", "game_status": "no_box_score",
            "player_played": None,
            "notes": "No game played or not posted yet",
        }

    minutes = parse_minutes(box.get("min"))
    if minutes == 0:
        return {
            "pick_id": pick["id"], "game_date": game_date,
            "outcome": "void", "game_status": "dnp",
            "player_played": False, "actual_minutes": 0,
            "raw_box_score": box,
            "notes": "DNP — pick voided",
        }

    # Extract stat value
    stat_map = {"Points": "pts", "Rebounds": "reb", "Assists": "ast",
                "Blocks": "blk", "Steals": "stl", "3PM": "fg3m"}
    col = stat_map.get(stat)
    if col is None:
        return {
            "pick_id": pick["id"], "game_date": game_date,
            "outcome": "no_data", "notes": f"Unknown stat {stat}",
        }

    actual = box.get(col, 0)
    if actual is None:
        actual = 0

    # Compute outcome
    if side == "Over":
        if actual > line:
            outcome = "hit"
        elif actual == line:
            outcome = "push"
        else:
            outcome = "miss"
    else:  # Under
        if actual < line:
            outcome = "hit"
        elif actual == line:
            outcome = "push"
        else:
            outcome = "miss"

    return {
        "pick_id": pick["id"], "game_date": game_date,
        "outcome": outcome, "actual_value": float(actual),
        "actual_minutes": minutes, "player_played": True,
        "game_status": "final", "raw_box_score": box,
        "notes": None,
    }


# ============================================================
# MLB SETTLEMENT
# ============================================================

_mlb_player_cache = {}


def mlb_player_id(name: str):
    if name in _mlb_player_cache:
        return _mlb_player_cache[name]
    season = date.today().year
    try:
        r = requests.get(f"{MLB_STATS_BASE}/sports/1/players",
                         params={"season": season}, timeout=15)
        if r.status_code != 200:
            return None
        target = name.lower().strip()
        people = r.json().get("people", [])
        for p in people:
            if p.get("fullName", "").lower() == target:
                _mlb_player_cache[name] = p["id"]
                return p["id"]
        last = name.split()[-1].lower()
        for p in people:
            if p.get("fullName", "").lower().endswith(last):
                _mlb_player_cache[name] = p["id"]
                return p["id"]
    except Exception:
        pass
    _mlb_player_cache[name] = None
    return None


def ip_to_outs(ip):
    try:
        s = str(ip)
        if "." in s:
            whole, frac = s.split(".")
            return int(whole) * 3 + int(frac)
        return int(float(ip)) * 3
    except Exception:
        return 0


def settle_mlb_pick(pick: dict, game_date: str) -> dict:
    player = pick["player"]
    stat = pick["stat"]
    line = pick["line"]
    side = pick["side"]

    pid = mlb_player_id(player)
    if pid is None:
        return {"pick_id": pick["id"], "game_date": game_date,
                "outcome": "no_data", "game_status": "player_not_found",
                "notes": f"MLB player lookup failed for {player}"}

    pitcher_stats = {"Strikeouts", "Earned Runs", "Outs Recorded",
                     "Hits Allowed", "Walks Issued"}
    group = "pitching" if stat in pitcher_stats else "hitting"

    try:
        r = requests.get(f"{MLB_STATS_BASE}/people/{pid}/stats",
                         params={"stats": "gameLog", "group": group,
                                 "season": date.today().year, "sportId": 1},
                         timeout=15)
        if r.status_code != 200:
            return {"pick_id": pick["id"], "game_date": game_date,
                    "outcome": "no_data", "notes": f"MLB API {r.status_code}"}
        splits = r.json().get("stats", [{}])[0].get("splits", [])
        # Find game on target date
        match = None
        for s in splits:
            if s.get("date") == game_date:
                match = s
                break
        if match is None:
            return {"pick_id": pick["id"], "game_date": game_date,
                    "outcome": "no_data", "game_status": "no_game_found",
                    "notes": f"No game played on {game_date}"}

        stat_obj = match.get("stat", {})
        stat_field_map = {
            "Hits": "hits", "Total Bases": "totalBases", "RBI": "rbi",
            "Runs": "runs", "Home Runs": "homeRuns",
            "Strikeouts": "strikeOuts", "Earned Runs": "earnedRuns",
            "Walks Issued": "baseOnBalls",
        }
        if stat == "Outs Recorded":
            actual = ip_to_outs(stat_obj.get("inningsPitched", 0))
        elif stat == "Hits Allowed":
            actual = stat_obj.get("hits", 0) if group == "pitching" else 0
        else:
            field = stat_field_map.get(stat)
            actual = stat_obj.get(field, 0) if field else 0

        if actual is None:
            actual = 0

        if side == "Over":
            outcome = "hit" if actual > line else ("push" if actual == line else "miss")
        else:
            outcome = "hit" if actual < line else ("push" if actual == line else "miss")

        return {
            "pick_id": pick["id"], "game_date": game_date,
            "outcome": outcome, "actual_value": float(actual),
            "player_played": True, "game_status": "final",
            "raw_box_score": stat_obj, "notes": None,
        }
    except Exception as e:
        return {"pick_id": pick["id"], "game_date": game_date,
                "outcome": "no_data", "notes": f"Exception: {e}"}


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"=== DFS Settlement — {datetime.now().isoformat()} ===")

    # Settle yesterday's picks
    target_date = (date.today() - timedelta(days=1)).isoformat()
    print(f"Target settlement date: {target_date}")

    run_id = log_run_start("settlement")

    picks = fetch_unsettled_picks(target_date)
    print(f"Unsettled picks: {len(picks)}")
    if not picks:
        log_run_end(run_id, "success", 0, 0)
        print("Nothing to settle.")
        return

    settlements = []
    errors = []
    for i, pick in enumerate(picks):
        if i % 25 == 0:
            print(f"  Settling {i}/{len(picks)}...")
        try:
            if pick["league"] == "nba":
                result = settle_nba_pick(pick, target_date)
            else:
                result = settle_mlb_pick(pick, target_date)
            settlements.append(result)
            time.sleep(0.1)  # rate limit
        except Exception as e:
            errors.append(f"pick {pick['id']}: {e}")

    print(f"Settlements built: {len(settlements)}")
    # Normalize every row so all dicts have the same keys (fixes PGRST102)
    normalized = [normalize_settlement(s) for s in settlements]
    written = insert_settlements(normalized)
    print(f"Written to Supabase: {written}")

    # Summary
    outcomes = {}
    for s in settlements:
        outcomes[s["outcome"]] = outcomes.get(s["outcome"], 0) + 1
    print(f"Outcome breakdown: {outcomes}")

    status = "success" if written == len(settlements) else "partial"
    log_run_end(run_id, status, len(picks), written,
                "; ".join(errors[:10]) if errors else None)


if __name__ == "__main__":
    main()
