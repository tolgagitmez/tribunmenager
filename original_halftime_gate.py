"""Opt-in visual state gate for a disposable, fixed-size native X11 display.

Calibration must come from the actual pinned build, locale and display.
Synthetic calibration tests do not establish real native recognition.
No OCR, guessed halftime timer or blind repeated key presses.
"""
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess

WIDTH,HEIGHT=1280,1024
MIN_PIXELS=120
MAX_PIXELS=100000

def box(value):
    if not isinstance(value,list) or len(value)!=4 or any(type(x) is not int for x in value):
        raise ValueError('Expected integer x,y,width,height')
    x,y,w,h=value
    if min(x,y)<0 or min(w,h)<8 or x+w>WIDTH or y+h>HEIGHT or w*h>MAX_PIXELS:
        raise ValueError('Invalid visual region')
    return x,y,w,h

def crop(frame,region):
    x,y,w,h=box(region)
    if len(frame)!=WIDTH*HEIGHT:
        raise ValueError('Expected complete grayscale display frame')
    return b''.join(frame[(y+i)*WIDTH+x:(y+i)*WIDTH+x+w] for i in range(h))

def learn_region(region,positive,negative):
    """Retain pixels stable in every positive and discriminative in negatives."""
    if len(positive)<2 or len(negative)<3:
        raise ValueError('Need two positive and three different negative screen samples')
    pos=[crop(f,region) for f in positive]
    neg=[crop(f,region) for f in negative]
    if len(set(pos))<2:
        # Static labels may be identical; the full screen positives must differ.
        if len(set(positive))<2:
            raise ValueError('Positive frames must be independent examples')
    # A pixel need not distinguish every negative; validate each negative
    # against the whole mask afterwards.
    indices=[i for i,p in enumerate(pos[0]) if all(abs(f[i]-p)<=3 for f in pos[1:])
             and any(abs(f[i]-p)>=32 for f in neg)]
    if len(indices)<MIN_PIXELS:
        raise ValueError('Insufficient discriminative visual pixels')
    values=bytes(pos[0][i] for i in indices)
    learned=dict(box=region,indices=indices,values=base64.b64encode(values).decode('ascii'))
    if any(score(learned,f)>.85 for f in negative):
        raise ValueError('Region cannot distinguish all negative examples')
    return learned

def score(region,frame):
    sample=crop(frame,region['box'])
    indices=region['indices']
    values=base64.b64decode(region['values'],validate=True)
    if (not isinstance(indices,list) or not MIN_PIXELS<=len(indices)<=len(sample)
        or len(indices)!=len(values) or any(type(i) is not int or not 0<=i<len(sample) for i in indices)
        or any(a>=b for a,b in zip(indices,indices[1:]))):
        raise ValueError('Invalid visual mask')
    return sum(abs(sample[i]-v)<=8 for i,v in zip(indices,values))/len(indices)

def validate_regions(regions):
    if not isinstance(regions,list) or len(regions)!=2:
        raise ValueError('Two independent title and button regions required')
    a,b=[box(r['box']) for r in regions]
    if a[0]<b[0]+b[2] and b[0]<a[0]+a[2] and a[1]<b[1]+b[3] and b[1]<a[1]+a[3]:
        raise ValueError('Visual regions overlap')

class OnceGate:
    def __init__(self,regions):
        validate_regions(regions)
        self.regions=regions
        self.streak=0
        self.fired=False
        self.last_scores=[]
    def observe(self,frame):
        self.last_scores=[score(r,frame) for r in self.regions]
        if self.fired:
            return False
        self.streak=self.streak+1 if min(self.last_scores)>=.98 else 0
        if self.streak<3:
            return False
        self.fired=True
        return True

def frame(env):
    if not re.fullmatch(r':\d+(?:\.0)?',env.get('DISPLAY','')):
        raise ValueError('Expected explicitly isolated X11 display')
    data=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-f','x11grab',
        '-draw_mouse','0','-video_size',f'{WIDTH}x{HEIGHT}','-i',env['DISPLAY'],
        '-frames:v','1','-pix_fmt','gray','-threads','1','-f','rawvideo','pipe:1'],
        env=env,timeout=8)
    if len(data)!=WIDTH*HEIGHT:
        raise RuntimeError('Invalid visual capture')
    return data

def league_calibration(regions,training,validation):
    """Validate independent reviewed native-league samples, not their origin.

    Each sample is (state, raw_frame). Positive/negative validation frames
    must be separate from training bytes. No source authenticity claim.
    """
    validate_regions(regions)
    labels={'halftime','gameplay','main-menu','fulltime'}
    def check(samples):
        if not isinstance(samples,list) or not 5<=len(samples)<=24:
            raise ValueError('Expected bounded labeled league samples')
        counts={state:0 for state in labels}
        hashes=[]
        for state,raw in samples:
            if state not in labels or len(raw)!=WIDTH*HEIGHT:
                raise ValueError('Invalid league reference sample')
            counts[state]+=1
            hashes.append(hashlib.sha256(raw).hexdigest())
        if counts['halftime']<2 or any(counts[s]<1 for s in labels-{'halftime'}):
            raise ValueError('Need halftime, gameplay, menu and fulltime examples')
        if len(set(hashes))!=len(hashes):
            raise ValueError('Duplicate league reference samples')
        return hashes
    train_hashes=check(training)
    validation_hashes=check(validation)
    if set(train_hashes)&set(validation_hashes):
        raise ValueError('Validation must not reuse training frames')
    measurements=[]
    for state,raw in validation:
        scores=[score(r,raw) for r in regions]
        if state=='halftime' and min(scores)<.98:
            raise ValueError('Held-out halftime sample not recognized')
        if state!='halftime' and max(scores)>.85:
            raise ValueError('Held-out negative sample too similar to halftime')
        measurements.append(dict(state=state,sha256=hashlib.sha256(raw).hexdigest(),scores=scores))
    return dict(scope='reviewed-normal-league',trainingSha256=train_hashes,
                validation=measurements,independentSamplesPassed=True,
                sourceAuthenticityVerified=False)

