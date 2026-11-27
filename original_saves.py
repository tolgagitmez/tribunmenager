"""Preserve only native league save files, never the engine configuration.
Linux launcher owns a per-revision lock and commits a snapshot on clean exit.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import uuid

MAX_FILES=10000
MAX_BYTES=2*1024**3
SNAPSHOT=re.compile(r'snapshot-[0-9a-f]{32}')


def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def walk_error(error):
    raise error


def same_tree(left,right):
    """Compare validated ordinary-file trees without trusting names alone."""
    def entries(root):
        items={}
        for base,dirs,files in os.walk(root,followlinks=False,onerror=walk_error):
            base=Path(base)
            for name in dirs+files:
                p=base/name
                info=p.lstat()
                if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                    raise RuntimeError('Geçersiz lig kayıt ağacı.')
                items[p.relative_to(root)]=(p,stat.S_ISDIR(info.st_mode),info.st_size)
        return items
    a,b=entries(left),entries(right)
    if a.keys()!=b.keys():
        return False
    for key,(p,is_dir,size) in a.items():
        q,other_dir,other_size=b[key]
        if is_dir!=other_dir or (not is_dir and size!=other_size):
            return False
        if not is_dir:
            with p.open('rb') as x,q.open('rb') as y:
                while True:
                    first,second=x.read(1024*1024),y.read(1024*1024)
                    if first!=second:
                        return False
                    if not first:
                        break
    return True


def copy_saves(source, destination):
    """Copy a bounded ordinary-file tree; reject links, special files, journals."""
    source=Path(source)
    if source.is_symlink() or not source.is_dir():
        raise RuntimeError('Geçersiz orijinal lig kayıt klasörü.')
    destination=Path(destination)
    destination.mkdir(mode=0o700)
    count=size=0
    for base,dirs,files in os.walk(source,followlinks=False,onerror=walk_error):
        base=Path(base)
        target=destination/base.relative_to(source)
        for name in dirs:
            p=base/name
            if not stat.S_ISDIR(p.lstat().st_mode):
                raise RuntimeError('Lig kayıtlarında sembolik bağlantı kabul edilmiyor.')
            (target/name).mkdir(mode=0o700)
            count+=1
            if count>MAX_FILES:
                raise RuntimeError('Lig kayıt sayısı sınırı aşıldı.')
        for name in files:
            p=base/name
            info=p.lstat()
            if not stat.S_ISREG(info.st_mode) or name.endswith(('-wal','-shm','-journal')):
                raise RuntimeError('Lig kayıt dosyası güvenli veya kapanmış değil.')
            count+=1
            size+=info.st_size
            if count>MAX_FILES or size>MAX_BYTES:
                raise RuntimeError('Lig kayıt boyutu sınırı aşıldı.')
            shutil.copyfile(p,target/name)
            (target/name).chmod(0o600)
            with (target/name).open('rb') as copied:
                os.fsync(copied.fileno())
    for base,_,_ in os.walk(destination,topdown=False,onerror=walk_error):
        sync_dir(base)


@contextmanager
def locked_store(root):
    root=Path(root)
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError('Geçersiz lig kayıt deposu.')
    fd=os.open(root/'session.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Başka bir orijinal motor oturumu açık.') from exc
        yield root
    finally:
        os.close(fd)


def current_snapshot(root):
    pointer=Path(root)/'current'
    if pointer.is_symlink():
        raise RuntimeError('Geçersiz lig kayıt işaretçisi.')
    if not pointer.exists():
        return None
    if not pointer.is_file() or pointer.stat().st_size>128:
        raise RuntimeError('Geçersiz lig kayıt işaretçisi.')
    name=pointer.read_text(encoding='ascii').strip()
    if not SNAPSHOT.fullmatch(name):
        raise RuntimeError('Geçersiz lig kayıt sürümü.')
    path=Path(root)/name
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError('Lig kayıt sürümü bulunamadı.')
    return path


def restore(root,session):
    source=current_snapshot(root)
    if source is not None:
        copy_saves(source,Path(session)/'saves')


def commit(root,session,exit_code):
    """Only a successful native exit advances the pointer; previous saves retained."""
    root=Path(root)
    source=Path(session)/'saves'
    if exit_code!=0 or (not source.exists() and not source.is_symlink()):
        return False
    # Validate old pointer before creating a replacement.
    previous=current_snapshot(root)
    with tempfile.TemporaryDirectory(prefix='.stage-',dir=root) as staging:
        staged=Path(staging)/'saves'
        copy_saves(source,staged)
        if previous is not None and same_tree(staged,previous):
            return True  # Successfully retained; no redundant snapshot.
        name='snapshot-'+uuid.uuid4().hex
        staged.rename(root/name)
        sync_dir(root)
        pointer=Path(staging)/'current'
        with pointer.open('w',encoding='ascii') as f:
            f.write(name+'\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(pointer,root/'current')
        sync_dir(root)
    return True
