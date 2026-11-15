#!/usr/bin/env python3
"""Run the complete stage13 suite and retain source-bound test evidence."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
digest = lambda b: hashlib.sha256(b).hexdigest()
paths = set()
for pattern in ('*.js', '*.html', '*.css', '*.json', '*.py'):
    paths.update(p for p in ROOT.glob(pattern) if p.name != 'BUILD_MANIFEST.json')
for folder in ('tests', 'tools', 'assets/player'):
    paths.update(p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
paths.add(ROOT / 'requirements-player-assets.txt')
sources = {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(paths)}
runtime = ROOT / 'work/stage13'
runtime.mkdir(parents=True, exist_ok=True)
log_path = runtime / 'final-tests.log'
with log_path.open('wb') as log:
    result = subprocess.run(['npm', 'run', 'test:stage13'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
data = log_path.read_bytes()
log = data.decode('utf-8')
assert result.returncode == 0, f'Test command failed ({result.returncode}); see {log_path}'
counts = {key: sum(map(int, re.findall(r'^(?:ℹ |# )' + key + r' (\d+)\s*$', log, re.M))) for key in ('tests', 'pass', 'fail', 'cancelled', 'skipped')}
python = list(map(int, re.findall(r'^Ran (\d+) tests? in ', log, re.M)))
assert counts['tests'] > 413 and counts['tests'] == counts['pass']
assert counts['fail'] == counts['cancelled'] == counts['skipped'] == 0
assert len(python) == 4 and sum(python) >= 27 and len(re.findall(r'^OK\s*$', log, re.M)) == 4
for path, sha in sources.items():
    assert digest((ROOT / path).read_bytes()) == sha, f'Source changed during tests: {path}'
artifact = 'docs/validation/player-asset-tests.log.gz'
(ROOT / artifact).write_bytes(gzip.compress(data, mtime=0))
report = {
    'generatedAt': datetime.now(timezone.utc).isoformat(), 'command': 'npm run test:stage13',
    'sources': sources, 'logSHA256': digest(data),
    'logArtifact': {'path': artifact, 'bytes': len(data), 'gzipSHA256': digest((ROOT / artifact).read_bytes())},
    'javascript': counts,
    'python': {'playerModel': python[0], 'fixtureRosterAPI': python[1], 'launcherHTTP': python[2], 'playerAssetRebuild': python[3]},
    'total': counts['tests'] + sum(python), 'passed': counts['pass'] + sum(python),
    'failed': 0, 'skipped': 0, 'verified': True,
    'scope': 'Prior simulation, identity, rules and launcher regression suites plus player asset validation, provenance, GLB/runtime equivalence, PNG identity, anatomical bounds, rejection of altered inputs and exact offline rebuild. Browser GPU/fault evidence is recorded separately.'
}
(ROOT / 'docs/validation/player-asset-tests.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ('total', 'passed', 'failed', 'skipped', 'verified')}))
