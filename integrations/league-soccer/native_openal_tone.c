/* Private CI-only OpenAL source, no game assets or gameplay modification. */
#include <AL/al.h>
#include <AL/alc.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#define RATE 48000
int main(int argc,char **argv){
 if(argc!=2)return 2;
 int hz=atoi(argv[1]); if(hz!=440&&hz!=880)return 2;
 ALCdevice *d=alcOpenDevice(NULL);if(!d)return 3;
 ALCcontext *ctx=alcCreateContext(d,NULL);if(!ctx||!alcMakeContextCurrent(ctx))return 4;
 int16_t *pcm=malloc(RATE*sizeof(*pcm));if(!pcm)return 5;
 for(int i=0;i<RATE;i++)pcm[i]=(int16_t)(12000*sin(6.283185307179586*hz*i/RATE));
 ALuint b,s;alGenBuffers(1,&b);alBufferData(b,AL_FORMAT_MONO16,pcm,RATE*sizeof(*pcm),RATE);
 alGenSources(1,&s);alSourcei(s,AL_BUFFER,b);alSourcei(s,AL_LOOPING,AL_TRUE);alSourcePlay(s);
 if(alGetError()!=AL_NO_ERROR)return 6;
 struct timespec delay={12,0};nanosleep(&delay,NULL);
 alSourceStop(s);alDeleteSources(1,&s);alDeleteBuffers(1,&b);
 free(pcm);alcMakeContextCurrent(NULL);alcDestroyContext(ctx);alcCloseDevice(d);
 return 0;
}
