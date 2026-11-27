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

class FinalObserver(gdb.Breakpoint):
    def __init__(self):
        super().__init__('GameOverPage::Process',internal=True)
        self.attempted=False
    def stop(self):
        if self.attempted:
            return False
        self.attempted=True
        self.enabled=False
        try:
            print('TRIBUN_NATIVE_PLAYER_SNAPSHOT '+json.dumps(snapshot(),allow_nan=False),flush=True)
        except Exception as error:
            print('TRIBUN_NATIVE_PLAYER_ERROR '+str(error),flush=True)
        return False

gdb.execute('set may-call-functions off')
gdb.execute('set pagination off')
FinalObserver()
