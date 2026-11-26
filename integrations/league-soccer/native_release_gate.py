"""Version-bound native deployment review. Never activates or authorizes commercial use."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from native_scheduler_policy import fingerprint,admitted_slots
from native_admission import number

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
KINDS=('league-e2e','capacity','hardware','rights')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def candidate():
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,timeout=10).strip()
    if not re.fullmatch('[0-9a-f]{40}',revision):raise ValueError('Unknown candidate revision')
    subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=ROOT,check=True,timeout=20)
    return revision

def runtime_identity(runtime):
    runtime=Path(runtime)
    return {'manifestSha256':sha(runtime/'tribun-runtime.json'),'binarySha256':sha(runtime/'gameplayfootball')}

def stamp(report,runtime,kind):
    if kind not in KINDS:raise ValueError('Unknown evidence kind')
    return {**report,'releaseBinding':{'schema':1,'kind':kind,'candidateCommit':candidate(),
        'runtime':runtime_identity(runtime),'bootHost':fingerprint(runtime),'observedAt':time.time()}}

def evaluate(reports,commit,runtime,host,now,*,required=3):
    if type(required) is not int or not 3<=required<=16:raise ValueError('At least one six-team round must fit')
    checks={}
    def bound(kind):
        row=reports.get(kind)
        if not isinstance(row,dict):return {}
        b=row.get('releaseBinding')
        if not isinstance(b,dict):return {}
        ok=(b.get('schema')==1 and b.get('kind')==kind and b.get('candidateCommit')==commit
            and b.get('runtime')==runtime and b.get('bootHost')==host
            and number(b.get('observedAt'),max(0,now-3600),now))
        checks[kind+'Bound']=bool(ok)
        return row if ok else {}
    e=bound('league-e2e');c=bound('capacity');h=bound('hardware');r=bound('rights')
    for kind in KINDS:checks.setdefault(kind+'Bound',False)
    history=e.get('commandHistory') or {}
    checks['fullLeagueMatch']=bool(e.get('passed') is True and e.get('nativeOnly') is True
        and e.get('authoritative') is False and e.get('leagueScreenVerified') is True
        and e.get('officialTablesUnchanged') is True and e.get('duplicateRejected') is True
        and e.get('fixtureCount')==1 and number(e.get('coverage'),.95,1.01)
        and type(e.get('appearanceCount')) is int and 22<=e['appearanceCount']<=36
        and history.get('verified') is True and history.get('submitted')==history.get('applied')==[1,1])
    try:slots=admitted_slots(c,host,now) if c else 0
    except (KeyError,TypeError,ValueError,AttributeError):slots=0
    checks['wholeRoundCapacity']=slots>=required
    checks['hardwareSingleMatch']=bool(h.get('passed') is True and (h.get('hardwareContext') or {}).get('hardwareContextVerified') is True
        and number(h.get('realMatchSeconds'),295,305) and number(h.get('coverage'),.95,1.01))
    checks['rightsInventoryPresent']=bool(r.get('status')=='rights-review-required' and r.get('pendingTrackedAssets',0)>0)
    # No automated process can approve rights. Deliberately disabled until
    # reviewed policy, rights and public security architecture are implemented.
    checks['commercialRightsCleared']=False
    checks['publicSecurityQualified']=False
    checks['authoritativeCutoverImplemented']=False
    return {'schema':1,'candidateCommit':commit,'checks':checks,'verifiedDiagnosticSlots':slots,
        'requiredConcurrentMatches':required,'privateRoundReviewEligible':checks['fullLeagueMatch'] and checks['wholeRoundCapacity'],
        'productionEnabled':False,'status':'blocked','scope':'Same-build, same-host diagnostic review; unsigned local evidence is not attestation'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runtime',type=Path)
    for k in KINDS:p.add_argument('--'+k,type=Path)
    p.add_argument('--required',type=int,default=3);p.add_argument('--output',type=Path)
    a=p.parse_args()
    reports={k:json.loads(getattr(a,k.replace('-','_')).read_text()) for k in KINDS if getattr(a,k.replace('-','_'))}
    result=evaluate(reports,candidate(),runtime_identity(a.runtime),fingerprint(a.runtime),time.time(),required=a.required)
    data=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(data)
    else:print(data,end='')
    return 2
if __name__=='__main__':raise SystemExit(main())
