"""Private audio/video HLS packaging for a single encoder.

No engine configuration changes, no public HTTP server, no viewer-specific
simulation. HLS adds segment latency; this module is a transport pilot.
"""
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time

SEGMENT_SECONDS=2
MAX_SEGMENTS=6
MAX_PLAYLIST_BYTES=16384
MAX_SEGMENT_BYTES=16*1024*1024
SEGMENT=re.compile(r'segment-\d{6}\.ts')
FMP4_SEGMENT=re.compile(r'segment-\d{6}\.m4s')

def encoder_args(display,monitor,output,*,fmp4=False,hd=False,retain=False):
    if not re.fullmatch(r':\d+(?:\.\d+)?',display):
        raise ValueError('Private X11 display required')
    if not re.fullmatch(r'tribun_[a-z0-9]+\.monitor',monitor):
        raise ValueError('Dedicated test audio monitor required')
    output=Path(output)
    if output.is_symlink() or not output.is_dir() or any(output.iterdir()):
        raise ValueError('Fresh private HLS directory required')
    return ['ffmpeg','-nostdin','-v','error',
            '-thread_queue_size','256','-f','x11grab','-draw_mouse','0',
            '-framerate','30' if hd else '25','-video_size','1280x1024','-i',display,
            '-thread_queue_size','256','-f','pulse','-i',monitor,
            *encoding_args(output,fmp4=fmp4,hd=hd,retain=retain)]

def encoding_args(output,*,fmp4=False,hd=False,retain=False):
    output=Path(output)
    extra=['-hls_segment_type','fmp4','-hls_fmp4_init_filename','init.mp4'] if fmp4 else []
    suffix='m4s' if fmp4 else 'ts'
    fps='30' if hd else '25'
    gop='60' if hd else '50'
    scale=('scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=fast_bilinear,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1' if hd else 'scale=640:512:flags=fast_bilinear')
    return ['-map','0:v:0','-map','1:a:0','-vf',scale,
            '-c:v','libx264','-threads','2','-preset','veryfast','-tune','zerolatency',
            '-pix_fmt','yuv420p','-r',fps,'-g',gop,'-keyint_min',gop,'-sc_threshold','0',
            '-c:a','aac','-ar','48000','-ac','2','-b:a','96k',
            '-f','hls','-hls_time',str(SEGMENT_SECONDS),'-hls_list_size',str(MAX_SEGMENTS),
            '-hls_delete_threshold','2','-hls_flags',('independent_segments+temp_file' if retain else 'delete_segments+independent_segments+temp_file'),
            *extra,'-hls_segment_filename',str(output/('segment-%06d.'+suffix)),str(output/'stream.m3u8')]

def read_published_file(path,limit):
    """Read the opened inode, even if the rolling encoder unlinks it."""
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as file:
        info=os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=limit:
            raise ValueError('Invalid HLS file')
        data=file.read(limit+1)
        if len(data)!=info.st_size:
            raise ValueError('HLS file changed')
    return data,info

def read_playlist(directory,*,fmp4=False):
    try:
        data,_=read_published_file(Path(directory)/'stream.m3u8',MAX_PLAYLIST_BYTES)
        return parse_playlist(data.decode('utf-8'),fmp4=fmp4)
    except (OSError,UnicodeError) as error:
        raise ValueError('Invalid live playlist') from error

def parse_playlist(text,*,fmp4=False):
    lines=text.splitlines()
    if not lines or lines[0]!='#EXTM3U':
        raise ValueError('Invalid HLS header')
    pattern=FMP4_SEGMENT if fmp4 else SEGMENT
    suffix='m4s' if fmp4 else 'ts'
    segments=[]
    sequence=None
    duration=None
    init=False
    ended=False
    for line in lines[1:]:
        if not line:
            continue
        if ended:
            raise ValueError('Reference after end of playlist')
        if line.startswith('#EXT-X-MEDIA-SEQUENCE:'):
            if sequence is not None or segments or duration is not None:
                raise ValueError('Duplicate or misplaced media sequence')
            sequence=int(line.split(':',1)[1])
        elif line.startswith('#EXT-X-MAP:'):
            if not fmp4 or init or segments or line!='#EXT-X-MAP:URI="init.mp4"':
                raise ValueError('Invalid initialization fragment')
            init=True
        elif line.startswith('#EXTINF:'):
            if duration is not None:
                raise ValueError('Missing segment reference')
            duration=float(line.split(':',1)[1].split(',',1)[0])
            if not math.isfinite(duration) or not 0<duration<=3:
                raise ValueError('Invalid segment duration')
        elif line=='#EXT-X-ENDLIST':
            ended=True
        elif not line.startswith('#'):
            if not pattern.fullmatch(line) or duration is None or (fmp4 and not init):
                raise ValueError('Invalid segment reference')
            segments.append(dict(name=line,seconds=duration))
            duration=None
    if fmp4 and not init:
        raise ValueError('Missing local initialization fragment')
    if duration is not None or sequence is None or sequence<0 or not 1<=len(segments)<=MAX_SEGMENTS:
        raise ValueError('Invalid bounded playlist window')
    if [s['name'] for s in segments]!=[f'segment-{i:06d}.{suffix}' for i in range(sequence,sequence+len(segments))]:
        raise ValueError('Discontinuous segment sequence')
    return dict(mediaSequence=sequence,segments=segments,
                windowSeconds=sum(s['seconds'] for s in segments),
                ended=ended)

