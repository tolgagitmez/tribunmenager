"""Isolated scheduled native kickoff proof, not a production match runner.

The existing pinned upstream UI probe runs in its own Xvfb, opens an exact
restored autosave and waits for native Match construction. Never promotes the
disposable runtime's save or writes a league result.
"""
from contextlib import closing
from pathlib import Path
import sys
import tempfile
import time

import original_engine as engine
from original_catalog import connect,formation
from original_fixture_dispatch import claim_locked
from original_fixture_gate import eligibility,next_native_fixture
from original_native_saves_probe import populate,save_manifest
from original_saves import current_snapshot,locked_store,restore


def inspect_lineups(path,fixture):
    """Inspect saved lineups, not the actual on-pitch players."""
    before=engine.digest(path)
    lineups=[]
    with closing(connect(path)) as db:
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
            raise ValueError('Native save integrity check failed')
        for team in (fixture['homeTeamId'],fixture['awayTeamId']):
            rows=db.execute('SELECT formation_xml,tactics_xml FROM teams WHERE id=?',(team,)).fetchall()
            if len(rows)!=1:
                raise ValueError('Native fixture team missing')
            slots=formation(rows[0][0])
            if len(slots)!=11:
                raise ValueError('Expected eleven native formation slots')
            players=db.execute('SELECT id,formationorder FROM players WHERE team_id=? ORDER BY formationorder,id',(team,)).fetchall()
            if len(players)<11 or len({p[0] for p in players})!=len(players):
                raise ValueError('Incomplete or duplicate native squad')
            starters=players[:11]
            if any(type(p[0]) is not int or p[0]<=0 for p in starters):
                raise ValueError('Invalid starter IDs')
            lineups.append(dict(teamId=team,savedStarterIds=[p[0] for p in starters],
                                savedFormationSlots=len(slots),savedRosterSize=len(players)))
    if engine.digest(path)!=before:
        raise RuntimeError('Saved lineup inspection changed source')
    return lineups


def probe_due_locked(root,work,build,env,save_name,fixture,reviewed,now=None):
    """CI-only; caller must hold the disposable store lock."""
    now=time.time() if now is None else now
    snapshot=current_snapshot(root)
    base=dict(probeOnly=True,automaticProductionKickoff=False,matchCompleted=False,
              scoreWritten=False,liveOnPitchLineupVerified=False)
    if snapshot is None:
        return dict(base,claimed=False,reason='no-closed-native-save')
    if not isinstance(save_name,str) or not save_name or save_name in ('.','..') or '/' in save_name or chr(92) in save_name:
        raise ValueError('Explicit native save name required')
    source=snapshot/save_name/'autosave.sqlite'
    if source.parent.is_symlink() or source.is_symlink() or not source.is_file():
        raise ValueError('Missing reviewed native autosave')
    if reviewed.get('snapshotId')!=snapshot.name or reviewed.get('saveName')!=save_name or reviewed.get('saveSha256')!=engine.digest(source):
        return dict(base,claimed=False,reason='stale-reviewed-save')
    native=next_native_fixture(source)
    gate=eligibility(fixture,reviewed,native,now)
    if not gate['eligible']:
        return dict(base,claimed=False,reason=gate['reason'])
    lineups=inspect_lineups(source,native)
    original=save_manifest(snapshot)
    # Prepare and verify the exact bytes before consuming the durable claim.
    with tempfile.TemporaryDirectory(prefix='scheduled-kickoff-proof-') as tmp:
        session=Path(tmp)/'runtime'
        populate(build,session)
        engine.check_config(work/'source',session)
        restore(root,session)
        copied=session/'saves'/save_name/'autosave.sqlite'
        if (save_manifest(session/'saves')!=original or
                list((session/'saves').glob('*/autosave.sqlite'))!=[copied] or
                next_native_fixture(copied)!=native or inspect_lineups(copied,native)!=lineups):
            raise RuntimeError('Restored fixture or saved roster differs from reviewed snapshot')
        claim=claim_locked(root,save_name,fixture,reviewed,now)
        if not claim['claimed']:
            return dict(base,**claim)
        try:
            engine.call([sys.executable,Path(__file__).with_name('original_native_reload_probe.py'),
                         session,'--kickoff'],env)
        finally:
            if current_snapshot(root)!=snapshot or save_manifest(snapshot)!=original:
                raise RuntimeError('Disposable kickoff modified retained native snapshot')
        return dict(base,**claim,nativeMenuKickoffProbePassed=True,
                    reviewedNativeFixture=native,savedLineups=lineups,
                    restoredSnapshotVerified=True,retainedSnapshotUnchanged=True,
                    expectedFixtureIndependentlyConfirmedInMatch=False)


def probe_due(root,work,build,env,save_name,fixture,reviewed,now=None):
    with locked_store(root) as root:
        return probe_due_locked(root,work,build,env,save_name,fixture,reviewed,now)
