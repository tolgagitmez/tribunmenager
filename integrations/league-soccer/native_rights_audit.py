"""Fail-closed rights inventory for private diagnostics; not a legal approval engine."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
CATEGORIES={'animation','model','image-texture','audio','font','database','shader','other-runtime'}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def validate(inventory,upstream):
    if inventory.get('schema')!=1 or inventory.get('upstreamRevision')!=upstream['revision'] or inventory.get('declaredProjectLicense')!=upstream['license']:
        raise ValueError('Upstream inventory version mismatch')
    counts={};seen=set()
    for row in inventory['assets']:
        name=row['path'];p=Path(name)
        if not name.startswith('data/') or '..' in p.parts or str(p)!=name or name in seen or row['category'] not in CATEGORIES:
            raise ValueError('Invalid asset path or category')
        if not re.fullmatch('[0-9a-f]{40}',row['gitBlob']) or type(row['bytes']) is not int or row['bytes']<0 or row['status']!='pending-review':
            raise ValueError('Unreviewed inventory cannot grant rights')
        seen.add(name);counts[row['category']]=counts.get(row['category'],0)+1
    if not seen or counts!=inventory['counts']:raise ValueError('Incomplete inventory')
    return counts

def runtime_inventory(root):
    root=root.resolve()
    files=[]
    for name in ('data','media','databases','locale'):
        base=root/name
        if not base.is_dir() or base.is_symlink():raise ValueError('Missing or unsafe runtime tree')
        for p in sorted(base.rglob('*')):
            if p.is_symlink():raise ValueError('Symlink in runtime assets')
            if p.is_file():files.append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
            elif not p.is_dir():raise ValueError('Nonregular runtime asset')
    return files

def audit(inventory,upstream,runtime=None):
    counts=validate(inventory,upstream)
    result={'schema':1,'upstreamRevision':upstream['revision'],'declaredProjectLicense':upstream['license'],
        'assetCounts':counts,'pendingTrackedAssets':sum(counts.values()),'commercialStreamingApproved':False,
        'assetRedistributionApproved':False,'productionEnabled':False,'status':'rights-review-required',
        'blockers':['asset-specific provenance and rights','font notices and licenses','third-party dependency notices',
                    'database and trademark rights','commercial audiovisual streaming review']}
    if runtime is not None:
        manifest=json.loads((runtime/'tribun-runtime.json').read_text())
        if manifest.get('upstream')!=upstream:raise ValueError('Runtime revision mismatch')
        result['runtimeAssets']=runtime_inventory(runtime)
        result['runtimeBinarySha256']=sha(runtime/'gameplayfootball')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--require-commercial',action='store_true')
    a=p.parse_args()
    result=audit(json.loads((HERE/'upstream-asset-inventory.json').read_text()),json.loads((HERE/'upstream.json').read_text()),a.runtime)
    data=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(data)
    else:print(data,end='')
    return 2 if a.require_commercial else 0

if __name__=='__main__':raise SystemExit(main())
