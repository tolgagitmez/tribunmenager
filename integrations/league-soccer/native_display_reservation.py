"""Reserve a dedicated Xvfb display for each local capture, fail closed on collision."""
import contextlib
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

def lock_root():
    root=Path(tempfile.gettempdir()) / ('tribun-xvfb-'+str(os.getuid()))
    root.mkdir(mode=0o700,exist_ok=True)
    info=root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
        raise ValueError('Unsafe private display lock directory')
    return root

def occupied(n):
    return os.path.lexists('/tmp/.X%d-lock'%n) or os.path.lexists('/tmp/.X11-unix/X%d'%n)

@contextlib.contextmanager
def reserve(root, numbers=range(100,164), busy=occupied):
    for n in numbers:
        fd=os.open(root / ('display-%d.lock'%n),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:continue
            if busy(n):continue
            yield n
            return
        finally:os.close(fd)
    raise RuntimeError('No isolated Xvfb display available')

def main():
    if len(sys.argv)<2:raise ValueError('Capture command required')
    with reserve(lock_root()) as n:
        # Never use -a: a selected display belongs to this reservation until exit.
        print('TRIBUN_DISPLAY_RESERVED',n,flush=True)
        return subprocess.call(['xvfb-run','-n',str(n),'-s','-screen 0 1920x1080x24 -nolisten tcp',*sys.argv[1:]])

if __name__=='__main__':raise SystemExit(main())
