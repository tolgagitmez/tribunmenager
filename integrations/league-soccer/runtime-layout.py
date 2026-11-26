"""Opt-in shared layout for trusted native diagnostic processes only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import time

SHARED=("gameplayfootball","media","locale")
PRIVATE=("data","databases","native-match.config","tribun-runtime.json","run_menu_smoke.sh")

def entries(path):
    yield path
    if path.is_dir() and not path.is_symlink():
        for p in sorted(path.iterdir()):yield from entries(p)

def inspect(path,readonly=False):
    for p in entries(path):
        mode=p.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError("Unexpected asset type: "+str(p))
        if readonly and mode&0o222:raise ValueError("Writable shared asset: "+str(p))
        yield p,mode

def identity(runtime):
    result={}
    for name in SHARED:
        for p,mode in inspect(runtime/name):
            key=str(p.relative_to(runtime))
            result[key]=hashlib.sha256(p.read_bytes()).hexdigest() if stat.S_ISREG(mode) else "directory"
    return result

def freeze(runtime,snapshot):
    # Copy once; never chmod the source or share a mutable DB.
    subprocess.run(["cp","-a","--reflink=auto",str(runtime),str(snapshot)],check=True)
    for name in SHARED:
        for p,mode in list(inspect(snapshot/name)):
            p.chmod(stat.S_IMODE(mode)&~0o222)
    if identity(runtime)!=identity(snapshot):raise ValueError("Asset snapshot differs")

def materialize(runtime,work,report):
    if not work.is_dir() or any(work.iterdir()):raise ValueError("Workspace must be empty")
    if runtime==work or runtime in work.parents or work in runtime.parents:
        raise ValueError("Workspace overlaps runtime")
    if set(p.name for p in runtime.iterdir())!=set(SHARED+PRIVATE):
        raise ValueError("Unexpected runtime layout; explicit classification required")
    start=time.monotonic()
    shared_bytes=0
    for name in SHARED:
        for p,mode in inspect(runtime/name,readonly=True):
            if stat.S_ISREG(mode):shared_bytes+=p.stat().st_size
        (work/name).symlink_to(runtime/name,target_is_directory=(runtime/name).is_dir())
    for name in PRIVATE:
        list(inspect(runtime/name))
        subprocess.run(["cp","-a","--reflink=auto",str(runtime/name),str(work/name)],check=True)
    private_bytes=sum(p.stat().st_size for name in PRIVATE for p in entries(work/name) if p.is_file())
    result={"sharedEntries":list(SHARED),"privateEntries":list(PRIVATE),
            "sharedLogicalBytes":shared_bytes,"privateLogicalBytes":private_bytes,
            "setupMs":round((time.monotonic()-start)*1000)}
    report.write_text(json.dumps(result,indent=2)+"\n")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("work",type=Path);p.add_argument("report",type=Path)
    a=p.parse_args()
    materialize(a.runtime.resolve(),a.work.resolve(),a.report)
if __name__=="__main__":main()
