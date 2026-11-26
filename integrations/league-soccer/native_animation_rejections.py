"""Count actual native selector exits for slow, uniquely controlled carriers."""
from collections import Counter, defaultdict
from pathlib import Path
import math
import re

REASONS = frozenset("""ball-distance ball-moving-away prediction-divergence
requeue-nonmovement requeue-possession-focus requeue-remaining-frames
requeue-movement-delay requeue-control-delay requeue-control-trap
requeue-trap-delay requeue-trap-control-delay requeue-similar-command
requeue-momentum requeue-small-change empty-crude-set incompatible-movement
no-applicable-animation""".split())
PATTERN = re.compile(r'\[tribun-anim210\] team=([01]) player=(\d+) phase=(\d+) actual_ms=(\d+) match_ms=(\d+) action=(movement|ball-control) result=(accepted|rejected) reason=([a-z-]+) interrupt=(\d+) requested=(\S+) current=(\S+) outgoing=(\S+) frame=(-?\d+)')
LIMIT = 32 * 1024 * 1024

def inspect_rejections(path):
    path = Path(path)
    if not path.is_file():
        return None
    if path.stat().st_size > LIMIT:
        raise ValueError('Game log too large')
    counts, reasons, by_player = Counter(), Counter(), defaultdict(Counter)
    invalid = observed = accepted_slow_output = 0
    with path.open(encoding='utf-8', errors='replace') as log:
        for line in log:
            if not line.startswith('[tribun-anim210]'):
                continue
            m = PATTERN.fullmatch(line.rstrip('\r\n'))
            try:
                if not m:
                    raise ValueError('Malformed selector record')
                team, player, phase, actual, match, action, result, reason, interrupt, req, curr, out, frame = m.groups()
                speeds = tuple(map(float, (req, curr, out)))
                if not all(math.isfinite(v) and v >= 0 for v in speeds):
                    raise ValueError('Invalid speeds')
                if (result == 'accepted' and reason != 'selected') or (result == 'rejected' and reason not in REASONS):
                    raise ValueError('Invalid exit reason')
                if int(phase) not in (1, 2):
                    raise ValueError('Invalid phase')
            except ValueError:
                invalid += 1
                continue
            observed += 1
            key = action + ':' + result
            counts[key] += 1
            by_player[team + ':' + player + ':' + phase][key] += 1
            if result == 'rejected':
                reasons[reason] += 1
                by_player[team + ':' + player + ':' + phase][reason] += 1
            elif speeds[0] >= 1.2 and speeds[2] < .75:
                accepted_slow_output += 1
    return {'observedEvents': observed, 'invalidLines': invalid,
            'counts': dict(counts), 'rejectionReasons': dict(reasons),
            'byPlayerPhase': {key: dict(value) for key, value in by_player.items()},
            'acceptedRequestedMoveButSlowOutgoing': accepted_slow_output,
            'evidenceAvailable': observed > 0,
            'scope': 'Native selector exits for eligible slow unique carriers; repeated attempts are not distinct failures. Outgoing animation speed is not observed player displacement.'}
