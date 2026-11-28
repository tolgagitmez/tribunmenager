"""Create a disposable league from native smoke, then collect default-config screens."""
import json
import os
from pathlib import Path
import sys
import tempfile
import original_engine as e
from original_native_saves_probe import populate,save_manifest
from original_saves import locked_store,commit,current_snapshot,restore

def run(output):
    output=Path(output).resolve()
    if output.exists():
        raise ValueError('New reference output directory required')
    env=e.clean_env(os.environ)
    work=e.cache_root()/e.REVISION
    build=e.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='native-league-references-') as tmp:
        base=Path(tmp)
        setup=base/'setup';session=base/'session'
        populate(build,setup)
        e.call(['bash',work/'source/tests/run_menu_smoke.sh',setup/'gameplayfootball',
                work/'source/data/menu_smoke_league.config','90',
                '[menu-smoke] Main menu ready, opening League Mode',
                '[menu-smoke] League save created, entering league page',
                '[menu-smoke] League page flow succeeded'],env,setup)
        with locked_store(base/'store') as root:
            if not commit(root,setup,0):
                raise RuntimeError('No closed native league save')
            snapshot=current_snapshot(root)
            before=save_manifest(snapshot)
            populate(build,session)
            restore(root,session)
            e.check_config(work/'source',session)
            if save_manifest(session/'saves')!=before:
                raise RuntimeError('Restored native save differs')
            try:
                e.call([sys.executable,Path(__file__).with_name('original_native_reload_probe.py'),
                    '--capture-league-references',session,output],env)
            finally:
                if current_snapshot(root)!=snapshot or save_manifest(snapshot)!=before:
                    raise RuntimeError('Reference capture changed retained save')
    e.verify_install(work,env)
    print(json.dumps(dict(referenceCollectionCompleted=True,operatorReviewed=False,
        productionSaveChanged=False,normalLeagueCalibrationVerified=False)),flush=True)

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Usage: original_league_reference_probe.py <new-output-directory>')
    run(sys.argv[1])
