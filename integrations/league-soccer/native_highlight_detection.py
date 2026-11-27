"""Classify recorded native football moments, independent of simulation and playback."""
import argparse
import json
import math
from pathlib import Path

from native_extended_clock_verify import DURATION, verify
from native_extended_capture import sha

BIN_MS = 1000
PITCH_HALF = 55.0
LEVELS = ('routine', 'build-up', 'dangerous', 'critical')
MAX_SAMPLE_GAP = 250


def vec(value):
    if not isinstance(value, list) or len(value) != 3 or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError('Invalid native vector')
    return value


def pair(value):
    if not isinstance(value, list) or len(value) != 2 or any(
            type(x) is not int or x < 0 for x in value):
        raise ValueError('Invalid native counter')
    return value


def classify(row):
    """Return heuristic importance and reason, not a goal probability."""
    ball = vec(row['ball'])
    velocity = vec(row['ballVelocity'])
    directions = row['attackDirection']
    if directions not in ([1, -1], [-1, 1]):
        raise ValueError('Missing attacking direction')
    players = row['players']
    if not isinstance(players, list) or not players:
        raise ValueError('Missing active players')
    for p in players:
        if type(p['team']) is not int or p['team'] not in (0, 1):
            raise ValueError('Invalid team')
        vec(p['position'])
        vec(p['velocity'])
        if type(p['uniquePossession']) is not bool or type(p['goalkeeper']) is not bool:
            raise ValueError('Missing possession or goalkeeper flag')
    if type(row['inPlay']) is not bool or type(row['setPiece']) is not bool:
        raise ValueError('Missing play state')
    if row['setPiece']:
        if abs(ball[0]) >= PITCH_HALF - 25 and abs(ball[1]) <= 24:
            return 2, 'attacking-set-piece'
        return 0, 'routine-restart'
    if not row['inPlay']:
        return 0, 'stopped-play'
    owners = [p for p in players if p['uniquePossession']]
    if len(owners) != 1:
        if abs(ball[0]) >= PITCH_HALF - 16.5 and abs(ball[1]) <= 20.15:
            return 2, 'loose-ball-in-box'
        if abs(ball[0]) >= PITCH_HALF - 35 and velocity[0] * ball[0] > 0 and abs(velocity[0]) >= 5:
            return 2, 'fast-ball-toward-goal'
        return 0, 'uncontrolled-midfield'
    owner = owners[0]
    if owner['goalkeeper']:
        return 0, 'goalkeeper-control'
    direction = directions[owner['team']]
    depth = PITCH_HALF - direction * ball[0]
    if 0 <= depth <= 16.5 and abs(ball[1]) <= 20.15:
        return 2, 'controlled-box'
    if 0 <= depth <= 26 and abs(ball[1]) <= 13:
        return 2, 'central-attacking-zone'
    # Project a moving receiver, but never label this a confirmed legal pass.
    opponents = [p for p in players if p['team'] != owner['team']]
    for mate in players:
        if mate['team'] != owner['team'] or mate['id'] == owner['id'] or mate['goalkeeper']:
            continue
        x, y, _ = mate['position']
        vx, vy, _ = mate['velocity']
        if vx * direction < 2:
            continue
        tx, ty = x + vx, y + vy
        progress = (tx - ball[0]) * direction
        distance = math.hypot(tx - ball[0], ty - ball[1])
        if not (4 <= progress <= 25 and 6 <= distance <= 32 and
                0 <= PITCH_HALF - direction * tx <= 22 and abs(ty) <= 18):
            continue
        if not opponents:
            continue
        if min(math.hypot(tx - q['position'][0] - q['velocity'][0],
                          ty - q['position'][1] - q['velocity'][1]) for q in opponents) >= 2.5:
            return 2, 'potential-forward-run'
    if 0 <= depth <= 37:
        if velocity[0] * direction >= 5:
            return 2, 'fast-forward-attack'
        return 1, 'attacking-build-up'
    return 0, 'routine-possession'


