"""Collect review-only screen candidates from a genuine restored native league.

No inferred phase labels, automatic halftime input, or production save writes.
The first-half capture stops at a bounded deadline, not a guessed halftime.
"""
import hashlib
import json
from pathlib import Path
import time

from original_halftime_gate import WIDTH,HEIGHT,frame

MAX_FRAMES=80

class ReferenceCapture:
    def __init__(self,output):
        self.output=Path(output)
        self.output.mkdir(mode=0o700)
        self.entries=[]
        self.hashes=set()
        self.started=time.monotonic()
    def add(self,raw,context,elapsed):
        if context not in ('restored-menu-candidate','post-kickoff-unlabeled'):
            raise ValueError('Unknown capture context')
        if len(raw)!=WIDTH*HEIGHT or not 0<=elapsed<=3600:
            raise ValueError('Invalid capture sample')
        if self.entries and elapsed<self.entries[-1]['elapsedSeconds']:
            raise ValueError('Capture clock regressed')
        sha=hashlib.sha256(raw).hexdigest()
        if sha in self.hashes or len(self.entries)>=MAX_FRAMES:
            return False
        name=f'{len(self.entries):03d}.gray'
        with (self.output/name).open('xb') as out:
            out.write(raw)
        # PGM preview uses the same exact bytes as the training candidate.
        with (self.output/(name+'.pgm')).open('xb') as out:
            out.write(f'P5\n{WIDTH} {HEIGHT}\n255\n'.encode()+raw)
        self.entries.append(dict(file=name,preview=name+'.pgm',rawSha256=sha,
            context=context,elapsedSeconds=elapsed,reviewedState=None))
        self.hashes.add(sha)
        return True
    def sample(self,env,context):
        return self.add(frame(env),context,round(time.monotonic()-self.started,3))
    def finish(self,revision,config_sha,fixture):
        if not self.entries:
            raise ValueError('No native candidate frames collected')
        result=dict(revision=revision,configSha256=config_sha,screen=[WIDTH,HEIGHT],
            source='restored-normal-league-default-config',nativeFixture=fixture,
            samples=self.entries,operatorReviewed=False,normalLeagueCalibrationVerified=False,
            actualHalftimeRecognized=False,fulltimeCapturedVerified=False,
            productionImportAllowed=False)
        with (self.output/'manifest.json').open('x') as f:
            json.dump(result,f,indent=2)
        return result
