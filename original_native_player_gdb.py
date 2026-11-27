"""GDB Python script for our own isolated native smoke process.

One breakpoint at GameOverPage::Process after native history was saved.
Read debug-symbol fields only; no inferior function calls or assignments.
The debugger briefly stops the process: this is not performance evidence.
"""
import json
import gdb

def vector(v,limit):
    impl=v['_M_impl']
    start,end=impl['_M_start'],impl['_M_finish']
    n=int(end-start)
    if not 0<=n<=limit:
        raise ValueError('Unexpected native vector size')
    return [(start+i).dereference() for i in range(n)]

def unique(v):
    printer=gdb.default_visualizer(v)
    if printer is None:
        raise ValueError('libstdc++ unique_ptr pretty printer unavailable')
    children=list(printer.children())
    if len(children)!=1 or children[0][1].type.strip_typedefs().code!=gdb.TYPE_CODE_PTR:
        raise ValueError('Unexpected unique_ptr debug layout')
    ptr=children[0][1]
    if int(ptr)==0:
        raise ValueError('Null native pointer')
    return ptr.dereference()

def snapshot():
    page=gdb.newest_frame().read_var('this').dereference()
    match=page['match'].dereference()
    data=match['matchData'].dereference()
    if not bool(data['historySaved']):
        raise ValueError('Native history not yet saved')
    teams=[]
    for side in (0,1):
        team=unique(match['teams'][side])
        team_id=int(team['teamData'].dereference()['databaseID'])
        scorers=[int(v) for v in vector(data['goalScorers']['_M_elems'][side],99)]
        players=[]
        for item in vector(team['players'],128):
            player=unique(item)
            pd=player['playerData'].dereference()
            players.append(dict(nativePlayerId=int(pd['databaseID']),
                                rawCardCode=int(player['cards']),
                                fatigueFactorInv=float(player['fatigueFactorInv']),
                                activeAtFullTime=bool(player['isActive'])))
        teams.append(dict(side=side,nativeTeamId=team_id,score=int(data['goalCount'][side]),
                          scorerIds=scorers,players=players))
    return dict(nativeMatchClockMs=int(match['matchTime_ms']),teams=teams,
                observationPoint='GameOverPage::Process',historySaved=True)

events=[]
tracked_match=None
period=None

def add_event(event):
    if len(events)>=1024:
        raise ValueError('Native event cap exceeded')
    events.append(event)

touch_events=[]

def touch_event(match,kind,phase,clock=None,**extra):
    if len(touch_events)>=12000:
        raise ValueError('Touch observation cap exceeded')
    data=match['matchData'].dereference()
    touch_events.append(dict(kind=kind,period=phase,
        clockMs=int(match['matchTime_ms']) if clock is None else clock,
        passes=[int(data['passAttempts'][s]) for s in (0,1)],
        shots=[int(data['shots'][s]) for s in (0,1)],
        score=[int(data['goalCount'][s]) for s in (0,1)],
        scorers=[[int(v) for v in vector(data['goalScorers']['_M_elems'][s],99)] for s in (0,1)],
        **extra))

class TouchObserver(gdb.Breakpoint):
    def stop(self):
        if tracked_match is None or final_observer.attempted:
            return False
        try:
            f=gdb.newest_frame()
            team=f.read_var('this').dereference()
            if int(team['match'])!=tracked_match:
                raise ValueError('Unexpected touch match instance')
            player=f.read_var('player').dereference()
            if not bool(player['isActive']):
                raise ValueError('Inactive touch player')
            typ=int(f.read_var('touchType'))
            touch_event(team['match'].dereference(),'touch',period,
                side=int(team['id']),nativePlayerId=int(player['playerData'].dereference()['databaseID']),touchType=typ)
        except Exception as error:
            print('TRIBUN_NATIVE_TOUCH_ERROR '+str(error),flush=True)
            self.enabled=False
        return False

class ResetObserver(gdb.Breakpoint):
    def stop(self):
        if tracked_match is None or final_observer.attempted:
            return False
        try:
            ptr=gdb.newest_frame().read_var('this')
            if int(ptr)!=tracked_match:
                raise ValueError('Unexpected reset match instance')
            touch_event(ptr.dereference(),'reset',period)
        except Exception as error:
            print('TRIBUN_NATIVE_TOUCH_ERROR '+str(error),flush=True)
            self.enabled=False
        return False

