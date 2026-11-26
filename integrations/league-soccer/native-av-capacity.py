"""Local concurrent native audiovisual benchmark; not production capacity certification."""
import argparse
import json
import math
import signal
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

HERE = Path(__file__).resolve().parent

def cpu():
    values = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    return sum(values), values[3] + values[4]

def host_sample(previous, disk):
    current = cpu()
    delta = current[0] - previous[0]
    memory = dict((row.split(':', 1)[0], int(row.split()[1])) for row in
                  Path('/proc/meminfo').read_text().splitlines() if row.startswith(('MemTotal:', 'MemAvailable:')))
    return current, {
        'cpuBusyPercent': round(100 * (1 - (current[1] - previous[1]) / delta), 2) if delta > 0 else None,
        'availableMemoryMiB': round(memory['MemAvailable'] / 1024, 2),
        'totalMemoryMiB': round(memory['MemTotal'] / 1024, 2),
        'freeDiskMiB': round(shutil.disk_usage(disk).free / 1048576, 2)
    }

def read(path):
    return json.loads(path.read_text())

def match_result(directory, native_rc, browser_rc):
    result = {'nativeExit': native_rc, 'browserExit': browser_rc, 'passed': False}
    try:
        native = read(directory / 'live-report.json')
        browser = read(directory / 'browser-playback-report.json')
        capture = read(directory / 'native-match.capture.json')
        control = native['control']
        evidence = control['traceEvidence']
        start, finish = capture['kickoffObserved'], capture['finalObserved']
        # Keep engine evidence even if browser completion failed.
        result.update(kickoff=start,final=finish,nativeClockMs=native['nativeClock']['nativeElapsedMs'],observedWallSeconds=native['checks']['observedWallSeconds'],fixtureSha256=native['fixtureSha256'],motionAudit=native.get('motionAudit'),renderProbe=native.get('renderProbe'),encoderThreads=native.get('encoderThreads',2),browserPassed=browser.get('passed'))
        result.update(
            kickoff=start, final=finish, nativeClockMs=native['nativeClock']['nativeElapsedMs'],
            observedWallSeconds=native['checks']['observedWallSeconds'],
            coverage=browser['coverageFraction'], droppedFrames=browser['droppedFrames'],
            decodedFrames=browser['decodedFrames'], fixtureSha256=native['fixtureSha256'],
            audioWindows=native['audio']['nonSilentWindows'], audioOwnershipVerified=native.get('audioOwnership',{}).get('verified'),
            encodedVideoMaxGapSeconds=native.get('mediaTimeline',{}).get('tracks',{}).get('video',{}).get('maxGapSeconds'),
            browserLongestProgressIntervalMs=browser.get('longestObservedProgressIntervalMs'),
            motionAudit=native.get('motionAudit'), acknowledgements=len(evidence['acknowledgements']), renderProbe=native.get('renderProbe'), softwareGLWorkers=native.get('softwareGLWorkers',2))
        result['passed'] = bool(
            native_rc == browser_rc == 0 and native['status'] == 'local-live-evidence'
            and result['nativeClockMs'] == 300000 and 295 <= result['observedWallSeconds'] <= 305
            and finish > start and native['mediaTimeline']['timelinePassed']
            and native['audio']['nonSilentCoveragePassed'] and native['audioOwnership']['verified'] is True and browser['passed']
            and browser['ended'] and browser['playlistComplete']
            and browser['videoWidth'] == 1280 and browser['videoHeight'] == 720
            and control['submitted'] == control['applied'] == [1, 1]
            and control['pending'] == [False, False] and control['formations'] == [442, 4231]
            and evidence['consistent'] and evidence['allSubmittedObserved']
            and result['acknowledgements'] == 2
            and all(a['formationTargetsVerified'] for a in evidence['acknowledgements']))
    except (OSError, ValueError, KeyError, TypeError) as error:
        result['evidenceErrorType'] = type(error).__name__
        if isinstance(error,KeyError) and error.args and error.args[0] in ('coverageFraction','droppedFrames','decodedFrames','control','traceEvidence','nativeClock','nativeElapsedMs','audio','nonSilentWindows','checks','observedWallSeconds','audioOwnership','verified','kickoffObserved','finalObserved','fixtureSha256','acknowledgements','videoWidth','videoHeight'):
            result['missingEvidenceField']=error.args[0]
        for filename, field in [('live-report.json','nativeFailureType'),('browser-playback-report.json','browserReportStatus')]:
            try:
                item=read(directory / filename)
                result[field]=item.get('failureType',item.get('status','present'))
                if filename=='browser-playback-report.json':
                    result['browserPassed']=item.get('passed')
                    msg=str(item.get('error','')).lower()
                    result['browserFailureCategory']='stalled-playback' if 'stopped progressing' in msg else 'playback-deadline' if 'ended event' in msg else 'assertion-or-other' if msg else None
                if filename=='live-report.json':
                    result['captureFailure']=item.get('captureFailure')
                    result['runnerExit']=item.get('runnerExit')
            except (OSError,ValueError,TypeError,AttributeError):
                result[field]='missing-or-invalid'
    return result

