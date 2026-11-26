#!/usr/bin/env python3
"""Tribün Manager 3D dev server. Stdlib-only; not production auth/security.
Serves static game and an SQLite-backed synchronized 6-club league.
The server alone decides daily match start/finish/results; clients cannot advance days.
"""
from __future__ import annotations
from contextlib import closing
import hashlib, json, os, secrets, shutil, sqlite3, threading, time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from economy import TransferService, EconomyError, SET_PIECE_ATTRIBUTES
from live_match import LiveMatchError, Registry, SCHEMA as LIVE_SCHEMA, kick_control
import season_state
import native_shadow
import native_live
import native_av_gateway
import importlib.util
_av_spec=importlib.util.spec_from_file_location('native_av_queue',Path(__file__).resolve().parent/'integrations/league-soccer/native_av_queue.py')
native_av_queue=importlib.util.module_from_spec(_av_spec)
_av_spec.loader.exec_module(native_av_queue)

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('TRIBUN_DB',str(ROOT/'tribun-dev.sqlite3')))
PORT=int(os.environ.get('PORT','8000'))
TEAMS=['Moreirense SK','Estrela Amadora','Altınşehir SK','Kuzey 1907','Fırtına FK','Anadolu Yıldızları']
DEFAULT={'formation':'4-3-3','mentality':'balanced','press':58,'tempo':61,'aggression':55,'playstyle':'possession','marking':'zone','line':'normal','offside':'off','passing':'mixed','width':'balanced','onLoss':'regroup','onWin':'retain','fullbacks':'support','crossing':'mixed','shooting':'balanced'}
ENUMS={'mentality':('balanced','attacking','defensive'),'playstyle':('possession','wing','counter','direct'),'marking':('zone','man'),'line':('low','normal','high'),'offside':('off','on'),'passing':('short','mixed','direct'),'width':('narrow','balanced','wide'),'onLoss':('regroup','counterpress'),'onWin':('retain','counter'),'fullbacks':('hold','support','overlap'),'crossing':('mixed','low','early'),'shooting':('patient','balanced','early')}
LOCK=threading.RLock()
ECONOMY = None
TRANSFERS_ENABLED = True
LIVE_MATCHES = Registry()

def transfer_service():
    global ECONOMY
    if ECONOMY is None or ECONOMY.path != DATA:
        ECONOMY = TransferService(DATA)
    return ECONOMY

def db():
    c=sqlite3.connect(DATA,timeout=20)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    return c

