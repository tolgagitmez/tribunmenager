"""Private full-renderer resolution comparison, without altering the simulation clock."""
import argparse
import re
from pathlib import Path
SIZES={'1280x720':(1280,720),'960x540':(960,540)}

def configure(source,size):
    if size not in SIZES:raise ValueError('Unsupported render size')
    width,height=SIZES[size]
    for key,value in (('context_x',width),('context_y',height),('context_fullscreen','false')):
        pattern=re.compile(r'^[ \t]*"'+key+r'"[ \t]+"[^"\r\n]*"[ \t]*$',re.MULTILINE)
        matches=list(pattern.finditer(source))
        if len(matches)>1:raise ValueError('Duplicate renderer property')
        line=f'"{key}" "{value}"'
        if matches:
            m=matches[0];source=source[:m.start()]+line+source[m.end():]
        else:source+=('' if not source or source.endswith('\n') else '\n')+line+'\n'
    return source

def verify_geometry(raw,size):
    if size not in SIZES:raise ValueError('Unknown render size')
    def value(k):
        rows=re.findall(r'^'+k+r'=([0-9]+)$',raw,re.MULTILINE)
        if len(rows)!=1:raise ValueError('Missing or ambiguous window geometry')
        return int(rows[0])
    width,height=value('WIDTH'),value('HEIGHT')
    if (width,height)!=SIZES[size]:raise ValueError('Native window size differs from requested configuration')
    return {'width':width,'height':height,'requested':size,'verified':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('size',choices=SIZES)
    a=p.parse_args()
    if a.source.resolve()==a.output.resolve():raise ValueError('Do not overwrite frozen configuration')
    a.output.write_text(configure(a.source.read_text(),a.size))
if __name__=='__main__':main()
