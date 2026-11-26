"""Track native contact-driven wall and triangle combination observations."""
from collections import Counter
from pathlib import Path
import re
PATTERN=re.compile(r'\[tribun-combination187\] team=([01]) kind=(wall|triangle) event=(start|receipt|second|complete|cancel) a=(\d+) b=(\d+) c=(\d+)')
LIMIT=32*1024*1024
def inspect_combinations(path):
    path=Path(path)
    if not path.is_file():return None
    if path.stat().st_size>LIMIT:raise ValueError('Game log too large')
    counts={'wall':Counter(),'triangle':Counter()}
    active={}
    unmatched=invalid=0
    with path.open(encoding='utf-8',errors='replace') as log:
        for line in log:
            if not line.startswith('[tribun-combination187]'):continue
            m=PATTERN.fullmatch(line.rstrip('\r\n'))
            if not m:
                invalid+=1;continue
            team,kind,event,a,b,c=m.groups()
            if a==b or (kind=='wall' and a!=c) or (kind=='triangle' and len({a,b,c})!=3):
                invalid+=1;continue
            key=(team,kind,a,b,c)
            previous=active.get(key)
            if event=='start':
                if previous:unmatched+=1
                active[key]='start'
            elif not previous or (event!='cancel' and previous!={'receipt':'start','second':'receipt','complete':'second'}[event]):
                unmatched+=1;continue
            elif event in ('complete','cancel'):
                del active[key]
            else:
                active[key]=event
            counts[kind][event]+=1
    return dict(counts={k:dict(v) for k,v in counts.items()},invalidLines=invalid,
        unmatchedEvents=unmatched,unresolvedKeys=len(active),evidenceAvailable=any(counts.values()),
        scope='Contact-driven combination stages. Unlogged resets can leave unresolved trials; no one-touch animation or causal improvement claim.')
