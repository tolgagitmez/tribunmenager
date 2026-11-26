"""Recompute arbitrary league command histories from the full native trace."""
from native_command_evidence import audit_commands

def verify(control,trace):
    requests=control['requests']
    submitted=control['submitted'];applied=control['applied']
    if not isinstance(submitted,list) or len(submitted)!=2 or any(type(x) is not int or not 0<=x<=120 for x in submitted):
        raise ValueError('Invalid submitted counters')
    if applied!=submitted or control['pending']!=[False,False] or not isinstance(requests,list) or len(requests)!=sum(submitted):
        raise ValueError('Unresolved command history')
    revisions=[[],[]];formations=[0,0]
    for req in requests:
        side= req['team']
        if type(side) is not int or side not in (0,1):raise ValueError('Invalid command side')
        revision=req['revision'];values=req['values']
        if type(revision) is not int or revision!=len(revisions[side])+1:
            raise ValueError('Nonconsecutive request revision')
        if set(values)!={'press','counter','support','width','tempo','formation'} or any(type(v) is not int for v in values.values()):
            raise ValueError('Invalid command values')
        if any(not 0<=values[k]<=100 for k in ('press','counter','support','width','tempo')) or values['formation'] not in (0,433,442,4231):
            raise ValueError('Unsupported command values')
        if type(req['earliestMatchMs']) is not int or not 0<=req['earliestMatchMs']<5400000:
            raise ValueError('Invalid request time')
        revisions[side].append(revision)
        formations[side]=values['formation'] or formations[side]
    if [len(x) for x in revisions]!=submitted or formations!=control['formations']:
        raise ValueError('Command summary mismatch')
    evidence=audit_commands(trace,requests)
    if evidence!=control['traceEvidence'] or evidence['allSubmittedObserved'] is not True or evidence['consistent'] is not True:
        raise ValueError('Command trace mismatch')
    return {'submitted':submitted,'applied':applied,'formations':formations,'verified':True}
