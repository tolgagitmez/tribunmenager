"""Offline video/audio retiming for an already kickoff-aligned match recording."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile

from native_playback_schedule import RATES, SOURCE_MS, TARGET_MS

FPS = 30
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS


def require(condition, message):
    if not condition:
        raise ValueError(message)


def seconds(ms):
    return f'{ms/1000:.9f}'


def ffmpeg(*args):
    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                    '-y',*map(str,args)],check=True)


def probe(path):
    result = json.loads(subprocess.check_output([
        'ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    streams = result['streams']
    videos = [s for s in streams if s['codec_type']=='video']
    audios = [s for s in streams if s['codec_type']=='audio']
    require(len(videos)==1 and len(audios)==1, 'Exactly one video and one audio track required')
    return videos[0], audios[0], result['format']


def duration(stream, fallback):
    value = float(stream.get('duration',fallback))
    require(math.isfinite(value) and value>0, 'Invalid stream duration')
    return value


def atempo_chain(rate):
    require(math.isfinite(rate) and 1<=rate<=12.000001, 'Invalid audio speed')
    filters=[]
    while rate>2:
        filters.append('atempo=2')
        rate/=2
    filters.append(f'atempo={rate:.12f}')
    return ','.join(filters)


def frame_boundary(ms):
    return (ms*FPS+500)//1000


def validate_plan(plan, source_ms=SOURCE_MS, target_ms=TARGET_MS):
    require(isinstance(plan,dict) and plan.get('schema')==1 and
            plan.get('simulationMs')==source_ms and
            plan.get('targetPlaybackMs')==target_ms and
            plan.get('plannedPlaybackMs')==target_ms and
            plan.get('targetFeasible') is True, 'A feasible exact-duration plan is required')
    require(frame_boundary(target_ms)*1000==target_ms*FPS,
            'Target duration must align to the output frame grid')
    rows=plan.get('segments')
    require(isinstance(rows,list) and 0<len(rows)<=1800, 'Invalid segment count')
    source_cursor=playback_cursor=0
    result=[]
    for row in rows:
        a,b,c,d=(row.get(k) for k in ('sourceStartMs','sourceEndMs',
                                     'playbackStartMs','playbackEndMs'))
        require(all(type(x) is int for x in (a,b,c,d)) and
                a==source_cursor and c==playback_cursor and a<b<=source_ms and
                c<d<=target_ms, 'Discontinuous source or presentation timeline')
        level=row.get('level')
        require(isinstance(level,str) and level in RATES, 'Invalid priority')
        rate=(b-a)/(d-c)
        lo,hi=RATES[level]
        declared=row.get('speed')
        require(type(declared) in (float,int) and math.isfinite(declared) and
                lo<=rate<=hi and abs(declared-rate)<1e-8, 'Invalid speed')
        frames=frame_boundary(d)-frame_boundary(c)
        require(frames>0, 'Segment has no output video frame')
        if level=='critical':
            require(b-a==d-c, 'Critical playback cannot be accelerated')
        result.append((a,b,rate,frames))
        source_cursor,playback_cursor=b,d
    require(source_cursor==source_ms and playback_cursor==target_ms, 'Incomplete timeline')
    return result


def render(source, plan, output, *, source_ms=SOURCE_MS, target_ms=TARGET_MS):
    """Source must already use native simulation time, not wall-time observations."""
    source,output=Path(source).resolve(),Path(output).resolve()
    require(source.is_file() and not output.exists() and output.suffix=='.mp4',
            'Use an existing aligned source and a new MP4 destination')
    rows=validate_plan(plan,source_ms,target_ms)
    video,audio,fmt=probe(source)
    require(all(abs(float(s.get('start_time',0)))<=.05 for s in (video,audio)),
            'Source tracks must start together at kickoff')
    require(all(abs(duration(s,fmt['duration'])-source_ms/1000)<=.10 for s in (video,audio)),
            'Source tracks must cover the complete simulation time')
    require(64<=int(video['width'])<=1920 and 64<=int(video['height'])<=1080,
            'Unsupported native recording dimensions')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='native-retime-',dir=output.parent) as tmp:
        tmp=Path(tmp)
        for i,(a,b,rate,frames) in enumerate(rows):
            samples=frames*SAMPLES_PER_FRAME
            # Trim source once, then use identical planned speed for both tracks.
            # CFR quantization is cumulative; padding covers filter boundary rounding.
            vf=(f'trim=duration={seconds(b-a)},setpts=(PTS-STARTPTS)/{rate:.12f},'
                f'fps={FPS},tpad=stop_mode=clone:stop_duration=0.10,'
                f'trim=end_frame={frames},setpts=N/({FPS}*TB),format=yuv420p')
            af=(f'atrim=duration={seconds(b-a)},asetpts=PTS-STARTPTS,'
                f'{atempo_chain(rate)},aresample={SAMPLE_RATE},'
                f'apad=pad_dur=0.15,atrim=end_sample={samples},asetpts=N/SR/TB')
            part=tmp/f'{i:05d}.mkv'
            ffmpeg('-ss',seconds(a),'-i',source,'-map','0:v:0','-map','0:a:0',
                   '-filter_threads','1','-vf',vf,'-af',af,
                   '-c:v','libx264','-threads','2','-preset','veryfast','-crf','21',
                   '-bf','0','-c:a','pcm_s16le','-ar',SAMPLE_RATE,'-ac','2',part)
            v,au,meta=probe(part)
            expected=frames/FPS
            require(abs(float(meta['duration'])-expected)<=.035,
                    f'Unexpected segment media duration: {i}')
        listing=tmp/'parts.txt'
        listing.write_text(''.join(f"file '{i:05d}.mkv'\n" for i in range(len(rows))),encoding='utf-8')
        staged=tmp/'final.mp4'
        ffmpeg('-f','concat','-safe','1','-i',listing,'-map','0:v:0','-map','0:a:0',
               '-c:v','copy','-c:a','aac','-b:a','128k','-movflags','+faststart',staged)
        v,a,meta=probe(staged)
        vd,ad=duration(v,meta['duration']),duration(a,meta['duration'])
        expected=target_ms/1000
        require(abs(vd-expected)<=.08 and abs(ad-expected)<=.08 and abs(vd-ad)<=.08,
                'Output A/V durations outside tolerance')
        staged.replace(output)
    return dict(plannedPlaybackMs=target_ms,videoSeconds=vd,audioSeconds=ad,
                durationDifferenceMs=round(abs(vd-ad)*1000,3),segments=len(rows),
                sourceAlignment='caller-provided kickoff-aligned simulation-time media',
                scope='Offline retiming; duration agreement is not proof of event-level A/V alignment or native capture provenance.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('plan',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--aligned-source',action='store_true',required=True,
                   help='Confirm input starts at kickoff and is indexed by native simulation time')
    a=p.parse_args()
    print(json.dumps(render(a.source,json.loads(a.plan.read_text()),a.output),indent=2))


if __name__=='__main__':
    main()
