"""Linux process-tree sampling for private audiovisual diagnostics, not production accounting."""
import os
from pathlib import Path

ROLES = ('engine_with_software_gl', 'video_encoder', 'media_audit', 'virtual_display',
         'audio_server', 'browser', 'supervisor_other')

def parse_stat(text):
    # The process name may contain spaces and parentheses.
    before, tail = text.rsplit(')', 1)
    pid = int(before.split(' ', 1)[0])
    parts = tail.split()
    return pid, int(parts[1]), int(parts[19]), int(parts[11]) + int(parts[12]), max(0, int(parts[21]))

def role(name, args):
    if name == 'gameplayfootball': return 'engine_with_software_gl'
    if name == 'ffmpeg' and 'x11grab' in args: return 'video_encoder'
    if name in ('ffmpeg', 'ffprobe'): return 'media_audit'
    if name == 'Xvfb': return 'virtual_display'
    if name == 'pulseaudio': return 'audio_server'
    if name.startswith(('chrome', 'chromium', 'headless_shell')): return 'browser'
    return 'supervisor_other'

def snapshot(root=Path('/proc')):
    rows = {}
    for entry in root.iterdir():
        if not entry.name.isdigit(): continue
        try:
            raw = (entry / 'stat').read_text()
            pid, ppid, start, ticks, rss = parse_stat(raw)
            name = raw.split('(', 1)[1].rsplit(')', 1)[0]
            args = (entry / 'cmdline').read_bytes().decode(errors='replace').split('\0')
            # Linux comm is limited to 15 characters, use executable basename too.
            exe = Path(args[0]).name if args and args[0] else name
            rows[pid] = (ppid, start, ticks, rss, role(exe, args))
        except (OSError, ValueError, IndexError):
            continue
    return rows

def descendants(rows, roots):
    children = {}
    for pid, row in rows.items():
        children.setdefault(row[0], []).append(pid)
    seen = set()
    pending = list(roots)
    while pending:
        pid = pending.pop()
        if pid in seen: continue
        seen.add(pid)
        pending.extend(children.get(pid, ()))
    return seen.intersection(rows)

class ProcessProfile:
    def __init__(self, hz=None, page_size=None):
        self.hz = hz or os.sysconf('SC_CLK_TCK')
        self.page_size = page_size or os.sysconf('SC_PAGE_SIZE')
        self.last = {}
        self.totals = {r: 0 for r in ROLES}
        self.peaks = {r: 0 for r in ROLES}
        self.samples = 0

    def observe(self, rows, roots):
        counts = {r: 0 for r in ROLES}
        memory = dict(counts)
        ticks = dict(counts)
        current = {}
        for pid in descendants(rows, roots):
            _, start, total, rss, group = rows[pid]
            key = (pid, start)
            counts[group] += 1
            memory[group] += rss * self.page_size / 1048576
            # Only deltas between consecutive observations; short-lived tasks
            # and CPU before first sample are deliberately excluded.
            if key in self.last:
                ticks[group] += max(0, total - self.last[key])
            current[key] = total
        self.last = current
        self.samples += 1
        for group in ROLES:
            self.totals[group] += ticks[group]
            self.peaks[group] = max(self.peaks[group], memory[group])
        return {group: {'processCount': counts[group], 'observedCpuSeconds': round(ticks[group]/self.hz, 3),
                        'summedRssMiB': round(memory[group], 2)} for group in ROLES}

    def report(self):
        return {'samples': self.samples, 'roles': {
            group: {'observedCpuSecondsLowerBound': round(self.totals[group]/self.hz, 3),
                    'peakSummedRssMiB': round(self.peaks[group], 2)} for group in ROLES},
            'note': 'Sampled descendants only; CPU lower bound, RSS may double-count shared memory. Native engine CPU includes software OpenGL, not separately measured AI or GPU.'}
