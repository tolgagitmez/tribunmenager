"""Private loopback-only AV reads, scoped to a native-only league and current attempt."""
import os
import re
import stat
from pathlib import Path
import native_league_mode
from native_av_gateway import GatewayError,resolve

def local_allowed(handler):
    # Only directly bound loopback dev server; do not expose through a proxy.
    return (os.environ.get('TRIBUN_NATIVE_PRIVATE_SCREEN')=='1'
        and handler.server.server_address[0]=='127.0.0.1'
        and handler.client_address[0]=='127.0.0.1'
        and handler.headers.get('Host') in ('127.0.0.1:'+str(handler.server.server_port),'localhost:'+str(handler.server.server_port))
        and not any(handler.headers.get(k) for k in ('Forwarded','X-Forwarded-For','X-Forwarded-Host','X-Real-IP')))

def authorize(db,token,round_number,now):
    person=db.execute('SELECT league FROM teams WHERE token=?',(token,)).fetchone()
    if not person or not native_league_mode.is_native(db,person[0]):raise GatewayError('Native deneme ligi erişimi gerekli.',403)
    attempt,side=resolve(db,token,round_number,now)
    return attempt,side

def media_file(root,attempt,name):
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise GatewayError('Geçersiz maç.',400)
    if name=='live.m3u8':mime='application/vnd.apple.mpegurl';limit=128*1024
    elif name=='init.mp4':mime='video/mp4';limit=2*1024*1024
    elif re.fullmatch(r'segment-[0-9]{5}\.m4s',name):mime='video/iso.segment';limit=16*1024*1024
    else:raise GatewayError('Dosya erişime kapalı.',404)
    base=Path(root).resolve();p=base/attempt/'run'/'hls'/name
    try:
        if p.resolve()!=p:raise OSError('Unsafe media path')
        # Final file must not be a symlink; encoder writes segments atomically.
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as f:
            info=os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or not 0<info.st_size<=limit:raise OSError('Unsafe media')
            data=f.read(limit+1)
            if not 0<len(data)<=limit:raise OSError('Oversized media')
    except OSError:raise GatewayError('Yayın parçası henüz hazır değil.',404) from None
    return mime,data
