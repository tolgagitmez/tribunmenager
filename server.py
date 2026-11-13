#!/usr/bin/env python3
"""Tribün Manager 3D dev server. Stdlib-only; not production auth/security.
Serves static game and an SQLite-backed synchronized 6-club league.
The server alone decides daily match start/finish/results; clients cannot advance days.
"""
from __future__ import annotations
import hashlib, json, os, random, secrets, sqlite3, threading, time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from economy import TransferService, EconomyError

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('TRIBUN_DB',str(ROOT/'tribun-dev.sqlite3')))
PORT=int(os.environ.get('PORT','8000'))
TEAMS=['Moreirense SK','Estrela Amadora','Altınşehir SK','Kuzey 1907','Fırtına FK','Anadolu Yıldızları']
DEFAULT={'formation':'4-3-3','mentality':'balanced','press':58,'tempo':61,'aggression':55,'playstyle':'possession','marking':'zone','line':'normal','offside':'off','passing':'mixed','width':'balanced','onLoss':'regroup','onWin':'retain','fullbacks':'support','crossing':'mixed','shooting':'balanced'}
ENUMS={'mentality':('balanced','attacking','defensive'),'playstyle':('possession','wing','counter','direct'),'marking':('zone','man'),'line':('low','normal','high'),'offside':('off','on'),'passing':('short','mixed','direct'),'width':('narrow','balanced','wide'),'onLoss':('regroup','counterpress'),'onWin':('retain','counter'),'fullbacks':('hold','support','overlap'),'crossing':('mixed','low','early'),'shooting':('patient','balanced','early')}
LOCK=threading.RLock()
ECONOMY = None

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
        home_reds INT,away_reds INT,PRIMARY KEY(league,round,home,away));''')

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
        active=c.execute('SELECT 1 FROM fixtures WHERE league=? AND kickoff<=? AND kickoff+300>? LIMIT 1',(person['league'],time.time(),time.time())).fetchone()
        if active:raise ValueError('Maç oynanırken taktikler kilitlidir; maç bitince değiştirebilirsin.')
        formation=formation if formation in ('4-3-3','4-2-3-1','4-4-2','3-5-2','5-3-2','4-5-1') else person['formation']
        c.execute('UPDATE teams SET formation=?,tactics=? WHERE token=?',(formation,serialize_tactics(tactics),token))
        return {'ok':True,'formation':formation}

def outcome(league,r,h,a,home,away):
    # Reproducible server-authoritative approximation, tactical choices are snapshotted at settle time.
    seed=int.from_bytes(hashlib.sha256(f'{league}:{r}:{h}:{a}'.encode()).digest()[:8],'big');rng=random.Random(seed)
    ht=json.loads(home['tactics']);at=json.loads(away['tactics'])
    def expectancy(team,enemy,t,et,home_adv):
        power=(team['quality']-enemy['quality'])*.025+home_adv
        style=.17 if t['playstyle']=='counter' and et['press']>68 else 0
        pressing=(t['press']-50)*.0032
        attack=.15 if t['mentality']=='attacking' else -.17 if t['mentality']=='defensive' else 0
        stamina=-max(0,t['tempo']+t['press']-145)*.009
        return max(.25,min(3.7,1.10+power+style+pressing+attack+stamina))
    def poisson(lam):
        import math
        p=math.exp(-lam);k=0;u=rng.random();s=p
        while u>s and k<9:k+=1;p*=lam/k;s+=p
        return k
    goal_h=poisson(expectancy(home,away,ht,at,.18));goal_a=poisson(expectancy(away,home,at,ht,0))
    def discipline(t):
        aggression=max(0,min(100,int(t['aggression'])));press=int(t['press']);
        yellow=sum(rng.random()<.18+aggression*.005+press*.0013 for _ in range(6))
        red=int(yellow>=2 and rng.random()<(aggression/160))
        return yellow,red
    yh,rh=discipline(ht);ya,ra=discipline(at)
    return goal_h,goal_a,yh,ya,rh,ra

def settle_due(now=None):
    now=time.time() if now is None else now
    with LOCK,db() as c:
        due=c.execute('SELECT league,round,home,away FROM fixtures WHERE kickoff+300<=? AND home_score IS NULL',(now,)).fetchall()
        for fixture in due:
            teams=c.execute('SELECT * FROM teams WHERE league=? ORDER BY slot',(fixture['league'],)).fetchall()
            result=outcome(fixture['league'],fixture['round'],fixture['home'],fixture['away'],teams[fixture['home']],teams[fixture['away']])
            c.execute('''UPDATE fixtures SET home_score=?,away_score=?,home_yellows=?,away_yellows=?,home_reds=?,away_reds=?
            WHERE league=? AND round=? AND home=? AND away=? AND home_score IS NULL''',(*result,fixture['league'],fixture['round'],fixture['home'],fixture['away']))
        return len(due)

def status(token, now=None):
    now=time.time() if now is None else now
    settle_due(now)
    with db() as c:
        person=identified(c,token)
        code=person['league'];teams=[dict(t) for t in c.execute('SELECT * FROM teams WHERE league=? ORDER BY slot',(code,))]
        fix=[dict(f) for f in c.execute('SELECT * FROM fixtures WHERE league=? ORDER BY round,home',(code,))]
        current_round=max(0,min(9,int((now-fix[0]['kickoff'])//86400))) if now>=fix[0]['kickoff'] else 0
        next_time=min((f['kickoff'] for f in fix if f['kickoff']>now),default=None)
        active=[f for f in fix if f['kickoff']<=now<f['kickoff']+300]
        standings=[]
        for t in teams:
            item={'slot':t['slot'],'club':t['name'],'manager':t['manager'],'played':0,'w':0,'d':0,'l':0,'gf':0,'ga':0,'points':0}
            for f in fix:
                if f['home_score'] is None or t['slot'] not in (f['home'],f['away']):continue
                home=t['slot']==f['home'];gf=f['home_score'] if home else f['away_score'];ga=f['away_score'] if home else f['home_score'];item['played']+=1;item['gf']+=gf;item['ga']+=ga;item['w']+=gf>ga;item['d']+=gf==ga;item['l']+=gf<ga;item['points']+=3 if gf>ga else 1 if gf==ga else 0
            standings.append(item)
        standings.sort(key=lambda a:(-a['points'],-(a['gf']-a['ga']),-a['gf'],a['slot']))
        match=next((f for f in fix if f['round']==current_round and person['slot'] in (f['home'],f['away'])),None)
        if not match:match=next((f for f in fix if f['round']==9 and person['slot'] in (f['home'],f['away'])),None)
        return {'server_time':now,'code':code,'manager':person['manager'],'my_slot':person['slot'],'my_club':person['name'],'my_formation':person['formation'],'my_tactics':json.loads(person['tactics']),
            'next_kickoff':next_time,'first_kickoff':fix[0]['kickoff'],'day':min(10,current_round+1),'active':active,'my_match':match,'standings':standings,
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
    'providerId','updatedAt')

def football_team_snapshot(c, team):
    result={'slot':team['slot'],'name':team['name'],'formation':team['formation'],
            'tactics':json.loads(team['tactics']),'source':'missing-roster',
            'players':[],'starters':[],'revision':None}
    exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='transfer_league_links'").fetchone()
    if not exists:return result
    row=c.execute('''SELECT p.state FROM transfer_league_links l
        JOIN transfer_profiles p ON p.id=l.profile WHERE l.league=? AND l.slot=?''',
        (team['league'],team['slot'])).fetchone()
    if not row:return result
    state=json.loads(row['state'])
    players=[{key:p[key] for key in FOOTBALL_FIELDS if key in p}
             for p in state.get('players',[]) if isinstance(p,dict) and p.get('owned',True)]
    ids={p.get('id') for p in players if type(p.get('id')) is int}
    starters=state.get('starters',[])
    if not isinstance(starters,list) or len(starters)!=11 or any(type(i) is not int or i not in ids for i in starters) or len(set(starters))!=11:
        result['source']='invalid-roster'
        return result
    result.update(source='linked-roster',players=players,starters=starters[:],revision=state.get('revision'))
    return result

def local_match(token, now=None):
    """Read a single football-only fixture snapshot; local play never settles it."""
    now=time.time() if now is None else now
    with db() as c:
        c.execute('BEGIN')
        person=identified(c,token)
        fixtures=c.execute('''SELECT * FROM fixtures WHERE league=? AND (home=? OR away=?)
            ORDER BY round''',(person['league'],person['slot'],person['slot'])).fetchall()
        # Prefer the active or next fixture. A completed season uses its last
        # fixture as a labelled preview, rather than inventing another opponent.
        fixture=next((f for f in fixtures if now<f['kickoff']+300 and f['home_score'] is None),None)
        fixture=fixture or (fixtures[-1] if fixtures else None)
        if fixture is None:raise ValueError('Kulübün için fikstür bulunamadı.')
        enemy_slot=fixture['away'] if fixture['home']==person['slot'] else fixture['home']
        enemy=c.execute('SELECT * FROM teams WHERE league=? AND slot=?',(person['league'],enemy_slot)).fetchone()
        if enemy is None:raise ValueError('Fikstürün rakip kulübü bulunamadı.')
        phase='completed' if fixture['home_score'] is not None else 'live' if fixture['kickoff']<=now<fixture['kickoff']+300 else 'scheduled'
        return {'version':1,'snapshotAt':now,
            'fixture':{key:fixture[key] for key in ('league','round','home','away','kickoff')} |
                {'isHome':fixture['home']==person['slot'],'state':phase},
            'ownTeam':football_team_snapshot(c,person),'opponent':football_team_snapshot(c,enemy)}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def json_response(self, data, code=200):
        body=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        p=urlsplit(self.path)
        if p.path=='/api/transfers/state':
            try:return self.json_response(transfer_service().status(self.transfer_token()))
            except EconomyError as e:return self.json_response({'error':str(e)},403)
        if p.path=='/api/health':return self.json_response({'ok':True,'mode':'development','daily_match_seconds':300})
        if p.path=='/api/league/status':
            try:return self.json_response(status(parse_qs(p.query).get('token',[''])[0]))
            except ValueError as e:return self.json_response({'error':str(e)},403)
        if p.path=='/api/league/local-match':
            try:return self.json_response(local_match(self.transfer_token()))
            except ValueError as e:return self.json_response({'error':str(e)},403)
        if p.path.startswith('/api/'):return self.json_response({'error':'API yolu bulunamadı.'},404)
        # Development data and server code must never be downloadable as assets.
        parts=Path(p.path).parts
        if any(x.startswith('.') for x in parts if x not in ('/','')) or p.path.endswith(('.py','.sqlite','.sqlite3','.db','-wal','-shm')):
            return self.json_response({'error':'Dosya erişime kapalı.'},403)
        return super().do_GET()
    def transfer_token(self):
        auth=self.headers.get('Authorization','')
        return auth[7:] if auth.startswith('Bearer ') else ''
    def do_POST(self):
        p=urlsplit(self.path).path
        if p.startswith('/api/transfers/') or p=='/api/commerce/verified-event':
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
        except (ValueError,json.JSONDecodeError) as e:return self.json_response({'error':str(e)},400)
    def log_message(self,format,*args):pass

def run():
    init_db();transfer_service().import_catalog(json.loads((ROOT/'data/player-catalog.json').read_text()))
    print(f'Tribün Manager 3D development server: http://localhost:{PORT} | database: {DATA}',flush=True)
    def worker():
        while True:
            try:settle_due();transfer_service().settle_all()
            except Exception as e:print('scheduler:',repr(e),flush=True)
            time.sleep(10)
    threading.Thread(target=worker,daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
if __name__=='__main__':run()
