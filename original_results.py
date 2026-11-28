"""Read native league autosave results after exit, without writing engine data."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile

MAX_SAVES = 20
MAX_RESULTS = 100
MAX_DB_BYTES = 64 * 1024 * 1024

QUERY = """
SELECT m.calendar_id, m.team1_id, m.team2_id, h.name, a.name,
       m.team1_goals, m.team2_goals, c.timestamp
FROM match_results m
JOIN calendar c ON c.id=m.calendar_id
  AND c.team1_id=m.team1_id AND c.team2_id=m.team2_id
JOIN teams h ON h.id=m.team1_id
JOIN teams a ON a.id=m.team2_id
WHERE m.played=1 AND (
  m.team1_id=(SELECT team_id FROM settings ORDER BY id LIMIT 1)
  OR m.team2_id=(SELECT team_id FROM settings ORDER BY id LIMIT 1))
ORDER BY c.timestamp DESC, m.calendar_id DESC
LIMIT ?
"""


# Calendar entries without a completed result are pending, not predicted scores.
PENDING_QUERY = """
SELECT c.id,c.team1_id,c.team2_id,h.name,a.name,c.timestamp
FROM calendar c
JOIN teams h ON h.id=c.team1_id
JOIN teams a ON a.id=c.team2_id
WHERE (c.team1_id=? OR c.team2_id=?)
AND NOT EXISTS (SELECT 1 FROM match_results m WHERE m.calendar_id=c.id
    AND m.team1_id=c.team1_id AND m.team2_id=c.team2_id AND m.played=1)
