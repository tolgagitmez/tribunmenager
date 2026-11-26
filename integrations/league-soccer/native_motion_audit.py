"""Decoded image repetition diagnostics; not semantic player or camera tracking."""
import argparse
import json
from fractions import Fraction
from pathlib import Path
import subprocess

def analyze(lines):
    timebase=None;prev=None;end=None;run_start=None;longest=0.;repeated=0;count=0;frozen=[]
    for line in lines:
        if line.startswith('#tb 0:'):
            timebase=Fraction(line.split(':',1)[1].strip())
        if line.startswith('#') or not line.strip():continue
        if timebase is None or timebase<=0:raise ValueError('Missing video time base')
        fields=[v.strip() for v in line.split(',')]
        if len(fields)!=6 or fields[0]!='0':raise ValueError('Invalid frame record')
        pts=int(fields[2])*timebase;duration=int(fields[3])*timebase
        if duration<=0 or (end is not None and pts<end):raise ValueError('Nonmonotonic frame timeline')
        if count>=30000:raise ValueError('Too many frames')
        digest=fields[5]
        if prev==digest and pts==end:
            repeated+=1
        else:
            if run_start is not None:
                length=float(end-run_start)
                longest=max(longest,length)
                if length>=.5:frozen.append({'startSeconds':float(run_start),'durationSeconds':length})
            run_start=pts
        prev=digest;end=pts+duration;count+=1
    if not count:raise ValueError('Missing decoded frames')
    length=float(end-run_start);longest=max(longest,length)
    if length>=.5:frozen.append({'startSeconds':float(run_start),'durationSeconds':length})
    return {'decodedFrames':count,'repeatedFrames':repeated,'repeatedFraction':repeated/count,
            'longestIdenticalImageSeconds':longest,'identicalRunsAtLeast500ms':len(frozen),
            'runs':frozen[:100],'scope':'Identical downscaled grayscale decoded frames; stationary scenes and menus may be legitimate. Not player, ball or camera specific, nor near-duplicate detection.'}

def audit(playlist):
    p=subprocess.run(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,crypto,data',
        '-allowed_extensions','ALL','-threads','1','-i',str(playlist),'-map','0:v:0','-an',
        '-filter_threads','1','-vf','scale=160:90:flags=area,format=gray','-vsync','0',
        '-f','framemd5','-'],capture_output=True,text=True,check=True,timeout=180)
    return analyze(p.stdout.splitlines())

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('playlist',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();a.output.write_text(json.dumps(audit(a.playlist),indent=2)+'\n')
