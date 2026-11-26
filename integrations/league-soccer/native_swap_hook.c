/* Diagnostic SDL OpenGL swap completion timestamps, not GPU presentation FPS. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static int fds[2]={-2,-2};
static void record(int which){
    struct timespec ts;
    if(clock_gettime(CLOCK_MONOTONIC,&ts))return;
    uint64_t ns=(uint64_t)ts.tv_sec*1000000000ull+(uint64_t)ts.tv_nsec;
    pthread_mutex_lock(&lock);
    if(fds[which]==-2){
        const char *base=getenv("TRIBUN_SWAP_LOG");
        char path[4096];
        int n=base?snprintf(path,sizeof(path),"%s.%s",base,which?"sdl1":"sdl2"):-1;
        fds[which]=(n>0 && n<(int)sizeof(path))?open(path,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600):-1;
    }
    if(fds[which]>=0 && write(fds[which],&ns,sizeof(ns))!=sizeof(ns)){
        close(fds[which]);fds[which]=-1;
    }
    pthread_mutex_unlock(&lock);
}
static void (*real2)(void*);
static void (*real1)(void);
static pthread_once_t once2=PTHREAD_ONCE_INIT,once1=PTHREAD_ONCE_INIT;
static void init2(void){real2=dlsym(RTLD_NEXT,"SDL_GL_SwapWindow");}
static void init1(void){real1=dlsym(RTLD_NEXT,"SDL_GL_SwapBuffers");}
void SDL_GL_SwapWindow(void *window){
    pthread_once(&once2,init2);
    if(!real2)_exit(126);
    real2(window);record(0);
}
void SDL_GL_SwapBuffers(void){
    pthread_once(&once1,init1);
    if(!real1)_exit(126);
    real1();record(1);
}
