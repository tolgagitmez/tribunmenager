"""Quota-bounded current-squad catalog. Local only; never logs raw provider data."""
import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from tools.api_football_probe import request, ProbeError

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "work" / "api-football"
POSITIONS = {"Goalkeeper": "GK", "Defender": "DEF", "Midfielder": "MID", "Attacker": "ATT"}
MAX_TEAMS = 20
RESERVE = 5

def positive(value):
    return type(value) is int and value > 0

def name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 150 or any(ord(c) < 32 for c in value):
        raise ProbeError("invalid name field")
    return value.strip()

def optional_int(value, lo, hi):
    return value if type(value) is int and lo <= value <= hi else None

def normalize_squad(team_id, payload, fetched_at):
    if not positive(team_id) or not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise ProbeError("invalid squad envelope")
    item = payload[0]
    team, players = item.get("team"), item.get("players")
    if not isinstance(team, dict) or team.get("id") != team_id or not isinstance(players, list) or not 11 <= len(players) <= 150:
        raise ProbeError("invalid or incomplete squad")
    result = []
    seen = set()
    for p in players:
        if not isinstance(p, dict) or not positive(p.get("id")) or p["id"] in seen:
            raise ProbeError("invalid or duplicate player identity")
        seen.add(p["id"])
        pos = POSITIONS.get(p.get("position"))
        result.append({"providerId": p["id"], "uid": f"api-football:player:{p['id']}", "name": name(p.get("name")),
                       "age": optional_int(p.get("age"), 14, 70), "number": optional_int(p.get("number"), 1, 99),
                       "pos": pos, "preferredFoot": "unknown", "rating": None,
                       "source": "api-football", "skillSource": "unavailable"})
    if sum(p["pos"] is not None for p in result) < 11 or not any(p["pos"] == "GK" for p in result):
        raise ProbeError("squad lacks a playable minimum or goalkeeper")
    return {"schema": 1, "source": "api-football", "teamId": team_id, "teamUid": f"api-football:team:{team_id}",
            "name": name(team.get("name")), "fetchedAt": fetched_at, "players": sorted(result, key=lambda p: p["providerId"])}

class Catalog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS current_squads (team_id INTEGER PRIMARY KEY, fetched_at TEXT NOT NULL, snapshot TEXT NOT NULL)")
    def connect(self):
        return sqlite3.connect(self.path, timeout=15)
    def read(self, team_id):
        with self.connect() as con:
            row = con.execute("SELECT snapshot FROM current_squads WHERE team_id=?", (team_id,)).fetchone()
        return json.loads(row[0]) if row else None
    def write_batch(self, snapshots):
        # Commit all requested valid squads together, or none. Older snapshots cannot replace newer ones.
        if len({s["teamId"] for s in snapshots}) != len(snapshots):
            raise ProbeError("duplicate team in batch")
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            for s in snapshots:
                old = con.execute("SELECT fetched_at FROM current_squads WHERE team_id=?", (s["teamId"],)).fetchone()
                if old and old[0] >= s["fetchedAt"]:
                    raise ProbeError("stale snapshot")
                con.execute("INSERT INTO current_squads VALUES (?, ?, ?) ON CONFLICT(team_id) DO UPDATE SET fetched_at=excluded.fetched_at,snapshot=excluded.snapshot",
                            (s["teamId"], s["fetchedAt"], json.dumps(s, ensure_ascii=False, separators=(",", ":"))))
    def export(self, team_id, path):
        data = self.read(team_id)
        if data is None:
            raise ProbeError("team has no local snapshot")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".roster-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(data, out, ensure_ascii=False, indent=2)
                out.write("\n")
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

def sync(key, team_ids, *, catalog=None, transport=request, wait=time.sleep, now=None):
    if not key or not key.strip():
        raise ProbeError("API_FOOTBALL_KEY is missing")
    ids = list(team_ids)
    if not 1 <= len(ids) <= MAX_TEAMS or len(set(ids)) != len(ids) or not all(positive(i) for i in ids):
        raise ProbeError("provide 1-20 distinct positive team IDs")
    status, header = transport(key, "status", {})
    if not isinstance(status, dict) or (status.get("subscription") or {}).get("active") is not True:
        raise ProbeError("inactive or invalid subscription")
    quota = status.get("requests") or {}
    used, limit = quota.get("current"), quota.get("limit_day")
    if type(used) is not int or type(limit) is not int or not 0 <= used <= limit:
        raise ProbeError("unknown quota")
    remaining = min(limit - used, header) if header is not None else limit - used
    if remaining < len(ids) + RESERVE:
        raise ProbeError("insufficient quota with reserve")
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="microseconds")
    snapshots = []
    for team in ids:
        if remaining <= RESERVE:
            raise ProbeError("daily reserve reached; batch not saved")
        wait(7)  # fewer than 10 requests/minute for this importer; no automatic retries
        payload, header = transport(key, "players/squads", {"team": team})
        remaining = min(remaining - 1, header) if header is not None else remaining - 1
        snapshots.append(normalize_squad(team, payload, stamp))
    if catalog is not None:
        catalog.write_batch(snapshots)
    return {"teams": len(snapshots), "players": sum(len(s["players"]) for s in snapshots),
            "requestsAttempted": len(ids) + 1, "remaining": remaining, "stored": catalog is not None}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--team", type=int, action="append", help="verified provider ID; repeat for up to 20 teams")
    action.add_argument("--export-team", type=int, help="export one locally stored squad")
    parser.add_argument("--store", action="store_true", help="persist to ignored local work directory")
    parser.add_argument("--rights-confirmed", action="store_true", help="operator confirms authorization for local storage/use")
    args = parser.parse_args()
    if (args.store or args.export_team is not None) and not args.rights_confirmed:
        parser.error("local persistence/export requires confirmed data rights")
    if args.export_team is not None and args.store:
        parser.error("--store applies to sync only")
    if args.export_team is not None and not positive(args.export_team):
        parser.error("invalid team ID")
    try:
        catalog = Catalog(LOCAL / "catalog.sqlite3") if args.store or args.export_team is not None else None
        if args.export_team is not None:
            catalog.export(args.export_team, LOCAL / f"team-{args.export_team}.json")
            print("Local roster export created in ignored work directory.")
        else:
            print(json.dumps(sync(os.environ.get("API_FOOTBALL_KEY", ""), args.team, catalog=catalog)))
        return 0
    except ProbeError as exc:
        print(f"Catalog operation failed: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("Catalog operation failed: local or provider error.", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
