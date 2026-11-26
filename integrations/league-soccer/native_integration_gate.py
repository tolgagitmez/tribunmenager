"""Strict diagnostic evidence gate; does not certify football quality."""
import argparse
import json
from pathlib import Path


REQUIRED_DIAGNOSTICS = ('actionExecution', 'skeletonMotion', 'transitionMotion',
                        'dribbleControl', 'duelEscape', 'pressureHold',
                        'passTiming', 'combinations', 'offballLanes')


def object_or_empty(value):
    return value if isinstance(value, dict) else {}


def valid_score(value):
    return isinstance(value, list) and len(value) == 2 and all(type(n) is int and n >= 0 for n in value)


def valid_counts(value, allowed):
    return isinstance(value, dict) and set(value) <= allowed and all(type(n) is int and n >= 0 for n in value.values())


def validate(report, mode):
    if mode not in ('lanes', 'coordinated'):
        raise ValueError('Invalid mode')
    report = object_or_empty(report)
    quality = object_or_empty(report.get('quality'))
    football = object_or_empty(quality.get('football'))
    presentation = object_or_empty(quality.get('presentation'))
    lanes = object_or_empty(quality.get('offballLanes'))
    selected = lanes.get('sampledSelections')
    coordination = lanes.get('coordinationSamples')
    checks_data = object_or_empty(presentation.get('checks'))
    stall = object_or_empty(quality.get('stallDiagnostics'))
    missing = [name for name in REQUIRED_DIAGNOSTICS if not isinstance(quality.get(name), dict)]
    if not isinstance(stall.get('carrier'), dict):
        missing.append('stallDiagnostics.carrier')
    dribble = object_or_empty(quality.get('dribbleControl'))
    for field in ('touches', 'separation'):
        if not isinstance(dribble.get(field), dict):
            missing.append('dribbleControl.' + field)
    valid_selected = valid_counts(selected, {'primary', 'secondary'})
    valid_coordination = valid_counts(coordination, {'paired', 'unpaired'})
    errors = quality.get('errors')
    def positive(value):
        return type(value) is int and value > 0
    checks = {
        'privateMatchPassed': report.get('passed') is True,
        'completeFootballEvidence': valid_score(report.get('score')) and valid_score(football.get('score')) and football['score'] == report['score'],
        'fiveMinuteClock': presentation.get('nativeElapsedMs') == 300000 and checks_data.get('fiveMinuteWall') is True,
        'browserPlayback': checks_data.get('fullBrowserPlayback') is True,
        'allDiagnosticsReadable': errors == {} and not missing,
        'laneEvidence': lanes.get('evidenceAvailable') is True and valid_selected and any(positive(n) for n in selected.values()),
        'validLaneRecords': type(lanes.get('invalidLines')) is int and lanes['invalidLines'] == 0,
        'modeEvidence': valid_coordination and (positive(coordination.get('paired')) if mode == 'coordinated' else not coordination),
    }
    return {'mode': mode, 'checks': checks, 'passed': all(checks.values()), 'missingDiagnostics': missing,
            'productionQualified': False, 'subjectiveQualityVerified': False,
            'scope': 'Evidence completeness only; independent matches do not establish a causal improvement. Zero observed paired selections fails evidence, not necessarily the engine.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('report', type=Path)
    p.add_argument('mode', choices=('lanes', 'coordinated'))
    p.add_argument('output', type=Path)
    a = p.parse_args()
    result = validate(json.loads(a.report.read_text()), a.mode)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
