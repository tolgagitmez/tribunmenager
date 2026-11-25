"""Convert real native participation to the existing season appearance contract.

Only a candidate report; never writes the live league database.
"""
import argparse
import json
import math
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import season_state

def require(ok, message):
    if not ok:
        raise ValueError(message)

def nonnegative(value):
    return type(value) is int and value >= 0

def decode_cards(code):
    # Pinned Player::GiveYellowCard adds 1; GiveRedCard adds 3.
    require(type(code) is int and 0 <= code <= 4, "Unsupported native card code")
    return (code if code < 3 else code - 3, code >= 2)

def candidate(final, manifest):
    require(final.get("engine") == "league-soccer" and final.get("done") is True
            and final.get("matchMs", 0) >= 5400000, "Complete regulation match required")
    score = final.get("score")
    require(isinstance(score,list) and len(score)==2 and all(nonnegative(n) for n in score), "Invalid score")
    require(manifest.get("schema")==1 and len(manifest.get("teams",[]))==2, "Invalid fixture manifest")
    expected = {}
    for team in manifest["teams"]:
        t=team["team"]
        require(type(t) is int and t in (0,1) and len(team["players"])==11, "Invalid team")
        for player in team["players"]:
            ident=player["nativeId"]
            require(type(ident) is int and ident not in expected, "Duplicate native identity")
            expected[ident]=(t,player)
    require(len(expected)==22, "Expected both starting elevens")
    rows=final.get("participation")
    require(isinstance(rows,list) and len(rows)==22, "Missing native participation")
    seen=set()
    identities=set()
    appearances=[]
    cards=[0,0]
    reds=[0,0]
    for row in rows:
        ident=row["databaseId"]
        require(ident in expected and ident not in seen, "Unknown or duplicate native player")
        seen.add(ident)
        t,p=expected[ident]
        require(row["team"]==t and type(row["active"]) is bool, "Native team mismatch")
        identity=season_state.player_key({"uid":p.get("rosterUid"),"id":p["rosterId"]})
        require((t,identity) not in identities, "Duplicate season identity")
        identities.add((t,identity))
        yellow,red=decode_cards(row["cardCode"])
        nominal,active,sprint=(row[k] for k in ("nominalMs","activeMs","sprintMs"))
        require(all(nonnegative(n) for n in (nominal,active,sprint)) and nominal<=5400000
                and sprint<=active and (not nominal or active>0), "Invalid participation duration")
        require(nominal>0 or not (yellow or red), "Zero-minute discipline needs explicit policy")
        require(not (red and row["active"]), "Dismissal not yet effective")
        factor=row["fatigueFactor"]
        before=p["startFitness"]
        require(type(factor) in (int,float) and math.isfinite(factor) and .009<=factor<=1.001
                and type(before) in (int,float) and math.isfinite(before) and 0<=before<=100, "Invalid fatigue")
        cards[t]+=yellow
        reds[t]+=int(red)
        appearances.append({"team":t,"rosterId":p["rosterId"],"rosterUid":p.get("rosterUid"),
            "minutes":nominal/60000,"seconds":active/1000,"sprintSeconds":sprint/1000,
            "yellow":yellow,"red":red,"startFitness":before,"nativeFatigueFactor":factor})
    require(seen==set(expected), "Incomplete lineups")
    # Guard against a wrong native clock/timing hook silently reporting zero minutes.
    for team in (0,1):
        require(max(a["minutes"] for a in appearances if a["team"]==team)>=89.5, "Missing full-match minutes")
    return {"schema":1,"engine":"league-soccer","authoritative":False,"done":True,"score":score,
            "cards":cards,"reds":reds,"appearances":appearances}

def preview(state):
    """Exercise the real idempotent season writer in a disposable SQLite DB."""
    with sqlite3.connect(":memory:") as db:
        db.row_factory=sqlite3.Row
        db.executescript(season_state.SCHEMA)
        key=("NATIVE-PREVIEW",0,0,1)
        season_state.apply_fixture(db,key,state["appearances"])
        return [dict(r) for r in db.execute("""SELECT slot,player_key,minutes,yellows,red,
            fitness_before,fitness_after FROM season_fixture_appearances ORDER BY slot,player_key""")]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("trace")
    parser.add_argument("manifest")
    parser.add_argument("output")
    args=parser.parse_args()
    with open(args.trace,encoding="utf-8") as handle:
        final=None
        for line in handle:
            if line.strip(): final=json.loads(line)
    manifest=json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    state=candidate(final or {},manifest)
    state["seasonPreview"]=preview(state)
    Path(args.output).write_text(json.dumps(state,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
