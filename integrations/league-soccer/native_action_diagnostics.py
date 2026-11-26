"""Native action evidence, not inferred animation success or a new match result."""
from collections import Counter
from pathlib import Path
import re
import math

LIMIT=16*1024*1024
MAX_EVENTS=200
PATTERN=re.compile(r'\[tribun-action\] phase=(-?\d+) actual_ms=(\d+) match_ms=(\d+) team=([01]) player=(-?\d+) event=(accepted|rejected|contact|missed-touch) action=(short-pass|long-pass|high-pass|shot|ball-control|movement)')

ALTERNATIVE=re.compile(r'\[tribun-action-alternative\] phase=(-?\d+) match_ms=(\d+) team=([01]) player=(-?\d+) from=(short-pass|long-pass|high-pass|shot) to=(short-pass|ball-control)')

RETRY=re.compile(r'\[tribun-touch-retry\] phase=(-?\d+) match_ms=(\d+) team=([01]) player=(-?\d+) from=(short-pass|long-pass|high-pass|shot) to=(short-pass|ball-control)')
GEOMETRY=re.compile(r'\[tribun-touch-geometry\] phase=(-?\d+) match_ms=(\d+) team=([01]) player=(-?\d+) action=(short-pass|long-pass|high-pass|shot) distance=(\S+) limit=(\S+) height_error=(\S+) body_angle=(\S+) player_speed=(\S+) ball_speed=(\S+) frame=(-?\d+) touch_frame=(-?\d+)')

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
    geometry_counts=Counter()
    geometry_events=[]
    retry_counts=Counter()
    with path.open('r',encoding='utf-8',errors='replace') as log:
        for line in log:
            line=line.rstrip('\r\n')
            if line.startswith('[tribun-touch-retry]'):
                m=RETRY.fullmatch(line)
                if not m or m[5]==m[6]:
                    invalid+=1
                    continue
                retry_counts[m[5]+'->'+m[6]]+=1
                continue
            if line.startswith('[tribun-touch-geometry]'):
                m=GEOMETRY.fullmatch(line)
                if not m:
                    invalid+=1
                    continue
                try:
                    distance,limit,height,angle,player_speed,ball_speed=map(float,m.groups()[5:11])
                    frame,touch_frame=map(int,m.groups()[11:13])
                    if (not all(math.isfinite(v) for v in (distance,limit,height,angle,player_speed,ball_speed))
                        or min(distance,height,player_speed,ball_speed)<0 or limit<=0 or frame!=touch_frame or frame<0):
                        raise ValueError('Invalid geometry')
                except ValueError:
                    invalid+=1
                    continue
                # The native log rounds to four decimal places: values at the threshold
                # can be ambiguous; do not infer exact underlying comparison.
                reason=('both' if distance>limit and height>1 else 'distance' if distance>limit
                        else 'height' if height>1 else 'threshold-or-rounded')
                geometry_counts[reason]+=1
                if len(geometry_events)<MAX_EVENTS:
                    geometry_events.append(dict(phase=int(m[1]),matchMs=int(m[2]),team=int(m[3]),
                        playerId=int(m[4]),action=m[5],distance=distance,limit=limit,heightError=height,
                        bodyAngle=angle,playerSpeed=player_speed,ballSpeed=ball_speed,frame=frame,reason=reason))
                continue
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
        touchGeometryCounts=dict(geometry_counts),touchGeometryEvents=geometry_events,
        touchGeometryTruncated=sum(geometry_counts.values())>len(geometry_events),
        touchRetryCounts=dict(retry_counts),touchRetryPromotions=sum(retry_counts.values()),
        evidenceAvailable=total>0 or bool(promotions) or bool(geometry_counts) or bool(retry_counts),
        scope='Candidates actually tried, animation selector results, and observed contact or geometry failure. Contacts can occur after possession changes. Counts are not paired requests or completion rates; movement acceptance does not prove displacement. Alternative promotions are queue-order changes, not proof of successful action. Touch retry promotions are a subset of alternative promotions, not additional actions. Geometry reasons use rounded measurements and are not a causal diagnosis. No events does not prove no problem.')
