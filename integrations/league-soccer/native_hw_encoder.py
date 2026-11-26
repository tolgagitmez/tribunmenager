"""Explicit local HLS hardware encode experiment; never silently fall back to x264."""
import json
import os
import re
import stat
import subprocess
from pathlib import Path
import tempfile

SCALE = 'scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2'
BACKENDS = ('x264', 'nvenc', 'qsv', 'vaapi')
CODECS = {'x264':'libx264','nvenc':'h264_nvenc','qsv':'h264_qsv','vaapi':'h264_vaapi'}

def plan(backend, device='', gpu_index=''):
    if backend not in BACKENDS:
        raise ValueError('Unknown video encoder')
    if backend == 'x264':
        if device or gpu_index: raise ValueError('Hardware device with software encoder')
        return [], ['-vf',SCALE,'-c:v','libx264','-threads','2','-preset','ultrafast','-crf','25','-pix_fmt','yuv420p'], ['-g','50','-keyint_min','50','-sc_threshold','0','-tune','zerolatency','-profile:v','baseline','-level:v','3.1']
    # Match format and cadence, not bit-exact quality or bandwidth.
    gop=['-g','50','-bf','0','-force_key_frames','expr:gte(t,n_forced*2)','-profile:v','baseline']
    rate=['-b:v','2500k','-maxrate','3500k','-bufsize','3500k']
    if backend == 'nvenc':
        if device or (gpu_index and not re.fullmatch(r'[0-9]{1,2}',gpu_index)):
            raise ValueError('NVENC needs an optional numeric GPU index, not a DRM path')
        return [], ['-vf',SCALE+',format=yuv420p','-c:v','h264_nvenc','-gpu',gpu_index or '0','-preset','p1','-tune','ull','-rc','cbr','-forced-idr','1',*rate], gop
    if gpu_index or not re.fullmatch(r'/dev/dri/renderD[0-9]{3,4}',device):
        raise ValueError('VAAPI/QSV requires an explicit DRM render node')
    init=['-init_hw_device','vaapi=va:'+device]
    if backend=='qsv':
        init += ['-init_hw_device','qsv=qs@va','-filter_hw_device','qs']
    else:
        init += ['-filter_hw_device','va']
    return init, ['-vf',SCALE+',format=nv12,hwupload=extra_hw_frames=64','-c:v',CODECS[backend],*rate], gop

def selected(env):
    backend=env.get('TRIBUN_AV_ENCODER','x264')
    device=env.get('TRIBUN_AV_DRM_DEVICE','')
    index=env.get('TRIBUN_AV_GPU_INDEX','')
    return backend, device, index, plan(backend,device,index)

def verify_stream(stream):
    return (stream.get('codec_name')=='h264' and stream.get('width')==1280
            and stream.get('height')==720 and stream.get('pix_fmt')=='yuv420p'
            and int(stream.get('has_b_frames',-1))==0
            and 'baseline' in stream.get('profile','').lower())

def preflight(backend,device,index):
    init,encode,gop=plan(backend,device,index)
    if backend=='x264': return {'backend':backend,'hardware':False}
    if device and (not stat.S_ISCHR(Path(device).stat().st_mode) or not os.access(device,os.R_OK|os.W_OK)):
        raise ValueError('DRM render node is not accessible')
    # A listed FFmpeg encoder is insufficient: encode and decode real test frames.
    with tempfile.TemporaryDirectory(prefix='tribun-encode-') as d:
        output=Path(d)/'probe.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error',*init,'-f','lavfi','-i','testsrc2=size=1280x720:rate=25','-t','4','-an',*encode,*gop,str(output)],check=True,timeout=45)
        data=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_streams','-of','json',str(output)],timeout=15))
        stream=data['streams'][0]
        if not verify_stream(stream) or int(stream.get('nb_read_frames',0))!=100:
            raise ValueError('Hardware probe did not produce expected baseline 720p25 H.264')
        subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(output),'-f','null','-'],check=True,timeout=30)
    return {'backend':backend,'codec':CODECS[backend],'hardware':True,'syntheticProbePassed':True,
            'frames':100,'width':1280,'height':720,'fps':25,'profile':stream['profile'],
            'note':'Actual selected encoder produced and decoded synthetic frames; full native match, quality and capacity not yet qualified.'}