def init_db():
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS leagues(
        code TEXT PRIMARY KEY,created REAL NOT NULL,first_kickoff REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS teams(
        league TEXT NOT NULL,slot INT NOT NULL,name TEXT NOT NULL,manager TEXT NOT NULL,
        token TEXT UNIQUE,formation TEXT NOT NULL,tactics TEXT NOT NULL,quality REAL NOT NULL,
        PRIMARY KEY(league,slot),FOREIGN KEY(league) REFERENCES leagues(code));
        CREATE TABLE IF NOT EXISTS fixtures(
        league TEXT NOT NULL,round INT NOT NULL,home INT NOT NULL,away INT NOT NULL,
        kickoff REAL NOT NULL,home_score INT,away_score INT,home_yellows INT,away_yellows INT,
        home_reds INT,away_reds INT,PRIMARY KEY(league,round,home,away));''' + LIVE_SCHEMA + season_state.SCHEMA + native_shadow.SCHEMA + native_av_queue.SCHEMA)

def rounds():
    # 6-team double round robin: 5 rounds each leg, 3 matches per day.
    arr=list(range(6));first=[]
    for r in range(5):
        pairs=[]
        for i in range(3):
            a,b=arr[i],arr[-i-1]
            if r%2:a,b=b,a
            pairs.append((a,b))
        first.append(pairs)
        arr=[arr[0],arr[-1],*arr[1:-1]]
    return first+[[(b,a) for a,b in pair] for pair in first]

def serialize_tactics(raw):
    t=dict(DEFAULT)
    if isinstance(raw,dict):
        for k in DEFAULT:
            if k in raw:
                v=raw[k]
                if k in ('press','tempo','aggression'):
                    try:v=max(0,min(100,int(v)))
                    except (ValueError,TypeError,OverflowError):continue
                elif not isinstance(v,str) or len(v)>60:continue
                elif k in ENUMS and v not in ENUMS[k]:continue
                t[k]=v
    return json.dumps(t,ensure_ascii=False,separators=(',',':'))

def new_league(manager):
    manager=str(manager or 'Menajer')[:35]
    with LOCK,db() as c:
        while True:
            code=secrets.token_hex(3).upper()
            if not c.execute('SELECT 1 FROM leagues WHERE code=?',(code,)).fetchone():break
        created=time.time();kickoff=created+86400
        c.execute('INSERT INTO leagues VALUES(?,?,?)',(code,created,kickoff))
        token=secrets.token_urlsafe(26)
        for i,name in enumerate(TEAMS):
            c.execute('INSERT INTO teams VALUES(?,?,?,?,?,?,?,?)',
                (code,i,name,manager if i==0 else 'Bilgisayar',token if i==0 else None,DEFAULT['formation'],serialize_tactics(DEFAULT),round(78+i*1.9,1)))
        for r,pairs in enumerate(rounds()):
            for a,b in pairs:c.execute('INSERT INTO fixtures(league,round,home,away,kickoff) VALUES(?,?,?,?,?)',(code,r,a,b,kickoff+r*86400))
    return {'code':code,'token':token,'club':TEAMS[0]}

def join_league(code,manager):
    code=str(code or '').strip().upper()
    with LOCK,db() as c:
        if not c.execute('SELECT 1 FROM leagues WHERE code=?',(code,)).fetchone():raise ValueError('Lig kodu bulunamadı.')
        row=c.execute('SELECT slot,name FROM teams WHERE league=? AND token IS NULL ORDER BY slot LIMIT 1',(code,)).fetchone()
        if not row:raise ValueError('Bu ligdeki altı takımın tamamı dolu.')
        tok=secrets.token_urlsafe(26)
        c.execute('UPDATE teams SET manager=?, token=? WHERE league=? AND slot=?',(str(manager or 'Menajer')[:35],tok,code,row['slot']))
        return {'code':code,'token':tok,'club':row['name']}

def identified(c,token):
    row=c.execute('SELECT * FROM teams WHERE token=?',(token,)).fetchone()
    if not row:raise ValueError('Geçersiz veya süresi dolmuş menajer anahtarı.')
    return row

def update_tactics(token, tactics, formation=None):
    settle_due()  # finalize old days before accepting edits
    with LOCK,db() as c:
        person=identified(c,token)
        active=c.execute('SELECT 1 FROM fixtures WHERE league=? AND kickoff<=? AND home_score IS NULL LIMIT 1',(person['league'],time.time())).fetchone()
        if active:raise ValueError('Maç oynanırken taktikler kilitlidir; maç bitince değiştirebilirsin.')
        formation=formation if formation in ('4-3-3','4-2-3-1','4-4-2','3-5-2','5-3-2','4-5-1') else person['formation']
        c.execute('UPDATE teams SET formation=?,tactics=? WHERE token=?',(formation,serialize_tactics(tactics),token))
        return {'ok':True,'formation':formation}

def settle_due(now=None):
    """Freeze EVERY due fixture once; results come only from the real Match worker.

    Configuration is persisted before a worker is made visible. A watcher and
    the scheduler race safely under LOCK; neither can choose different squads
    nor create a second match. No Python approximation is permitted here.
    """
    now=time.time() if now is None else now
    created=[]
    with LOCK:
        with db() as c:
            # Acquire the SQLite write lock before reading any squad. Linked
            # transfer profiles use independent database connections, so this
            # makes all three fixture snapshots an atomic kickoff boundary.
            c.execute('BEGIN IMMEDIATE')
            due=c.execute('''SELECT f.league,f.round,f.home,f.away,f.kickoff FROM fixtures f
                WHERE f.kickoff<=? AND f.home_score IS NULL
                AND NOT EXISTS (SELECT 1 FROM live_matches l
                WHERE l.league=f.league AND l.round=f.round
                AND l.home=f.home AND l.away=f.away)
                ORDER BY f.kickoff,f.league,f.round,f.home,f.away''',(now,)).fetchall()
            if due and not shutil.which('node'):
                raise LiveMatchError('Lig fikstürlerini oynatmak için sunucuda Node.js gerekli.')
            for fixture in due:
                # If a server missed more than one matchday, freeze only the
                # earliest unfinished round. A later round must NOT capture
                # yesterday's fitness or suspensions before the previous real
                # workers have settled their authoritative results.
                prior=c.execute('''SELECT 1 FROM fixtures WHERE league=?
                    AND round<? AND home_score IS NULL LIMIT 1''',
                    (fixture['league'],fixture['round'])).fetchone()
                if prior:continue
                key=tuple(fixture[field] for field in ('league','round','home','away'))
                kickoff=fixture['kickoff']
                config=live_config(c,key,now,kickoff)
                c.execute('''INSERT INTO live_matches
                    (league,round,home,away,kickoff,config) VALUES(?,?,?,?,?,?)''',
                    (*key,kickoff,json.dumps(config,ensure_ascii=False)))
                native_shadow.enqueue(c,key,config)
                created.append((key,kickoff,config))
            if os.environ.get('TRIBUN_NATIVE_AV_QUEUE')=='1':
                native_av_queue.sync(c,now)
            pending=c.execute('''SELECT league,round,home,away,kickoff,config
                FROM live_matches WHERE final_state IS NULL AND kickoff<=?
                ORDER BY kickoff,league,round,home,away''',(now,)).fetchall()
        # Register only after the committed kickoff snapshots exist. Reconcile
        # already provisioned matches as well, so a process failure between
        # committing a fixture and registering its worker cannot strand it.
        registry_path=Path(DATA).resolve()
        for item in pending:
            key=tuple(item[field] for field in ('league','round','home','away'))
            LIVE_MATCHES.get(registry_path,key,item['kickoff'],json.loads(item['config']))
    return len(created)

def status(token, now=None):
    now=time.time() if now is None else now
    settle_due(now)
    with db() as c:
        person=identified(c,token)
        code=person['league'];teams=[dict(t) for t in c.execute('SELECT * FROM teams WHERE league=? ORDER BY slot',(code,))]
        fix=[dict(f) for f in c.execute('SELECT * FROM fixtures WHERE league=? ORDER BY round,home',(code,))]
        current_round=max(0,min(9,int((now-fix[0]['kickoff'])//86400))) if now>=fix[0]['kickoff'] else 0
        next_time=min((f['kickoff'] for f in fix if f['kickoff']>now),default=None)
        active=[f for f in fix if f['kickoff']<=now and f['home_score'] is None]
        standings=[]
        for t in teams:
            item={'slot':t['slot'],'club':t['name'],'manager':t['manager'],'played':0,'w':0,'d':0,'l':0,'gf':0,'ga':0,'points':0}
            for f in fix:
                if f['home_score'] is None or t['slot'] not in (f['home'],f['away']):continue
                home=t['slot']==f['home'];gf=f['home_score'] if home else f['away_score'];ga=f['away_score'] if home else f['home_score'];item['played']+=1;item['gf']+=gf;item['ga']+=ga;item['w']+=gf>ga;item['d']+=gf==ga;item['l']+=gf<ga;item['points']+=3 if gf>ga else 1 if gf==ga else 0
            standings.append(item)
        standings.sort(key=lambda a:(-a['points'],-(a['gf']-a['ga']),-a['gf'],a['slot']))
        # The league screen displays *its own* roster, including currently
        # benched players, not stale or other-manager wallet data.
        roster=football_team_snapshot(c,person,current_round)
        own_players=roster['players'] if roster['players'] else [
            season_state.status(c,code,person['slot'],p,current_round)
            for p in season_state.demo_roster(person['formation'])]
        rotation=[{'name':p.get('name','Oyuncu'),'position':p.get('subposition') or p.get('pos'),
                   'rating':p.get('rating',80),'fitness':p.get('fitness',95),
                   **p.get('season',{})} for p in own_players]
        match=next((f for f in fix if f['round']==current_round and person['slot'] in (f['home'],f['away'])),None)
        if not match:match=next((f for f in fix if f['round']==9 and person['slot'] in (f['home'],f['away'])),None)
        return {'server_time':now,'code':code,'manager':person['manager'],'my_slot':person['slot'],'my_club':person['name'],'my_formation':person['formation'],'my_tactics':json.loads(person['tactics']),
            'next_kickoff':next_time,'first_kickoff':fix[0]['kickoff'],'day':min(10,current_round+1),'active':active,'my_match':match,'standings':standings,
            'my_rotation':rotation,'my_rotation_source':roster['source'],
            'teams':[{'slot':t['slot'],'name':t['name'],'manager':t['manager'],'claimed':bool(t['token'])} for t in teams],
            'recent':[{**f,'home_name':TEAMS[f['home']],'away_name':TEAMS[f['away']]} for f in fix if f['home_score'] is not None][-12:]}

# This projection is deliberately separate from the transfer-account view. A
# local opponent needs football data, never the other manager's wallet, offers,
# scouting results, account identifiers or authentication material.
FOOTBALL_FIELDS = ('id','uid','name','number','face','pos','subposition','positions','archetype',
    'rating','fitness','form','preferredFoot','weakFoot','passing','shooting',
    'tackling','dribbling','pace','agility','heading','crossing','strength','vision',
    'composure','acceleration','balance','endurance','anticipation','decisions',
    'workRate','goalkeeping','reactions','handling','keeperHandling','reflexes','dataKind',
    'providerId','updatedAt', *SET_PIECE_ATTRIBUTES)

def football_team_snapshot(c, team, round_number=None, *, fixture_ready=False):
    result={'slot':team['slot'],'name':team['name'],'formation':team['formation'],
            'tactics':json.loads(team['tactics']),'source':'missing-roster',
            'players':[],'starters':[],'revision':None}
    exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='transfer_league_links'").fetchone()
    if not exists:return eligible_team_snapshot(c,team,result,round_number,fixture_ready)
    row=c.execute('''SELECT p.state FROM transfer_league_links l
        JOIN transfer_profiles p ON p.id=l.profile WHERE l.league=? AND l.slot=?''',
        (team['league'],team['slot'])).fetchone()
    if not row:return eligible_team_snapshot(c,team,result,round_number,fixture_ready)
    state=json.loads(row['state'])
    players=[{key:p[key] for key in FOOTBALL_FIELDS if key in p}
             for p in state.get('players',[]) if isinstance(p,dict) and p.get('owned',True)]
    ids={p.get('id') for p in players if type(p.get('id')) is int}
    starters=state.get('starters',[])
    if not isinstance(starters,list) or len(starters)!=11 or any(type(i) is not int or i not in ids for i in starters) or len(set(starters))!=11:
        result['source']='invalid-roster'
        return result
    result.update(source='linked-roster',players=players,starters=starters[:],revision=state.get('revision'))
    return eligible_team_snapshot(c,team,result,round_number,fixture_ready)

def eligible_team_snapshot(c,team,result,round_number,fixture_ready):
    if round_number is None:return result
    if fixture_ready and result['source']=='missing-roster':
        result={**result,'players':season_state.demo_roster(team['formation']),
                'starters':list(range(11)),'source':'league-demo'}
    if not result['players']:return result
    projected=[season_state.status(c,team['league'],team['slot'],p,round_number) for p in result['players']]
    result={**result,'players':projected}
    try:
        result['starters'],replacements=season_state.check_lineup(projected,result['starters'])
    except ValueError as exc:
        if fixture_ready:raise LiveMatchError(str(exc),409) from exc
        result['lineupError']=str(exc)
        return result
    result['automaticReplacements']=replacements
    return result

def local_match(token, now=None):
    """Read a single football-only fixture snapshot; local play never settles it."""
    now=time.time() if now is None else now
    settle_due(now)
    with db() as c:
        c.execute('BEGIN')
        person=identified(c,token)
        fixtures=c.execute('''SELECT f.*, EXISTS(SELECT 1 FROM live_matches l WHERE l.league=f.league
            AND l.round=f.round AND l.home=f.home AND l.away=f.away) AS watched
            FROM fixtures f WHERE league=? AND (home=? OR away=?)
            ORDER BY round''',(person['league'],person['slot'],person['slot'])).fetchall()
        # All due fixtures have authoritative records now. 'Watched' is no
        # longer a proxy for the current round: prefer the newest started
        # unfinished fixture, then the next future match.
        unfinished=[f for f in fixtures if f['home_score'] is None]
        started=[f for f in unfinished if f['kickoff']<=now]
        upcoming=[f for f in unfinished if f['kickoff']>now]
        fixture=max(started,key=lambda f:(f['kickoff'],f['round'])) if started else (
            min(upcoming,key=lambda f:(f['kickoff'],f['round'])) if upcoming else (
                fixtures[-1] if fixtures else None))
        if fixture is None:raise ValueError('Kulübün için fikstür bulunamadı.')
        enemy_slot=fixture['away'] if fixture['home']==person['slot'] else fixture['home']
        enemy=c.execute('SELECT * FROM teams WHERE league=? AND slot=?',(person['league'],enemy_slot)).fetchone()
        if enemy is None:raise ValueError('Fikstürün rakip kulübü bulunamadı.')
        active=fixture['kickoff']<=now and (fixture['watched'] or now<fixture['kickoff']+300)
        phase='completed' if fixture['home_score'] is not None else 'live' if active else 'scheduled'
        config_row=c.execute('''SELECT config FROM live_matches
            WHERE league=? AND round=? AND home=? AND away=?''',
            tuple(fixture[field] for field in ('league','round','home','away'))).fetchone()
        if config_row:
            # The football-only local preview must display the SAME immutable
            # XI and tactics that the server worker actually started with.
            config=json.loads(config_row['config'])
            def frozen_team(side,slot):
                home=side==0
                return {'slot':slot,'name':config['homeName' if home else 'awayName'],
                    'formation':config['formation' if home else 'awayFormation'],
                    'tactics':config['tactics' if home else 'awayTactics'],
                    'players':config['players' if home else 'awayPlayers'],
                    'starters':config['starters' if home else 'awayStarters'],
                    'source':config.get('homeRosterSource' if home else 'awayRosterSource','kickoff-snapshot'),
                    'revision':config.get('homeRosterRevision' if home else 'awayRosterRevision')}
            own=frozen_team(0 if fixture['home']==person['slot'] else 1,person['slot'])
            opponent=frozen_team(0 if fixture['home']==enemy_slot else 1,enemy_slot)
        else:
            own=football_team_snapshot(c,person,fixture['round'])
            opponent=football_team_snapshot(c,enemy,fixture['round'])
        return {'version':1,'snapshotAt':now,'competitionRules':{'maxSubstitutions':5,'substitutionWindows':3,'minPlayers':7},
            'fixture':{key:fixture[key] for key in ('league','round','home','away','kickoff')} |
                {'isHome':fixture['home']==person['slot'],'state':phase},
            'ownTeam':own,'opponent':opponent}

def live_config(database, key, now, kickoff):
    teams = [database.execute('SELECT * FROM teams WHERE league=? AND slot=?', (key[0], slot)).fetchone()
             for slot in key[2:]]
    home, away = (football_team_snapshot(database, team, key[1],fixture_ready=True) for team in teams)
    seed = int.from_bytes(hashlib.sha256(':'.join(map(str, key)).encode()).digest()[:4], 'big')
    # No attendance-dependent catchup or data lookup after this durable commit.
    # Recovery derives elapsed ticks from kickoff and replays stored operations.
    return {'seed':seed,'matchMinutes':5,'snapshotAt':kickoff,'capturedAt':now,'seasonTracking':True,
            'engineSHA256':hashlib.sha256((ROOT/'football-sim.js').read_bytes()).hexdigest(),
            'workerSHA256':hashlib.sha256((ROOT/'live-match-worker.cjs').read_bytes()).hexdigest(),
            'homeName':home['name'],'awayName':away['name'],'formation':home['formation'],
            'awayFormation':away['formation'],'tactics':home['tactics'],'awayTactics':away['tactics'],
            'players':home['players'],'awayPlayers':away['players'],'starters':home['starters'],
            'awayStarters':away['starters'],
            'homeAutomaticReplacements':home.get('automaticReplacements',[]),
            'awayAutomaticReplacements':away.get('automaticReplacements',[]),
            'homeRosterSource':home['source'],'awayRosterSource':away['source'],
            'homeRosterRevision':home['revision'],'awayRosterRevision':away['revision']}

def live_session(token, round_number, *, watch, now=None):
    if type(round_number) is not int or not 0 <= round_number < 10:
        raise LiveMatchError('Maç günü geçersiz.',400)
    now = time.time() if now is None else now
    # Provisioning is independent of the viewer. On the usual background
    # scheduler path the record already exists before a page is opened.
    settle_due(now)
    with LOCK, closing(db()) as c, c:
        try:
            person = identified(c,token)
        except ValueError as exc:
            raise LiveMatchError(str(exc),403) from exc
        fixture = c.execute('SELECT * FROM fixtures WHERE league=? AND round=? AND (home=? OR away=?)',
                            (person['league'],round_number,person['slot'],person['slot'])).fetchone()
        if fixture is None:
            raise LiveMatchError('Bu maç için izleyici yetkin yok.',403)
        key = tuple(fixture[field] for field in ('league','round','home','away'))
        kickoff = fixture['kickoff']
        stored = c.execute('SELECT config FROM live_matches WHERE league=? AND round=? AND home=? AND away=?',
                           key).fetchone()
        if stored is None or (watch and now < kickoff):
            raise LiveMatchError('Bu karşılaşma şu anda canlı izlenemiyor.',409)
        config = json.loads(stored['config'])
        side = 0 if person['slot']==fixture['home'] else 1
    return LIVE_MATCHES.get(Path(DATA).resolve(),key,kickoff,config), side

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def json_response(self, data, code=200):
        body=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def native_av_access(self,round_number,body=None):
        root=os.environ.get('TRIBUN_NATIVE_AV_GATEWAY_ROOT')
        if not root or Path(root).resolve().is_relative_to(ROOT.resolve()):return self.json_response({'error':'Native AV deneysel erişimi kapalı.'},503)
        try:
            with LOCK,closing(db()) as c:
                attempt,side=native_av_gateway.resolve(c,self.transfer_token(),round_number,time.time())
            return self.json_response(native_av_gateway.forward(root,attempt,side,round_number,body),202 if body is not None else 200)
        except (native_av_gateway.GatewayError,native_live.ControlError) as e:return self.json_response({'error':str(e)},e.status)
        except (sqlite3.Error,OSError,ValueError,TypeError):return self.json_response({'error':'Native AV erişimi kullanılamıyor.'},503)
    def do_GET(self):
        p=urlsplit(self.path)
        if p.path=='/api/league/native-av/tactics':
            v=parse_qs(p.query).get('round',[''])[0]
            return self.native_av_access(int(v) if len(v)==1 and v in '0123456789' else None)
        if p.path=='/api/transfers/state':
            if not TRANSFERS_ENABLED:return self.json_response({'error':'Lig modunda transfer hizmeti kapalı.'},503)
            try:return self.json_response(transfer_service().status(self.transfer_token()))
            except EconomyError as e:return self.json_response({'error':str(e)},403)
        if p.path=='/api/health':return self.json_response({'ok':True,'mode':'development' if TRANSFERS_ENABLED else 'league','daily_match_seconds':300,'dailyLeague':True,'transfers':TRANSFERS_ENABLED})
        if p.path=='/api/league/status':
            try:return self.json_response(status(parse_qs(p.query).get('token',[''])[0]))
            except LiveMatchError as e:return self.json_response({'error':str(e)},e.status)
            except ValueError as e:return self.json_response({'error':str(e)},403)
        if p.path=='/api/league/local-match':
            try:return self.json_response(local_match(self.transfer_token()))
            except LiveMatchError as e:return self.json_response({'error':str(e)},e.status)
            except ValueError as e:return self.json_response({'error':str(e)},403)
        if p.path in ('/api/league/native-pilot','/api/league/native-pilot/broadcast'):
            try:
                value=parse_qs(p.query).get('round',[''])[0]
                round_number=int(value) if len(value)==1 and value in '0123456789' else None
                match,side=live_session(self.transfer_token(),round_number,watch=True)
                with closing(db()) as c:
                    if p.path.endswith('/broadcast'):
                        if native_live.is_interactive(c,match.key):
                            return self.json_response(native_shadow.interactive_broadcast(c,match.key,side))
                        return self.json_response(native_shadow.broadcast(c,match.key,time.time()))
                    return self.json_response(native_shadow.status(c,match.key,time.time()))
            except LiveMatchError as e:return self.json_response({'error':str(e)},e.status)
            except (sqlite3.Error,ValueError,OSError):return self.json_response({'error':'Native pilot kaydına ulaşılamadı.'},503)
        if p.path=='/api/league/live-match':
            try:
                value=parse_qs(p.query).get('round',[''])[0]
                round_number=int(value) if len(value)==1 and value in '0123456789' else None
                match,side=live_session(self.transfer_token(),round_number,watch=True)
                return self.json_response(match.read(side))
            except LiveMatchError as e:return self.json_response({'error':str(e)},e.status)
            except sqlite3.Error:return self.json_response({'error':'Canlı maç kaydına ulaşılamadı.'},503)
        if p.path.startswith('/api/'):return self.json_response({'error':'API yolu bulunamadı.'},404)
        # Development data and server code must never be downloadable as assets.
        # Decode before checking private paths; native capability files must never be static assets.
        from urllib.parse import unquote
        decoded=unquote(p.path)
        if any(part.startswith('local-manager-') or part in ('local-url.txt','league-gateway.key') for part in Path(decoded).parts):
            return self.json_response({'error':'Dosya erişime kapalı.'},403)
        parts=Path(decoded).parts
        if any(x.startswith('.') or x in ('work','node_modules','__pycache__') for x in parts if x not in ('/','')) or decoded.endswith(('.py','.sqlite','.sqlite3','.db','-wal','-shm')):
            return self.json_response({'error':'Dosya erişime kapalı.'},403)
        return super().do_GET()
    def transfer_token(self):
        auth=self.headers.get('Authorization','')
        return auth[7:] if auth.startswith('Bearer ') else ''
    def do_POST(self):
        p=urlsplit(self.path).path
        if p=='/api/league/native-av/tactics':
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2048:raise ValueError()
                self.connection.settimeout(5)
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError()
                native_live.validate_command(body)
                return self.native_av_access(body.get('round'),body)
            except native_live.ControlError as e:return self.json_response({'error':str(e)},e.status)
            except (ValueError,TypeError,UnicodeError,TimeoutError):return self.json_response({'error':'Geçersiz komut.'},400)
        if p=='/api/league/native-pilot/tactics':
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2048:raise native_live.ControlError('Geçersiz istek boyutu.',400)
                body=json.loads(self.rfile.read(length))
                ident,values=native_live.validate_command(body)
                match,side=live_session(self.transfer_token(),body['round'],watch=True)
                session=native_live.lookup(match.key)
                if session is None:raise native_live.ControlError('Etkileşimli motor çalışmıyor.')
                return self.json_response(session.command(side,ident,values),202)
            except (LiveMatchError,native_live.ControlError) as e:return self.json_response({'error':str(e)},e.status)
            except (sqlite3.Error,OSError):return self.json_response({'error':'Komut kaydedilemedi.'},503)
            except (ValueError,TypeError,UnicodeError):return self.json_response({'error':'Geçersiz komut.'},400)
        if p=='/api/league/live-match/kick':
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=1024:raise LiveMatchError('Geçersiz istek boyutu.',400)
                body=json.loads(self.rfile.read(length))
                id_,control=kick_control(body)
                match,side=live_session(self.transfer_token(),body.get('round'),watch=False)
                return self.json_response(match.kick(side,id_,control))
            except LiveMatchError as e:return self.json_response({'error':str(e)},e.status)
            except sqlite3.Error:return self.json_response({'error':'Vuruş kaydedilemedi. Maça yeniden bağlanmayı dene.'},503)
            except (ValueError,UnicodeError):return self.json_response({'error':'Vuruş isteği okunamadı.'},400)
        if p.startswith('/api/transfers/') or p=='/api/commerce/verified-event':
            if not TRANSFERS_ENABLED:return self.json_response({'error':'Lig modunda transfer hizmeti kapalı.'},503)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=32000:raise EconomyError('Geçersiz istek boyutu.')
                raw=self.rfile.read(length)
                if p=='/api/commerce/verified-event':
                    return self.json_response(transfer_service().verified_commerce(raw,self.headers.get('X-Tribun-Signature','')))
                body=json.loads(raw)
                if not isinstance(body,dict):raise EconomyError('İstek nesne olmalı.')
                if p=='/api/transfers/profile':return self.json_response(transfer_service().create_profile(body.get('legacy')),201)
                if p=='/api/transfers/command':
                    return self.json_response(transfer_service().command(self.transfer_token(),body.get('requestId'),body.get('action'),body.get('payload',{})))
                return self.json_response({'error':'API yolu bulunamadı.'},404)
            except (ValueError,TypeError,UnicodeError) as e:return self.json_response({'error':str(e)},400)
        if p not in ('/api/league/create','/api/league/join','/api/league/tactics'):return self.json_response({'error':'API yolu bulunamadı.'},404)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<12000:raise ValueError('Geçersiz istek boyutu.')
            body=json.loads(self.rfile.read(length))
            if p.endswith('create'):data=new_league(body.get('manager'))
            elif p.endswith('join'):data=join_league(body.get('code'),body.get('manager'))
            else:data=update_tactics(body.get('token'),body.get('tactics'),body.get('formation'))
            return self.json_response(data)
        except LiveMatchError as e:return self.json_response({'error':str(e)},e.status)
        except (ValueError,json.JSONDecodeError) as e:return self.json_response({'error':str(e)},400)
    def log_message(self,format,*args):pass

def run(host='127.0.0.1', port=None, *, with_transfers=True):
    global TRANSFERS_ENABLED
    port=PORT if port is None else port
    TRANSFERS_ENABLED=with_transfers
    init_db()
    if with_transfers:
        transfer_service().import_catalog(json.loads((ROOT/'data/player-catalog.json').read_text()))
    LIVE_MATCHES.restore(Path(DATA).resolve())
    if native_shadow.enabled():native_shadow.recover(Path(DATA).resolve())
    print(f'Tribün Manager 3D development server: http://{host}:{port} | database: {DATA}',flush=True)
    stop=threading.Event()
    def worker():
        next_transfers=0
        while not stop.is_set():
            try:
                # Create all three immutable round fixtures at kickoff, even
                # with zero connected viewers. Do not wait for kickoff +300.
                settle_due()
                if with_transfers and time.monotonic()>=next_transfers:
                    transfer_service().settle_all()
                    next_transfers=time.monotonic()+10
            except Exception as e:print('scheduler:',repr(e),flush=True)
            stop.wait(.5)
    def live_worker():
        while not stop.is_set():
            LIVE_MATCHES.tick()
            stop.wait(.1)
    def native_worker():
        while not stop.is_set():
            try:
                if not native_shadow.process_one(Path(DATA).resolve(),stop=stop):stop.wait(1)
            except Exception as e:
                print('native scheduler:',repr(e),flush=True)
                stop.wait(1)
    shadow_threads=[]
    if native_shadow.enabled():
        try:count=native_shadow.worker_count()
        except ValueError as exc:
            print("Native pilot disabled:",str(exc),flush=True)
            count=0
        for index in range(count):
            thread=threading.Thread(target=native_worker,name=f"native-pilot-{index}",daemon=True)
            thread.start()
            shadow_threads.append(thread)
    threading.Thread(target=worker,daemon=True).start()
    ticker=threading.Thread(target=live_worker,daemon=True)
    ticker.start()
    try:
        with ThreadingHTTPServer((host,port),Handler) as service:
            service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        ticker.join()
        for thread in shadow_threads:thread.join(timeout=5)
        LIVE_MATCHES.close()
if __name__=='__main__':run()
