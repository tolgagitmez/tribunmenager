"""Read-only native phase observations for an isolated normal league trial."""
import json
import os
import time
import gdb

out=open(os.environ['TRIBUN_LEAGUE_TRACE'],'x',encoding='utf-8',buffering=1)
tracked=None
control_out=open(os.environ['TRIBUN_LEAGUE_TRACE']+'.controls','x',encoding='utf-8',buffering=1)
control_menu_seen=False
cpu_released=False
game_ready=False
pause_seen=False
input_out=open(os.environ['TRIBUN_LEAGUE_TRACE']+'.inputs','x',encoding='utf-8',buffering=1)
input_count=0
last_sides=None

def input_record(kind,**fields):
    global input_count
    if input_count>=160:
        return
    input_count+=1
    input_out.write(json.dumps(dict(kind=kind,monotonic=time.monotonic(),**fields),allow_nan=False)+'\n')
    input_out.flush()

def view_name(ptr):
    if not int(ptr):
        return None
    return ptr.dereference()['name']['_M_dataplus']['_M_p'].string()

def control(kind,**fields):
    control_out.write(json.dumps(dict(kind=kind,**fields),allow_nan=False)+'\n')
    control_out.flush()

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

def human_counts(match):
    counts=[]
    for i in (0,1):
        v=unique(match['teams'][i])['humanGamers']['_M_impl']
        counts.append(int(v['_M_finish']-v['_M_start']))
    return counts

def active_match():
    if tracked is None:
        raise ValueError('No tracked native match')
    return gdb.Value(tracked).cast(gdb.lookup_type('Match').pointer()).dereference()

class GameplayReady(gdb.Breakpoint):
    def stop(self):
        global game_ready
        try:
            page=gdb.newest_frame().read_var('this').dereference()
            ptr=page['match']
            if tracked is None or int(ptr)!=tracked:
                return False
            m=ptr.dereference()
            # The match constructor and first-half signal can precede the
            # input-receiving GamePage. Wait for an actual initialized page.
            if int(m['actualTime_ms'])<1000:
                return False
            self.enabled=False
            control('game-ready',humanCounts=human_counts(m),
                    actualTimeMs=int(m['actualTime_ms']),clockMs=int(m['matchTime_ms']))
            reload_observer.enabled=False
            game_ready=True
            sdl_observer.enabled=True
            keyboard_observer.enabled=True
            try:
                input_record('game-focus',name=view_name(page['windowManager']['focus']))
            except Exception as exc:
                input_record('diagnostic-error',message=str(exc))
        except Exception as exc:
            self.enabled=False
            control('error',message=str(exc))
        return False

class SDLEscape(gdb.Breakpoint):
    def stop(self):
        try:
            event=gdb.newest_frame().read_var('event')
            kind=int(event['type'])
            if kind in (768,769):
                key=int(event['key']['keysym']['sym'])
                if key in (27,13,1073741903,1073741904,1073741905,1073741906) and not int(event['key']['repeat']):
                    input_record('sdl-key',key=key,pressed=kind==768)
        except Exception as exc:
            input_record('diagnostic-error',message=str(exc))
            self.enabled=False
        return False

class GameplayKeyboard(gdb.Breakpoint):
    def stop(self):
        try:
            event=gdb.newest_frame().read_var('event').dereference()
            pp=gdb.default_visualizer(event['keyOnce'])
            if pp is None:
                raise ValueError('Native keyboard set visualizer unavailable')
            keys=[int(value) for _,value in pp.children()]
            if keys:
                input_record('game-key-once',keys=keys,
                             actualTimeMs=int(active_match()['actualTime_ms']))
        except Exception as exc:
            input_record('diagnostic-error',message=str(exc))
            self.enabled=False
        return False

class ReloadFocus(gdb.Breakpoint):
    def stop(self):
        try:
            name=view_name(gdb.newest_frame().read_var('view'))
            input_record('reload-focus',name=name)
        except Exception as exc:
            self.enabled=False
            control('error',message=str(exc))
        return False

class PauseFocus(gdb.Breakpoint):
    def stop(self):
        try:
            name=view_name(gdb.newest_frame().read_var('view'))
            if name and name.startswith('button_'):
                input_record('pause-focus',name=name)
        except Exception as exc:
            input_record('diagnostic-error',message=str(exc))
            self.enabled=False
        return False

class PauseMenu(gdb.Breakpoint):
    def stop(self):
        global pause_seen
        if not game_ready:
            return False
        self.enabled=False
        try:
            control('pause-menu',humanCounts=human_counts(active_match()))
            pause_seen=True
            keyboard_observer.enabled=False
            focus_observer.enabled=True
        except Exception as exc:
            control('error',message=str(exc))
        return False

class ControllerMenu(gdb.Breakpoint):
    def stop(self):
        global control_menu_seen
        self.enabled=False
        try:
            control('controller-menu',humanCounts=human_counts(active_match()))
            control_menu_seen=True
            focus_observer.enabled=False
            sides_observer.enabled=True
        except Exception as exc:
            control('error',message=str(exc))
        return False

