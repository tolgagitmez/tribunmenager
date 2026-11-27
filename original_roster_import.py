"""Explicit, local bridge from a saved web roster export to a disposable native pack.

No account credentials, live server writes, engine changes or persistent native
saves. The operator must review player IDs, name splits and native slot order.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import tempfile

import original_engine as engine
from original_catalog import connect,catalog
from original_native_saves_probe import populate
from original_roster_pack import build_pack,validate_mapping,validate_lineup

MAX_JSON=256*1024


def read_json(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_JSON:
        raise ValueError('Invalid roster JSON file')
    return json.loads(path.read_text(encoding='utf-8'))


def prepare_rows(snapshot,mapping):
    if not isinstance(snapshot,dict) or snapshot.get('schema')!=1 or snapshot.get('source')!='saved-web-roster' or snapshot.get('nativeApplied') is not False:
        raise ValueError('Use the saved web roster preflight export')
    players=snapshot.get('players')
    if not isinstance(players,list) or not 11<=len(players)<=128:
        raise ValueError('Complete roster required')
    indexed={}
    starters={}
    for p in players:
        if not isinstance(p,dict):
            raise ValueError('Invalid exported player')
        idx=p.get('localIndex')
        name=p.get('name')
        slot=p.get('starterSlot')
        if type(idx) is not int or idx<0 or idx in indexed or not isinstance(name,str) or not name.strip() or len(name)>160:
            raise ValueError('Invalid or duplicate exported player')
        indexed[idx]=p
        if slot is not None:
            if type(slot) is not int or not 1<=slot<=11 or slot in starters:
                raise ValueError('Invalid exported starter slot')
            starters[slot]=idx
    if set(starters)!=set(range(1,12)):
        raise ValueError('Exactly eleven saved starters required')
    if not isinstance(mapping,dict) or mapping.get('schema')!=1:
        raise ValueError('Explicit mapping schema required')
    assignments=mapping.get('assignments')
    order=mapping.get('nativeSlotOrder')
    if not isinstance(assignments,list) or len(assignments)!=len(indexed):
        raise ValueError('Map every exported player')
    if not isinstance(order,list) or len(order)!=11 or any(type(i) is not int for i in order) or set(order)!=set(starters.values()):
        raise ValueError('Native order must contain exactly the saved starters')
    rows=[]
    seen=set()
    for a in assignments:
        if not isinstance(a,dict):
            raise ValueError('Invalid explicit mapping')
        idx=a.get('localIndex')
        if type(idx) is not int or idx not in indexed or idx in seen:
            raise ValueError('Unknown or repeated local player index')
        p=indexed[idx]
        first,last=a.get('firstName'),a.get('lastName')
        if not isinstance(first,str) or not isinstance(last,str) or ' '.join((first+' '+last).split())!=' '.join(p['name'].split()):
            raise ValueError('Mapped name must match exported player')
        seen.add(idx)
        rows.append(dict(localIndex=idx,nativePlayerId=a.get('nativePlayerId'),
            firstName=first,lastName=last,webRole=p.get('webRole'),
            nativeRole=a.get('nativeRole')))
    return rows,order


def suggest_mapping(snapshot,team):
    """Propose only unique exact name matches and compatible existing slots.
    No fuzzy identity guessing, no arbitrary native player substitution.
    """
    from original_roster_pack import NATIVE_ROLES,ROLE_OPTIONS
    from collections import Counter,defaultdict
    players=snapshot.get('players') if isinstance(snapshot,dict) else None
    if (not isinstance(snapshot,dict) or snapshot.get('schema')!=1 or
        snapshot.get('source')!='saved-web-roster' or snapshot.get('nativeApplied') is not False or
        not isinstance(players,list) or not 11<=len(players)<=128):
        raise ValueError('Valid saved roster export required')
    native=team['players']
    if team.get('truncated'):
        raise ValueError('Native roster is truncated')
    # Unicode casefold plus whitespace only; accents remain significant.
    norm=lambda s:' '.join(s.split()).casefold()
    groups=defaultdict(list)
    for p in native:
        groups[norm(p['name'])].append(p)
    counts=Counter(norm(p['name']) for p in players)
    assignments=[]
    blocked=[]
    starter_groups=defaultdict(list)
    seen=set()
    for p in players:
        idx=p.get('localIndex')
        if type(idx) is not int or idx<0 or idx in seen:
            raise ValueError('Duplicate or invalid web index')
        seen.add(idx)
        source=p.get('webRole')
        choices={source} if isinstance(source,str) and source in NATIVE_ROLES else ROLE_OPTIONS.get(source,set()) if isinstance(source,str) else set()
        matches=groups.get(norm(p['name']),[])
        if counts[norm(p['name'])]!=1 or len(matches)!=1 or len(choices)!=1:
            blocked.append(dict(localIndex=idx,name=p['name'],reason='ambiguous-or-missing-name' if counts[norm(p['name'])]!=1 or len(matches)!=1 else 'unsupported-role'))
            continue
        role=next(iter(choices))
        name=p['name'].split()
        first,last=' '.join(name[:-1]),name[-1]
        if len(first)>64 or len(last)>64:
            blocked.append(dict(localIndex=idx,name=p['name'],reason='name-too-long'))
            continue
        assignments.append(dict(localIndex=idx,nativePlayerId=matches[0]['id'],firstName=first,lastName=last,nativeRole=role))
        if p.get('starterSlot') is not None:
            starter_groups[role].append((p['starterSlot'],idx))
    slots=team['formation']
    order=[]
    for slot in slots:
        candidates=starter_groups[slot['role']]
        candidates.sort()
        if candidates:
            order.append(candidates.pop(0)[1])
        else:
            order.append(None)
    complete=(len(assignments)==len(players)==len(native) and len(order)==11 and
              all(i is not None for i in order) and not any(starter_groups.values()))
    mapping=dict(schema=1,teamId=team['id'],nativeSlotOrder=order,assignments=assignments)
    if complete:
        prepare_rows(snapshot,mapping)
    return dict(mapping=mapping,complete=complete,requiresReview=True,unresolved=blocked,
                nativeSlotRoles=[s['role'] for s in slots],nativePlayerCount=len(native),
                webPlayerCount=len(players),nativeApplied=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot',type=Path)
    parser.add_argument('mapping',type=Path,nargs='?')
    parser.add_argument('--inspect-team',type=int)
    parser.add_argument('--suggest-team',type=int)
    args=parser.parse_args()
    snapshot=read_json(args.snapshot)
    env=engine.clean_env(os.environ)
    work=engine.cache_root()/engine.REVISION
    build=engine.verify_install(work,env)
    default=build/'databases/default/database.sqlite'
    if args.suggest_team is not None:
        if args.mapping is not None or args.inspect_team is not None:
            parser.error('Choose one operation')
        proposal=suggest_mapping(snapshot,catalog(default,args.suggest_team))
        if proposal['complete']:
            rows,order=prepare_rows(snapshot,proposal['mapping'])
            with closing(connect(default)) as db:
                validate_mapping(db,args.suggest_team,rows)
                validate_lineup(db,args.suggest_team,rows,order)
        print(json.dumps(proposal,ensure_ascii=False,indent=2))
        return
    if args.inspect_team is not None:
        if args.mapping is not None:
            parser.error('Choose inspection or a reviewed mapping, not both')
        print(json.dumps(catalog(default,args.inspect_team),ensure_ascii=False,indent=2))
        return
    if args.mapping is None:
        parser.error('Reviewed mapping file required; inspect native team IDs first')
    mapping=read_json(args.mapping)
    rows,order=prepare_rows(snapshot,mapping)
    team=mapping.get('teamId')
    with closing(connect(default)) as db:
        validate_mapping(db,team,rows)
        validate_lineup(db,team,rows,order)
    with tempfile.TemporaryDirectory(prefix='tribun-reviewed-roster-') as tmp:
        runtime=Path(tmp)/'runtime'
        populate(build,runtime)
        engine.check_config(work/'source',runtime)
        report=build_pack(runtime,team,rows,slot_order=order)
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        print('Geçici deneysel oturum: League Mode > New League > tribun-roster-pilot.',flush=True)
        print('Seçilen takım ID: '+str(team)+'. Yetenekler, yaş, görünüm ve taktikler orijinal veri olarak kalır.',flush=True)
        print('Bu oturum normal kayıt deposuna yazılmaz ve kapatıldığında silinir.',flush=True)
        code=subprocess.run([str(runtime/'gameplayfootball')],cwd=runtime,env=env).returncode
        if code:
            raise RuntimeError('Native pilot did not exit normally')
        engine.verify_install(work,env)


if __name__=='__main__':
    main()
