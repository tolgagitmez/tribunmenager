"""Linux CPU affinity and cgroup v2 telemetry for diagnostic matches."""
import os
from pathlib import Path

def partition(cpus,count):
    cpus=sorted(set(cpus))
    if type(count) is not int or count<1 or len(cpus)<2*count:
        raise ValueError('Need at least two logical CPUs per match')
    return [cpus[i::count] for i in range(count)]

def affinity_command(command,cpus):
    return ['taskset','-c',','.join(map(str,cpus)),*command] if cpus else command

def cgroup_path():
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        if line.startswith('0::'):
            root=Path('/sys/fs/cgroup')
            path=root/line[3:].lstrip('/')
            if (path/'cpu.stat').is_file():return path
            if (root/'cpu.stat').is_file():return root
    return None

def counters(path):
    if path is None:return {}
    data={}
    try:
        for line in (path/'cpu.stat').read_text().splitlines():
            k,v=line.split()
            if k in ('usage_usec','nr_periods','nr_throttled','throttled_usec'):data[k]=int(v)
        quota,period=(path/'cpu.max').read_text().split()
        data['quotaCpus']=None if quota=='max' else int(quota)/int(period)
        data['memoryCurrentBytes']=int((path/'memory.current').read_text())
        limit=(path/'memory.max').read_text().strip()
        data['memoryLimitBytes']=None if limit=='max' else int(limit)
    except (OSError,ValueError,ZeroDivisionError):pass
    return data

def delta(previous,current):
    return {k:current[k]-previous[k] for k in ('usage_usec','nr_periods','nr_throttled','throttled_usec')
            if k in previous and k in current and current[k]>=previous[k]}
