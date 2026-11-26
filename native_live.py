"""Isolated interactive native pilot, one server process per database.

Only observed frames are exposed; final frame is released after archive validation.
Interrupted interactive matches fail closed instead of replaying lost commands.
"""
import importlib.util
import json
import math
from pathlib import Path
import re
import threading
import time

spec=importlib.util.spec_from_file_location("native_mailbox",Path(__file__).resolve().parent/"integrations/league-soccer/manager-control.py")
mailbox=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mailbox)

FIELDS=("press","counter","support","width","tempo","formation")
SCHEMA="""CREATE TABLE IF NOT EXISTS native_interactive_matches(
    league TEXT NOT NULL,round INTEGER NOT NULL,home INTEGER NOT NULL,away INTEGER NOT NULL,
    PRIMARY KEY(league,round,home,away)
);"""
KEY="league=? AND round=? AND home=? AND away=?"

class ControlError(ValueError):
    def __init__(self,message,status=409):
        super().__init__(message)
        self.status=status

def is_interactive(db,key):
    return db.execute(f"SELECT 1 FROM native_interactive_matches WHERE {KEY}",key).fetchone() is not None

def validate_command(body):
    if not isinstance(body,dict) or set(body)!={"round","requestId","tactics"}:
        raise ControlError("Geçersiz taktik isteği.",400)
    ident=body["requestId"]
    if not isinstance(ident,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}",ident):
        raise ControlError("Geçersiz istek kimliği.",400)
    values=body["tactics"]
    if not isinstance(values,dict) or set(values)!=set(FIELDS):
        raise ControlError("Tüm taktik alanları gerekli.",400)
    if any(type(values[k]) is not int or not 0<=values[k]<=100 for k in FIELDS[:-1]):
        raise ControlError("Taktikler 0–100 arasında olmalı.",400)
    if type(values["formation"]) is not int or values["formation"] not in (0,433,442,4231):
        raise ControlError("Desteklenmeyen diziliş.",400)
    return ident,tuple(values[k] for k in FIELDS)

def metadata(config):
    players=[]
    for team,rk,sk in ((0,"players","starters"),(1,"awayPlayers","awayStarters")):
        roster=config.get(rk,[])
        by_id={p["id"]:p for p in roster}
        starters=config.get(sk,[])
        selected=[(team*11+i+1,i,by_id.get(pid,{}),False) for i,pid in enumerate(starters)]
        reserves=[p for p in roster if p["id"] not in starters and p.get("owned") is not False and not (p.get("season") or {}).get("suspended")][:7]
        selected += [(23+team*7+i,11+i,p,True) for i,p in enumerate(reserves)]
        for ident,slot,p,reserve in selected:
            players.append(dict(nativeId=ident,slot=slot,team=team,name=p.get("name",""),
                number=p.get("number",slot+1),position=p.get("subposition") or p.get("pos"),
                rating=p.get("rating"),startFitness=p.get("fitness"),reserve=reserve))
    return dict(players=players,homeName=config.get("homeName","Ev sahibi"),awayName=config.get("awayName","Deplasman"))

