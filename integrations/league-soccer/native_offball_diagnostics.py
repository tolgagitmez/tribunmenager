"""Sample native off-ball attraction targets, not completed runs."""
from pathlib import Path
from collections import Counter
import math
import re

PATTERN=re.compile(r'\[tribun-offball188\] team=([01]) player=(\d+) role=(primary|secondary) match_ms=(\d+) x=(\S+) y=(\S+) score=(\S+)')
LIMIT=32*1024*1024
def inspect_offball(path):
    path=Path(path)
    if not path.is_file():return None
    if path.stat().st_size>LIMIT:raise ValueError('Game log too large')
    counts=Counter()
    players=set()
    seen=set()
    invalid=duplicates=0
    with path.open(encoding='utf-8',errors='replace') as log:
        for line in log:
            if not line.startswith('[tribun-offball188]'):continue
            m=PATTERN.fullmatch(line.rstrip('\r\n'))
            try:
                if not m:raise ValueError('Bad record')
                x,y,score=map(float,m.groups()[4:])
                if not all(math.isfinite(v) for v in (x,y,score)) or abs(y)>24.0001:raise ValueError('Bad target')
            except ValueError:
                invalid+=1;continue
            team,player,role,match=m.groups()[:4]
            key=(team,player,role,match)
            if key in seen:
                duplicates+=1;continue
            seen.add(key);counts[role]+=1;players.add((team,player))
    return dict(sampledSelections=dict(counts),uniquePlayers=len(players),invalidLines=invalid,
        duplicateSamples=duplicates,evidenceAvailable=bool(counts),
        scope='Sparse native run-target selections. Targets are force-field preferences, not confirmed routes, actual receptions, or proof of decoy movement.')
