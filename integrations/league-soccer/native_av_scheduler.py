"""Opt-in local diagnostic worker supervisor. Never schedules official games."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import stat
import time
import native_av_queue as q
from native_scheduler_policy import fingerprint,sample,pressure_ok,admitted_slots

def lock_host():
    path=Path('/tmp')/('tribun-av-supervisor-'+str(os.getuid())+'.lock')
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        st=os.fstat(fd)
        if st.st_uid!=os.getuid() or not stat.S_ISREG(st.st_mode) or st.st_mode&0o077:raise ValueError('Unsafe supervisor lock')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return fd
    except BaseException:os.close(fd);raise

def execute(db,runtime,out,job):
    key,sha,_,attempt=job
    try:
        report=q.run_match(runtime,out,job,database=db)
        if not q.finish(db,key,sha,attempt,report=report):raise RuntimeError('Reservation lost')
        return 'ready'
    except Exception as exc:
        q.finish(db,key,sha,attempt,error=type(exc).__name__)
        return 'failed'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('database',type=Path);p.add_argument('runtime',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--evidence',type=Path,required=True);p.add_argument('--max-jobs',type=int,default=16)
    a=p.parse_args()
    if not 1<=a.max_jobs<=1000:p.error('Invalid maximum jobs')
    if os.environ.get('TRIBUN_NATIVE_DIAGNOSTIC_SUPERVISOR')!='1':p.error('Explicit diagnostic opt-in required')
    db,runtime,out=(x.resolve() for x in (a.database,a.runtime,a.output))
    if not db.is_file() or out.is_relative_to(q.HERE.parents[1]):p.error('Private database and output outside web root required')
    out.mkdir(mode=0o700,parents=True,exist_ok=True)
    if out.stat().st_mode&0o077:p.error('Private output permissions required')
    lock=lock_host()
    active=set();started=0;results=[]
    try:
        with ThreadPoolExecutor(max_workers=16) as pool:
            while started<a.max_jobs or active:
                done={f for f in active if f.done()}
                for f in done:results.append(f.result())
                active-=done
                slots=0
                try:
                    evidence=json.loads(a.evidence.read_text())
                    slots=admitted_slots(evidence,fingerprint(runtime),time.time())
                    if slots and not pressure_ok(sample(out)):slots=0
                except (OSError,ValueError,KeyError,TypeError):slots=0
                # One new reservation per fresh resource sample. Atomic DB claim
                # includes quarantined capacity; no retry of a failed match.
                job=q.claim(db,slots,managed=True) if started<a.max_jobs and slots else None
                if job:
                    active.add(pool.submit(execute,db,runtime,out,job));started+=1
                elif not active:break
                time.sleep(2)
        print(json.dumps({'started':started,'ready':results.count('ready'),'failed':results.count('failed'),
            'productionQualified':False,'scope':'Private diagnostic queue; no public scheduler or official scores'}))
    finally:os.close(lock)

if __name__=='__main__':main()
