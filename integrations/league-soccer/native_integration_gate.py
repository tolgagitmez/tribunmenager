"""Strict diagnostic evidence gate; does not certify football quality."""
import argparse
import json
from pathlib import Path


def validate(report, mode):
    quality = report.get('quality') or {}
    football = quality.get('football') or {}
    presentation = quality.get('presentation') or {}
    lanes = quality.get('offballLanes') or {}
    selected = lanes.get('sampledSelections') or {}
    coordination = lanes.get('coordinationSamples') or {}
    errors = quality.get('errors')
    def positive(value):
        return type(value) is int and value > 0
    checks = {
        'privateMatchPassed': report.get('passed') is True,
        'completeFootballEvidence': bool(football) and football.get('score') == report.get('score'),
        'fiveMinuteClock': presentation.get('nativeElapsedMs') == 300000 and (presentation.get('checks') or {}).get('fiveMinuteWall') is True,
        'browserPlayback': (presentation.get('checks') or {}).get('fullBrowserPlayback') is True,
        'allDiagnosticsReadable': errors == {},
        'laneEvidence': lanes.get('evidenceAvailable') is True and any(positive(n) for n in selected.values()),
        'validLaneRecords': lanes.get('invalidLines') == 0,
        'modeEvidence': (positive(coordination.get('paired')) if mode == 'coordinated' else not coordination),
    }
    return {'mode': mode, 'checks': checks, 'passed': all(checks.values()),
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
