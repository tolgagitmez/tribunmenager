"""Minimal read-only API-Football access probe; never print credentials or raw payloads."""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

BASE = "https://v3.football.api-sports.io/"
MAX_REQUESTS = 3

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class ProbeError(Exception):
    pass

def request(key, endpoint, params):
    url = BASE + endpoint + ("?" + urlencode(params) if params else "")
    req = Request(url, headers={"x-apisports-key": key, "Accept": "application/json"})
    try:
        with build_opener(NoRedirect()).open(req, timeout=20) as res:
            data = res.read(2_000_001)
            if len(data) > 2_000_000:
                raise ProbeError("response too large")
            payload = json.loads(data)
            remaining = res.headers.get("x-ratelimit-requests-remaining")
    except HTTPError as exc:
        raise ProbeError(f"HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ProbeError("network or invalid JSON response") from None
    if not isinstance(payload, dict):
        raise ProbeError("invalid response envelope")
    if payload.get("errors"):
        # Provider error values can contain input data; only fixed classifications.
        errors = payload["errors"]
        labels = set(errors) if isinstance(errors, dict) else set()
        reason = "plan/season restriction" if "plan" in labels or "season" in labels else "provider rejected request"
        raise ProbeError(reason)
    return payload.get("response"), int(remaining) if remaining and remaining.isdecimal() else None

def probe(key, transport=request):
    if not key or not key.strip():
        raise ProbeError("API_FOOTBALL_KEY is missing")
    calls = 0
    remaining = None
    def call(endpoint, params):
        nonlocal calls, remaining
        if calls >= MAX_REQUESTS or (remaining is not None and remaining < 1):
            raise ProbeError("request budget exhausted")
        calls += 1
        result, header_remaining = transport(key, endpoint, params)
        if header_remaining is not None:
            remaining = header_remaining
        elif remaining is not None:
            remaining -= 1
        return result
    status = call("status", {})
    if not isinstance(status, dict):
        raise ProbeError("unexpected status response")
    subscription = status.get("subscription") or {}
    quota = status.get("requests") or {}
    if subscription.get("active") is not True:
        raise ProbeError("subscription is not active")
    used, limit = quota.get("current"), quota.get("limit_day")
    if type(used) is not int or type(limit) is not int or not (0 <= used <= limit <= 10_000_000):
        raise ProbeError("unknown daily quota; refusing additional calls")
    remaining = min(remaining, limit-used) if remaining is not None else limit-used
    print(f"Subscription active; daily requests used={used}, limit={limit}.")
    squads = call("players/squads", {"team": 33})
    if not isinstance(squads, list) or len(squads) != 1 or not isinstance(squads[0], dict):
        raise ProbeError("unexpected squad response")
    team = squads[0].get("team") or {}
    players = squads[0].get("players")
    if team.get("id") != 33 or not isinstance(players, list) or not players:
        raise ProbeError("no valid squad returned")
    ids = [p.get("id") for p in players if isinstance(p, dict)]
    if len(ids) != len(players) or any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) != len(ids):
        raise ProbeError("invalid or duplicate player IDs")
    print(f"Current squad endpoint accessible: {len(players)} player records (no personal data logged).")
    try:
        teams = call("teams", {"league": 39, "season": 2026})
        if not isinstance(teams, list) or not teams:
            raise ProbeError("no team records for requested season")
        print(f"2026 Premier League season endpoint accessible: {len(teams)} team records.")
    except ProbeError as exc:
        print(f"2026 season check unavailable: {exc}. Current squad access remains confirmed.")
    print(f"Probe completed; calls attempted={calls}, estimated remaining={remaining}.")

def main():
    try:
        probe(os.environ.get("API_FOOTBALL_KEY", ""))
    except ProbeError as exc:
        print(f"Access probe failed: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("Access probe failed: unexpected response or local error.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
