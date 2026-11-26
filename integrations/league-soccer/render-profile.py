"""Only modify the graphics sequence cadence; never change the game tick."""
import argparse
from pathlib import Path
import re
KEY=re.compile(r'^[ \t]*"graphics3d_frametime_ms"[ \t]+"[^"\r\n]*"[ \t]*$',re.MULTILINE)
def configure(source,interval):
    if type(interval) is not int or interval!=100:
        raise ValueError("Only the isolated 100 ms experiment is supported")
    matches=list(KEY.finditer(source))
    if len(matches)>1:raise ValueError("Duplicate graphics cadence property")
    entry='"graphics3d_frametime_ms" "100"'
    if matches:
        match=matches[0]
        return source[:match.start()]+entry+source[match.end():]
    return source+("" if not source or source.endswith("\n") else "\n")+entry+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path);p.add_argument("output",type=Path)
    p.add_argument("interval",type=int,choices=[100])
    a=p.parse_args()
    if a.source.resolve()==a.output.resolve():raise ValueError("Do not overwrite frozen runtime config")
    a.output.write_text(configure(a.source.read_text(),a.interval))
if __name__=="__main__":main()