def analyze(path):
    # First independently require a complete 30-minute native recording.
    verified = verify(path)
    count = DURATION // BIN_MS
    levels = [0] * count
    reasons = [set() for _ in range(count)]
    previous = None
    event_counts = {'goal': 0, 'shot': 0, 'keeper-parry': 0, 'card-change': 0,
                    'foul': 0}
    event_times = set()

    def mark(start, end, level, reason):
        start = max(0, min(DURATION - 1, start))
        end = max(start + 1, min(DURATION, end))
        for i in range(start // BIN_MS, (end - 1) // BIN_MS + 1):
            if level > levels[i]:
                levels[i] = level
                reasons[i].clear()
            if level == levels[i]:
                reasons[i].add(reason)

    def event(t, kind, key, before=5000, after=3000):
        token = (kind, key)
        if token in event_times:
            return
        event_times.add(token)
        event_counts[kind] += 1
        mark(t - before, t + after, 3, kind)

    with Path(path).open(encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            clock = row['fixedClock']
            if not clock['started']:
                continue
            t = clock['elapsedMs']
            score = pair(row['score'])
            shots = pair(row['stats']['shots'])
            cards = {(p['team'], p['databaseId']): p['cardCode'] for p in row['participation']}
            level, reason = classify(row)
            mark(t, t + 1, level, reason)
            if level == 2:
                mark(t - 2000, t + 1000, 2, reason)
            if previous is not None:
                pt, ps, pshots, pcards = previous
                if t - pt > MAX_SAMPLE_GAP:
                    mark(pt, t, 3, 'unobserved-gap')
                if any(a < b for a, b in zip(score, ps)) or any(a < b for a, b in zip(shots, pshots)):
                    raise ValueError('Native counters reversed')
                for team in (0, 1):
                    for n in range(ps[team] + 1, score[team] + 1):
                        event(t, 'goal', (team, n), 7000, 5000)
                    for n in range(pshots[team] + 1, shots[team] + 1):
                        event(t, 'shot', (team, n))
                for key, card in cards.items():
                    if key in pcards and card != pcards[key]:
                        event(t, 'card-change', (key, t))
            for field, kind, match_kind in (
                    ('nativeKeeperEvents', 'keeper-parry', 'parry'),
                    ('nativeFouls', 'foul', None)):
                for record in row[field]:
                    if match_kind is not None and record.get('kind') != match_kind:
                        continue
                    actual = record['timeMs']
                    if type(actual) is not int or not 0 <= actual - clock['startMs'] <= t:
                        raise ValueError('Invalid native event time')
                    event(actual - clock['startMs'], kind,
                          (actual, record['team'], record['playerId']))
            # A shot contact protects its actual timestamp even if the score counter
            # is updated on a later frame. Counts above remain authoritative.
            for contact in row['nativeContacts']:
                if contact['kind'] == 'shot':
                    actual = contact['timeMs'] - clock['startMs']
                    if 0 <= actual <= t:
                        mark(actual - 5000, actual + 3000, 3, 'shot-contact')
            previous = t, score, shots, cards
    mark(0, 2000, 3, 'kickoff')
    mark(DURATION // 2 - 1000, DURATION // 2 + 3000, 3, 'halftime')
    mark(DURATION - 3000, DURATION, 3, 'full-time')
    segments = []
    totals = dict.fromkeys(LEVELS, 0)
    for i, level in enumerate(levels):
        names = sorted(reasons[i]) or ['no-priority']
        totals[LEVELS[level]] += BIN_MS
        if segments and segments[-1]['level'] == LEVELS[level] and segments[-1]['reasons'] == names:
            segments[-1]['endMs'] = (i + 1) * BIN_MS
        else:
            segments.append({'startMs': i * BIN_MS, 'endMs': (i + 1) * BIN_MS,
                             'level': LEVELS[level], 'reasons': names})
    return {'schema': 1, 'simulationMs': DURATION, 'targetPlaybackMs': 300000,
            'levelDurationsMs': totals, 'eventCounts': event_counts,
            'score': verified['score'], 'segments': segments, 'sourceTraceSha256': sha(path),
            'scope': 'Recorded importance heuristic; no legal-pass, xG, playback-duration or quality guarantee.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = analyze(args.trace)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'segments'}, indent=2))
