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
    team_ids=set()
    for team in manifest["teams"]:
        t=team["team"]
        require(type(t) is int and t in (0,1) and t not in team_ids and len(team["players"])==11
                and len(team.get("bench",[]))<=7, "Invalid team")
        team_ids.add(t)
        roster_ids=set()
        for p in [*team["players"],*team.get("bench",[])]:
            require(nonnegative(p.get("rosterId")) and p["rosterId"] not in roster_ids,"Duplicate or invalid roster ID")
            roster_ids.add(p["rosterId"])
        for player in [*team["players"], *team.get("bench",[])]:
            ident=player["nativeId"]
            require(type(ident) is int and ident>0 and ident not in expected, "Duplicate native identity")
            expected[ident]=(t,player)
    require(22<=len(expected)<=36, "Expected both starting elevens and valid bench")
    rows=final.get("participation")
    require(isinstance(rows,list) and len(rows)==len(expected), "Missing native participation")
    seen=set()
    identities=set()
    appearances=[]
    cards=[0,0]
    reds=[0,0]
    for row in rows:
        ident=row["databaseId"]
        require(type(ident) is int and ident in expected and ident not in seen, "Unknown or duplicate native player")
        seen.add(ident)
        t,p=expected[ident]
        require(type(row["team"]) is int and row["team"]==t and type(row["active"]) is bool, "Native team mismatch")
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
    substitutions=[]
    by_native={row["databaseId"]:row for row in rows}
    for team in manifest["teams"]:
        starters={p["nativeId"] for p in team["players"]}
        bench={p["nativeId"] for p in team.get("bench",[])}
        used_out=set();used_in=set()
        for change in team.get("substitutions",[]):
            a,b=change["out"],change["in"]
            require(type(a) is int and type(b) is int and a in starters and b in bench and a not in used_out and b not in used_in,"Invalid substitution identities")
            used_out.add(a);used_in.add(b)
            out, incoming=by_native[a],by_native[b]
            performed=incoming["nominalMs"]>0
            if performed:
                require(not out["active"] and out["nominalMs"]>0 and out["nominalMs"]<=2700000 and incoming["nominalMs"]<=2700000
                        and out["nominalMs"]+incoming["nominalMs"]<=5400000, "Invalid halftime substitution timing")
            substitutions.append({"team":team["team"],"out":expected[change["out"]][1]["rosterId"],"in":expected[change["in"]][1]["rosterId"],"performed":performed})
        for ident in bench-used_in:
            require(by_native[ident]["nominalMs"]==0 and not by_native[ident]["active"],"Unplanned bench participation")
        for ident in starters:
            require(by_native[ident]["nominalMs"]>0,"Missing starter participation")
        require(sum(by_native[ident]["nominalMs"] for ident in starters|bench)<=11*5400000,"Excess team minutes")
    # Guard against a wrong native clock/timing hook silently reporting zero minutes.
    for team in (0,1):
        require(max(a["minutes"] for a in appearances if a["team"]==team)>=89.5, "Missing full-match minutes")
    return {"schema":1,"engine":"league-soccer","authoritative":False,"done":True,"score":score,
            "cards":cards,"reds":reds,"appearances":appearances,"substitutions":substitutions}

def verify_report(final,manifest,report):
    """Recompute every season field; do not trust a score-only sidecar."""
    expected=candidate(final,manifest)
    require(isinstance(report,dict),"Invalid season report")
    supplied={k:v for k,v in report.items() if k!="seasonPreview"}
    require(json.dumps(supplied,sort_keys=True,allow_nan=False)==json.dumps(expected,sort_keys=True,allow_nan=False),
            "Native season report differs from recorded participation")
    require(report.get("seasonPreview")==preview(expected),"Native season preview mismatch")
    return expected

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
