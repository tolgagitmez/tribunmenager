"""Optimize the stage 218 timeline, never weaken critical playback protection."""
import argparse
import json
from pathlib import Path

from native_playback_schedule import RATES, SOURCE_MS, TARGET_MS, schedule, require

BIN = 1000


def expand(highlights):
    bins = []
    for row in highlights['segments']:
        start, end = row['startMs'], row['endMs']
        require(start % BIN == 0 and end % BIN == 0, 'Expected one-second highlight grid')
        bins.extend([(row['level'], tuple(row['reasons']))] * ((end-start)//BIN))
    require(len(bins) == SOURCE_MS//BIN, 'Invalid highlight grid')
    return bins


def coalesce(highlights, bins, shoulder):
    ranks = {name: i for i, name in enumerate(RATES)}
    levels = [level for level, _ in bins]
    # Add slower approach/departure intervals around entire critical blocks.
    # Existing dangerous/critical intervals cannot be demoted.
    for i, (level, _) in enumerate(bins):
        if level != 'critical':
            continue
        for j in range(max(0, i-shoulder), min(len(bins), i+shoulder+1)):
            if ranks[levels[j]] < ranks['dangerous']:
                levels[j] = 'dangerous'
    rows = []
    totals = dict.fromkeys(RATES, 0)
    for i, level in enumerate(levels):
        original, reasons = bins[i]
        reasons = set(reasons)
        if level != original:
            reasons.add('critical-transition-shoulder')
        totals[level] += BIN
        # Keep exact reasons in sourceHighlightSegments. Here reasons are
        # a union across the rate-control block, not per-frame event evidence.
        promoted = level != original
        if rows and rows[-1]['level'] == level and rows[-1]['transitionShoulder'] == promoted:
            rows[-1]['endMs'] = (i+1)*BIN
            rows[-1]['reasons'] = sorted(set(rows[-1]['reasons']) | reasons)
        else:
            rows.append(dict(startMs=i*BIN,endMs=(i+1)*BIN,level=level,
                             reasons=sorted(reasons),transitionShoulder=promoted))
    return dict(highlights, segments=rows, levelDurationsMs=totals)


def transitions(plan):
    rates = [row['speed'] for row in plan['segments']]
    ratios = [max(a/b,b/a) for a,b in zip(rates,rates[1:])]
    return dict(speedChanges=sum(r > 1.01 for r in ratios),
                abruptChanges=sum(r > 3.0 for r in ratios),
                maximumJumpRatio=max(ratios, default=1.0))


def original_danger_ms(plan, bins):
    # Time assigned to actual dangerous intervals, excluding added shoulders.
    result = 0.0
    for s in plan['segments']:
        first, last = s['sourceStartMs']//BIN, s['sourceEndMs']//BIN
        count = sum(level == 'dangerous' for level, _ in bins[first:last])
        result += count*BIN/s['speed']
    return result


def optimize(highlights, target_ms=TARGET_MS):
    initial = schedule(highlights, target_ms)
    bins = expand(highlights)
    base = schedule(coalesce(highlights,bins,0),target_ms)
    # Coalescing removes integer-rounding and reason-only speed changes.
    # If its feasible range shrinks, preserve the original valid plan.
    if abs(base['deviationMs']) > abs(initial['deviationMs']):
        base = initial
    chosen = base
    chosen_shoulder = 0
    baseline_danger = original_danger_ms(base,bins)
    candidates = []
    def key(plan, shoulder):
        m = transitions(plan)
        return (abs(plan['deviationMs']),m['abruptChanges'],
                round(m['maximumJumpRatio'],6),m['speedChanges'],-shoulder)
    for shoulder in (1,2,3):
        manifest = coalesce(highlights,bins,shoulder)
        limits = {row['startMs']:(3,4) for row in manifest['segments'] if row['transitionShoulder']}
        candidate = schedule(manifest,target_ms,rate_limits=limits)
        danger = original_danger_ms(candidate,bins)
        eligible = (abs(candidate['deviationMs']) <= abs(base['deviationMs'])
                    and danger >= baseline_danger-1.0)
        candidates.append(dict(shoulderSeconds=shoulder,eligible=eligible,
                               deviationMs=candidate['deviationMs'],
                               originalDangerPlaybackMs=round(danger,3),
                               **transitions(candidate)))
        if eligible and key(candidate,shoulder) < key(chosen,chosen_shoulder):
            chosen,chosen_shoulder = candidate,shoulder
    require(chosen['criticalAtNormalSpeed'], 'Critical playback protection lost')
    require(chosen['playbackDurationsMs']['critical']==initial['playbackDurationsMs']['critical'],
            'Critical duration changed')
    chosen = dict(chosen)
    chosen['optimization'] = dict(shoulderSeconds=chosen_shoulder,
        before=transitions(initial),after=transitions(chosen),
        originalDangerPlaybackMsBefore=round(baseline_danger,3),
        originalDangerPlaybackMsAfter=round(original_danger_ms(chosen,bins),3),
        candidates=candidates)
    chosen['sourceHighlightSegments'] = highlights['segments']
    chosen['scope'] = ('Optimized presentation plan only; rate-control block reasons are unions. '
                       'Original highlight intervals preserved separately. No measured playback or smoothness claim.')
    return chosen


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('highlights',type=Path)
    p.add_argument('output',type=Path)
    args=p.parse_args()
    result=optimize(json.loads(args.highlights.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ('segments','sourceHighlightSegments')},indent=2))
    return 0 if result['targetFeasible'] else 2


if __name__=='__main__':
    raise SystemExit(main())