class ControllerSides(gdb.Breakpoint):
    def stop(self):
        global last_sides
        try:
            page=gdb.newest_frame().read_var('this').dereference()
            if not bool(page['inGame']):
                return False
            v=page['sides']['_M_impl']
            start=v['_M_start']
            count=int(v['_M_finish']-start)
            if not 1<=count<=16:
                raise ValueError('Unexpected native controller count')
            sides=[int((start+i).dereference()['side']) for i in range(count)]
            if sides!=last_sides:
                last_sides=sides
                input_record('controller-sides',sides=sides)
        except Exception as exc:
            self.enabled=False
            input_record('diagnostic-error',message=str(exc))
        return False

class ControlApplied(gdb.FinishBreakpoint):
    def stop(self):
        global cpu_released
        try:
            counts=human_counts(active_match())
            control('cpu-control',humanCounts=counts)
            cpu_released=counts==[0,0]
        except Exception as exc:
            control('error',message=str(exc))
        return False
    def out_of_scope(self):
        control('error',message='Controller update did not return')

class ControllerUpdate(gdb.Breakpoint):
    def stop(self):
        if not control_menu_seen:
            return False
        self.enabled=False
        sides_observer.enabled=False
        try:
            if int(gdb.newest_frame().read_var('this'))!=tracked:
                raise ValueError('Controller update on different match')
            ControlApplied(gdb.newest_frame(),internal=True)
        except Exception as exc:
            control('error',message=str(exc))
        return False

class ResumeFinished(gdb.FinishBreakpoint):
    def stop(self):
        try:
            m=active_match()
            if bool(m['pause']) or human_counts(m)!=[0,0]:
                raise ValueError('Native resume did not leave an unpaused CPU match')
            control('resumed',humanCounts=[0,0],clockMs=int(m['matchTime_ms']))
            sdl_observer.enabled=False
        except Exception as exc:
            control('error',message=str(exc))
        return False
    def out_of_scope(self):
        control('error',message='Native resume did not return')

class ResumeMatch(gdb.Breakpoint):
    def stop(self):
        if not cpu_released:
            return False
        self.enabled=False
        try:
            ResumeFinished(gdb.newest_frame(),internal=True)
        except Exception as exc:
            control('error',message=str(exc))
        return False

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
                     timeScale=float(m['matchTimeScale']),actualTimeMs=int(m['actualTime_ms']))
            elif tracked!=int(ptr):
                raise ValueError('Native match identity changed')
            elif name=='e_MatchPhase_2ndHalf':
                if human_counts(m)!=[0,0]:
                    raise ValueError('Human controller active at halftime')
                emit('half-boundary',clockMs=int(m['matchTime_ms']),actualTimeMs=int(m['actualTime_ms']))
            elif name=='e_MatchPhase_1stExtraTime':
                # Upstream uses this transition even at normal regulation end.
                if bool(m['inPlay']) or bool(m['inSetPiece']):
                    raise ValueError('Regulation boundary while playing')
                emit('regulation-end',clockMs=int(m['matchTime_ms']),actualTimeMs=int(m['actualTime_ms']))
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
            if int(ptr)!=tracked or not bool(m['gameOver']) or not bool(data['historySaved']) or human_counts(m)!=[0,0]:
                raise ValueError('Unexpected final history state')
            emit('fulltime',teamIds=ids(m),clockMs=int(m['matchTime_ms']),
                 score=[int(data['goalCount'][i]) for i in (0,1)])
        except Exception as exc:
            emit('error',message=str(exc))
        return False

gdb.execute('set may-call-functions off')
gdb.execute('set pagination off')
sdl_observer=SDLEscape('blunted::UserEventManager::InputSDLEvent',internal=True)
keyboard_observer=GameplayKeyboard('GamePage::ProcessKeyboardEvent',internal=True)
focus_observer=PauseFocus('blunted::Gui2WindowManager::SetFocus',internal=True)
sides_observer=ControllerSides('ControllerSelectPage::SetImagePositions',internal=True)
for observer in (sdl_observer,keyboard_observer,focus_observer,sides_observer):
    if observer.pending:
        raise ValueError('Unresolved native input observation')
    observer.enabled=False
reload_observer=ReloadFocus('blunted::Gui2WindowManager::SetFocus',internal=True)
if reload_observer.pending:
    raise ValueError('Unresolved native reload focus observation')
for observer in (Phase('Match::SetMatchPhase',internal=True),
                 GameplayReady('GamePage::Process',internal=True),
                 PauseMenu('IngamePage::IngamePage',internal=True),
                 ResumeMatch('IngamePage::ResumeMatch',internal=True),
                 ControllerMenu('IngamePage::GoControllerSelect',internal=True),
                 ControllerUpdate('Match::UpdateControllerSetup',internal=True),
                 HalfMenu('MatchPhasePage::Process','half-menu'),
                 HalfMenu('MatchPhasePage::ContinueGame','half-continue'),
                 Final('GameOverPage::Process',internal=True)):
    if observer.pending:
        raise ValueError('Unresolved native phase observation')
emit('ready',pid=gdb.selected_inferior().pid)
