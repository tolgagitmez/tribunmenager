"""Verify native Pulse sink input ownership, without logging private endpoints."""
import os
from pathlib import Path
import re
import subprocess

def descendants(pid,root=Path('/proc')):
    result=set()
    pending=[pid]
    while pending:
        p=pending.pop()
        if p in result:continue
        result.add(p)
        try:
            pending.extend(int(x) for x in (root/str(p)/'task'/str(p)/'children').read_text().split())
        except (OSError,ValueError):pass
    return result

def parse_inputs(text):
    rows=[]
    for block in re.split(r'(?m)^Sink Input #\d+\s*$',text)[1:]:
        sink=re.search(r'(?m)^\s*Sink:\s*(\d+)\s*$',block)
        pid=re.search(r'(?m)^\s*application\.process\.id\s*=\s*"([0-9]+)"\s*$',block)
        rows.append({'sink':int(sink.group(1)) if sink else None,'pid':int(pid.group(1)) if pid else None})
    return rows

def owned_input(rows,sink,pids):
    return bool(rows) and all(r['sink']==sink and r['pid'] in pids for r in rows)

def probe(env,pid):
    e=dict(env,LC_ALL='C')
    try:
        sinks=subprocess.check_output(['pactl','list','short','sinks'],env=e,text=True,timeout=4)
        ids=[int(x.split()[0]) for x in sinks.splitlines() if len(x.split())>1 and x.split()[1]=='tribun_match']
        if len(ids)!=1:return 'wrong-sink'
        rows=parse_inputs(subprocess.check_output(['pactl','list','sink-inputs'],env=e,text=True,timeout=4))
        if not rows:return 'no-input'
        if owned_input(rows,ids[0],descendants(pid)):return 'owned'
        return 'foreign-or-unidentified-input'
    except (OSError,ValueError,subprocess.SubprocessError):return 'probe-unavailable'
