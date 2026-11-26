"""Measure completed SDL swap calls, not encoded or unique displayed frames."""
import math
import struct
import subprocess
from pathlib import Path

def compile_probe(source,target):
    subprocess.run(['cc','-O2','-shared','-fPIC',str(source),'-o',str(target),'-ldl','-pthread'],check=True,timeout=30)

def summarize(base,start,end):
    if not all(type(x) in (int,float) and math.isfinite(x) for x in (start,end)) or end<=start:
        return {'observed':False,'reason':'invalid-match-window'}
    paths=[p for p in (Path(str(base)+'.sdl1'),Path(str(base)+'.sdl2')) if p.is_file()]
    if len(paths)!=1:return {'observed':False,'reason':'missing-or-ambiguous-sdl-hook'}
    path=paths[0]
    if path.stat().st_size>16*1024*1024 or path.stat().st_size%8:
        return {'observed':False,'reason':'invalid-swap-log'}
    timestamps=[n/1e9 for n, in struct.iter_unpack('=Q',path.read_bytes())]
    if any(b<a for a,b in zip(timestamps,timestamps[1:])):
        return {'observed':False,'reason':'nonmonotonic-swaps'}
    match=[t for t in timestamps if start<=t<=end]
    if len(match)<2:return {'observed':False,'reason':'insufficient-swap-evidence'}
    gaps=sorted([match[0]-start,end-match[-1]]+[b-a for a,b in zip(match,match[1:])])
    return {'observed':True,'hook':path.suffix[1:],'completedSwaps':len(match),
            'observedSeconds':round(end-start,3),'averageSwapsPerSecond':round(len(match)/(end-start),3),
            'p95GapMs':round(gaps[math.ceil(.95*len(gaps))-1]*1000,2),'maxGapMs':round(gaps[-1]*1000,2),
            'scope':'Completed SDL GL swap calls in observed match window; not unique frames, actual display FPS or GPU execution timing.'}
