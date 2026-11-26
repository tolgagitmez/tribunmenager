"""Read-only native roster projection and strict quarantined half-time evidence.

Do not generate participation, injuries or substitutions in the browser.
"""
import json,math
from pathlib import Path
def require(ok,message):
    if not ok:raise ValueError(message)
def plan_from_config(config):
    source=config.get("nativeSubstitutions", [[],[]])
    require(isinstance(source,list) and len(source)==2,"Invalid substitution plan")
    plans=[]
    for side,changes in enumerate(source):
        require(isinstance(changes,list) and len(changes)<=5,"Invalid substitution count")
        if not changes:continue
        r=config["players" if side==0 else "awayPlayers"]
        starters=config["starters" if side==0 else "awayStarters"]
        reserves=[p for p in r if p["id"] not in starters and p.get("owned") is not False and not (p.get("season") or {}).get("suspended")][:7]
        ids=[p["id"] for p in reserves]
        out_ids=set();in_ids=set()
        for change in changes:
            require(isinstance(change,dict) and set(change)=={"out","in"},"Invalid plan fields")
            a,b=change["out"],change["in"]
            require(a in starters and b in ids and a not in out_ids and b not in in_ids,"Invalid planned identities")
            out_ids.add(a);in_ids.add(b)
            plans.append({"team":side,"out":side*11+starters.index(a)+1,"in":23+side*7+ids.index(b)})
    return plans
def unit(v,lo=0,hi=1):
    return type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi
def decode(code):
    require(type(code) is int and 0<=code<=4,"Invalid native card")
    return (code if code<3 else code-3,code>=2)
def roster_snapshot(frame,metadata,plans,side):
    if not frame or not isinstance(frame.get("participation"),list):
        return {"available":False,"players":[],"changes":[]}
    by_id={p["nativeId"]:p for p in metadata if p["team"]==side}
    if not by_id:return {"available":False,"players":[],"changes":[]}
    try:
        rows={}
        for p in frame["participation"]:
            if p.get("team")!=side:continue
            ident=p.get("databaseId")
            require(type(ident) is int and ident in by_id and ident not in rows,"Unexpected native identity")
            require(type(p.get("active")) is bool and type(p.get("nominalMs")) is int and 0<=p["nominalMs"]<=5400000,"Invalid participation")
            require(unit(p.get("fatigueFactor"),.009,1.001),"Invalid native fatigue")
            injury=p.get("injuryLevel");require(injury is None or unit(injury),"Invalid native injury")
            yellow,red=decode(p.get("cardCode"))
            status="active" if p["active"] else "dismissed" if red else "used" if p["nominalMs"] else "reserve" if by_id[ident]["reserve"] else "inactive"
            rows[ident]={"nativeId":ident,"name":by_id[ident]["name"],"active":p["active"],"nominalMs":p["nominalMs"],
              "fatigueFactor":p["fatigueFactor"],"injuryLevel":injury,"yellow":yellow,"red":red,"status":status}
        require(set(rows)==set(by_id) and sum(p["active"] for p in rows.values())<=11,"Incomplete native roster")
        changes=[]
        for change in plans:
            if change["team"]!=side:continue
            a,b=rows[change["out"]],rows[change["in"]]
            observed=b["nominalMs"]>0 and not a["active"]
            changes.append({"outName":a["name"],"inName":b["name"],"state":"observed" if observed else "not-observed" if frame["matchMs"]>=2700000 else "planned"})
        return {"available":True,"matchMs":frame["matchMs"],"players":list(rows.values()),"changes":changes}
    except (ValueError,KeyError,TypeError):
        return {"available":False,"players":[],"changes":[]}
def verify_halftime(trace,manifest,season):
    manifest=json.loads(Path(manifest).read_text())
    season=json.loads(Path(season).read_text())
    expected={(t["team"],c["out"],c["in"]) for t in manifest["teams"] for c in t.get("substitutions",[])}
    require(expected,"No native substitution plan")
    starters={t["team"]:{p["nativeId"] for p in t["players"]} for t in manifest["teams"]}
    registered={t["team"]:{p["nativeId"] for p in t["players"]+t.get("bench",[])} for t in manifest["teams"]}
    before=set();seen={};last=None;frames=0
    with Path(trace).open() as f:
        for line in f:
            frame=json.loads(line)
            require(frame["engine"]=="league-soccer" and frame["humanGamers"]==[0,0],"Wrong simulation")
            if last:require(not last["done"] and frame["matchMs"]>=last["matchMs"],"Invalid native chronology")
            active={p["databaseId"]:p["team"] for p in frame["players"]}
            require(len(active)==len(frame["players"]),"Duplicate active player")
            require(all(t in (0,1) and p in registered[t] for p,t in active.items()),"Unknown active player")
            require(all(sum(t==side for t in active.values())<=11 for side in (0,1)),"Too many players")
            if frame["fixedClock"]["started"]:
                minute=frame["matchMs"]
                for change in expected:
                    t,a,b=change
                    if minute<2700000 and active.get(a)==t and b not in active:before.add(change)
                    if b in active:
                        require(minute>=2700000 and active[b]==t and a not in active and change in before,"Invalid half-time switch")
                        if change not in seen:seen[change]=minute
                    if change in seen:require(a not in active,"Outgoing player re-entered")
            last=frame;frames+=1
    require(last and last["done"],"Missing final frame")
    require(season.get("done") and season.get("score")==last["score"],"Season result differs")
    require(len(season["substitutions"])==len(expected),"Incomplete season substitution report")
    identity={(t["team"],p["nativeId"]):p["rosterId"] for t in manifest["teams"] for p in t["players"]+t.get("bench",[])}
    reported={(c["team"],c["out"],c["in"]) for c in season["substitutions"] if c["performed"] is True}
    target={(t,identity[t,a],identity[t,b]) for t,a,b in expected}
    require(before==expected and set(seen)==expected and reported==target,"Unobserved native substitution or season mismatch")
    rows=last["participation"]
    require(all(unit(p.get("injuryLevel")) for p in rows),"Missing native injury telemetry")
    return {"allPlannedChangesObserved":True,"frames":frames,"changes":[{"team":t,"out":a,"in":b,"firstObservedMatchMs":seen[t,a,b]} for t,a,b in sorted(expected)],
      "participationVerified":True,"injuryTelemetryVerified":True,"seasonPreviewOnly":True,"liveArbitrarySubstitutions":False}
