"""Local per-team capability URLs, native mailbox and real trace acknowledgement.

Not public league authentication. No engine scores or future frames served here.
"""
import secrets,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import native_live as n
from native_roster import plan_from_config,roster_snapshot
class ControlBridge:
    error_type=n.ControlError
    def __init__(self,config,directory,trace,clock=None):
        self.directory=Path(directory).resolve()
        self.directory.mkdir(mode=0o700,exist_ok=False)
        self.tokens=[secrets.token_urlsafe(24),secrets.token_urlsafe(24)]
        self.session=n.Session(config,self.directory,**({"clock":clock} if clock else {}))
        self.tail=n.Tail(trace,self.session)
        self.plans=plan_from_config(config)
    def drain(self):self.tail.drain()
    def close(self):self.session.close()
    def read(self,side):
        state=self.session.read(side)
        frame=state["frame"]
        # Only open play, fresh native frame, no human controller, no final.
        eligible=bool(frame and frame.get("inPlay") is True and not frame.get("setPiece")
            and frame.get("humanGamers")==[0,0] and state["canControl"])
        return {k:state[k] for k in ("side","submittedRevision","appliedRevision","commandState","finalizing")} | {
            "canControl":eligible,"engineMatchMs":frame.get("matchMs") if frame else None,
            "roster":roster_snapshot(frame,self.session.meta["players"],self.plans,side)}
    def submit(self,side,body):
        if not isinstance(body,dict) or body.get("round")!=0 or type(body.get("round")) is not int:
            raise n.ControlError("Geçersiz yerel maç.",400)
        ident,values=n.validate_command(body)
        with self.session.lock:
            # Duplicate retries must remain idempotent even while waiting.
            if ident not in self.session.requests[side] and not self.read(side)["canControl"]:
                raise n.ControlError("Motor şu anda komut kabul etmiyor.")
            return self.session.command(side,ident,values)
    def report(self):
        with self.session.lock:
            return {"submitted":self.session.revisions[:],"applied":self.session.applied[:],
                "formations":self.session.applied_formation[:],"pending":[p is not None for p in self.session.pending],
                "leagueAuthorization":False,"localCapabilityOnly":True}
