"""Trusted local control mailbox for a single running native pilot process.

No HTTP access, no user authentication claims, no production league mutation.
Latest revision per team wins; the trace is the only applied acknowledgement.
"""
import argparse
import fcntl
import os
from pathlib import Path
import tempfile

MAX_REVISION = 1_000_000

def publish(directory, team, revision, earliest_ms, press, counter, support, width, tempo=50, formation=0):
    if type(team) is not int or team not in (0,1):
        raise ValueError("Invalid team")
    if type(revision) is not int or not 1 <= revision <= MAX_REVISION:
        raise ValueError("Invalid revision")
    if type(earliest_ms) is not int or not 0 <= earliest_ms < 5_400_000:
        raise ValueError("Invalid earliest regulation time")
    values=(press,counter,support,width,tempo)
    if type(formation) is not int or formation not in (0,433,442,4231):
        raise ValueError("Unsupported formation")
    if any(type(v) is not int or not 0 <= v <= 100 for v in values):
        raise ValueError("Tactics must be integer values 0–100")
    directory=Path(directory).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("Command directory required")
    dest=directory/f"team-{team}.txt"
    # A per-team lock serializes cooperating writers. Native reads atomic rename.
    with (directory/f"team-{team}.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if dest.exists():
            parts=dest.read_text(encoding="ascii").split()
            if (len(parts),parts[0] if parts else "") not in ((7,"TRIBUNTACTIC1"),(9,"TRIBUNTACTIC2")):
                raise ValueError("Malformed existing command")
            if revision<=int(parts[1]):
                raise ValueError("Revision must increase")
        with tempfile.NamedTemporaryFile(mode="w",encoding="ascii",dir=directory,delete=False) as handle:
            temp=Path(handle.name)
            try:
                handle.write("TRIBUNTACTIC2 "+" ".join(map(str,(revision,earliest_ms,*values,formation)))+"\n")
                handle.flush()
                os.fsync(handle.fileno())
                os.replace(temp,dest)
            finally:
                temp.unlink(missing_ok=True)
    return {"team":team,"revision":revision,"earliestMatchMs":earliest_ms,"state":"submitted-not-applied"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("directory")
    for key in ("team","revision","earliest_ms","press","counter","support","width"):
        p.add_argument(key,type=int)
    p.add_argument("--tempo",type=int,default=50)
    p.add_argument("--formation",type=int,default=0,choices=(0,433,442,4231))
    args=p.parse_args()
    print(publish(args.directory,args.team,args.revision,args.earliest_ms,args.press,args.counter,args.support,args.width,args.tempo,args.formation))

if __name__=="__main__":
    main()
