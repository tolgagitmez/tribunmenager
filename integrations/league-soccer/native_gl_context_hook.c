/* Query GL strings from the game's current context, not a separate GLX client. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static pthread_mutex_t guard=PTHREAD_MUTEX_INITIALIZER;
static int recorded=0;
static void record_context(void){
    pthread_mutex_lock(&guard);
    if(!recorded){
        const unsigned char *(*get)(unsigned int)=dlsym(RTLD_DEFAULT,"glGetString");
        const unsigned char *vendor=get?get(0x1F00):NULL;
        const unsigned char *renderer=get?get(0x1F01):NULL;
        const unsigned char *version=get?get(0x1F02):NULL;
        const char *path=getenv("TRIBUN_NATIVE_GL_CONTEXT_LOG");
        if(vendor&&renderer&&version&&path){
            int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
            if(fd>=0){
                dprintf(fd,"vendor=%.512s\nrenderer=%.512s\nversion=%.512s\n",vendor,renderer,version);
                close(fd);
            }
            recorded=1;
        }
    }
    pthread_mutex_unlock(&guard);
}
static void (*real2)(void*);
static void (*real1)(void);
static pthread_once_t once2=PTHREAD_ONCE_INIT,once1=PTHREAD_ONCE_INIT;
static void init2(void){real2=dlsym(RTLD_NEXT,"SDL_GL_SwapWindow");}
static void init1(void){real1=dlsym(RTLD_NEXT,"SDL_GL_SwapBuffers");}
void SDL_GL_SwapWindow(void *window){
    pthread_once(&once2,init2);
    if(!real2)_exit(126);
    record_context();real2(window);
}
void SDL_GL_SwapBuffers(void){
    pthread_once(&once1,init1);
    if(!real1)_exit(126);
    record_context();real1();
}
