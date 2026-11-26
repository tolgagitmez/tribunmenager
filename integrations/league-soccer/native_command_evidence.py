"""Independently verify actual native command acknowledgements and formation targets.

Only the native trace provides evidence. No new football decisions or motion.
"""
import json,math
from pathlib import Path
FIELDS=("press","counter","support","width","tempo","formation")
SLOTS={
    433:[(-24,23),(-28,8),(-28,-8),(-24,-23),(-2,15),(-8,0),(-2,-15),(23,22),(28,0),(23,-22)],
    442:[(-25,23),(-28,8),(-28,-8),(-25,-23),(-1,23),(-5,8),(-5,-8),(-1,-23),(25,8),(25,-8)],
    4231:[(-25,23),(-28,8),(-28,-8),(-25,-23),(-9,9),(-9,-9),(13,22),(13,0),(13,-22),(27,0)]
}
def require(ok,message):
    if not ok:raise ValueError(message)
def formation_targets(frame,side,formation):
    field=[p for p in frame["players"] if p["team"]==side and p.get("goalkeeper") is False]
    keepers=[p for p in frame["players"] if p["team"]==side and p.get("goalkeeper") is True]
    require(len(field)==10 and len(keepers)==1,"Formation requires ten field players and one keeper")
    require(len({p["databaseId"] for p in field+keepers})==11,"Duplicate native player")
    targets=[]
    for p in field:
        v=p["formationTarget"]
        require(isinstance(v,list) and len(v)==3 and all(type(x) in (int,float) and math.isfinite(x) for x in v),"Invalid native formation target")
        x,y,z=v[0]*52.5,v[1]*34,v[2]
        require(abs(x-round(x))<.02 and abs(y-round(y))<.02 and abs(z)<.02,"Nonmatching native slot")
        targets.append((round(x),round(y)))
    require(sorted(targets)==sorted(SLOTS[formation]),"Native formation coordinates differ")
    return True
def audit_frames(frames,requests):
    expected={}
    for req in requests:
        key=(req["team"],req["revision"])
        require(key not in expected and key[0] in (0,1) and type(key[1]) is int and key[1]>0,"Invalid requested revision")
        require(set(req["values"])==set(FIELDS),"Missing command values")
        expected[key]=req
    revisions=[0,0];formations=[0,0];seen={};last=None
    for frame in frames:
        require(frame.get("engine")=="league-soccer","Wrong command evidence engine")
        if last is not None:
            require(not last["done"] and frame["matchMs"]>=last["matchMs"] and frame["elapsedMs"]>=last["elapsedMs"],"Invalid command trace chronology")
        rows=frame["managerTactics"]
        require(len(rows)==2 and {a["team"] for a in rows}=={0,1},"Invalid acknowledgement teams")
        for ack in rows:
            side=ack["team"];rev=ack["revision"]
            require(type(rev) is int and revisions[side]<=rev<=revisions[side]+1,"Invalid acknowledgement sequence")
            if rev==revisions[side]:
                if rev:
                    previous=seen[(side,rev)]
                    require(all(ack[k]==previous["values"][k] for k in FIELDS) and ack["appliedMatchMs"]==previous["appliedMatchMs"] and ack["appliedElapsedMs"]==previous["appliedElapsedMs"],"Acknowledged command mutated")
                continue
            key=(side,rev);require(key in expected,"Unrequested native acknowledgement")
            req=expected[key];values=req["values"];formation=values["formation"] or formations[side]
            actual={k:ack[k] for k in FIELDS}
            require(actual=={**values,"formation":formation},"Native acknowledgement values differ")
            require(req["earliestMatchMs"]<=ack["appliedMatchMs"]<=frame["matchMs"] and 0<=ack["appliedElapsedMs"]<=frame["elapsedMs"],"Invalid native acknowledgement time")
            verified=formation_targets(frame,side,formation) if values["formation"] else None
            seen[key]={"team":side,"revision":rev,"values":actual,"appliedMatchMs":ack["appliedMatchMs"],"appliedElapsedMs":ack["appliedElapsedMs"],
                "firstObservedMatchMs":frame["matchMs"],"formationTargetsVerified":verified}
            revisions[side]=rev;formations[side]=formation
        last=frame
    require(last is not None and last["done"] is True,"Missing final native command frame")
    return {"consistent":True,"allSubmittedObserved":set(expected)==set(seen),
        "acknowledgements":[seen[k] for k in sorted(seen)],"unobserved":[{"team":t,"revision":r} for t,r in sorted(set(expected)-set(seen))],
        "note":"Verified acknowledged values and formation target coordinates, not player movement or tactical effectiveness."}
def audit_commands(path,requests):
    with Path(path).open() as handle:return audit_frames((json.loads(line) for line in handle if line.strip()),requests)
