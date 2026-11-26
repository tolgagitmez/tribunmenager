"""Validate an actual extended native trace, not a five-minute live report."""
import json
import sys
from pathlib import Path

DURATION = 1_800_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(path):
    start = None
    previous = None
    half_boundary = False
    half_seen = False
    final = None
    frames = 0
    with Path(path).open(encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            clock = row.get('fixedClock')
            require(isinstance(clock, dict), 'Missing native fixed clock')
            require(final is None, 'Frames after full time')
            require(type(clock.get('started')) is bool, 'Invalid clock state')
            if not clock['started']:
                require(start is None and row.get('done') is False, 'Unexpected stopped clock')
                continue
            elapsed = clock.get('elapsedMs')
            origin = clock.get('startMs')
            require(type(elapsed) is int and 0 <= elapsed <= DURATION, 'Invalid extended elapsed time')
            require(type(origin) is int and origin >= 0, 'Invalid clock origin')
            if start is None:
                require(elapsed == 0, 'Missing kickoff frame')
                start = origin
            require(origin == start and (previous is None or elapsed >= previous), 'Clock reversed or restarted')
            require(row.get('matchMs') == elapsed * 3, 'Incorrect 90-minute nominal clock')
            half_boundary |= elapsed == DURATION // 2
            if clock.get('half') is True:
                require(elapsed >= DURATION // 2, 'Early halftime')
                half_seen = True
            elif half_seen:
                raise ValueError('Halftime state reverted')
            if row.get('done') is True:
                require(elapsed == DURATION and half_seen, 'Premature full time')
                final = row
            previous = elapsed
            frames += 1
    require(start is not None and half_boundary and half_seen and final is not None, 'Incomplete extended match')
    require(frames > 100, 'Insufficient recorded frames')
    return {'simulationMs': DURATION, 'nominalMs': final['matchMs'],
            'halfBoundaryObserved': half_boundary, 'recordedFrames': frames,
            'score': final['score'], 'stats': final['stats'],
            'scope': 'Native simulation time only; no five-minute playback or wall-clock throughput claim.'}


if __name__ == '__main__':
    result = verify(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
