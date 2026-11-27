import sys
from pathlib import Path
import unittest
import tempfile
import subprocess

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_frame_calibration import WIDTH,HEIGHT,checksum,decode,audit_frames,frames,audio_packet_audit


def marker(ident):
    code=(10<<28)|(ident<<4)|checksum(ident)
    row=b''.join(bytes([255 if code & (1<<(31-i)) else 0])*8 for i in range(32))
    return row*HEIGHT


class FrameCalibrationTest(unittest.TestCase):
    def test_marker_decoding(self):
        for n in (1,42,65535,0xffffff):
            self.assertEqual(decode(marker(n)),n)

    def test_corrupt_marker_rejected(self):
        f=bytearray(marker(1234))
        for y in range(HEIGHT):
            for x in range(248,256):
                f[y*WIDTH+x]=255-f[y*WIDTH+x]
        self.assertIsNone(decode(f))
        self.assertIsNone(decode(bytes([128])*WIDTH*HEIGHT))

    def test_latency_and_coverage(self):
        ms=[i*40 for i in range(26)]
        records={i+1:(1000000000+t*1000,1000000000+t*1000+1000)
                 for i,t in enumerate(ms)}
        data=[(t/1000+.02,i+1) for i,t in enumerate(ms)]
        result=audit_frames(data,records,1000,.02,1.02)
        self.assertTrue(result['visualCalibrationPassed'])
        self.assertAlmostEqual(result['maximumLateMs'],19)
        self.assertFalse(result['eligibleForAutomaticRetime'])

    def test_excessive_latency(self):
        records={i+1:(1000000000+i*40000,1000000000+i*40000+1000)
                 for i in range(26)}
        result=audit_frames([(i*.04+.4,i+1) for i in range(26)],records,1000,.4,1.4)
        self.assertFalse(result['visualCalibrationPassed'])

    def test_missing_markers(self):
        result=audit_frames([(i*.04,None) for i in range(26)],{},1000,0,1)
        self.assertFalse(result['visualCalibrationPassed'])

    def test_reversed_ids(self):
        with self.assertRaises(ValueError):
            audit_frames([(0,2),(.1,1)],{1:(1000000000,1000001000),
                2:(1000000000,1000001000)},1000,0,1)

    def test_audio_packet_continuity(self):
        packets=[dict(pts_time=i*.02,duration_time=.02) for i in range(50)]
        self.assertTrue(audio_packet_audit(packets,0,1)['continuityPassed'])
        self.assertFalse(audio_packet_audit(packets[:10]+packets[20:],0,1)['continuityPassed'])

    def test_real_encoded_marker_decode(self):
        # Synthetic input validates the decoder through H264, not native rendering.
        with tempfile.TemporaryDirectory() as d:
            video=Path(d)/'marker.mp4'
            data=bytearray()
            for ident in (101,102,103):
                img=bytearray([128])*(320*64)
                m=marker(ident)
                for y in range(HEIGHT):
                    i=(64-24+y)*320+8
                    img[i:i+WIDTH]=m[y*WIDTH:(y+1)*WIDTH]
                data.extend(img)
            subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','gray',
                '-video_size','320x64','-framerate','25','-i','pipe:0','-c:v','libx264',
                '-crf','25','-pix_fmt','yuv420p',str(video)],input=data,check=True)
            self.assertEqual([n for _,n in frames(video)],[101,102,103])


if __name__=='__main__':
    unittest.main()
