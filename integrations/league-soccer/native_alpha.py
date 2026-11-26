"""Local one-match native alpha launcher (Linux, private diagnostic only)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PATCHES=('instrument.py','fixture_patch.py','short_match_patch.py')
PREFIXES=('TRIBUN_','GF_CAPTURE_')
TOOLS=('git','node','npm','cmake','c++','ffmpeg','ffprobe','xvfb-run','xauth','pulseaudio','pactl','xdotool')

def clean_env(source):
    # Do not inherit any experimental AI, rendering, league or GPU switches.
    return {k:v for k,v in source.items() if not k.startswith(PREFIXES)}

def expected_manifest():
    return {'upstream':json.loads((HERE/'upstream.json').read_text()),
        'patches':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in PATCHES}}

def validate_runtime(runtime):
    runtime=Path(runtime).resolve()
    if not (runtime/'gameplayfootball').is_file() or not os.access(runtime/'gameplayfootball',os.X_OK):
        raise ValueError('Motor çalıştırılabilir dosyası eksik.')
    if not (runtime/'native-match.config').is_file():
        raise ValueError('Motor maç ayarı eksik.')
    if json.loads((runtime/'tribun-runtime.json').read_text())!=expected_manifest():
        raise ValueError('Motor bu kaynak koduyla eşleşmiyor; yeniden derle.')
    return runtime

def private_base(path):
    path=Path(path).expanduser().resolve()
    if path.is_relative_to(ROOT.resolve()):raise ValueError('Alfa kayıtları oyun klasörü dışında olmalı.')
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    st=path.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.getuid() or st.st_mode&0o077:
        raise ValueError('Alfa klasörü yalnızca kullanıcıya ait olmalı (0700).')
    return path

def find_runtime(base):
    # Reuse only the matching build in a private, non-symlink session.
    for session in sorted(base.glob('alpha-*'),key=lambda x:x.stat().st_mtime,reverse=True):
        if session.is_symlink() or not session.is_dir():continue
        st=session.stat()
        if st.st_uid!=os.getuid() or st.st_mode&0o077:continue
        runtime=session/'runtime'
        if runtime.is_symlink():continue
        try:return validate_runtime(runtime)
        except (OSError,ValueError):continue
    return None

def execute(args,env):
    subprocess.run(args,cwd=ROOT,env=env,check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime',type=Path,help='Use an already prepared matching runtime')
    p.add_argument('--session-root',type=Path,default=Path.home()/'.local/state/tribun-manager-native-alpha')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--delay',type=int,default=120)
    p.add_argument('--install-deps',action='store_true',help='Explicitly allow Ubuntu apt/npm/Chrome dependency installation')
    p.add_argument('--prepare-only',action='store_true',help='Prepare runtime, then exit without starting match')
    p.add_argument('--private-diagnostic',action='store_true')
    p.add_argument('--wsl-gpu',action='store_true',help='Local WSLg GPU trial; keep game window visible')
    a=p.parse_args()
    if not a.private_diagnostic:p.error('Yerel özel test için --private-diagnostic gerekli.')
    if not sys.platform.startswith('linux'):p.error('Şimdilik yalnızca Linux destekleniyor.')
    if not 1024<=a.port<=65535 or not 30<=a.delay<=300:p.error('Geçersiz port veya gecikme.')
    env=clean_env(os.environ)
    try:
        base=private_base(a.session_root)
        if a.install_deps:
            if not shutil.which('apt-get') or not shutil.which('sudo'):raise ValueError('Otomatik bağımlılık kurulumu Ubuntu/Debian apt ve sudo gerektirir.')
            execute(['sudo','apt-get','update'],env)
            execute(['sudo','apt-get','install','-y','git','build-essential','cmake','python3','ffmpeg','xdotool','xvfb','xauth','pulseaudio','pulseaudio-utils','libopenal-dev'],env)
        missing=[x for x in TOOLS if not shutil.which(x)]
        if missing:raise ValueError('Eksik araçlar: '+', '.join(missing)+'. Node.js 22 ve npm önceden kurulmalı.')
        if a.install_deps:
            execute(['npm','ci'],env)
            execute(['npx','playwright','install','--with-deps','chrome'],env)
        else:
            # Check the actual Chrome executable can start; package presence alone is insufficient.
            execute(['node','-e',"const {chromium}=require('playwright');(async()=>{const b=await chromium.launch({headless:true,channel:'chrome'});await b.close()})().catch(()=>process.exit(1))"],env)
        if a.wsl_gpu:
            from native_gpu_display import wsl_environment,probe
            gpu=probe(wsl_environment(env))
            print('WSLg GPU preflight: '+gpu['renderer'],flush=True)
        session=Path(tempfile.mkdtemp(prefix='alpha-',dir=base))
        runtime=validate_runtime(a.runtime) if a.runtime else find_runtime(base)
        if runtime is not None:
            print('Eslesen hazir motor kullaniliyor.',flush=True)
        else:
            runtime=session/'runtime'
            build_env={**env,'TRIBUN_PREPARE_ONLY':'1','TRIBUN_NATIVE_RUNTIME_OUT':str(runtime),'TRIBUN_BUILD_JOBS':'2'}
            if a.install_deps:build_env['TRIBUN_INSTALL_NATIVE_DEPS']='1'
            print('Sabitlenmiş League-Soccer motoru derleniyor. Kaynak kodundan gerçek derleme.',flush=True)
            execute(['bash',str(HERE/'run-pilot.sh'),str(session/'build.ndjson')],build_env)
            validate_runtime(runtime)
        print('Özel oturum klasörü: '+str(session),flush=True)
        print('Motor: '+str(runtime),flush=True)
        if a.prepare_only:return 0
        print('Tek maç; deneysel özellikler kapalı. Giriş bağlantısı ve anahtar yolu aşağıda görünecek.',flush=True)
        cmd=[sys.executable,str(HERE/'native_private_beta.py'),str(runtime),str(session/'match'),
            '--port',str(a.port),'--delay',str(a.delay),'--private-diagnostic','--result-seconds','120']
        if a.wsl_gpu:cmd.append('--wsl-gpu')
        return subprocess.call(cmd,cwd=ROOT,env=env)
    except (OSError,ValueError,subprocess.CalledProcessError) as exc:
        print('Alfa başlatılamadı: '+str(exc),file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Alfa durduruldu.',file=sys.stderr)
        return 130
if __name__=='__main__':raise SystemExit(main())
