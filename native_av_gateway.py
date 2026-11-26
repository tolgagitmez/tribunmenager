"""Opt-in development league-to-native control gateway.
No public media, no official result authority, no user-supplied upstream URL.
"""
import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit
import urllib.request
import urllib.error
import native_live

KEY='league=? AND round=? AND home=? AND away=?'
class GatewayError(ValueError):
    def __init__(self,message,status=409):
        super().__init__(message);self.status=status

def resolve(db,token,round_number,now):
    if not isinstance(token,str) or not 1<=len(token)<=128:
        raise GatewayError('Geçersiz menajer anahtarı.',403)
    if type(round_number) is not int or not 0<=round_number<10:
        raise GatewayError('Maç günü geçersiz.',400)
    person=db.execute('SELECT league,slot FROM teams WHERE token=?',(token,)).fetchone()
    if person is None:raise GatewayError('Geçersiz menajer anahtarı.',403)
    rows=db.execute("""SELECT f.league,f.round,f.home,f.away,f.kickoff,n.attempt,n.state
        FROM fixtures f LEFT JOIN native_av_jobs n USING(league,round,home,away)
        WHERE f.league=? AND f.round=? AND (f.home=? OR f.away=?)""",
        (person[0],round_number,person[1],person[1])).fetchall()
    if len(rows)!=1:raise GatewayError('Maç erişim yetkisi yok.',403)
    league,r,h,a,kickoff,attempt,state=rows[0]
    if now<kickoff or state!='running' or not isinstance(attempt,str) or not re.fullmatch('[0-9a-f]{32}',attempt):
        raise GatewayError('Native maç şu anda erişilebilir değil.')
    return attempt,0 if person[1]==h else 1

def private_url(root,attempt,side):
    root=Path(root).resolve()
    if not re.fullmatch('[0-9a-f]{32}',attempt) or side not in (0,1):raise GatewayError('Geçersiz maç.')
    path=root/attempt/'run'/('local-manager-%d.txt'%side)
    try:
        if path.resolve()!=path or not path.is_file():raise OSError()
        info=path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_size>256:raise OSError()
        value=path.read_text().strip()
        if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/[A-Za-z0-9_-]{24,128}/',value):raise ValueError()
        u=urlsplit(value)
        if not 1<=u.port<=65535:raise ValueError()
        return value
    except (OSError,ValueError):raise GatewayError('Motor bağlantısı hazır değil.') from None

def gateway_secret(root,attempt):
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise GatewayError('Geçersiz maç.')
    path=Path(root).resolve()/attempt/'run'/'league-gateway.key'
    try:
        if path.resolve()!=path:raise OSError()
        info=path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_size>128:raise OSError()
        value=path.read_text().strip()
        if not re.fullmatch('[A-Za-z0-9_-]{43}',value):raise ValueError()
        return value
    except (OSError,ValueError):raise GatewayError('Lig kontrollü motor bağlantısı hazır değil.') from None

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def forward(root,attempt,side,round_number,body=None):
    base=private_url(root,attempt,side)
    data=None;headers={'Accept':'application/json','X-Tribun-Internal-Control':gateway_secret(root,attempt)}
    if body is not None:
        native_live.validate_command(body)
        if type(body['round']) is not int or body['round']!=round_number:raise GatewayError('Maç günü eşleşmiyor.',400)
        data=json.dumps({**body,'round':0},allow_nan=False).encode()
        headers.update({'Content-Type':'application/json','Origin':base.split('/',3)[0]+'//'+urlsplit(base).netloc})
    # No proxies, redirects, credentials or arbitrary client endpoints.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    req=urllib.request.Request(base+'tactics.json',data=data,headers=headers)
    try:
        with opener.open(req,timeout=4) as res:
            raw=res.read(65537)
            if len(raw)>65536:raise ValueError('Oversized native response')
            result=json.loads(raw)
            if not isinstance(result,dict):raise ValueError('Invalid native response')
            if body is None:
                if result.get('side')!=side:raise ValueError('Native side mismatch')
                # Never forward arbitrary response fields/capability secrets.
                allowed=('side','submittedRevision','appliedRevision','commandState','finalizing','canControl','engineMatchMs','lastAcknowledgement','latestRequestId','pendingCommand','roster')
            else:allowed=('revision','earliestMatchMs','state','commandState','appliedRevision','submittedRevision','requestId')
            return {k:result[k] for k in allowed if k in result}
    except urllib.error.HTTPError as e:
        raise GatewayError('Motor komutu kabul etmedi.',e.code if e.code in (400,403,409,429) else 503) from None
    except (OSError,ValueError,TypeError):raise GatewayError('Motor bağlantısı kullanılamıyor.',503) from None