def require_league_calibration(data):
    proof=data.get('leagueCalibration')
    if not isinstance(proof,dict) or proof.get('scope')!='reviewed-normal-league' or proof.get('independentSamplesPassed') is not True:
        raise ValueError('Reviewed normal league held-out calibration required')
    train=proof.get('trainingSha256')
    rows=proof.get('validation')
    if not isinstance(train,list) or not isinstance(rows,list) or not 5<=len(train)<=24 or not 5<=len(rows)<=24:
        raise ValueError('Incomplete league calibration evidence')
    if any(not isinstance(x,str) or not re.fullmatch('[0-9a-f]{64}',x) for x in train):
        raise ValueError('Invalid league training digest')
    seen=set(train)
    if len(seen)!=len(train) or seen!=set(data.get('positiveSha256',[])+data.get('negativeSha256',[])):
        raise ValueError('League training evidence mismatch')
    counts={s:0 for s in ('halftime','gameplay','main-menu','fulltime')}
    for row in rows:
        state=row.get('state');sha=row.get('sha256');scores=row.get('scores')
        if (state not in counts or not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha)
            or sha in seen or not isinstance(scores,list) or len(scores)!=2
            or any(type(v) not in (float,int) or not 0<=v<=1 for v in scores)):
            raise ValueError('Invalid independent league calibration evidence')
        if (state=='halftime' and min(scores)<.98) or (state!='halftime' and max(scores)>.85):
            raise ValueError('Independent league calibration thresholds failed')
        seen.add(sha);counts[state]+=1
    if counts['halftime']<2 or any(counts[s]<1 for s in counts if s!='halftime'):
        raise ValueError('Incomplete league validation states')


def load_bundle(path,revision,config_sha,*,require_league=False):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>4*1024*1024:
        raise ValueError('Invalid calibration bundle')
    data=json.loads(path.read_text())
    if (data.get('revision')!=revision or data.get('configSha256')!=config_sha
        or data.get('screen')!=[WIDTH,HEIGHT] or data.get('state')!='halftime'):
        raise ValueError('Calibration does not match native revision, settings or display')
    if data.get('operatorReviewed') is not True:
        raise ValueError('Explicit visual calibration review required')
    if require_league:
        require_league_calibration(data)
    gate=OnceGate(data['regions'])
    # Validate masks before starting a match.
    for r in gate.regions:
        score(r,bytes(WIDTH*HEIGHT))
    return gate

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text())
    if manifest.get('operatorReviewed') is not True:
        raise ValueError('Review actual native positive and negative screen samples first')
    for key in ('revision','configSha256'):
        if not re.fullmatch('[0-9a-f]{40}' if key=='revision' else '[0-9a-f]{64}',manifest.get(key,'')):
            raise ValueError('Invalid calibration revision/config identity')
    def samples(key):
        names=manifest[key]
        if not isinstance(names,list) or not 2<=len(names)<=12:
            raise ValueError('Invalid sample count')
        result=[]
        for name in names:
            path=Path(name)
            if path.is_symlink() or not path.is_file() or path.stat().st_size!=WIDTH*HEIGHT:
                raise ValueError('Expected raw grayscale reference frame')
            result.append(path.read_bytes())
        if len(set(result))!=len(result):
            raise ValueError('Duplicate calibration frames')
        return result
    positive,negative=samples('positive'),samples('negative')
    regions=[learn_region(r,positive,negative) for r in manifest['regions']]
    validate_regions(regions)
    output=dict(revision=manifest['revision'],configSha256=manifest['configSha256'],
        screen=[WIDTH,HEIGHT],state='halftime',operatorReviewed=True,regions=regions,
        positiveSha256=[hashlib.sha256(f).hexdigest() for f in positive],
        negativeSha256=[hashlib.sha256(f).hexdigest() for f in negative])
    if manifest.get('scope')=='reviewed-normal-league':
        labels=manifest.get('trainingNegativeStates')
        if not isinstance(labels,list) or len(labels)!=len(negative) or any(s not in ('gameplay','main-menu','fulltime') for s in labels):
            raise ValueError('Explicit negative league labels required')
        validation=[]
        for state in ('halftime','gameplay','main-menu','fulltime'):
            key='validation_'+state
            names=manifest.get(key)
            if not isinstance(names,list) or not 1<=len(names)<=12:
                raise ValueError('Missing independent league samples: '+state)
            for name in names:
                path=Path(name)
                if path.is_symlink() or not path.is_file() or path.stat().st_size!=WIDTH*HEIGHT:
                    raise ValueError('Expected raw grayscale validation frame')
                validation.append((state,path.read_bytes()))
        training=[('halftime',f) for f in positive]+list(zip(labels,negative))
        output['leagueCalibration']=league_calibration(regions,training,validation)
        require_league_calibration(output)
    with args.output.open('x') as out:
        json.dump(output,out)

if __name__=='__main__':
    main()
