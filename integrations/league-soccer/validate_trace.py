"""Reject empty, synthetic-schema or truncated native pilot recordings."""
import json
import math
import sys

def check(condition, message):
    if not condition:
        raise ValueError(message)

def vector(v):
    return isinstance(v, list) and len(v) == 3 and all(
        type(x) in (int, float) and math.isfinite(x) for x in v)

def validate(path):
    count = 0
    last = None
    moving = False
    full_lineup = False
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            frame = json.loads(line)
            check(frame["schema"] == 1 and frame["engine"] == "league-soccer", "wrong schema")
            check(type(frame["done"]) is bool, "invalid final flag")
            for field in ("elapsedMs", "matchMs"):
                check(type(frame[field]) is int and frame[field] >= 0, "invalid clock")
            check(len(frame["score"]) == 2 and all(type(x) is int and x >= 0 for x in frame["score"]), "invalid score")
            check(vector(frame["ball"]) and vector(frame["ballVelocity"]), "invalid ball")
            players = frame["players"]
            ids = set()
            teams = [0, 0]
            for player in players:
                check(type(player["id"]) is int and player["id"] not in ids, "duplicate/invalid player ID")
                ids.add(player["id"])
                check(type(player["team"]) is int and player["team"] in (0, 1), "invalid team")
                teams[player["team"]] += 1
                check(all(vector(player[field]) for field in ("position", "velocity", "direction")), "invalid player vector")
            check(all(1 <= n <= 11 for n in teams), "invalid active team size")
            full_lineup |= teams == [11, 11]
            if last is not None:
                check(not last["done"], "data after final frame")
                check(frame["elapsedMs"] >= last["elapsedMs"], "elapsed clock reversed")
                check(all(a >= b for a, b in zip(frame["score"], last["score"])), "score reversed")
                moving |= frame["ball"] != last["ball"]
            last = frame
            count += 1
    check(count > 100 and moving and full_lineup, "insufficient live simulation")
    check(last["done"] and last["matchMs"] >= 90 * 60 * 1000, "no full-time frame")
    print(f"Native trace OK: {count} frames; final score {last['score']}")
    return count

if __name__ == "__main__":
    validate(sys.argv[1])
