"""Observe native shielding trials, not inferred body contact or pass success."""
from collections import Counter
from pathlib import Path
import re

LIMIT=32*1024*1024
PATTERN=re.compile(r'\[tribun-pressure-hold\] team=([01]) carrier=(\d+) event=(started|held|released|received|lost|cancelled)')

def inspect_pressure_hold(path):
    path=Path(path)
    if not path.is_file():return None
    if path.stat().st_size>LIMIT:raise ValueError('Game log too large')
    counts=Counter()
    active={}
    invalid=unmatched=0
    with path.open('r',encoding='utf-8',errors='replace') as log:
        for line in log:
            if not line.startswith('[tribun-pressure-hold]'):continue
            m=PATTERN.fullmatch(line.rstrip('\r\n'))
            if not m:
                invalid+=1;continue
            team,carrier,event=m.groups()
            key=(team,carrier)
            if event=='started':
                if key in active:unmatched+=1
                active[key]='started'
            elif key not in active:
                unmatched+=1;continue
            elif event=='held':
                if active[key]!='started':
                    unmatched+=1;continue
                active[key]='held'
            elif event=='released':
                if active[key] not in ('started','held'):
                    unmatched+=1;continue
                if active[key]=='started':counts['earlyReleased']+=1
                active[key]='released'
            elif event=='received':
                if active[key]!='released':
                    unmatched+=1;continue
                del active[key]
            else:
                del active[key]
            counts[event]+=1
    return dict(counts=dict(counts),invalidLines=invalid,unmatchedEvents=unmatched,
        unresolvedKeys=len(active),evidenceAvailable=bool(counts),
        scope='Native shielding trial requests and sampled outcomes. Held denotes 400 ms retained control; early release precedes that milestone. Received requires a matching native short-pass contact and receiver possession. Reset or shot cancellations can be unlogged. Not proof of body shielding or improved pass completion compared with baseline.')