ORDER BY c.timestamp ASC,c.id ASC LIMIT ?
"""
MAX_PENDING=30


def read_context(conn):
    rows=conn.execute("""SELECT s.team_id,t.name FROM settings s
        JOIN teams t ON t.id=s.team_id ORDER BY s.id LIMIT 2""").fetchall()
    if len(rows)!=1:
        raise ValueError('Missing or ambiguous managed team')
    team,name=rows[0]
    if type(team) is not int or team<=0 or not isinstance(name,str) or not 0<len(name)<=256:
        raise ValueError('Invalid managed team')
    pending=conn.execute(PENDING_QUERY,(team,team,MAX_PENDING+1)).fetchall()
    fixtures=[]
    for fixture,home,away,hn,an,date in pending[:MAX_PENDING]:
        if (any(type(x) is not int for x in (fixture,home,away)) or
            min(fixture,home,away)<=0 or home==away or
            not all(isinstance(x,str) and 0<len(x)<=256 for x in (hn,an,date))):
            raise ValueError('Invalid pending fixture')
        fixtures.append(dict(nativeFixtureId=fixture,homeTeamId=home,awayTeamId=away,
            homeTeam=hn,awayTeam=an,nativeDate=date))
    return dict(managedTeam=dict(id=team,name=name),pendingFixtures=fixtures,
                pendingTruncated=len(pending)>MAX_PENDING)


# Mirror the pinned native standings screen: all played match_results,
# grouped by league name, then points, goal difference, original name order.
# Limit the web report to the managed club's league and never show partial ranks.
MAX_STANDING_TEAMS=100
MAX_STANDING_MATCHES=100000


def read_standings(conn,team_id):
    league=conn.execute("""SELECT l.name FROM teams t JOIN leagues l ON t.league_id=l.id
        WHERE t.id=?""",(team_id,)).fetchone()
    if not league or not isinstance(league[0],str) or not 0<len(league[0])<=256:
        raise ValueError('Managed club league unavailable')
    teams=conn.execute("""SELECT t.id,t.name FROM teams t JOIN leagues l ON t.league_id=l.id
        WHERE l.name=? ORDER BY t.name LIMIT ?""",(league[0],MAX_STANDING_TEAMS+1)).fetchall()
    if not teams or len(teams)>MAX_STANDING_TEAMS:
        raise ValueError('League exceeds complete table limit')
    rows={}
    for ident,name in teams:
        if type(ident) is not int or ident<=0 or ident in rows or not isinstance(name,str) or not 0<len(name)<=256:
            raise ValueError('Invalid standings team')
        rows[ident]=dict(teamId=ident,name=name,played=0,won=0,drawn=0,lost=0,
                         goalsFor=0,goalsAgainst=0,goalDifference=0,points=0,form='',
                         managed=ident==team_id)
    if team_id not in rows:
        raise ValueError('Managed team absent from table')
    matches=conn.execute("""SELECT mr.team1_id,mr.team2_id,mr.team1_goals,mr.team2_goals,
        c.id FROM match_results mr LEFT JOIN calendar c ON mr.calendar_id=c.id
        WHERE mr.played=1 ORDER BY date(c.timestamp),mr.id LIMIT ?""",
        (MAX_STANDING_MATCHES+1,)).fetchall()
    if len(matches)>MAX_STANDING_MATCHES:
        raise ValueError('Standings match limit exceeded')
    for home,away,hg,ag,calendar_id in matches:
        if home not in rows and away not in rows:
            continue
        if (any(type(v) is not int for v in (home,away,hg,ag)) or min(home,away)<=0 or
            home==away or min(hg,ag)<0 or max(hg,ag)>99):
            raise ValueError('Invalid played match in standings')
        for ident,gf,ga in ((home,hg,ag),(away,ag,hg)):
            if ident not in rows:
                continue
            row=rows[ident]
            row['played']+=1
            row['goalsFor']+=gf
            row['goalsAgainst']+=ga
            row['goalDifference']+=gf-ga
            outcome='W' if gf>ga else 'D' if gf==ga else 'L'
            row[{'W':'won','D':'drawn','L':'lost'}[outcome]]+=1
            row['points']+={'W':3,'D':1,'L':0}[outcome]
            # Native form includes only played results with a calendar join.
            if calendar_id is not None:
                row['form']=(row['form']+outcome)[-5:]
    ordered=sorted(rows.values(),key=lambda row:(-row['points'],-row['goalDifference']))
    for position,row in enumerate(ordered,1):
        row['position']=position
    return dict(league=league[0],rows=ordered,scope='managed-club-league',
                source='native-standings-rules-derived-from-save',
                includesAllPlayedCompetitions=True)




def read_managed_squad(conn,team_id):
    """Saved club roster, not the live eleven or an automatic tactic mapping."""
    import original_catalog as catalog
    from xml.etree.ElementTree import ParseError
    row=conn.execute('SELECT formation_xml,tactics_xml FROM teams WHERE id=?',(team_id,)).fetchone()
    if row is None:
        raise ValueError('Managed club unavailable')
    players=conn.execute("""SELECT id,firstname,lastname,role,formationorder
        FROM players WHERE team_id=? ORDER BY formationorder,id LIMIT ?""",
        (team_id,catalog.MAX_PLAYERS+1)).fetchall()
    roster=[]
    seen=set()
    for ident,first,last,role,order in players[:catalog.MAX_PLAYERS]:
        if (type(ident) is not int or ident<=0 or ident in seen or
            not all(x is None or isinstance(x,str) and len(x)<=128 for x in (first,last,role)) or
            (order is not None and type(order) is not int)):
            raise ValueError('Invalid saved player')
        name=' '.join(x for x in (first,last) if x)
        if not name.strip():
            raise ValueError('Missing saved player name')
        seen.add(ident)
        roster.append(dict(id=ident,name=name,role=role,formationOrder=order))
    try:
        formation=catalog.formation(row[0] or '')
    except (ValueError,ParseError):
        formation=None
    try:
        tactics=catalog.tactics(row[1] or '') if row[1] else None
    except (ValueError,ParseError):
        tactics=None
    return dict(players=roster,formation=formation,tactics=tactics,
                truncated=len(players)>catalog.MAX_PLAYERS,source='saved-native-club',
                readOnly=True,representsLiveLineup=False)




def read_save(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_DB_BYTES:
        raise ValueError('Unsupported native save')
    # This is called after the native process exits; reject sidecar journals
    # instead of asking SQLite to recover or write them.
    for suffix in ('-wal','-shm','-journal'):
        if Path(str(path)+suffix).exists():
            raise ValueError('Unsettled native save journal')
    conn=sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        conn.execute('PRAGMA trusted_schema=OFF')
        conn.execute('PRAGMA query_only=ON')
        rows=conn.execute(QUERY,(MAX_RESULTS+1,)).fetchall()
        context=read_context(conn)
        try:
            context['standings']=read_standings(conn,context['managedTeam']['id'])
        except (sqlite3.Error,ValueError):
            # Older/incomplete saves may lack standings schema; retain valid results.
            context['standings']=None
        try:
            context['managedSquad']=read_managed_squad(conn,context['managedTeam']['id'])
        except (sqlite3.Error,ValueError):
            context['managedSquad']=None
    finally:
        conn.close()
    results=[]
    ids=set()
    for fixture,home,away,hn,an,hg,ag,date in rows[:MAX_RESULTS]:
        if (any(type(x) is not int for x in (fixture,home,away,hg,ag)) or
                min(fixture,home,away)<=0 or home==away or min(hg,ag)<0 or
                max(hg,ag)>99 or fixture in ids or
                not all(isinstance(x,str) and 0<len(x)<=256 for x in (hn,an,date))):
            raise ValueError('Invalid or ambiguous native result')
        ids.add(fixture)
        results.append(dict(nativeFixtureId=fixture,homeTeamId=home,awayTeamId=away,
            homeTeam=hn,awayTeam=an,homeGoals=hg,awayGoals=ag,nativeDate=date))
    return dict(results=results,truncated=len(rows)>MAX_RESULTS,**context)


def collect(session, revision, exit_code):
    report=dict(schema=1,revision=revision,exitCode=exit_code,
                source='native-league-autosave',automaticLeagueImport=False,
                provesRenderedMatch=False,saves=[],skippedSaves=0)
    saves=Path(session)/'saves'
    if exit_code!=0 or not saves.is_dir() or saves.is_symlink():
        return report
    candidates=sorted(saves.iterdir())
    report['saveLimitReached']=len(candidates)>MAX_SAVES
    for folder in candidates[:MAX_SAVES]:
        db=folder/'autosave.sqlite'
        if folder.is_symlink() or not folder.is_dir() or not db.is_file():
            continue
        try:
            result=read_save(db)
        except (OSError,sqlite3.Error,ValueError):
            report['skippedSaves']+=1
            continue
        report['saves'].append(dict(saveName=folder.name[:128],**result))
    return report


def store(report,path):
    path=Path(path)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                     prefix='.native-results-',delete=False) as f:
        temp=Path(f.name)
        try:
            json.dump(report,f,ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        except Exception:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)
