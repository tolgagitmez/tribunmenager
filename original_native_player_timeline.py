"""Reconstruct observed on-pitch game-clock exposure, not wall-clock minutes.

Upstream resets matchTime_ms to 45:00 for the second half. Sum each
period independently; never count halftime or infer appearances from a roster.
"""
import math

STARTS={1:0,2:2700000}
ENDS={1:2700000,2:5400000}

def reconstruct(events,final):
    if not isinstance(events,list) or not 3<=len(events)<=1024:
        raise ValueError('Bounded complete native event list required')
    all_players={(side,p['nativePlayerId']):p for side,t in enumerate(final['teams']) for p in t['players']}
    if len(all_players)!=sum(len(t['players']) for t in final['teams']):
        raise ValueError('Duplicate final player identity')
    active=set();entered={};durations={k:0 for k in all_players}
    initial_fatigue={};period=None;last=None;period_ends={};changes=[]
    def read_key(row):
        k=(row.get('side'),row.get('nativePlayerId'))
        if any(type(v) is not int for v in k) or k not in all_players:
            raise ValueError('Unknown observed player')
        return k
    def active_rows(rows):
        if not isinstance(rows,list):
            raise ValueError('Missing active roster')
        keys=[read_key(r) for r in rows]
        if len(keys)!=len(set(keys)) or any(sum(k[0]==side for k in keys)>11 for side in (0,1)):
            raise ValueError('Invalid active roster')
        return set(keys)
    def advance(clock):
        nonlocal last
        if type(clock) is not int or last is None or not last<=clock<=ENDS[period]+900000:
            raise ValueError('Invalid or nonmonotonic period clock')
        for k in active:
            durations[k]+=clock-last
        last=clock
    for index,event in enumerate(events):
        kind=event.get('kind')
        if kind=='period':
            new=event.get('period')
            if type(new) is not int or new not in STARTS or new!=(1 if period is None else period+1):
                raise ValueError('Unexpected native period sequence')
            snapshot=active_rows(event.get('active'))
            if new==1:
                if index!=0 or any(sum(k[0]==side for k in snapshot)!=11 for side in (0,1)):
                    raise ValueError('Expected eleven starting players per side')
                active=snapshot
                fatigue=event.get('fatigue')
                if not isinstance(fatigue,list):
                    raise ValueError('Missing initial fatigue observations')
                for row in fatigue:
                    k=read_key(row);v=row.get('fatigueFactorInv')
                    if k in initial_fatigue or type(v) not in (float,int) or not math.isfinite(v) or not .009999<=v<=1:
                        raise ValueError('Invalid initial fatigue')
                    initial_fatigue[k]=v
                if set(initial_fatigue)!=set(all_players):
                    raise ValueError('Incomplete initial fatigue observations')
            else:
                advance(event.get('previousClockMs'))
                if last<ENDS[period] or active!=snapshot:
                    raise ValueError('First-half end or active lineup mismatch')
                period_ends[period]=last
            period=new;last=STARTS[new]
        elif kind in ('activate','deactivate'):
            if period is None or event.get('period')!=period:
                raise ValueError('Player transition outside observed period')
            advance(event.get('clockMs'))
            k=read_key(event)
            if kind=='activate':
                if k in active or sum(x[0]==k[0] for x in active)>=11:
                    raise ValueError('Invalid duplicate or excess activation')
                active.add(k);entered[k]=entered.get(k,0)+1
            else:
                if k not in active:
                    raise ValueError('Invalid deactivation')
                active.remove(k)
            changes.append(dict(kind=kind,side=k[0],nativePlayerId=k[1],period=period,clockMs=last))
        elif kind=='final':
            if index!=len(events)-1 or period!=2:
                raise ValueError('Final event must end second half')
            advance(event.get('clockMs'))
            saved_clock=final['nativeMatchClockMs']
            reset=event.get('regulationEndReset') is True
            if (last<ENDS[2] or (reset and (event.get('historyClockMs')!=saved_clock or saved_clock!=ENDS[2]))
                or (not reset and last!=saved_clock)):
                raise ValueError('Final clock differs from native history or regulation reset')
            expected={k for k,p in all_players.items() if p['activeAtFullTime']}
            if active!=expected:
                raise ValueError('Unobserved player transition before full time')
            period_ends[2]=last
        else:
            raise ValueError('Unknown native event')
    if set(period_ends)!={1,2}:
        raise ValueError('Missing full native periods')
    elapsed=period_ends[1]+period_ends[2]-STARTS[2]
    for side in (0,1):
        if sum(v for k,v in durations.items() if k[0]==side)>11*elapsed:
            raise ValueError('Excess observed on-pitch time')
    rows=[]
    for k,p in sorted(all_players.items()):
        rows.append(dict(side=k[0],nativePlayerId=k[1],observedOnPitchClockMs=durations[k],
                         observedOnPitchMinutes=round(durations[k]/60000,3),
                         initialFatigueFactorInv=initial_fatigue[k],
                         finalFatigueFactorInv=p['fatigueFactorInv'],
                         fatigueFactorInvDelta=round(p['fatigueFactorInv']-initial_fatigue[k],6),
                         assists=None))
    return dict(players=rows,periodEndClockMs=[period_ends[1],period_ends[2]],
                observedMatchClockExposureMs=elapsed,playerTransitions=changes,
                regulationEndResetObserved=events[-1].get('regulationEndReset') is True,
                historyClockMs=final['nativeMatchClockMs'],
                eventSequenceConsistent=True,officialMinutesVerified=False,
                substitutionsIndependentlyVerified=False,assistsAvailable=False,
                productionImportAllowed=False)
