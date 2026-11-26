"""Native experimental duel trial counts; not a calibrated dribble success rate."""
from collections import Counter
from pathlib import Path
import re

LIMIT=32*1024*1024
PATTERN=re.compile(r'\[tribun-duel-escape\] team=([01]) carrier=(\d+) defender=(\d+) event=(started|progressed|lost|cancelled)')

def inspect_duels(path):
    path=Path(path)
    if not path.is_file():return None
    if path.stat().st_size>LIMIT:raise ValueError('Game log too large')
    counts=Counter()
    active=set()
    invalid=unmatched=0
    with path.open('r',encoding='utf-8',errors='replace') as log:
        for line in log:
            if not line.startswith('[tribun-duel-escape]'):continue
            m=PATTERN.fullmatch(line.rstrip('\r\n'))
            if not m:
                invalid+=1;continue
            team,carrier,defender,event=m.groups()
            key=(team,carrier,defender)
            if event=='started':
                if key in active:
                    # A restart/reset may end the earlier trial without a log.
                    unmatched+=1
                active.add(key)
            elif key not in active:
                unmatched+=1;continue
            else:
                active.remove(key)
            counts[event]+=1
    return {'counts':dict(counts),'unmatchedEvents':unmatched,'unresolvedKeys':len(active),
            'invalidLines':invalid,'evidenceAvailable':bool(counts),
            'scope':'Experimental native duel selection and sampled outcomes. Progress requires retained carrier control and passing the named defender. Resets may not emit an outcome; cancelled and unresolved trials are not wins. Baseline does not run this trial policy.'}
