"""Allowlisted diagnostic categories; no raw logs, command lines, or private URLs."""
from pathlib import Path
PATTERNS=(
 ('x_display_start',('xvfb failed to start','no isolated xvfb display available','server is already active for display','native sdl window not found')),
 ('pulse_start',('private audio server exited','private audio monitor unavailable')),
 ('openal_fallback',('native openal fallback to silent audio','falling back to silent audio','using silent audio')),
 ('openal_no_sink',('native openal sink input never observed','no native sound producer observed')),
 ('pulse_daemon_conflict',('daemon already running','failed to create secure directory','failed to acquire lock','failed to create pid file')),
 ('encoder_early_exit',('video encoder stopped before full time',)),
 ('encoder_resource',('resource temporarily unavailable','cannot allocate memory','failed to configure output pad','error while opening encoder')),
 ('native_incomplete',('native match did not complete','missing native completion markers')),
 ('runtime_mismatch',('native runtime revision or patches differ',)),
 ('season_validation',('native season report differs','missing native participation','invalid participation duration')),
 ('timeout',('timeoutexpired','timed out','exceeded limit')),
)
FILES=('runner.log','native-match.capture.log','native-match.game.log','native-audio.log')

def summarize(directory):
    categories=set()
    for name in FILES:
        p=Path(directory)/name
        try:
            with p.open('rb') as f:
                f.seek(0,2);f.seek(max(0,f.tell()-262144));tail=f.read().decode(errors='replace').lower()
        except OSError:continue
        for key,patterns in PATTERNS:
            if any(x in tail for x in patterns):categories.add(key)
    return {'categories':sorted(categories),'availableLogs':[n for n in FILES if (Path(directory)/n).is_file()],
            'scope':'Allowlisted log markers; not proof of root cause'}
