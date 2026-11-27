"""Private audio/video HLS packaging for a single encoder.

No engine configuration changes, no public HTTP server, no viewer-specific
simulation. HLS adds segment latency; this module is a transport pilot.
"""
import math
from pathlib import Path
import re
import subprocess
import time

SEGMENT_SECONDS=2
MAX_SEGMENTS=6
SEGMENT=re.compile(r'segment-\d{6}\.ts')
FMP4_SEGMENT=re.compile(r'segment-\d{6}\.m4s')

def encoder_args(display,monitor,output,*,fmp4=False):
    if not re.fullmatch(r':\d+(?:\.\d+)?',display):
        raise ValueError('Private X11 display required')
    if not re.fullmatch(r'tribun_[a-z0-9]+\.monitor',monitor):
        raise ValueError('Dedicated test audio monitor required')
    output=Path(output)
    if output.is_symlink() or not output.is_dir() or any(output.iterdir()):
        raise ValueError('Fresh private HLS directory required')
    return ['ffmpeg','-nostdin','-v','error',
            '-thread_queue_size','256','-f','x11grab','-draw_mouse','0',
            '-framerate','25','-video_size','1280x1024','-i',display,
            '-thread_queue_size','256','-f','pulse','-i',monitor,
            *encoding_args(output,fmp4=fmp4)]

def encoding_args(output,*,fmp4=False):
    output=Path(output)
    extra=['-hls_segment_type','fmp4','-hls_fmp4_init_filename','init.mp4'] if fmp4 else []
    suffix='m4s' if fmp4 else 'ts'
    return ['-map','0:v:0','-map','1:a:0','-vf','scale=640:512:flags=fast_bilinear',
            '-c:v','libx264','-threads','2','-preset','veryfast','-tune','zerolatency',
            '-pix_fmt','yuv420p','-r','25','-g','50','-keyint_min','50','-sc_threshold','0',
            '-c:a','aac','-ar','48000','-ac','2','-b:a','96k',
            '-f','hls','-hls_time',str(SEGMENT_SECONDS),'-hls_list_size',str(MAX_SEGMENTS),
            '-hls_delete_threshold','2','-hls_flags','delete_segments+independent_segments+temp_file',
            *extra,'-hls_segment_filename',str(output/('segment-%06d.'+suffix)),str(output/'stream.m3u8')]

def read_playlist(directory,*,fmp4=False):
    path=Path(directory)/'stream.m3u8'
    if path.is_symlink() or not path.is_file() or path.stat().st_size>16384:
        raise ValueError('Invalid live playlist')
    lines=path.read_text(encoding='utf-8').splitlines()
    if not lines or lines[0]!='#EXTM3U':
        raise ValueError('Invalid HLS header')
    if fmp4 and '#EXT-X-MAP:URI="init.mp4"' not in lines:
        raise ValueError('Missing local initialization fragment')
    pattern=FMP4_SEGMENT if fmp4 else SEGMENT
    suffix='m4s' if fmp4 else 'ts'
    segments=[]
    sequence=None
    duration=None
    for line in lines[1:]:
        if line.startswith('#EXT-X-MEDIA-SEQUENCE:'):
            sequence=int(line.split(':',1)[1])
        elif line.startswith('#EXTINF:'):
            duration=float(line.split(':',1)[1].split(',',1)[0])
            if not math.isfinite(duration) or not 0<duration<=3:
                raise ValueError('Invalid segment duration')
        elif line and not line.startswith('#'):
            if not pattern.fullmatch(line) or duration is None:
                raise ValueError('Invalid segment reference')
            segments.append(dict(name=line,seconds=duration))
            duration=None
    if sequence is None or sequence<0 or not 1<=len(segments)<=MAX_SEGMENTS:
        raise ValueError('Invalid bounded playlist window')
    if [s['name'] for s in segments]!=[f'segment-{i:06d}.{suffix}' for i in range(sequence,sequence+len(segments))]:
        raise ValueError('Discontinuous segment sequence')
    return dict(mediaSequence=sequence,segments=segments,
                windowSeconds=sum(s['seconds'] for s in segments),
                ended='#EXT-X-ENDLIST' in lines)

def segment_probe(path):
    import json
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not SEGMENT.fullmatch(path.name):
        raise ValueError('Invalid segment')
    data=json.loads(subprocess.check_output(['ffprobe','-v','error',
        '-show_entries','stream=codec_type,codec_name,sample_rate,width,height',
        '-of','json',str(path)],text=True,timeout=10))
    streams=data['streams']
    video=[s for s in streams if s.get('codec_type')=='video']
    audio=[s for s in streams if s.get('codec_type')=='audio']
    if len(video)!=1 or len(audio)!=1 or video[0].get('codec_name')!='h264' or audio[0].get('codec_name')!='aac' or audio[0].get('sample_rate')!='48000':
        raise ValueError('Expected H264 and 48 kHz AAC in same segment')
    return dict(video=video[0],audio=audio[0],bytes=path.stat().st_size)

def publication_age_ms(path,now=None):
    """Local file age only; not capture-to-screen latency."""
    now=time.time() if now is None else now
    return max(0,round((now-Path(path).stat().st_mtime)*1000))
