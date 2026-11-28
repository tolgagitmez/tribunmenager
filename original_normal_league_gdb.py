"""Read-only native phase observations for an isolated normal league trial."""
import json
import os
import time
import gdb

out=open(os.environ['TRIBUN_LEAGUE_TRACE'],'x',encoding='utf-8',buffering=1)
tracked=None

def emit(kind,**fields):
    out.write(json.dumps(dict(kind=kind,monotonic=time.monotonic(),**fields),allow_nan=False)+'\n')
    out.flush()

def unique(value):
    printer=gdb.default_visualizer(value)
    children=list(printer.children()) if printer is not None else []
    if len(children)!=1 or not int(children[0][1]):
        raise ValueError('Invalid native unique pointer')
    return children[0][1].dereference()

def phase_name(value):
    return str(value).split('::')[-1]

def ids(match):
    return [int(unique(match['teams'][i])['teamData'].dereference()['databaseID']) for i in (0,1)]

class Phase(gdb.Breakpoint):
    def stop(self):
        global tracked
        try:
            f=gdb.newest_frame()
            ptr=f.read_var('this')
            name=phase_name(f.read_var('newMatchPhase'))
            if name=='e_MatchPhase_PreMatch':
                return False
            m=ptr.dereference()
            if name=='e_MatchPhase_1stHalf':
                if tracked is not None:
                    raise ValueError('Multiple first halves')
                tracked=int(ptr)
                emit('first-half',teamIds=ids(m),durationMinutes=float(m['matchDurationMinutes']),
                     timeScale=float(m['matchTimeScale']))
            elif tracked!=int(ptr):
                raise ValueError('Native match identity changed')
            elif name=='e_MatchPhase_2ndHalf':
                emit('half-boundary',clockMs=int(m['matchTime_ms']))
            elif name=='e_MatchPhase_1stExtraTime':
                # Upstream uses this transition even at normal regulation end.
                if bool(m['inPlay']) or bool(m['inSetPiece']):
                    raise ValueError('Regulation boundary while playing')
                emit('regulation-end',clockMs=int(m['matchTime_ms']))
            else:
                raise ValueError('Unexpected extra time phase')
        except Exception as exc:
            emit('error',message=str(exc))
            self.enabled=False
        return False

class HalfMenu(gdb.Breakpoint):
    def __init__(self,symbol,kind):
        super().__init__(symbol,internal=True)
        if self.pending:
            raise ValueError('Unresolved '+symbol)
        self.kind=kind
    def stop(self):
        self.enabled=False
        try:
            page=gdb.newest_frame().read_var('this').dereference()
            if tracked is None or phase_name(page['nextPhase'])!='e_MatchPhase_2ndHalf':
                raise ValueError('Unexpected phase menu')
            emit(self.kind)
        except Exception as exc:
            emit('error',message=str(exc))
        return False

class Final(gdb.Breakpoint):
    def stop(self):
        self.enabled=False
        try:
            page=gdb.newest_frame().read_var('this').dereference()
            ptr=page['match']
            m=ptr.dereference()
            data=m['matchData'].dereference()
            if int(ptr)!=tracked or not bool(m['gameOver']) or not bool(data['historySaved']):
                raise ValueError('Unexpected final history state')
            emit('fulltime',teamIds=ids(m),clockMs=int(m['matchTime_ms']),
                 score=[int(data['goalCount'][i]) for i in (0,1)])
        except Exception as exc:
            emit('error',message=str(exc))
        return False

gdb.execute('set may-call-functions off')
gdb.execute('set pagination off')
for observer in (Phase('Match::SetMatchPhase',internal=True),
                 HalfMenu('MatchPhasePage::Process','half-menu'),
                 HalfMenu('MatchPhasePage::ContinueGame','half-continue'),
                 Final('GameOverPage::Process',internal=True)):
    if observer.pending:
        raise ValueError('Unresolved native phase observation')
emit('ready',pid=gdb.selected_inferior().pid)
