"""Compare two completed private matches descriptively, not causally."""
import argparse
import json
import math
from pathlib import Path


def metric(value, label):
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid ' + label)
    return value


def total(value, label):
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 2 or any(type(n) is not int or n < 0 for n in value):
        raise ValueError('Invalid ' + label)
    return sum(value)


def profile(report):
    q = report.get('quality') or {}
    f = q.get('football') or {}
    p = q.get('presentation') or {}
    checks = p.get('checks') or {}
    if report.get('passed') is not True or q.get('errors') != {} or checks.get('fiveMinuteWall') is not True or checks.get('fullBrowserPlayback') is not True:
        raise ValueError('Incomplete native match evidence')
    if total(report.get('score'), 'score') is None or f.get('score') != report['score']:
        raise ValueError('Missing or inconsistent score')
    passes = total(f.get('passes'), 'passes')
    completed = total(f.get('completed'), 'completed')
    if passes is None or completed is None or completed > passes:
        raise ValueError('Invalid pass totals')
    shots = total(f.get('shots'), 'shots')
    on_target = total(f.get('onTarget'), 'onTarget')
    if shots is None or on_target is None or on_target > shots:
        raise ValueError('Invalid shot totals')
    return {'goals': sum(report['score']), 'shots': shots, 'shotsOnTarget': on_target,
            'passes': passes, 'completedPasses': completed,
            'passCompletionPercent': round(100 * completed / passes, 2) if passes else None,
            'controlledBoxCrossings': total(f.get('controlledBoxCrossings'), 'controlledBoxCrossings'),
            'observedOpenPlayMs': metric(f.get('observedOpenPlayMs'), 'observedOpenPlayMs'),
            'excludedGapMs': metric(f.get('excludedGapMs'), 'excludedGapMs'),
            'longestIdenticalImageSeconds': metric(p.get('longestIdenticalImageSeconds'), 'longestIdenticalImageSeconds'),
            'droppedFraction': metric(p.get('droppedFraction'), 'droppedFraction')}


def compare(baseline, experimental):
    a, b = profile(baseline), profile(experimental)
    return {'baseline': a, 'experimental': b,
            'deltaExperimentalMinusBaseline': {k: None if a[k] is None or b[k] is None else round(b[k] - a[k], 5) for k in a},
            'seedMatchedVerified': False, 'causalImprovementVerified': False,
            'productionQualified': False,
            'scope': 'Two completed private matches; descriptive differences only. Missing measurements are null, not zero.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'experimental', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = compare(json.loads(args.baseline.read_text()), json.loads(args.experimental.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
