"""Build a bounded, continuous presentation timeline from native highlights."""
import argparse
import json
from pathlib import Path

SOURCE_MS = 1_800_000
TARGET_MS = 300_000
# (minimum playback rate, maximum playback rate)
RATES = {'routine': (4, 12), 'build-up': (2, 12),
         'dangerous': (1, 4), 'critical': (1, 1)}
PRIORITY = ('critical', 'dangerous', 'build-up', 'routine')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ceil_div(a, b):
    return (a + b - 1) // b


def schedule(highlights, target_ms=TARGET_MS, *, rate_limits=None):
    require(isinstance(highlights, dict) and highlights.get('schema') == 1 and
            highlights.get('simulationMs') == SOURCE_MS, 'Invalid native highlight manifest')
    require(type(target_ms) is int and target_ms > 0, 'Invalid playback budget')
    segments = highlights.get('segments')
    require(isinstance(segments, list) and bool(segments), 'Missing highlight segments')
    source_end = 0
    totals = dict.fromkeys(RATES, 0)
    rows = []
    for s in segments:
        require(isinstance(s, dict), 'Invalid segment')
        start, end, level = s.get('startMs'), s.get('endMs'), s.get('level')
        require(type(start) is int and type(end) is int and
                start == source_end and start < end <= SOURCE_MS, 'Non-contiguous source timeline')
        require(isinstance(level, str) and level in RATES, 'Invalid importance level')
        reasons = s.get('reasons')
        require(isinstance(reasons, list) and all(isinstance(x, str) for x in reasons),
                'Invalid importance reasons')
        duration = end - start
        min_rate, max_rate = RATES[level]
        if rate_limits is not None and start in rate_limits:
            low, high = rate_limits[start]
            require(type(low) is int and type(high) is int and min_rate <= low <= high <= max_rate,
                    'Invalid narrowed rate limits')
            min_rate, max_rate = low, high
        minimum = ceil_div(duration, max_rate)
        maximum = duration // min_rate
        require(minimum <= maximum, 'Segment too short for integer-ms playback bounds')
        rows.append(dict(sourceStartMs=start, sourceEndMs=end, level=level,
                         reasons=list(reasons), duration=duration,
                         minimum=minimum, maximum=maximum, playback=minimum))
        totals[level] += duration
        source_end = end
    require(source_end == SOURCE_MS, 'Incomplete source timeline')
    require(highlights.get('levelDurationsMs') == totals, 'Importance duration mismatch')

    minimum = sum(row['minimum'] for row in rows)
    maximum = sum(row['maximum'] for row in rows)
    feasible = minimum <= target_ms <= maximum
    actual_budget = min(maximum, max(minimum, target_ms))
    remaining = actual_budget - minimum

    # Spend available viewing time on more important plays first. Share each
    # level's allocation proportionally to capacity, not chronologically.
    for level in PRIORITY:
        group = [row for row in rows if row['level'] == level]
        capacity = sum(row['maximum'] - row['minimum'] for row in group)
        allocation = min(remaining, capacity)
        if capacity:
            cumulative = previous_share = 0
            for row in group:
                cumulative += row['maximum'] - row['minimum']
                share = allocation * cumulative // capacity
                row['playback'] += share - previous_share
                previous_share = share
        remaining -= allocation
    require(remaining == 0, 'Playback allocation failed')

    cursor = 0
    output = []
    playback_totals = dict.fromkeys(RATES, 0)
    for row in rows:
        duration = row['playback']
        output.append(dict(sourceStartMs=row['sourceStartMs'], sourceEndMs=row['sourceEndMs'],
                           playbackStartMs=cursor, playbackEndMs=cursor+duration,
                           speed=row['duration']/duration, level=row['level'], reasons=row['reasons']))
        playback_totals[row['level']] += duration
        cursor += duration
    require(cursor == actual_budget, 'Playback duration mismatch')
    return dict(schema=1, simulationMs=SOURCE_MS, targetPlaybackMs=target_ms,
                plannedPlaybackMs=cursor, minimumPlaybackMs=minimum, maximumPlaybackMs=maximum,
                targetFeasible=feasible, deviationMs=cursor-target_ms,
                status='target-met' if feasible else 'target-too-short' if target_ms < minimum else 'target-too-long',
                sourceDurationsMs=totals, playbackDurationsMs=playback_totals,
                criticalAtNormalSpeed=playback_totals['critical']==totals['critical'],
                score=highlights.get('score'), segments=output,
                scope='Presentation plan only; no dropped source intervals, no physics changes or measured video duration.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('highlights', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = schedule(json.loads(args.highlights.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='segments'}, indent=2))
    return 0 if result['targetFeasible'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
