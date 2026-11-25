"""Prove the native match actually fielded the selected Tribun IDs."""
import json
import sys

def validate(trace, manifest):
    with open(manifest, encoding="utf-8") as f:
        teams = json.load(f)["teams"]
        starters = {t["team"]: {p["nativeId"] for p in t["players"]} for t in teams}
        expected = {t["team"]: {p["nativeId"] for p in t["players"] + t.get("bench", [])} for t in teams}
    frames = 0
    with open(trace, encoding="utf-8") as f:
        for line in f:
            frame = json.loads(line)
            actual = {team: set() for team in expected}
            for p in frame["players"]:
                actual[p["team"]].add(p["databaseId"])
            if any(not actual[t] <= expected[t] for t in expected):
                raise ValueError("Unexpected upstream database player")
            if actual == starters:
                frames += 1
    if not frames:
        raise ValueError("Both frozen starting elevens never appeared in native match")
    print(f"Native fixture identity verified in {frames} frames")

if __name__ == "__main__":
    validate(*sys.argv[1:])
