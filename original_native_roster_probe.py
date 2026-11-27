"""Real native menu roundtrip for a complete experimental roster.

Test-only player labels and targets, never a user's production team.
The unchanged upstream game itself creates the league autosave.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

import original_engine as engine
from original_catalog import connect,formation
from original_native_saves_probe import populate
from original_roster_pack import build_pack
from original_skill_mapping import factor,plan_profile

PACK='tribun-roster-pilot'


def prepare(runtime):
    path=runtime/'databases/default/database.sqlite'
    with closing(connect(path)) as db:
        team,name,xml=db.execute('SELECT id,name,formation_xml FROM teams ORDER BY name LIMIT 1').fetchone()
        slots=formation(xml)
        if len(slots)!=11:
            raise ValueError('First native club has no complete formation')
        players=db.execute('SELECT id,age,base_stat,profile_xml FROM players WHERE team_id=? ORDER BY formationorder,id',(team,)).fetchall()
        if len(players)<11:
            raise ValueError('First native club has too few players')
        # Reverse the original eleven deliberately, so a default lineup
        # cannot pass. Assign each synthetic record an explicit native role.
        order=list(reversed(range(11)))
        roles={index:slot['role'] for index,slot in zip(order,slots)}
        rows=[]
        for i,(ident,age,base,profile) in enumerate(players):
            role=roles.get(i,'GK')
            target=min(.95,factor(base,age)*(.22 if i%2==0 else .52))*100
            rows.append(dict(nativePlayerId=ident,localIndex=i,
                firstName='Pilot',lastName=f'Roster {i+1:02d}',webRole=role,
                nativeRole=role,webValues={'shooting':target}))
            if not plan_profile(base,age,profile,rows[-1]['webValues'])['proposed']:
                raise ValueError('Native shooting field cannot be mapped')
    report=build_pack(runtime,team,rows,skill_pilot=True,slot_order=order)
    if not report['experimentalLineupWritten'] or report['experimentalSkillProfilesWritten']!=len(rows):
        raise RuntimeError('Incomplete roster pilot')
    return team,name,rows,order


def verify(runtime,team,name,rows,order):
    files=list((runtime/'saves').glob('*/autosave.sqlite'))
    if len(files)!=1:
        raise ValueError('Expected a single native-created league')
    original=runtime/'databases/default/database.sqlite'
    path=files[0]
    before=engine.digest(path)
    columns='id,firstname,lastname,role,age,base_stat,profile_xml,formationorder'
    query='SELECT '+columns+' FROM players WHERE team_id=? ORDER BY formationorder,id'
    with closing(connect(runtime/'databases'/PACK/'database.sqlite')) as pack, closing(connect(path)) as saved, closing(connect(original)) as default:
        expected=pack.execute(query,(team,)).fetchall()
        observed=saved.execute(query,(team,)).fetchall()
        untouched=default.execute(query,(team,)).fetchall()
        if saved.execute('PRAGMA quick_check').fetchall()!=[('ok',)] or expected!=observed or observed==untouched:
            raise ValueError('Native league roster differs from explicit package')
        if saved.execute('SELECT team_id FROM settings').fetchall()!=[(team,)]:
            raise ValueError('Native league did not select the mapped club')
        expected_ids=[rows[i]['nativePlayerId'] for i in order]
        if [r[0] for r in observed[:11]]!=expected_ids:
            raise ValueError('Native saved starting eleven differs')
        for row in observed:
            old=next(x for x in untouched if x[0]==row[0])
            if row[4:6]!=old[4:6] or row[6]==old[6]:
                raise ValueError('Native age/base changed or profile missing')
        q='SELECT formation_xml,tactics_xml FROM teams WHERE id=?'
        if saved.execute(q,(team,)).fetchone()!=default.execute(q,(team,)).fetchone():
            raise ValueError('Native formation or tactics unexpectedly changed')
        if saved.execute('SELECT COUNT(*) FROM calendar').fetchone()[0]<1:
            raise ValueError('Native league fixture missing')
    if engine.digest(path)!=before:
        raise RuntimeError('Read-only verification changed save')
    return dict(nativeRosterSaveRoundtripVerified=True,club=name,players=len(rows),
        starterIds=expected_ids,profileRowsVerified=len(rows),nativeFormationUnchanged=True,
        nativeTacticsUnchanged=True,liveOnPitchLineupVerified=False,
        skillBehaviorVerified=False,productionRosterImported=False)


def main(full_match=False):
    env=engine.clean_env(os.environ)
    work=engine.cache_root()/engine.REVISION
    build=engine.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='native-roster-proof-') as tmp:
        runtime=Path(tmp)/'runtime'
        populate(build,runtime)
        engine.check_config(work/'source',runtime)
        before=engine.digest(runtime/'databases/default/database.sqlite')
        team,name,rows,order=prepare(runtime)
        if full_match:
            from original_match_history import HISTORY_PATH
            if (runtime/'saves').exists() or (runtime/HISTORY_PATH).exists():
                raise RuntimeError('Fresh test runtime unexpectedly contains previous league data')
            print('Geçici 3D kadro testi — League Mode > New League > '+PACK,flush=True)
            print('Takım: '+name+'; varsayılan süre ve zorluğu değiştirme.',flush=True)
            print('Play next match > Kick off > Start. Maç başlayınca Esc > Game Plan.',flush=True)
            print('Motorun canlı Match TeamData nesnesinden çizilen saha planındaki isimleri karşılaştır:',flush=True)
            for slot,i in enumerate(order,1):
                row=rows[i]
                print(f"  p{slot}: {row['nativeRole']} / {row['lastName']} (ID {row['nativePlayerId']})",flush=True)
            print('Kadro/taktik değiştirme. Bir 3D maç tamamla, Continue ile sonucu kaydet ve normal menüden çık.',flush=True)
            print('Hızlı simülasyon veya ikinci maç yapma. Görsel kontrol otomatik olarak doğrulanmış sayılmaz.',flush=True)
            if subprocess.run([str(runtime/'gameplayfootball')],cwd=runtime,env=env).returncode!=0:
                raise RuntimeError('Native match did not exit normally')
        else:
            engine.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                sys.executable,Path(__file__).with_name('original_custom_database_probe.py').resolve(),
                '--inside-private-menu',runtime,PACK],env)
        if engine.digest(runtime/'databases/default/database.sqlite')!=before:
            raise RuntimeError('Default native database changed')
        engine.verify_install(work,env)
        report=verify(runtime,team,name,rows,order)
        if full_match:
            from original_full_league_validation import verify as verify_match
            report['fullMatch']=verify_match(runtime)
            report['normalExitVerified']=True
            report['defaultConfigAtLaunch']=True
            report['commandArgumentCount']=0
            report['visualLineupReviewRequired']=True
            report['sessionConfigByteUnchanged']=(runtime/'football.config').read_bytes()==(work/'source/data/football.config').read_bytes()
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['--full-match']:
        main(full_match=True)
    elif len(sys.argv)==1:
        main()
    else:
        raise SystemExit('Usage: original_native_roster_probe.py [--full-match]')
