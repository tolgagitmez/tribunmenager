"""Build and launch the pinned, completely unpatched upstream desktop game."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

UPSTREAM = 'https://github.com/awest813/League-Soccer.git'
REVISION = '087414cde936c3e26ed0b8c244d9d85425ec5657'
ROOT = Path(__file__).resolve().parent
RUNTIME = ('gameplayfootball', 'football.config', 'data', 'databases', 'locale', 'media')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def clean_env(source):
    # No legacy experiment flags, injected libraries, or capture overrides.
    blocked = {'LD_PRELOAD', 'DYLD_INSERT_LIBRARIES', 'LD_AUDIT',
               'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER', 'ALSOFT_DRIVERS',
               'ALSOFT_CONF', 'LIBGL_ALWAYS_SOFTWARE', 'LP_NUM_THREADS',
               'MESA_GL_VERSION_OVERRIDE', 'GALLIUM_DRIVER',
               'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH'}
    return {k: v for k, v in source.items()
            if not k.startswith(('TRIBUN_', 'GF_', 'GF_CAPTURE_')) and k not in blocked}


def call(args, env, cwd=None):
    subprocess.run([str(a) for a in args], env=env, cwd=cwd, check=True)


def git_output(source, env, *args):
    return subprocess.check_output(['git', '-C', str(source), *args],
                                   env=env, text=True).strip()


def check_source(source, env):
    require(git_output(source, env, 'rev-parse', 'HEAD') == REVISION,
            'Motorun kaynak sürümü eşleşmiyor.')
    require(not git_output(source, env, 'status', '--porcelain', '--untracked-files=all'),
            'Orijinal motor kaynakları değiştirilmiş.')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def runtime_manifest(runtime):
    entries = {}
    for name in RUNTIME:
        p = runtime / name
        require(p.exists() and not p.is_symlink(), f'Eksik veya geçersiz motor dosyası: {name}')
        files = [p] if p.is_file() else sorted(p.rglob('*'))
        for f in files:
            require(not f.is_symlink(), 'Motor paketinde sembolik bağlantı kabul edilmiyor.')
            if f.is_file():
                entries[f.relative_to(runtime).as_posix()] = digest(f)
    return entries


def check_config(source, runtime):
    original = (source / 'data/football.config').read_bytes()
    for p in (runtime/'football.config', runtime/'data/football.config'):
        require(p.read_bytes() == original, 'Orijinal motor yapılandırması değişmiş.')


def prepare(work, env, jobs=2):
    source, build = work/'source', work/'build'
    call(['git','init','-q',source],env)
    call(['git','-C',source,'remote','add','origin',UPSTREAM],env)
    call(['git','-C',source,'fetch','--depth','1','origin',REVISION],env)
    call(['git','-C',source,'checkout','--detach','FETCH_HEAD'],env)
    check_source(source,env)
    call(['cmake','-S',source,'-B',build,'-DCMAKE_BUILD_TYPE=Release','-DBUILD_TESTING=OFF'],env)
    call(['cmake','--build',build,'--parallel',str(jobs)],env)
    check_source(source,env)
    check_config(source,build)
    # Retain upstream source, license, build and assets locally. Never publish them.
    manifest = dict(revision=REVISION,files=runtime_manifest(build))
    (work/'pristine-manifest.json').write_text(json.dumps(manifest,sort_keys=True)+'\n')
    return build


def verify_install(work, env):
    check_source(work/'source',env)
    build=work/'build'
    manifest=json.loads((work/'pristine-manifest.json').read_text())
    require(manifest['revision']==REVISION and manifest['files']==runtime_manifest(build),
            'Motorun yerel paketi değiştirilmiş; temiz kurulum gerekli.')
    check_config(work/'source',build)
    return build


def launch(build, env):
    # New private runtime copy per launch; upstream may write its own settings.
    # No synthetic fixture, clock, manager command, configuration argument or patch.
    with tempfile.TemporaryDirectory(prefix='tribun-original-session-') as temp:
        session=Path(temp)
        for name in RUNTIME:
            src=build/name
            if src.is_dir():
                shutil.copytree(src,session/name)
            else:
                shutil.copy2(src,session/name)
        return subprocess.run([str(session/'gameplayfootball')],cwd=session,env=env).returncode


def cache_root():
    return Path.home()/'.cache'/'tribun-manager-original'


def main(*, build_only=False, installed_only=False):
    require(sys.platform.startswith('linux'), 'Orijinal motor bağlantısı şimdilik Linux/WSL grafik oturumu için hazırlanmıştır.')
    require(all(shutil.which(c) for c in ('git','cmake')), 'Git ve CMake kurulmalı; League-Soccer Linux bağımlılıkları da gerekli.')
    env=clean_env(os.environ)
    cache=cache_root()
    require(not cache.resolve().is_relative_to(ROOT), 'Motor paketi web dizininin dışında olmalı.')
    cache.mkdir(mode=0o700,parents=True,exist_ok=True)
    work=cache/REVISION
    if not work.exists():
        require(not installed_only, 'Orijinal motor kurulu değil; terminalden kurulum yap.')
        # Atomic install; partial builds are never used by the launcher.
        with tempfile.TemporaryDirectory(prefix='install-',dir=cache) as temp:
            staging=Path(temp)/'engine'
            staging.mkdir()
            prepare(staging,env)
            try:
                staging.rename(work)
            except OSError:
                if not work.exists():
                    raise
    build=verify_install(work,env)
    print('League-Soccer: orijinal kaynak ve varsayılan dosyalar doğrulandı.',flush=True)
    if build_only:
        return 0
    return launch(build,env)
