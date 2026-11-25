"""Strict evidence gate for experimental native halftime changes."""
import json
import sys
from pathlib import Path

def verify(frames,manifest):
    planned={t["team"]:t.get("substitutions",[]) for t in manifest["teams"]}
    if not all(planned.get(t) for t in (0,1)):
        raise ValueError("Expected planned changes on both teams")
    seen_before=set()
    seen_after=set()
    last=None
    for f in frames:
        active={p["databaseId"]:p["team"] for p in f["players"]}
        if len(active)!=len(f["players"]):raise ValueError("Duplicate active identity")
        if any(sum(t==team for t in active.values())>11 for team in (0,1)):
            raise ValueError("Too many active players")
        minute=f["matchMs"]
        for team,changes in planned.items():
            for c in changes:
                out,inc=c["out"],c["in"]
                if inc in active:
                    if minute<2700000 or active[inc]!=team or out in active:
                        raise ValueError("Premature or overlapping substitution")
                    seen_after.add((team,out,inc))
                if minute<2700000 and active.get(out)==team and inc not in active:
                    seen_before.add((team,out,inc))
                if (team,out,inc) in seen_after and out in active:
                    raise ValueError("Outgoing player re-entered")
        last=f
    expected={(t,c["out"],c["in"]) for t,changes in planned.items() for c in changes}
    if not last or last.get("done") is not True or seen_before!=expected or seen_after!=expected:
        raise ValueError("Missing observed substitutions or full-time")
    print("Verified native halftime changes:",sorted(expected))

if __name__=="__main__":
    trace,manifest=map(Path,sys.argv[1:])
    with trace.open() as f:verify((json.loads(line) for line in f if line.strip()),json.loads(manifest.read_text()))