def summarize(matches):
    complete = bool(matches) and all(m['passed'] for m in matches)
    overlap = max(0, min(m['final'] for m in matches) - max(m['kickoff'] for m in matches)) if complete else 0
    distinct = complete and len({m['fixtureSha256'] for m in matches}) == len(matches)
    return {'passed': bool(complete and distinct and overlap >= 285),
            'allMatchesPassed': complete, 'distinctFixtures': distinct, 'overlapSeconds': overlap}

def resource_summary(samples):
    busy = sorted(s['cpuBusyPercent'] for s in samples if s['cpuBusyPercent'] is not None)
    return {
        'cpuP95Percent': busy[math.ceil(.95 * len(busy)) - 1] if busy else None,
        'minimumAvailableMemoryMiB': min((s['availableMemoryMiB'] for s in samples), default=None),
        'minimumFreeDiskMiB': min((s['freeDiskMiB'] for s in samples), default=None)
    }

def prepare_fixtures(fixtures, destination, count):
    destination.mkdir()
    templates = ('balanced', 'counter-possession', 'possession-counter')
    names = []
    for i in range(count):
        config = read(fixtures / (templates[i % len(templates)] + '.json'))
        config['seed'] = 12400 + i
        name = 'match-%02d' % (i + 1)
        (destination / (name + '.json')).write_text(json.dumps(config) + '\n')
        names.append(name)
    return names

def stop_jobs(jobs):
    # Browser and native supervisors have different process groups; the native
    # supervisor handles TERM and cleans its separate engine process group.
    for _, native, browser in jobs:
        if browser is not None and browser.poll() is None:
            os.killpg(browser.pid, signal.SIGTERM)
        if native.poll() is None:
            native.terminate()
    for _, native, browser in jobs:
        for proc in (native, browser):
            if proc is None:
                continue
            try:
                proc.wait(timeout=25)
            except subprocess.TimeoutExpired:
                if proc is browser:
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
                proc.wait()