class PeriodObserver(gdb.Breakpoint):
    def stop(self):
        global tracked_match,period
        try:
            f=gdb.newest_frame()
            ptr=f.read_var('this')
            phase=str(f.read_var('newMatchPhase')).split('::')[-1]
            if phase=='e_MatchPhase_PreMatch':
                return False
            if phase not in ('e_MatchPhase_1stHalf','e_MatchPhase_2ndHalf'):
                raise ValueError('Unsupported match phase '+phase)
            new=1 if phase=='e_MatchPhase_1stHalf' else 2
            match=ptr.dereference()
            if new==1:
                if tracked_match is not None:
                    raise ValueError('Repeated first half')
                tracked_match=int(ptr)
            elif tracked_match!=int(ptr):
                raise ValueError('Unexpected match instance')
            active=[];fatigue=[]
            for side in (0,1):
                team=unique(match['teams'][side])
                for item in vector(team['players'],128):
                    p=unique(item)
                    key=dict(side=side,nativePlayerId=int(p['playerData'].dereference()['databaseID']))
                    if bool(p['isActive']):
                        active.append(key)
                    fatigue.append(dict(key,fatigueFactorInv=float(p['fatigueFactorInv'])))
            add_event(dict(kind='period',period=new,previousClockMs=int(match['matchTime_ms']),active=active,fatigue=fatigue))
            if assists_enabled:
                touch_event(match,'period',new,clock=0 if new==1 else 2700000)
            period=new
        except Exception as error:
            print('TRIBUN_NATIVE_TIMELINE_ERROR '+str(error),flush=True)
        return False

class ActivityObserver(gdb.Breakpoint):
    def __init__(self,name,kind):
        super().__init__(name,internal=True)
        if self.pending:
            raise ValueError('Unresolved native activity breakpoint: '+name)
        self.kind=kind
    def stop(self):
        if tracked_match is None or final_observer.attempted:
            return False
        try:
            p=gdb.newest_frame().read_var('this').dereference()
            if int(p['match'])!=tracked_match:
                raise ValueError('Unexpected player match instance')
            match=p['match'].dereference()
            team=p['team'].dereference()
            side=int(team['id'])
            active=bool(p['isActive'])
            if active!=(self.kind=='deactivate'):
                raise ValueError('Unexpected pre-transition activity')
            add_event(dict(kind=self.kind,period=period,clockMs=int(match['matchTime_ms']),
                           side=side,nativePlayerId=int(p['playerData'].dereference()['databaseID'])))
        except Exception as error:
            print('TRIBUN_NATIVE_TIMELINE_ERROR '+str(error),flush=True)
        return False

class FinalObserver(gdb.Breakpoint):
    def __init__(self):
        super().__init__('GameOverPage::Process',internal=True)
        if self.pending:
            raise ValueError('Unresolved native full-time breakpoint')
        self.attempted=False
    def stop(self):
        if self.attempted:
            return False
        self.attempted=True
        self.enabled=False
        try:
            result=snapshot()
            print('TRIBUN_NATIVE_PLAYER_SNAPSHOT '+json.dumps(result,allow_nan=False),flush=True)
            if timeline_enabled:
                page=gdb.newest_frame().read_var('this').dereference()
                if tracked_match!=int(page['match']):
                    raise ValueError('Final match differs from observed match')
                add_event(dict(kind='final',clockMs=result['nativeMatchClockMs']))
                print('TRIBUN_NATIVE_PLAYER_TIMELINE '+json.dumps(events,allow_nan=False),flush=True)
                if assists_enabled:
                    touch_event(page['match'].dereference(),'final',period)
                    print('TRIBUN_NATIVE_TOUCH_EVENTS '+json.dumps(touch_events,allow_nan=False),flush=True)
        except Exception as error:
            print('TRIBUN_NATIVE_PLAYER_ERROR '+str(error),flush=True)
        return False

gdb.execute('set may-call-functions off')
gdb.execute('set pagination off')
timeline_enabled=bool(int(gdb.parse_and_eval('$tribun_timeline')))
assists_enabled=bool(int(gdb.parse_and_eval('$tribun_assists')))
final_observer=FinalObserver()
if timeline_enabled:
    PeriodObserver('Match::SetMatchPhase',internal=True)
    ActivityObserver('Player::Activate','activate')
    ActivityObserver('Player::Deactivate','deactivate')

if assists_enabled:
    if not timeline_enabled:
        raise ValueError('Touch tracing requires period tracking')
    TouchObserver('Team::SetLastTouchPlayer',internal=True)
    ResetObserver('Match::ResetSituation',internal=True)

print('TRIBUN_NATIVE_OBSERVER_READY timeline='+str(timeline_enabled)+' assists='+str(assists_enabled),flush=True)
