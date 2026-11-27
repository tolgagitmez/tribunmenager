/* Private diagnostic marker on the actual SDL default framebuffer before swap.
 * Never use in production presentation. Does not alter simulation state. */
#define _GNU_SOURCE
#include <GL/gl.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

static FILE *log_file;
static uint32_t serial;
static pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
static uint64_t wall_us(void){
    struct timespec t;
    if(clock_gettime(CLOCK_REALTIME,&t))return 0;
    return (uint64_t)t.tv_sec*1000000ull+t.tv_nsec/1000;
}
static unsigned checksum(uint32_t id){
    unsigned c=0;
    for(unsigned i=0;i<6;i++)c^=(id>>(4*i))&15u;
    return c;
}
static uint32_t marker(void){
    GLint vp[4], fbo=0, scissor[4], draw;
    GLboolean mask[4], enabled, dither;
    GLfloat color[4];
    glGetIntegerv(GL_VIEWPORT,vp);
    glGetIntegerv(0x8CA6,&fbo); /* GL_DRAW_FRAMEBUFFER_BINDING */
    glGetIntegerv(GL_DRAW_BUFFER,&draw);
    if(fbo||draw!=GL_BACK||vp[0]||vp[1]||vp[2]<272||vp[3]<32||serial>=0xffffffu)return 0;
    glGetIntegerv(GL_SCISSOR_BOX,scissor);
    glGetBooleanv(GL_COLOR_WRITEMASK,mask);
    glGetFloatv(GL_COLOR_CLEAR_VALUE,color);
    enabled=glIsEnabled(GL_SCISSOR_TEST);
    dither=glIsEnabled(GL_DITHER);
    glEnable(GL_SCISSOR_TEST);
    glDisable(GL_DITHER);
    glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
    uint32_t id=++serial;
    uint32_t code=(0xau<<28)|(id<<4)|checksum(id);
    for(unsigned i=0;i<32;i++){
        float v=(code>>(31-i))&1u?1.0f:0.0f;
        glScissor(8+8*i,8,8,16);
        glClearColor(v,v,v,1);
        glClear(GL_COLOR_BUFFER_BIT);
    }
    glClearColor(color[0],color[1],color[2],color[3]);
    glColorMask(mask[0],mask[1],mask[2],mask[3]);
    glScissor(scissor[0],scissor[1],scissor[2],scissor[3]);
    if(!enabled)glDisable(GL_SCISSOR_TEST);
    if(dither)glEnable(GL_DITHER);
    return id;
}
static void record(uint32_t id,uint64_t before,uint64_t after){
    if(!id||!before||after<before)return;
    if(!log_file){
        const char *path=getenv("TRIBUN_FRAME_MARKERS_LOG");
        if(!path)return;
        log_file=fopen(path,"wx");
        if(!log_file)return;
    }
    fprintf(log_file,"%u,%llu,%llu\n",id,(unsigned long long)before,(unsigned long long)after);
    fflush(log_file);
}
static void (*swap2)(void*);
static void (*swap1)(void);
static pthread_once_t once2=PTHREAD_ONCE_INIT,once1=PTHREAD_ONCE_INIT;
static void init2(void){swap2=dlsym(RTLD_NEXT,"SDL_GL_SwapWindow");}
static void init1(void){swap1=dlsym(RTLD_NEXT,"SDL_GL_SwapBuffers");}
static __thread int inside;
void SDL_GL_SwapWindow(void *window){
    pthread_once(&once2,init2);
    if(!swap2)_exit(126);
    if(inside){swap2(window);return;}
    inside=1;pthread_mutex_lock(&mutex);
    uint32_t id=marker();uint64_t before=wall_us();
    swap2(window);record(id,before,wall_us());
    pthread_mutex_unlock(&mutex);inside=0;
}
void SDL_GL_SwapBuffers(void){
    pthread_once(&once1,init1);
    if(!swap1)_exit(126);
    if(inside){swap1();return;}
    inside=1;pthread_mutex_lock(&mutex);
    uint32_t id=marker();uint64_t before=wall_us();
    swap1();record(id,before,wall_us());
    pthread_mutex_unlock(&mutex);inside=0;
}
