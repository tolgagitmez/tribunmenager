"""Conservative assist candidates from native touch/counter observations.

Counters are read BEFORE Team::SetLastTouchPlayer updates, so a delta at the
next observation describes the preceding touch. Never treat this heuristic
as the engine's own official assist metric.
"""
MAX_EVENTS=12000
WINDOW_MS=120000

def analyze(events,history,roster):
    if not isinstance(events,list) or not 3<=len(events)<=MAX_EVENTS:
        raise ValueError('Bounded touch observations required')
    if events[0].get('kind')!='period' or events[-1].get('kind')!='final':
        raise ValueError('Expected first period and final observations')
    def counts(event,key):
        v=event.get(key)
        if not isinstance(v,list) or len(v)!=2 or any(type(x) is not int or x<0 for x in v):
            raise ValueError('Invalid native '+key)
        return v
    previous=None;chain=None;period=0;goals=[];touches=0;classified_passes=0;classified_shots=0
    for i,event in enumerate(events):
        kind=event.get('kind')
        phase=event.get('period')
        clock=event.get('clockMs')
        if type(clock) is not int or clock<0 or type(phase) is not int or phase not in (1,2):
            raise ValueError('Invalid native period/clock')
        if kind=='period':
            if phase!=period+1 or clock!=(0 if phase==1 else 2700000):
                raise ValueError('Missing, repeated or invalid period boundary')
        elif phase!=period or clock<(0 if phase==1 else 2700000):
            raise ValueError('Event outside established native period')
        ps,ss,gs=(counts(event,k) for k in ('passes','shots','score'))
        scorers=event.get('scorers')
        if not isinstance(scorers,list) or len(scorers)!=2 or any(not isinstance(v,list) or len(v)>gs[s] or any(type(p) is not int or p not in roster[s] for p in v) for s,v in enumerate(scorers)):
            raise ValueError('Invalid native goal-scorer history')
        if previous is None:
            if phase!=1 or any(ps+ss+gs) or clock!=0:
                raise ValueError('Expected clean first-half counters')
        else:
            if phase<period or (phase==period and clock<previous['clockMs']):
                raise ValueError('Native clock moved backwards within period')
            deltas=[[v[s]-previous[k][s] for s in (0,1)] for k,v in (('passes',ps),('shots',ss),('score',gs))]
            dp,ds,dg=deltas
            if any(x<0 for row in deltas for x in row) or sum(dg)>1:
                raise ValueError('Native counters regressed or skipped a goal')
            for s in (0,1):
                old=previous['scorers'][s]
                if scorers[s][:len(old)]!=old or len(scorers[s])-len(old)>dg[s]:
                    raise ValueError('Native scorer sequence mismatch')
            # Attach an action only to a directly preceding unambiguous touch.
            if sum(dp)+sum(ds):
                if previous['kind']!='touch' or sum(dp)+sum(ds)!=1 or previous['touchType'] not in (0,1):
                    chain=None
                else:
                    side,pid=previous['side'],previous['nativePlayerId']
                    if dp[side]==1:
                        classified_passes+=1
                        chain=dict(side=side,passer=pid,clockMs=previous['clockMs'],period=period,
                                   receiver=None,shot=False)
                    elif ds[side]==1:
                        classified_shots+=1
                        if chain and chain['side']==side and chain['receiver']==pid:
                            chain['shot']=True
                        else:
                            chain=None
                    else:
                        chain=None
            if sum(dg):
                side=dg.index(1)
                credited=scorers[side][len(previous['scorers'][side]):]
                scorer=credited[0] if credited else None
                candidate=None
                if (scorer is not None and chain and chain['side']==side and chain['receiver']==scorer
                        and chain['passer']!=scorer and chain['shot'] and chain['period']==period
                        and 0<=clock-chain['clockMs']<=WINDOW_MS and phase==period):
                    candidate=chain['passer']
                goals.append(dict(side=side,scorerId=scorer,assistCandidateId=candidate,
                                  period=period,observedAtClockMs=clock))
                chain=None
        if kind=='period':
            chain=None
        elif kind=='reset':
            chain=None
        elif kind=='touch':
            side,pid,typ=event.get('side'),event.get('nativePlayerId'),event.get('touchType')
            if type(side) is not int or side not in (0,1) or type(pid) is not int or pid not in roster[side] or type(typ) is not int or typ not in (0,1,2):
                raise ValueError('Invalid native touch identity')
            touches+=1
            if chain:
                if side!=chain['side'] or typ==2 or phase!=chain['period'] or clock-chain['clockMs']>WINDOW_MS:
                    chain=None
                elif chain['receiver'] is None:
                    if pid!=chain['passer']:
                        chain['receiver']=pid
                elif pid!=chain['receiver']:
                    chain=None
        elif kind!='final' or i!=len(events)-1:
            raise ValueError('Unexpected native event')
        previous=event;period=phase
    saved_clock=history['nativeMatchClockMs']
    reset=previous.get('regulationEndReset') is True
    clock_matches=(previous.get('historyClockMs')==saved_clock==5400000 and
                   5400000<=previous['clockMs']<=6300000) if reset else previous['clockMs']==saved_clock
    if period!=2 or not clock_matches or previous['score']!=[history['homeGoals'],history['awayGoals']] or previous['passes']!=history['passAttempts'] or previous['shots']!=history['shots']:
        raise ValueError('Final counters disagree with native history')
    return dict(goals=goals,touchCount=touches,classifiedPasses=classified_passes,
                classifiedShots=classified_shots,assistCandidates=sum(g['assistCandidateId'] is not None for g in goals),
                nativeFinalCountersMatched=True,assistWindowGameClockMs=WINDOW_MS,
                officialAssistsVerified=False,productionImportAllowed=False)
