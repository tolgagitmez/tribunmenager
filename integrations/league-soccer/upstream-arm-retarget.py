"""Local raw animation skeleton -> bounded wrist targets, not native engine pose.

Uses actual local rotations and hierarchy. No root displacement, no asset upload.
"""
import argparse,base64,hashlib,json,math,struct
from pathlib import Path
def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def mul(a,n):return tuple(x*n for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unit(a):
    n=math.sqrt(dot(a,a))
    if not math.isfinite(n) or n<1e-8:raise ValueError("Degenerate vector")
    return mul(a,1/n)
def qmul(a,b):
    v=add(add(mul(a[:3],b[3]),mul(b[:3],a[3])),cross(a[:3],b[:3]))
    return (*v,a[3]*b[3]-dot(a[:3],b[:3]))
def rotate(q,v):return qmul(qmul(q,(*v,0)),(*mul(q[:3],-1),q[3]))[:3]
def slerp(a,b,t):
    d=dot(a,b)
    if d<0:b=mul(b,-1);d=-d
    if d>.9995:return unit(add(mul(a,1-t),mul(b,t)))
    angle=math.acos(max(-1,min(1,d)))
    return unit(add(mul(a,math.sin((1-t)*angle)/math.sin(angle)),mul(b,math.sin(t*angle)/math.sin(angle))))
def sample(track,t):
    times,values=track
    if t<=times[0]:return values[0]
    if t>=times[-1]:return values[-1]
    for i in range(1,len(times)):
        if t<=times[i]:return slerp(values[i-1],values[i],(t-times[i-1])/(times[i]-times[i-1]))
    raise AssertionError()
def load(g):
    b=base64.b64decode(g["buffers"][0]["uri"].split(",",1)[1],validate=True)
    if len(b)!=g["buffers"][0]["byteLength"]:raise ValueError("Invalid glTF buffer")
    def accessor(i):
        a=g["accessors"][i];v=g["bufferViews"][a["bufferView"]]
        width={"SCALAR":1,"VEC4":4,"VEC3":3}[a["type"]]
        if a["componentType"]!=5126 or v["byteLength"]!=a["count"]*width*4:raise ValueError("Invalid accessor")
        vals=struct.unpack_from("<"+"f"*(a["count"]*width),b,v["byteOffset"])
        if not all(math.isfinite(x) for x in vals):raise ValueError("Nonfinite accessor")
        return [tuple(vals[j:j+width]) for j in range(0,len(vals),width)]
    nodes=g["nodes"];names={n["name"]:i for i,n in enumerate(nodes)}
    if len(nodes)!=14 or len(names)!=14:raise ValueError("Unexpected skeleton")
    parents={c:i for i,n in enumerate(nodes) for c in n["children"]}
    def clip(name):
        a=next(a for a in g["animations"] if a["name"]==name);tracks={}
        for ch in a["channels"]:
            if ch["target"]["path"]!="rotation":continue
            s=a["samplers"][ch["sampler"]]
            times=[x[0] for x in accessor(s["input"])]
            values=[unit(x) for x in accessor(s["output"])]
            if len(times)!=len(values) or any(x>=y for x,y in zip(times,times[1:])):raise ValueError("Bad key times")
            tracks[ch["target"]["node"]]=(times,values)
        if len(tracks)!=13:raise ValueError("Missing rotation tracks")
        return tracks,max(t[0][-1] for t in tracks.values())
    def arm_vectors(tracks,t):
        cache={}
        def world(i):
            if i in cache:return cache[i]
            if i==names["player"]:result=((0,0,0),(0,0,0,1))
            else:
                p,q=world(parents[i]);result=(add(p,rotate(q,nodes[i]["translation"])),qmul(q,sample(tracks[i],t)))
            cache[i]=result;return result
        chest,_=world(names["middle"]);neck,_=world(names["neck"])
        shoulders=[world(names[s+"_shoulder"])[0] for s in ("left","right")]
        up=unit(sub(neck,chest));right=unit(sub(shoulders[1],shoulders[0]))
        forward=unit(cross(up,right));right=unit(cross(forward,up))
        row=[]
        for side,shoulder in zip(("left","right"),shoulders):
            elbow,q=world(names[side+"_elbow"])
            # Source upper arm axis inferred from actual shoulder/elbow offsets.
            # Lower arm points along local down; use target anatomical lengths.
            upper=unit(sub(elbow,shoulder));lower=unit(rotate(q,(0,-1,0)))
            wrist=add(mul(upper,.315),mul(lower,.29))
            row.append([dot(wrist,forward),dot(wrist,up),dot(wrist,right)])
        return row
    return clip,arm_vectors
def convert(path,out):
    g=json.loads(path.read_text());clip,vectors=load(g)
    bank={"schema":1,"source":"upstream-raw-retarget","clips":{}}
    report={"schema":1,"authoritative":False,"productionEnabled":False,"assetRedistributionApproved":False,
      "inputSha256":hashlib.sha256(path.read_bytes()).hexdigest(),"clips":{}}
    for target,name in (("idle","idle"),("run","sprint")):
        tracks,duration=clip(name);count=max(2,math.ceil(duration*60))
        samples=[vectors(tracks,duration*i/count) for i in range(count+1)]
        maximum=max(math.sqrt(dot(a,a)) for row in samples for a in row)
        if not 0<maximum<=.6050001:raise ValueError("Invalid target reach")
        bank["clips"][target]={"duration":duration,"samples":samples}
        report["clips"][target]={"source":name,"sampleCount":len(samples),"maxReachMetres":maximum}
    dest=out/"native-arm-bank.json";dest.write_text(json.dumps(bank,separators=(",",":"),allow_nan=False))
    report["bankSha256"]=hashlib.sha256(dest.read_bytes()).hexdigest()
    report["note"]="Approximate wrist retarget, no mesh or engine pose parity; lower arm axis assumed local -Y. No contact, locomotion root or leg modifications."
    (out/"arm-retarget-report.json").write_text(json.dumps(report,indent=2))
    return report
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();print(json.dumps(convert(a.source,a.out),indent=2))
