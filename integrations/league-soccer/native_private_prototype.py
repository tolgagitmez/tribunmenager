"""Fail-closed private prototype: trim a near-real-time capture then retime it.

Does not approve distribution or claim exact event-level audio synchronization.
"""
import argparse
import json
from pathlib import Path
import tempfile

from native_extended_capture import sha
from native_extended_clock_verify import DURATION
from native_media_retime import ffmpeg, probe, duration, render, validate_plan, TARGET_MS

MAX_NATIVE_CLOCK_RESIDUAL_US = 80000


def require(ok,message):
    if not ok:
        raise ValueError(message)


def check_mapping(mapping, source_ms):
    require(mapping.get('candidateMappingPassed') is True and
            mapping.get('simulationMs')==source_ms,'Unqualified shared epoch mapping')
    anchors=mapping.get('anchors')
    require(isinstance(anchors,list) and len(anchors)>=2,'Missing native anchors')
    first=anchors[0]['candidatePtsUs']
    previous_n=-1
    previous_u=-1
    maximum=0
    for a in anchors:
        n,u=a['nativeMs'],a['candidatePtsUs']
        require(type(n) is int and type(u) is int and n>previous_n and
                u>previous_u and 0<=n<=source_ms,'Invalid native anchors')
        maximum=max(maximum,abs(u-first-n*1000))
        previous_n,previous_u=n,u
    require(anchors[0]['nativeMs']==0 and previous_n==source_ms and first>=0,
            'Incomplete source mapping')
    require(maximum<=MAX_NATIVE_CLOCK_RESIDUAL_US,
            'Nonlinear native/media clock drift: piecewise normalization required')
    return first/1e6,maximum


def aligned_source(source, output, start, source_ms):
    """Use absolute input PTS for BOTH streams. Reject missing match coverage."""
    v,a,meta=probe(source)
    end=start+source_ms/1000
    for track in (v,a):
        first=float(track['start_time'])
        last=first+duration(track,meta['duration'])
        require(first<=start+.04 and last>=end-.04,'Encoded tracks do not cover trim')
    vf=(f'trim=start={start:.9f}:end={end:.9f},'
        f'setpts=PTS-{start:.9f}/TB,fps=30:start_time=0,'
        f'tpad=stop_mode=clone:stop_duration=0.08,trim=duration={source_ms/1000:.9f},format=yuv420p')
    af=(f'atrim=start={start:.9f}:end={end:.9f},asetpts=PTS-{start:.9f}/TB,'
        'aresample=48000:first_pts=0,apad=pad_dur=0.08,'
        f'atrim=end_sample={source_ms*48},asetpts=N/SR/TB')
    ffmpeg('-copyts','-i',source,'-map','0:v:0','-map','0:a:0',
           '-filter_threads','1','-vf',vf,'-af',af,'-c:v','libx264',
           '-threads','2','-preset','veryfast','-crf','20','-c:a','aac',
           '-ar','48000','-ac','2',output)
    v,a,meta=probe(output)
    require(all(abs(float(s['start_time']))<=.05 and
                abs(duration(s,meta['duration'])-source_ms/1000)<=.08 for s in (v,a)),
            'Aligned recording duration mismatch')


def require_same_run(capture, mapping, frame, trace, video, markers, alignment_path):
    require(capture.get('status')=='raw-capture-observed' and
            capture.get('rawCoveragePassed') is True,'Raw native capture did not pass')
    require(frame.get('visualCalibrationPassed') is True and
            frame.get('audioPacketContinuity',{}).get('continuityPassed') is True,
            'Visual calibration or AAC continuity failed')
    trace_hash,video_hash=sha(trace),sha(video)
    require(capture.get('traceSha256')==trace_hash and capture.get('videoSha256')==video_hash and
            mapping.get('traceSha256')==trace_hash and mapping.get('videoSha256')==video_hash and
            frame.get('videoSha256')==video_hash and frame.get('markersSha256')==sha(markers) and
            frame.get('alignmentSha256')==sha(alignment_path),'Mixed or changed evidence files')
    return trace_hash,video_hash


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture_dir','alignment','calibration','plan','output','report'):
        p.add_argument(name,type=Path)
    p.add_argument('--private-diagnostic',action='store_true',required=True)
    a=p.parse_args()
    root=a.capture_dir
    video,trace,markers=(root/'native-match.mp4',root/'match.ndjson',root/'native-frame-markers.csv')
    capture=json.loads((root/'extended-capture-report.json').read_text())
    mapping=json.loads(a.alignment.read_text())
    frame=json.loads(a.calibration.read_text())
    plan=json.loads(a.plan.read_text())
    report=dict(schema=1,status='blocked',productionEnabled=False,
                videoRedistributionApproved=False,exactAudioAlignmentVerified=False)
    def save():
        a.report.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        trace_hash,video_hash=require_same_run(capture,mapping,frame,trace,video,markers,a.alignment)
        validate_plan(plan)
        require(plan.get('sourceTraceSha256')==trace_hash,'Playback plan belongs to a different trace')
        start,residual=check_mapping(mapping,DURATION)
        require(not a.output.exists(),'New output required')
        with tempfile.TemporaryDirectory(prefix='native-private-prototype-',dir=root) as tmp:
            aligned=Path(tmp)/'aligned.mp4'
            aligned_source(video,aligned,start,DURATION)
            metrics=render(aligned,plan,a.output)
        report.update(status='private-prototype-created',nativeClockResidualUs=residual,
                      traceSha256=trace_hash,sourceVideoSha256=video_hash,
                      outputSha256=sha(a.output),metrics=metrics,
                      scope='Private diagnostic footage, visible frame marker; duration check only. '
                            'No exact audio-event alignment, production or redistribution approval.')
        save()
        print(json.dumps(report,indent=2))
    except Exception as exc:
        report['blocker']=str(exc)
        save()
        raise


if __name__=='__main__':
    main()
