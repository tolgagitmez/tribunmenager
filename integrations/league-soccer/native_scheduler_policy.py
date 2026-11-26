"""Conservative single-host admission, not a distributed scheduler."""
import hashlib
import json
import math
import os
from pathlib import Path
import time
from native_cpu_partition import cgroup_path

MAX_AGE=3600

def limits(root):
    # Consider parent cgroups as well as the leaf.
    root=Path(root).resolve()
    base=Path('/sys/fs/cgroup').resolve()
    if not root.is_relative_to(base):raise ValueError('Unknown cgroup hierarchy')
    return read_limits(root,base)

def read_limits(root,base):
    rows=[]
    for path in (root,*root.parents):
        if not path.is_relative_to(base):break
        if (path/'cpu.max').is_file() and (path/'memory.max').is_file():
            quota,period=(path/'cpu.max').read_text().split()
            memory=(path/'memory.max').read_text().strip()
            rows.append((str(path.relative_to(base)),None if quota=='max' else int(quota)/int(period),
                None if memory=='max' else int(memory)))
        if path==base:break
    if not rows:raise ValueError('Resource limits unavailable')
    return rows

def fingerprint(runtime):
    from native_admission import identity
    group=cgroup_path()
    if group is None:raise ValueError('cgroup v2 required')
    rows=limits(group)
    return {'host':identity(runtime),'affinity':sorted(os.sched_getaffinity(0)),
            'limitsSha256':hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest(),
            'cgroup':str(group.relative_to('/sys/fs/cgroup'))}

def group_sample(group,base=Path('/sys/fs/cgroup')):
    rows=read_limits(group,base)
    headroom=[]
    for path,quota,memory in rows:
        if memory is not None:
            headroom.append(max(0,memory-int((base/path/'memory.current').read_text()))/1048576)
    quota=min([len(os.sched_getaffinity(0))]+[r[1] for r in rows if r[1] is not None])
    if quota<=0:raise ValueError('Invalid CPU quota')
    def cpu():
        fields=dict(line.split() for line in (group/'cpu.stat').read_text().splitlines())
        return int(fields['usage_usec']),int(fields['nr_periods']),int(fields['nr_throttled'])
    start=time.monotonic();a=cpu();time.sleep(1);b=cpu()
    elapsed=time.monotonic()-start
    if b[0]<a[0] or b[1]<a[1] or b[2]<a[2]:raise ValueError('Regressing cgroup counters')
    return {'groupCpuBusyPercent':100*(b[0]-a[0])/(elapsed*1000000*quota),
            'groupThrottleFraction':(b[2]-a[2])/max(1,b[1]-a[1]),
            'groupMemoryHeadroomMiB':min(headroom) if headroom else None}

def sample(out):
    from native_admission import sample_host
    group=cgroup_path()
    if group is None:raise ValueError('cgroup v2 required')
    return {**sample_host(out),**group_sample(group)}

def pressure_ok(row):
    from native_admission import pressure_ok as host_ok,number
    if not host_ok(row):return False
    mem=row.get('groupMemoryHeadroomMiB')
    return (number(row.get('groupCpuBusyPercent'),0,80)
        and number(row.get('groupThrottleFraction'),0,.05)
        and 'groupMemoryHeadroomMiB' in row and (mem is None or number(mem,1024)))

def admitted_slots(report,host,now):
    from native_admission import verified_slots,number
    if not isinstance(report,dict) or report.get('admissionIdentity')!=host:return 0
    completed=report.get('completedAt')
    if not number(completed,max(0,now-MAX_AGE),now):return 0
    n=verified_slots(report,host['host'])
    if not n:return 0
    if report.get('allMatchesPassed') is not True or report.get('distinctFixtures') is not True:return 0
    for m in report['matches']:
        if not (m.get('nativeExit')==m.get('browserExit')==0 and m.get('nativeClockMs')==300000
                and number(m.get('observedWallSeconds'),295,305) and number(m.get('coverage'),.95,1.01)
                and m.get('audioOwnershipVerified') is True and m.get('acknowledgements')==2):return 0
        decoded,dropped=m.get('decodedFrames'),m.get('droppedFrames')
        if not number(decoded,1) or not number(dropped,0,decoded) or dropped/decoded>.01:return 0
    group=report.get('admissionGroupSummary')
    if not isinstance(group,dict) or not pressure_ok(group):return 0
    return n
