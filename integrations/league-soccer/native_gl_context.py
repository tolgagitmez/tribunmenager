"""Compare a sampled actual game GL context with the dedicated-display probe."""
import subprocess
from pathlib import Path
from native_gpu_display import SOFTWARE

def compile_hook(source,dest):
    subprocess.run(['cc','-O2','-shared','-fPIC',str(source),'-o',str(dest),'-ldl','-pthread'],check=True,timeout=30)

def verify(path,preflight):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>4096:
        raise ValueError('Missing native GL context evidence')
    rows=path.read_text().splitlines()
    if len(rows)!=3 or [x.split('=',1)[0] for x in rows]!=['vendor','renderer','version']:
        raise ValueError('Malformed native GL context evidence')
    context=dict(row.split('=',1) for row in rows)
    if any(not v.strip() for v in context.values()) or any(x in context['renderer'].lower() for x in SOFTWARE):
        raise ValueError('Native game GL context is software or inconclusive')
    if preflight.get('eligible') is not True or any(context[k].strip().casefold()!=str(preflight.get(k,'')).strip().casefold() for k in ('vendor','renderer')):
        raise ValueError('Native context differs from hardware display preflight')
    return {**context,'hardwareContextVerified':True,'scope':'First observed game SDL GL swap context; not continuous GPU utilization or proof of encoder device identity'}
