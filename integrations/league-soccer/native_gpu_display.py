"""Opt-in hardware GLX diagnostic. A dedicated, local, authenticated X server is required."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SOFTWARE = ('llvmpipe', 'softpipe', 'swrast', 'software rasterizer', 'swiftshader', 'lavapipe')

def local_display(value):
    if not re.fullmatch(r':[0-9]{1,4}(?:\.0)?', value):
        raise ValueError('Dedicated local X display required, e.g. :90')
    return value.split('.')[0]

def parse_glx(text):
    def field(name):
        return next((line.split(':', 1)[1].strip() for line in text.splitlines()
                     if line.strip().startswith(name + ':')), '')
    renderer = field('OpenGL renderer string')
    vendor = field('OpenGL vendor string')
    version = field('OpenGL version string')
    direct = field('direct rendering').lower() == 'yes'
    accelerated = field('Accelerated').lower()
    software = not renderer or any(s in renderer.lower() for s in SOFTWARE)
    # Mesa exposes Accelerated; proprietary implementations may omit it.
    known_gpu = bool(re.search(r'nvidia|amd|radeon|intel|iris|arc|geforce|quadro', renderer, re.I))
    return dict(renderer=renderer, vendor=vendor, version=version, direct=direct,
                accelerated=accelerated or None, software=software,
                eligible=bool(direct and not software and (accelerated == 'yes' or (not accelerated and known_gpu))))

def hardware_env(source, display):
    env = dict(source)
    for key in ('LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER','MESA_LOADER_DRIVER_OVERRIDE',
                'LIBGL_ALWAYS_INDIRECT','LP_NUM_THREADS','MESA_GL_VERSION_OVERRIDE',
                'MESA_GLSL_VERSION_OVERRIDE','WAYLAND_DISPLAY'):
        env.pop(key, None)
    env.update(DISPLAY=local_display(display), SDL_VIDEODRIVER='x11')
    return env

def wsl_environment(source):
    # WSLg's shared Xwayland display is not a dedicated GPU X server.
    # Only an explicitly requested private local alpha may use it.
    if 'microsoft' not in Path('/proc/sys/kernel/osrelease').read_text().lower() or not Path('/dev/dxg').exists() or not Path('/mnt/wslg').is_dir():
        raise ValueError('WSLg GPU not available')
    display=local_display(source.get('DISPLAY',''))
    if display!=':0':raise ValueError('WSLg local display :0 required')
    env=hardware_env(source,display)
    env['GALLIUM_DRIVER']='d3d12'
    return env

def probe(env):
    result = subprocess.run(['glxinfo','-B'], env=env, text=True, capture_output=True, timeout=15, check=True)
    report = parse_glx(result.stdout)
    if not report['eligible']:
        raise ValueError('Hardware GLX unavailable or inconclusive: ' + report['renderer'])
    return report

def exclusive_display(display):
    # Private per-user lock; a dedicated display must not serve other applications.
    root=Path(tempfile.gettempdir()) / ('tribun-gpu-' + str(os.getuid()))
    root.mkdir(mode=0o700, exist_ok=True)
    stat=root.lstat()
    if not root.is_dir() or root.is_symlink() or stat.st_uid!=os.getuid() or stat.st_mode & 0o077:
        raise ValueError('Unsafe display lock directory')
    fd=os.open(root / ('display-' + display[1:] + '.lock'), os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--display', required=True)
    p.add_argument('--wsl-local',action='store_true')
    p.add_argument('--capture', nargs=2, metavar=('CONFIG','LIMIT'))
    args=p.parse_args()
    display=local_display(args.display)
    env=wsl_environment(os.environ) if args.wsl_local else hardware_env(os.environ,display)
    if env['DISPLAY']!=display:raise ValueError('GPU display mismatch')
    if not args.capture:
        print(json.dumps(probe(env),indent=2))
        return
    if (not args.wsl_local and env.get('TRIBUN_GPU_DEDICATED')!='1') or (args.wsl_local and env.get('TRIBUN_GPU_WSL_LOCAL')!='1') or not env.get('TRIBUN_NATIVE_HLS_DIR'):
        raise ValueError('Explicit dedicated-display opt-in and local HLS required')
    lock=exclusive_display(display)
    try:
        evidence=probe(env)
        if args.wsl_local and not evidence['renderer'].lower().startswith('d3d12'):raise ValueError('Expected D3D12 GPU renderer')
        check=subprocess.run(['xdotool','search','--onlyvisible','--name','^League Soccer$'],
                             env=env,capture_output=True,text=True,timeout=10)
        if check.returncode!=1 or check.stdout.strip():
            raise ValueError('Display is occupied or cannot be checked')
        out=Path(env['TRIBUN_NATIVE_VIDEO_OUT']).parent / 'gpu-preflight.json'
        out.write_text(json.dumps({**evidence,'scope':'WSLg private local shared display; keep match visible' if args.wsl_local else 'GLX preflight on dedicated display; not proof of engine context or capacity',
                                   'productionQualified':False},indent=2)+'\n')
        subprocess.run([sys.executable,str(HERE/'native-video-pilot.py'),'--capture-window',*args.capture],
                       env=env,check=True)
    finally:
        os.close(lock)

if __name__=='__main__': main()
