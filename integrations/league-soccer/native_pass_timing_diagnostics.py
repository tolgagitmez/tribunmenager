"""Separate selected lead-pass requests from native long-pass contacts."""
from pathlib import Path
import re
import math
LIMIT=32*1024*1024
SELECT=re.compile(r'\[tribun-pass-timing\] team=([01]) passer=(\d+) receiver=(\d+) match_ms=(\d+) odds=(\S+)')
CONTACT=re.compile(r'\[tribun-pass-timing-contact\] team=([01]) passer=(\d+) receiver=(\d+) match_ms=(\d+)')
def inspect_pass_timing(path):
    path=Path(path)
    if not path.is_file():return None
    if path.stat().st_size>LIMIT:raise ValueError('Game log too large')
    requests=contacts=invalid=0
    odds_sum=0.
    with path.open('r',encoding='utf-8',errors='replace') as log:
        for line in log:
            line=line.rstrip('\r\n')
            if line.startswith('[tribun-pass-timing]'):
                m=SELECT.fullmatch(line)
                try:
                    if not m or m[2]==m[3]:raise ValueError('Invalid request')
                    odds=float(m[5])
                    if not math.isfinite(odds) or not .76<=odds<=1:raise ValueError('Invalid odds')
                except ValueError:
                    invalid+=1;continue
                requests+=1;odds_sum+=odds
            elif line.startswith('[tribun-pass-timing-contact]'):
                m=CONTACT.fullmatch(line)
                if not m or m[2]==m[3]:
                    invalid+=1;continue
                contacts+=1
    return dict(selectedRequests=requests,nativeLongPassContacts=contacts,invalidLines=invalid,
        meanSelectedOdds=round(odds_sum/requests,5) if requests else None,
        evidenceAvailable=bool(requests or contacts),
        scope='Requests may repeat or be rejected by native animation selection. Contacts include all native long passes in enabled matches, not just selected experimental requests. No request-to-contact pairing or receiver confirmation; not a completion rate.')