class Session:
    def __init__(self,config,directory,clock=time.monotonic):
        self.meta=metadata(config)
        self.directory=directory
        self.clock=clock
        self.lock=threading.RLock()
        self.frame=None
        self.sequence=-1
        self.ended=False
        self.last_received=None
        self.first_open=None
        self.final_received=None
        self.first_native_elapsed=None
        self.final_native_elapsed=None
        self.revisions=[0,0]
        self.last_submit=[-math.inf,-math.inf]
        self.requests=[{},{}]
        self.applied=[0,0]
        self.applied_formation=[0,0]
        self.pending=[None,None]
    def ingest(self,frame):
        with self.lock:
            if self.ended:raise ValueError("Trace continued after final")
            if frame.get("schema")!=1 or frame.get("engine")!="league-soccer":
                raise ValueError("Wrong live engine schema")
            if type(frame.get("done")) is not bool or any(type(frame.get(k)) is not int or frame[k]<0 for k in ("elapsedMs","matchMs")):
                raise ValueError("Invalid native clock")
            score=frame.get("score")
            if not isinstance(score,list) or len(score)!=2 or any(type(v) is not int or v<0 for v in score):
                raise ValueError("Invalid native score")
            if self.frame and (frame["elapsedMs"]<self.frame["elapsedMs"] or frame["matchMs"]<self.frame["matchMs"] or any(x<y for x,y in zip(score,self.frame["score"]))):
                raise ValueError("Regressing native frame")
            self.verify_acknowledgements(frame)
            observed=self.clock()
            if self.first_open is None and frame.get("inPlay") is True and frame["matchMs"]<2700000 and not frame["done"]:
                self.first_open=observed
                self.first_native_elapsed=frame["elapsedMs"]
            if frame["done"]:
                self.ended=True
                self.final_received=observed
                self.final_native_elapsed=frame["elapsedMs"]
                return
            self.frame=frame
            self.sequence+=1
            self.last_received=self.clock()
    def verify_acknowledgements(self,frame):
        # The mailbox is not an acknowledgement. Only a matching trace
        # revision and values can release the one-command-per-team gate.
        rows=frame.get("managerTactics")
        if rows is None:
            if any(self.revisions):raise ValueError("Missing native command acknowledgements")
            return
        if not isinstance(rows,list) or len(rows)!=2 or any(not isinstance(a,dict) or type(a.get("team")) is not int for a in rows) or {a["team"] for a in rows}!={0,1}:
            raise ValueError("Invalid native acknowledgement teams")
        updates=[]
        for ack in rows:
            side=ack["team"];rev=ack.get("revision")
            if type(rev) is not int or not self.applied[side]<=rev<=self.revisions[side]:
                raise ValueError("Unexpected native acknowledgement revision")
            if rev==self.applied[side]:continue
            pending=self.pending[side]
            if not pending or rev!=pending["revision"]:raise ValueError("Unknown native acknowledgement")
            values=pending["values"]
            formation=values[-1] or self.applied_formation[side]
            if any(type(ack.get(k)) is not int or ack[k]!=v for k,v in zip(FIELDS,(*values[:-1],formation))):
                raise ValueError("Native acknowledgement values differ")
            match_ms,elapsed_ms=ack.get("appliedMatchMs"),ack.get("appliedElapsedMs")
            if type(match_ms) is not int or not pending["earliest"]<=match_ms<=frame["matchMs"] or type(elapsed_ms) is not int or not pending["elapsed"]<=elapsed_ms<=frame["elapsedMs"]:
                raise ValueError("Invalid acknowledgement time")
            updates.append((side,rev,formation))
        # Validate both teams before committing any state.
        for side,rev,formation in updates:
            self.applied[side]=rev;self.applied_formation[side]=formation;self.pending[side]=None
    def close(self):
        with self.lock:self.ended=True
    def timing(self):
        with self.lock:
            if self.first_open is None or self.final_received is None:
                return {"targetMs":300000,"observedWallMs":None,"withinFiveSeconds":False}
            observed=round((self.final_received-self.first_open)*1000)
            return {"targetMs":300000,"observedWallMs":observed,
                    "nativeElapsedMs":self.final_native_elapsed-self.first_native_elapsed,
                    "deviationMs":observed-300000,"withinFiveSeconds":abs(observed-300000)<=5000}
    def read(self,side):
        with self.lock:
            frame=self.frame
            fresh=self.last_received is not None and self.clock()-self.last_received<5
            can=bool(frame and fresh and not self.ended and frame["matchMs"]<5400000)
            waiting=self.pending[side] is not None
            pending_state="not-applied-at-end" if waiting and self.ended else "waiting-for-engine" if waiting else "applied" if self.applied[side] else "idle"
            return dict(engine="league-soccer",authoritative=False,source="interactive-native",
                state="running",phase="playing" if frame else "waiting",frame=frame,sequence=self.sequence,
                side=side,canControl=can and not waiting,submittedRevision=self.revisions[side],
                appliedRevision=self.applied[side],commandState=pending_state,finalizing=self.ended,
                observedWallMs=None if self.first_open is None else max(0,round(((self.final_received if self.final_received is not None else self.clock())-self.first_open)*1000)),**self.meta)
    def command(self,side,ident,values):
        if type(side) is not int or side not in (0,1):raise ControlError("Takım yetkisi yok.",403)
        with self.lock:
            previous=self.requests[side].get(ident)
            if previous:
                if previous[0]!=values:raise ControlError("Aynı istek kimliği farklı komut içeriyor.")
                return previous[1]
            if self.pending[side] is not None:raise ControlError("Önceki komutun motor onayı bekleniyor.")
            if not self.read(side)["canControl"]:raise ControlError("Motor şu anda komut kabul etmiyor.")
            if len(self.requests[side])>=120:raise ControlError("Maç komut sınırına ulaşıldı.",429)
            now=self.clock()
            if now-self.last_submit[side]<2:raise ControlError("Komutlar arasında iki saniye bekle.",429)
            if values[-1] and sum(p.get("team")==side for p in self.frame.get("players",[]))!=11:
                raise ControlError("Eksik oyuncuyla diziliş değişikliği desteklenmiyor.")
            revision=self.revisions[side]+1
            reply=mailbox.publish(self.directory,side,revision,self.frame["matchMs"],*values)
            self.revisions[side]=revision
            self.pending[side]={"revision":revision,"values":values,"earliest":self.frame["matchMs"],"elapsed":self.frame["elapsedMs"]}
            self.last_submit[side]=now
            self.requests[side][ident]=(values,reply)
            return reply

class Tail:
    def __init__(self,path,session):
        self.path=Path(path)
        self.session=session
        self.offset=0
    def drain(self):
        if not self.path.exists():return
        with self.path.open("rb") as f:
            if f.seek(0,2)<self.offset:raise ValueError("Native trace truncated")
            f.seek(self.offset)
            while True:
                line=f.readline(262145)
                if len(line)>262144:raise ValueError("Native frame too large")
                if not line.endswith(b"\n"):break
                self.session.ingest(json.loads(line))
                self.offset=f.tell()

_lock=threading.Lock()
_sessions={}
def register(key,session):
    with _lock:
        if key in _sessions:raise RuntimeError("Duplicate interactive session")
        _sessions[key]=session
def lookup(key):
    with _lock:return _sessions.get(key)
def remove(key):
    with _lock:_sessions.pop(key,None)
