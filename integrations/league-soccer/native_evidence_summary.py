"""Publish bounded, structured native evidence diagnostics without changing the gate."""
import json
import os
from pathlib import Path

CHECKS = (
    'privateMatchPassed', 'completeFootballEvidence', 'fiveMinuteClock',
    'browserPlayback', 'allDiagnosticsReadable', 'laneEvidence',
    'validLaneRecords', 'modeEvidence',
)
PROFILES = (
    ('lanes', 'alpha-state', 'baseline-evidence.json', 'BASELINE_OUTCOME'),
    ('coordinated', 'coordinated-state', 'coordinated-evidence.json', 'EXPERIMENTAL_OUTCOME'),
)
OUTCOMES = ('success', 'failure', 'cancelled', 'skipped')
METRICS = ('goals', 'shots', 'shotsOnTarget', 'controlledBoxCrossings',
           'stationaryCarrierEpisodes', 'longestStationaryCarrierMs')


def read_object(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def obj(value):
    return value if isinstance(value, dict) else {}


def count(value):
    return str(value) if type(value) is int and value >= 0 else 'unknown'


def outcome(env, key):
    value = env.get(key)
    return value if value in OUTCOMES else 'unknown'


def summarize(root, env):
    lines = ['## Native real match evidence', '',
             'Build: **' + outcome(env, 'BUILD_OUTCOME') + '** | '
             'Strict gate: **' + outcome(env, 'GATE_OUTCOME') + '**', '',
             '| Profile | Match step | Reports | Gate | Failed or missing checks |',
             '| --- | --- | ---: | --- | --- |']
    notices = []
    detail = []
    for mode, directory, gate_file, env_key in PROFILES:
        reports = sorted((root / directory).glob('alpha-*/match/private-beta-report.json'))
        gate = read_object(root / gate_file)
        checks = obj(obj(gate).get('checks'))
        failed = [key for key in CHECKS if checks.get(key) is not True]
        status = 'missing/unreadable'
        if gate is not None:
            status = ('pass' if gate.get('passed') is True and not failed
                      and gate.get('mode') == mode else 'fail/inconsistent')
        lines.append('| ' + ' | '.join((mode, outcome(env, env_key), str(len(reports)),
                                          status, ', '.join(failed) or 'none')) + ' |')
        if status != 'pass' or len(reports) != 1:
            notices.append(mode + ': ' + status + '; report count=' + str(len(reports))
                           + '; failed/missing checks: ' + (', '.join(failed) or 'none'))
        report = read_object(reports[0]) if len(reports) == 1 else None
        lanes = obj(obj(obj(report).get('quality')).get('offballLanes'))
        selected = obj(lanes.get('sampledSelections'))
        paired = obj(lanes.get('coordinationSamples'))
        detail.append('| ' + ' | '.join((mode, count(selected.get('primary')),
                         count(selected.get('secondary')), count(paired.get('paired')),
                         count(paired.get('unpaired')), count(lanes.get('invalidLines')))) + ' |')
    lines += ['', '### Observed lane and coordination records', '',
              '| Profile | Primary | Secondary | Paired | Unpaired | Invalid lines |',
              '| --- | ---: | ---: | ---: | ---: | ---: |', *detail,
              '', 'Absent or invalid counts are unknown, not zero.']
    comparison = read_object(root / 'attack-comparison.json')
    if comparison is None:
        lines += ['', 'Comparison report missing or unreadable.']
        notices.append('Comparison report missing or unreadable')
    else:
        lines += ['', '### Descriptive comparison', '',
                  '| Metric | Lanes | Coordinated |', '| --- | ---: | ---: |']
        for metric in METRICS:
            lines.append('| ' + ' | '.join((metric,
                count(obj(comparison.get('baseline')).get(metric)),
                count(obj(comparison.get('experimental')).get(metric)))) + ' |')
        same = obj(comparison.get('provenance')).get('fixtureIdentityMatched')
        lines += ['', 'Fixture identity matched: **' +
                  ('yes' if same is True else 'no' if same is False else 'unknown') + '**.']
    lines += ['', 'Diagnostic reporting only. The original validation exit status is unchanged. '
              'No causal improvement or production qualification is inferred.', '']
    if outcome(env, 'GATE_OUTCOME') == 'failure' and not notices:
        notices.append('Strict evidence step failed; inspect comparison and gate execution.')
    return '\n'.join(lines), notices


def main():
    summary, notices = summarize(Path(os.environ['RUNNER_TEMP']), os.environ)
    with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a', encoding='utf-8') as output:
        output.write(summary)
    # Fixed field names and numeric counts only, not arbitrary log or report text.
    for message in notices:
        print('::error title=Native match evidence::' + message)


if __name__ == '__main__':
    main()
