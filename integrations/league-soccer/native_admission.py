"""Conservative single-host diagnostic admission policy. No production or GPU claims."""
import argparse
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil

PROFILE='software-gl/x264/720p25/audio48k'
TIERS=(2,4,8,16)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def identity(runtime):
    # Boot-scoped evidence: do not reuse a result from another CI runner/reboot.
    return {'bootHash':digest('/proc/sys/kernel/random/boot_id'),
            'runtimeManifestSha256':digest(Path(runtime)/'tribun-runtime.json'),
            'logicalCpus':len(os.sched_getaffinity(0))}

def number(value, minimum=0, maximum=math.inf):
    return type(value) in (int,float) and math.isfinite(value) and minimum<=value<=maximum

def verified_slots(report, host):
    if not isinstance(report,dict) or report.get('hostIdentity')!=host or report.get('profile')!=PROFILE:
        return 0
    n=report.get('requestedMatches')
    if type(n) is not int or n not in TIERS or report.get('passed') is not True:
        return 0
    rows=report.get('matches')
    if not isinstance(rows,list) or len(rows)!=n or not all(isinstance(m,dict) and m.get('passed') is True for m in rows):
        return 0
    fixtures=[m.get('fixtureSha256') for m in rows]
    if not all(isinstance(f,str) and re.fullmatch('[0-9a-f]{64}',f) for f in fixtures) or len(set(fixtures))!=n:
        return 0
    if not number(report.get('overlapSeconds'),285,310):
        return 0
    if report.get('filterThreads')!=0:
        return 0
    resources=report.get('resourceSummary',{})
    if not isinstance(resources,dict) or not report.get('samples'):
        return 0
    if not (number(resources.get('cpuP95Percent'),0,85)
            and number(resources.get('minimumAvailableMemoryMiB'),1024)
            and number(resources.get('minimumFreeDiskMiB'),2048)):
        return 0
    return n

def pressure_ok(sample):
    return (number(sample.get('cpuBusyPercent'),0,85)
            and number(sample.get('availableMemoryMiB'),1024)
            and number(sample.get('freeDiskMiB'),2048))

class Queue:
    """FIFO admission with explicit running reservations; callers must release on exit."""
    def __init__(self, slots):
        if type(slots) is not int or not 0<=slots<=16: raise ValueError('Invalid slot limit')
        self.slots=slots
        self.waiting=deque()
        self.active=set()
        self.seen=set()

    def enqueue(self, match_id):
        if not isinstance(match_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',match_id) or match_id in self.seen:
            raise ValueError('Invalid or duplicate match id')
        self.seen.add(match_id)
        self.waiting.append(match_id)

    def admit(self, sample):
        if not pressure_ok(sample): return []
        admitted=[]
        while self.waiting and len(self.active)<self.slots:
            item=self.waiting.popleft()
            self.active.add(item)
            admitted.append(item)
        return admitted

    def release(self, match_id):
        if match_id not in self.active: raise ValueError('Match not reserved')
        self.active.remove(match_id)

def sample_host(out):
    import time
    def ticks():
        a=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
        return sum(a),a[3]+a[4]
    a=ticks();time.sleep(1);b=ticks()
    cpu=100*(1-(b[1]-a[1])/(b[0]-a[0])) if b[0]>a[0] else None
    mem=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))/1024
    return {'cpuBusyPercent':cpu,'availableMemoryMiB':mem,'freeDiskMiB':shutil.disk_usage(out).free/1048576}

def main():
    p=argparse.ArgumentParser(description='Dry-run admission; does not start games or accept public requests.')
    p.add_argument('runtime',type=Path)
    p.add_argument('disk',type=Path)
    p.add_argument('--evidence',type=Path,action='append',default=[])
    p.add_argument('matches',nargs='+')
    a=p.parse_args()
    host=identity(a.runtime)
    reports=[json.loads(f.read_text()) for f in a.evidence]
    slots=max((verified_slots(r,host) for r in reports),default=0)
    q=Queue(slots)
    for match in a.matches:q.enqueue(match)
    sample=sample_host(a.disk)
    admitted=q.admit(sample)
    print(json.dumps({'dryRun':True,'profile':PROFILE,'hardwareEligible':False,'verifiedSlots':slots,
                      'wouldAdmit':admitted,'waiting':list(q.waiting),'pressure':sample,
                      'productionQualified':False},indent=2))

if __name__=='__main__':main()
