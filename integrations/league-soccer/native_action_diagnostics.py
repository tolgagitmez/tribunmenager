"""Native action evidence, not inferred animation success or a new match result."""
from collections import Counter
from pathlib import Path
import re

LIMIT=16*1024*1024
MAX_EVENTS=200
PATTERN=re.compile(r'\[tribun-action\] phase=(-?\d+) actual_ms=(\d+) match_ms=(\d+) team=([01]) player=(-?\d+) event=(accepted|rejected|contact|missed-touch) action=(short-pass|long-pass|high-pass|shot|ball-control|movement)')

ALTERNATIVE=re.compile(r'\[tribun-action-alternative\] phase=(-?\d+) match_ms=(\d+) team=([01]) player=(-?\d+) from=(short-pass|long-pass|high-pass|shot) to=(short-pass|ball-control)')

def inspect_actions(path):
    path=Path(path)
    if not path.is_file():
        return None
    if path.stat().st_size>LIMIT:
        raise ValueError('Action log too large')
    counts={}
    events=[]
    total=invalid=0
    promotions=Counter()
    promotion_events=[]
    with path.open('r',encoding='utf-8',errors='replace') as log:
        for line in log:
            line=line.rstrip('\r\n')
            if line.startswith('[tribun-action-alternative]'):
                m=ALTERNATIVE.fullmatch(line)
                if not m:
                    invalid+=1
                    continue
                phase,match,team,player,original,alternative=m.groups()
                if original==alternative:
                    invalid+=1
                    continue
                promotions[original+'->'+alternative]+=1
                if len(promotion_events)<MAX_EVENTS:
                    promotion_events.append(dict(phase=int(phase),matchMs=int(match),
                        team=int(team),playerId=int(player),original=original,alternative=alternative))
                continue
            if not line.startswith('[tribun-action]'):
                continue
            m=PATTERN.fullmatch(line)
            if not m:
                invalid+=1
                continue
            phase,actual,match,team,player,event,action=m.groups()
            if action=='movement' and event in ('contact','missed-touch'):
                invalid+=1
                continue
            counts.setdefault(action,Counter())[event]+=1
            total+=1
            if len(events)<MAX_EVENTS:
                events.append(dict(phase=int(phase),actualMs=int(actual),matchMs=int(match),
                    team=int(team),playerId=int(player),event=event,action=action))
    return dict(observedEvents=total,invalidLines=invalid,events=events,
        truncated=total>len(events),counts={a:dict(c) for a,c in counts.items()},
        alternativePromotions=sum(promotions.values()),alternativeCounts=dict(promotions),
        alternativeEvents=promotion_events,alternativesTruncated=sum(promotions.values())>len(promotion_events),
        evidenceAvailable=total>0 or bool(promotions),
        scope='Candidates actually tried, animation selector results, and observed contact or geometry failure. Contacts can occur after possession changes. Counts are not paired requests or completion rates; movement acceptance does not prove displacement. Alternative promotions are queue-order changes, not proof of successful action. No events does not prove no problem.')
