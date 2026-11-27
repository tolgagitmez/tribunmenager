"""Native player evidence contract: read closed rosters, validate observed data.

The pinned upstream League Mode stores team totals, not a player event log.
This module does not observe the running engine and cannot certify a manually
supplied observation. It never writes the production season database.
"""
from contextlib import closing
import math
from original_catalog import connect
from original_engine import digest,REVISION
from season_state import player_key

FIELDS=('goals','assists','playedClockMs','yellow','red','fatigueFactorInv')
MAX_PLAYERS=128

def roster_baseline(path,fixture):
    before=digest(path)
    teams=[]
    with closing(connect(path)) as db:
        for team in (fixture['homeTeamId'],fixture['awayTeamId']):
            rows=db.execute("""SELECT id,firstname,lastname,formationorder FROM players
                WHERE team_id=? ORDER BY formationorder,id LIMIT ?""",(team,MAX_PLAYERS+1)).fetchall()
            if not 11<=len(rows)<=MAX_PLAYERS:
                raise ValueError('Native roster incomplete or too large')
            ids=[r[0] for r in rows]
            if any(type(i) is not int or i<=0 for i in ids) or len(set(ids))!=len(ids):
                raise ValueError('Ambiguous native player identity')
            teams.append(dict(nativeTeamId=team,players=[
                dict(nativePlayerId=i,name=' '.join(filter(None,(first,last))),
                     savedFormationOrder=order,savedStarter=index<11)
                for index,(i,first,last,order) in enumerate(rows)]))
    if teams[0]['nativeTeamId']==teams[1]['nativeTeamId']:
        raise ValueError('Identical native teams')
    if digest(path)!=before:
        raise RuntimeError('Native roster changed during inspection')
    return dict(revision=REVISION,sourceSaveSha256=before,teams=teams,
                source='closed-native-league-roster',liveLineupVerified=False,
                observedPlayerStatsAvailable=False)

def identity_map(baseline,reviewed,web_rosters):
    """Bind explicit reviewed native IDs to frozen web roster identities.

    Do not match by name, slot, or database ID coincidence.
    """
    if len(baseline['teams'])!=2 or len(web_rosters)!=2 or not isinstance(reviewed,list):
        raise ValueError('Two full rosters and explicit identity mapping required')
    expected={(side,p['nativePlayerId']) for side,t in enumerate(baseline['teams']) for p in t['players']}
    allowed=[]
    for roster in web_rosters:
        keys=[player_key(p) for p in roster]
        if len(keys)!=len(set(keys)):
            raise ValueError('Duplicate web roster identity')
        allowed.append(set(keys))
    mapped={}
    used=set()
    for row in reviewed:
        side,pid,key=row['side'],row['nativePlayerId'],row['webPlayerKey']
        if type(side) is not int or side not in (0,1) or type(pid) is not int or (side,pid) not in expected:
            raise ValueError('Unknown native player identity')
        if not isinstance(key,str) or key not in allowed[side] or (side,key) in used or (side,pid) in mapped:
            raise ValueError('Missing or duplicate web player mapping')
        mapped[side,pid]=key
        used.add((side,key))
    if set(mapped)!=expected or any({key for s,key in used if s==side}!=allowed[side] for side in (0,1)):
        raise ValueError('Incomplete roster identity mapping')
    return mapped

def validate_observations(baseline,mapped,report,history):
    """Validate shape and conservation, not origin or authenticity.

    Each row must explicitly carry null for unavailable measurements.
    Native fatigue is not web fitness; never synthesize that conversion.
    """
    if report.get('revision')!=baseline['revision'] or report.get('sourceSaveSha256')!=baseline['sourceSaveSha256']:
        raise ValueError('Observation does not match frozen native roster')
    clock=history['nativeMatchClockMs']
    if type(clock) is not int or clock<5400000:
        raise ValueError('Full-time native clock required')
    rows=report.get('players')
    if not isinstance(rows,list) or len(rows)!=len(mapped):
        raise ValueError('Complete observed roster rows required')
    seen=set();output=[]
    for row in rows:
        side,pid=row.get('side'),row.get('nativePlayerId')
        if type(side) is not int or type(pid) is not int or (side,pid) not in mapped or (side,pid) in seen:
            raise ValueError('Unknown or duplicate observed player')
        seen.add((side,pid))
        clean=dict(side=side,nativePlayerId=pid,webPlayerKey=mapped[side,pid])
        for field in FIELDS:
            if field not in row:
                raise ValueError('Unavailable fields must be explicit null')
            value=row[field]
            if value is not None:
                if field=='fatigueFactorInv':
                    valid=type(value) in (int,float) and math.isfinite(value) and .01<=value<=1
                else:
                    limit={'goals':99,'assists':99,'playedClockMs':clock,'yellow':2,'red':1}[field]
                    valid=type(value) is int and 0<=value<=limit
                if not valid:
                    raise ValueError('Invalid native player metric: '+field)
            clean[field]=value
        if clean['playedClockMs']==0 and any(clean[k] not in (0,None) for k in ('goals','assists')):
            raise ValueError('Nonparticipant cannot score or assist')
        output.append(clean)
    for side,total in enumerate((history['homeGoals'],history['awayGoals'])):
        team=[r for r in output if r['side']==side]
        if sum(r['goals'] or 0 for r in team)>total or sum(r['assists'] or 0 for r in team)>total:
            raise ValueError('Player scoring totals exceed native team score')
        if sum(r['playedClockMs'] or 0 for r in team)>11*clock:
            raise ValueError('Player clock exceeds eleven-player team time')
    missing={field:sum(r[field] is None for r in output) for field in FIELDS}
    return dict(players=output,missingCounts=missing,shapeValidated=True,
                sourceAuthenticityVerified=False,nativePlayerTelemetryVerified=False,
                nativeFatigueIsWebFitness=False,productionImportAllowed=False)