def read_segment(path):
    path=Path(path)
    fragmented=bool(FMP4_SEGMENT.fullmatch(path.name))
    if not fragmented and not SEGMENT.fullmatch(path.name):
        raise ValueError('Invalid segment')
    try:
        media,_=read_published_file(path,MAX_SEGMENT_BYTES)
        init=read_published_file(path.with_name('init.mp4'),MAX_SEGMENT_BYTES)[0] if fragmented else b''
    except OSError as error:
        raise ValueError('Invalid or expired segment') from error
    return init+media,len(media)

def probe_streams(data):
    data=json.loads(subprocess.check_output(['ffprobe','-v','error',
        '-show_entries','stream=codec_type,codec_name,sample_rate,width,height,start_time',
        '-of','json','-i','pipe:0'],input=data,timeout=10))
    streams=data['streams']
    video=[s for s in streams if s.get('codec_type')=='video']
    audio=[s for s in streams if s.get('codec_type')=='audio']
    if len(video)!=1 or len(audio)!=1 or video[0].get('codec_name')!='h264' or audio[0].get('codec_name')!='aac' or audio[0].get('sample_rate')!='48000':
        raise ValueError('Expected H264 and 48 kHz AAC in same segment')
    try:
        audio_start=float(audio[0]['start_time'])
        video_start=float(video[0]['start_time'])
        offset=round((audio_start-video_start)*1000,3)
    except (KeyError,TypeError,ValueError,OverflowError):
        offset=None
    return dict(video=video[0],audio=audio[0],muxAudioMinusVideoStartMs=offset if offset is not None and math.isfinite(offset) else None)

def segment_probe(path):
    data,size=read_segment(path)
    return dict(**probe_streams(data),bytes=size)

def publication_age_ms(path,now=None):
    """Local file age only; not capture-to-screen latency."""
    now=time.time() if now is None else now
    return max(0,round((now-Path(path).stat().st_mtime)*1000))


def audit_packet_timeline(fragments,*,fps=25):
    """Check encoded track continuity, not physical A/V synchronization."""
    if fps not in (25,30):
        raise ValueError('Unsupported encoded frame rate')
    tracks={'video':[], 'audio':[]}
    boundaries=[]
    for media in fragments:
        data=json.loads(subprocess.check_output(['ffprobe','-v','error',
            '-show_entries','stream=index,codec_type,codec_name,sample_rate:packet=stream_index,pts_time,duration_time',
            '-of','json','-i','pipe:0'],input=media,timeout=10))
        mapping={s['index']:s['codec_type'] for s in data['streams']}
        if sorted(mapping.values())!=['audio','video']:
            raise ValueError('Expected exactly one video and audio track')
        part={'video':[], 'audio':[]}
        for packet in data.get('packets',[]):
            kind=mapping[packet['stream_index']]
            pts=float(packet['pts_time'])
            # Some ffprobe builds omit duration in isolated fMP4 fragments.
            # Infer only missing durations from the known constant-rate encoder.
            # Actual PTS are never inferred, so gaps/duplicates remain detectable.
            raw=packet.get('duration_time')
            duration=(1024/48000 if kind=='audio' else 1/fps) if raw in (None,'N/A') else float(raw)
            if not math.isfinite(pts) or not math.isfinite(duration) or duration<=0:
                raise ValueError('Invalid encoded packet timing')
            part[kind].append((pts,duration))
        for kind, packets in part.items():
            if not packets:
                raise ValueError('Missing encoded '+kind+' packets')
            # The configured zero-latency H264 encoder has no B-frames.
            if any(b[0]<=a[0] for a,b in zip(packets,packets[1:])):
                raise ValueError('Non-monotonic '+kind+' presentation timestamps')
            tracks[kind].extend(packets)
        boundaries.extend([part['audio'][0][0]-part['video'][0][0],
            sum(part['audio'][-1])-sum(part['video'][-1])])
    if len(boundaries)<4:
        raise ValueError('Need at least two consecutive fragments')
    gap={}; overlap={}
    for kind,packets in tracks.items():
        deltas=[b[0]-sum(a) for a,b in zip(packets,packets[1:])]
        if any(b[0]<=a[0] for a,b in zip(packets,packets[1:])):
            raise ValueError('Non-monotonic '+kind+' fragment timeline')
        gap[kind]=round(max(0,*deltas)*1000,3)
        overlap[kind]=round(max(0,*[-x for x in deltas])*1000,3)
    offset=round(max(abs(x) for x in boundaries)*1000,3)
    return dict(encodedTimelineVerified=max(*gap.values(),*overlap.values())<=50 and offset<=100,
                fragmentCount=len(boundaries)//2, maxPacketGapMs=gap,maxPacketOverlapMs=overlap,
                firstVideoPts=tracks['video'][0][0], lastVideoEnd=sum(tracks['video'][-1]),
                firstAudioPts=tracks['audio'][0][0], lastAudioEnd=sum(tracks['audio'][-1]),
                maxTrackBoundaryOffsetMs=offset,physicalAVSyncVerified=False)
