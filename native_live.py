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
        self.revisions=[0,0]
        self.last_submit=[-math.inf,-math.inf]
        self.requests=[{},{}]
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
            if self.frame and (frame["elapsedMs"]<self.frame["elapsedMs"] or any(x<y for x,y in zip(score,self.frame["score"]))):
                raise ValueError("Regressing native frame")
            if frame["done"]:
                self.ended=True
                return
            self.frame=frame
            self.sequence+=1
            self.last_received=self.clock()
    def read(self,side):
        with self.lock:
            frame=self.frame
            fresh=self.last_received is not None and self.clock()-self.last_received<5
            can=bool(frame and fresh and not self.ended and frame["matchMs"]<5400000)
            ack=next((x for x in (frame or {}).get("managerTactics",[]) if x.get("team")==side),{})
            return dict(engine="league-soccer",authoritative=False,source="interactive-native",
                state="running",phase="playing" if frame else "waiting",frame=frame,sequence=self.sequence,
                side=side,canControl=can,submittedRevision=self.revisions[side],
                appliedRevision=ack.get("revision",0),finalizing=self.ended,**self.meta)
    def command(self,side,ident,values):
        if type(side) is not int or side not in (0,1):raise ControlError("Takım yetkisi yok.",403)
        with self.lock:
            previous=self.requests[side].get(ident)
            if previous:
                if previous[0]!=values:raise ControlError("Aynı istek kimliği farklı komut içeriyor.")
                return previous[1]
            if not self.read(side)["canControl"]:raise ControlError("Motor şu anda komut kabul etmiyor.")
            if len(self.requests[side])>=120:raise ControlError("Maç komut sınırına ulaşıldı.",429)
            now=self.clock()
            if now-self.last_submit[side]<2:raise ControlError("Komutlar arasında iki saniye bekle.",429)
            if values[-1] and sum(p.get("team")==side for p in self.frame.get("players",[]))!=11:
                raise ControlError("Eksik oyuncuyla diziliş değişikliği desteklenmiyor.")
            revision=self.revisions[side]+1
            reply=mailbox.publish(self.directory,side,revision,self.frame["matchMs"],*values)
            self.revisions[side]=revision
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
