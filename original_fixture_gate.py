"""Read-only fixture eligibility guard for the original native engine.

The web kickoff timestamp is external scheduling metadata, not the native
calendar date. No launch or simulated result is produced here.
"""
from contextlib import closing
import math
from original_catalog import connect
from original_engine import digest

def next_native_fixture(path):
    before=digest(path)
    with closing(connect(path)) as db:
        teams=db.execute('SELECT team_id FROM settings LIMIT 2').fetchall()
        if len(teams)!=1 or type(teams[0][0]) is not int or teams[0][0]<=0:
            raise ValueError('Exactly one managed team required')
        team=teams[0][0]
        # Mirror LeagueGetUserNextFixture's exclusion by calendar ID, not
        # by team pair. Refuse ambiguous equal earliest timestamps.
        rows=db.execute("""SELECT c.id,c.team1_id,c.team2_id,c.timestamp
            FROM calendar c JOIN teams h ON h.id=c.team1_id JOIN teams a ON a.id=c.team2_id
            WHERE (c.team1_id=? OR c.team2_id=?)
            AND c.id NOT IN (SELECT calendar_id FROM match_results WHERE played=1)
            ORDER BY c.timestamp LIMIT 2""",(team,team)).fetchall()
        if len(rows)==2 and rows[0][3]==rows[1][3]:
            raise ValueError('Ambiguous earliest native fixture')
        result=None
        if rows:
            ident,home,away,date=rows[0]
            if any(type(i) is not int or i<=0 for i in (ident,home,away)) or home==away or not isinstance(date,str) or not date:
                raise ValueError('Invalid native fixture')
            result=dict(nativeFixtureId=ident,homeTeamId=home,awayTeamId=away,nativeDate=date,managedTeamId=team)
    if digest(path)!=before:
        raise RuntimeError('Native save changed during inspection')
    return result

def eligibility(fixture,expected,native,now):
    """Compare a reviewed explicit fixture mapping. Fail closed on mismatch."""
    if not isinstance(fixture,dict) or not isinstance(expected,dict):
        raise ValueError('Explicit web fixture and native mapping required')
    kickoff=fixture.get('kickoff')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (kickoff,now)):
        raise ValueError('Invalid scheduling timestamp')
    key=('league','round','home','away','kickoff')
    if any(k not in fixture or k not in expected for k in key):
        raise ValueError('Incomplete web fixture identity')
    if any(fixture[k]!=expected[k] for k in key):
        reason='web-fixture-mismatch'
    elif fixture.get('home_score') is not None or fixture.get('away_score') is not None:
        reason='already-scored'
    elif native is None:
        reason='no-native-fixture'
    elif any(k not in expected or native.get(k)!=expected[k] for k in ('nativeFixtureId','homeTeamId','awayTeamId','nativeDate','managedTeamId')):
        reason='native-fixture-mismatch'
    elif now<kickoff:
        reason='not-due'
    else:
        reason='eligible-for-reviewed-launch'
    return dict(eligible=reason=='eligible-for-reviewed-launch',reason=reason,
                kickoff=kickoff,automaticLaunch=False,scoreWritten=False)