def main():
    from native_process_profile import ProcessProfile, snapshot
    from native_admission import identity, PROFILE
    from native_cpu_partition import partition, affinity_command, cgroup_path, counters, delta
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime', type=Path)
    p.add_argument('fixtures', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--count', type=int, choices=(1, 2, 4, 8, 16), default=2)
    p.add_argument('--filter-threads', type=int, choices=(0, 1), default=0)
    p.add_argument('--cpu-partition', action='store_true')
    p.add_argument('--render-probe', action='store_true')
    p.add_argument('--gl-workers', type=int, choices=(1,2), default=2)
    p.add_argument('--motion-audit', action='store_true')
    p.add_argument('--encoder-threads', type=int, choices=(1,2), default=2)
    args = p.parse_args()
    groups = partition(os.sched_getaffinity(0), args.count) if args.cpu_partition else [[] for _ in range(args.count)]
    if os.environ.get('TRIBUN_AV_ENCODER','x264') != 'x264':
        p.error('Hardware encoder concurrency is not qualified; use single-match pilot')
    if os.environ.get('TRIBUN_GPU_DISPLAY'):
        p.error('Concurrent GPU diagnostics require separate dedicated displays; use single-match GPU pilot')
    runtime, fixtures, out = (x.resolve() for x in (args.runtime, args.fixtures, args.out))
    host_identity = identity(runtime)
    trial_id = uuid.uuid4().hex
    out.mkdir(parents=True, exist_ok=False)
    names = prepare_fixtures(fixtures, out / 'fixtures', args.count)
    env = dict(os.environ, TRIBUN_EXPECT_AUDIO='1', TRIBUN_EXPECT_CONTROL='1',
               TRIBUN_EXPECT_FULL_PLAYBACK='1', TRIBUN_PLAYBACK_MIN_SECONDS='300',
               TRIBUN_EXPECT_SUSTAINED='0')
    env['TRIBUN_AV_FILTER_THREADS'] = str(args.filter_threads)
    env['TRIBUN_AV_SWAP_PROBE'] = '1' if args.render_probe else '0'
    env['TRIBUN_AV_GL_WORKERS'] = str(args.gl_workers)
    env['TRIBUN_AV_X264_THREADS'] = str(args.encoder_threads)
    env['TRIBUN_AV_MOTION_AUDIT'] = '1' if args.motion_audit else '0'
    meter = ProcessProfile()
    jobs = []
    logs = []
    samples = []
    started = time.monotonic()
    previous = cpu()
    group_path = cgroup_path()
    group_start = group_previous = counters(group_path)
    try:
        for i, name in enumerate(names):
            directory = out / name
            native_log = (out / (name + '-native.log')).open('wb')
            logs.append(native_log)
            native = subprocess.Popen(affinity_command(['python3', str(HERE / 'native-live-video.py'),
                 str(runtime), str(out / 'fixtures' / (name + '.json')), str(directory), '--audio', '--interactive', '--linger', '60'], groups[i]),
                 stdout=native_log, stderr=subprocess.STDOUT, env=env)
            jobs.append([directory, native, None])
        for i, job in enumerate(jobs):
            directory = job[0]
            browser_log = (out / (directory.name + '-browser.log')).open('wb')
            logs.append(browser_log)
            job[2] = subprocess.Popen(affinity_command(['node', str(HERE / 'native-live-video-browser.cjs'),
                str(directory / 'local-url.txt')], groups[i]), env=env, stdout=browser_log, stderr=subprocess.STDOUT, start_new_session=True)
        while any(proc.poll() is None for _, native, browser in jobs for proc in (native, browser)):
            if time.monotonic() - started > 1200:
                raise TimeoutError('Capacity tier exceeded 1200 seconds')
            time.sleep(2)
            previous, sample = host_sample(previous, out)
            sample['elapsedSeconds'] = round(time.monotonic() - started, 2)
            sample['processRoles'] = meter.observe(snapshot(), [proc.pid for _, n, b in jobs for proc in (n,b) if proc.poll() is None])
            current_group = counters(group_path)
            sample['cgroup'] = {**current_group, 'intervalDelta': delta(group_previous,current_group)}
            group_previous = current_group
            samples.append(sample)
        matches = [match_result(d, n.returncode, b.returncode) for d, n, b in jobs]
        report = {**summarize(matches), 'trialId': trial_id, 'matches': matches, 'hostLogicalCpus': os.cpu_count(),
                  'samples': samples, 'processProfile': meter.report(), 'filterThreads': args.filter_threads, 'resourceSummary': resource_summary(samples), 'requestedMatches': args.count, 'wallSeconds': round(time.monotonic() - started, 2),
                  'encoderThreads': args.encoder_threads, 'renderProbeRequested': args.render_probe, 'glWorkers': args.gl_workers, 'cpuPartition': args.cpu_partition, 'cpuGroups': groups, 'cgroupTotalDelta': delta(group_start,counters(group_path)), 'hostIdentity': host_identity, 'profile': PROFILE, 'productionQualified': False, 'scope': 'concurrent audio+video matches on this host only'}
        if args.motion_audit:
            report['motionAuditRequested']=True
            report['passed']=report['passed'] and all(isinstance(m.get('motionAudit'),dict) for m in matches)
        if args.render_probe:
            report['renderEvidenceComplete'] = all(isinstance(m.get('renderProbe'),dict) and m['renderProbe'].get('observed') is True for m in matches)
            report['passed'] = report['passed'] and report['renderEvidenceComplete']
        (out / 'capacity-report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k: v for k, v in report.items() if k != 'samples'}, indent=2))
        return 0 if report['passed'] else 1
    except (OSError, ValueError, TimeoutError, KeyboardInterrupt) as error:
        stop_jobs(jobs)
        matches = [match_result(d, n.returncode, b.returncode if b is not None else None) for d,n,b in jobs]
        (out / 'capacity-report.json').write_text(json.dumps({
            'passed': False, 'trialId': trial_id, 'productionQualified': False, 'cpuPartition': args.cpu_partition, 'cpuGroups': groups, 'cgroupTotalDelta': delta(group_start,counters(group_path)), 'hostIdentity': host_identity, 'profile': PROFILE, 'requestedMatches': args.count,
            'encoderThreads': args.encoder_threads, 'failureType': type(error).__name__, 'matches': matches, 'samples': samples,
            'resourceSummary': resource_summary(samples), 'processProfile': meter.report(), 'filterThreads': args.filter_threads
        }, indent=2) + '\n')
        return 1
    finally:
        stop_jobs(jobs)
        for log in logs:
            log.close()

if __name__ == '__main__':
    raise SystemExit(main())
