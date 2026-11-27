"""Decode private native framebuffer markers and compare actual encoded frame PTS."""
import argparse
import csv
import json
import math
from pathlib import Path
import subprocess
from native_extended_capture import sha

WIDTH, HEIGHT = 256, 16
MAX_LAG_MS = 200
MAX_EARLY_MS = 40


def require(ok, message):
    if not ok:
        raise ValueError(message)


def checksum(number):
    return _xor_nibbles(number)


def _xor_nibbles(number):
    value=0
    for i in range(6):
        value ^= (number >> (4*i)) & 15
    return value


def decode(frame):
    require(len(frame)==WIDTH*HEIGHT,'Invalid marker image dimensions')
    code=0
    for i in range(32):
        pixels=[frame[y*WIDTH+x] for y in range(4,12) for x in range(i*8+2,i*8+6)]
        mean=sum(pixels)/len(pixels)
        if 65<mean<190:
            return None
        code=(code<<1)|int(mean>=190)
    ident=(code>>4)&0xffffff
    return ident if code>>28==10 and ident and code&15==checksum(ident) else None


def read_markers(path):
    markers={}
    last=0
    with Path(path).open() as f:
        for row in csv.reader(f):
            require(len(row)==3,'Invalid marker log row')
            ident,before,after=map(int,row)
            require(0<last+1==ident<=0xffffff and 0<before<=after,'Invalid marker log order')
            markers[ident]=(before,after)
            last=ident
    require(markers,'Empty native marker log')
    return markers


def audit_frames(frames, markers, origin, first_pts, last_pts):
    require(type(origin) is int and origin>0 and 0<=first_pts<last_pts,'Invalid match clock window')
    total=valid=timely=0
    previous_pts=-1
    previous_id=0
    maximum_gap=0
    previous_valid=first_pts
    maximum_lag=0
    maximum_early=0
    for pts,ident in frames:
        require(math.isfinite(pts) and pts>previous_pts,'Non-increasing encoded video PTS')
        previous_pts=pts
        if not first_pts<=pts<=last_pts:
            continue
        total+=1
        if ident not in markers:
            continue
        require(ident>=previous_id,'Rendered frame IDs reversed')
        previous_id=ident
        before,after=markers[ident]
        absolute=origin*1000000+pts*1000000
        early=max(0,(before-absolute)/1000)
        lag=max(0,(absolute-after)/1000)
        maximum_lag=max(maximum_lag,lag)
        maximum_early=max(maximum_early,early)
        valid+=1
        if early<=MAX_EARLY_MS and lag<=MAX_LAG_MS:
            timely+=1
            maximum_gap=max(maximum_gap,pts-previous_valid)
            previous_valid=pts
    maximum_gap=max(maximum_gap,last_pts-previous_valid)
    checks=dict(enoughFrames=total>=10*(last_pts-first_pts),
                decodedCoverage=total>0 and valid/total>=.99,
                timelyCoverage=total>0 and timely/total>=.99,
                maxTimelyGap=maximum_gap<=.5)
    return dict(totalFrames=total,decodedFrames=valid,timelyFrames=timely,
                maximumLateMs=round(maximum_lag,3),maximumEarlyMs=round(maximum_early,3),
                maximumTimelyGapMs=round(maximum_gap*1000,3),
                checks=checks,visualCalibrationPassed=all(checks.values()),
                exactAudioAlignmentVerified=False,eligibleForAutomaticRetime=False,
                scope='Diagnostic framebuffer swap marker vs encoded PTS. Not native-state or audio-event alignment proof.')


def frames(video):
    # Probe display-order timestamps, then decode the same stream without FPS conversion.
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(video)]))
    timestamps=[float(f['best_effort_timestamp_time']) for f in info['frames']]
    proc=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-i',str(video),'-map','0:v:0',
        '-vf','crop=256:16:8:ih-24,format=gray','-vsync','0','-f','rawvideo','-'],stdout=subprocess.PIPE)
    try:
        with proc.stdout as stream:
            for pts in timestamps:
                data=stream.read(WIDTH*HEIGHT)
                require(len(data)==WIDTH*HEIGHT,'Decoded frame count mismatch')
                yield pts,decode(data)
            require(not stream.read(1),'Extra decoded video frames')
        require(proc.wait(timeout=30)==0,'Video decode failed')
    finally:
        if proc.poll() is None:
            proc.kill();proc.wait()


def audio_packet_audit(packets, first_pts, last_pts):
    previous_end=None
    max_gap=0.0
    count=0
    first=None
    for p in packets:
        pts=float(p['pts_time'])
        duration=float(p['duration_time'])
        require(math.isfinite(pts) and math.isfinite(duration) and 0<duration<=.1,
                'Invalid AAC packet timing')
        end=pts+duration
        if end<first_pts or pts>last_pts:
            continue
        if first is None:
            first=pts
        if previous_end is not None:
            require(pts>=previous_end-.003,'Audio timestamps overlap or reverse')
            max_gap=max(max_gap,pts-previous_end)
        previous_end=end
        count+=1
    passed=(count>0 and first<=first_pts+.05 and previous_end>=last_pts-.05 and max_gap<=.05)
    return dict(packetCount=count,maxGapMs=round(max_gap*1000,3),
                continuityPassed=passed,scope='AAC packet PTS continuity only; no sound-event alignment proof.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('video','markers','alignment','output'):
        p.add_argument(name,type=Path)
    a=p.parse_args()
    m=json.loads(a.alignment.read_text())
    require(m.get('candidateMappingPassed') is True,'Shared epoch candidate did not pass')
    result=audit_frames(frames(a.video),read_markers(a.markers),m['mediaEpochOriginSeconds'],
                       m['kickoffCandidatePtsSeconds'],m['fullTimeCandidatePtsSeconds'])
    audio=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0',
        '-show_packets','-show_entries','packet=pts_time,duration_time','-of','json',str(a.video)]))
    result['audioPacketContinuity']=audio_packet_audit(audio['packets'],
        m['kickoffCandidatePtsSeconds'],m['fullTimeCandidatePtsSeconds'])
    result.update(videoSha256=sha(a.video),markersSha256=sha(a.markers),alignmentSha256=sha(a.alignment))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0 if result['visualCalibrationPassed'] and result['audioPacketContinuity']['continuityPassed'] else 2


if __name__=='__main__':
    raise SystemExit(main())
