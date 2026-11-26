"""Diagnostic conversion of pinned League-Soccer raw animation tracks to glTF.

No mesh, no engine retargeting, no redistribution approval. Local checkout only.
"""
import argparse,base64,hashlib,json,math,struct,subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
NAMES=("player","body","middle","neck","left_shoulder","left_elbow","right_shoulder","right_elbow","left_thigh","left_knee","left_ankle","right_thigh","right_knee","right_ankle")
PILOT={"base":"base.anim.util","idle":"movement/idle/000_idlelevel1.anim","walk-turn":"movement/walk/045.anim","sprint":"movement/sprint/000_idlelevel1.anim","control":"ballcontrol/idle/000.anim","keeper-low-catch":"deflect/idle/000_ground_holdball.anim","celebration":"celebration/happy_normal/000.anim"}
STEP=.01
def require(ok,message):
    if not ok:raise ValueError(message)
def finite(values):
    v=tuple(float(x) for x in values)
    require(all(math.isfinite(x) for x in v),"Nonfinite component")
    return v
def unit(q):
    n=math.sqrt(sum(x*x for x in q))
    require(abs(n-1)<=.005,"Non-unit quaternion")
    return tuple(x/n for x in q)
def basis(v):
    # Native +Z up, -Y forward, +X anatomical left.
    # Project +Y up, +X forward, -Z anatomical left. Proper rotation, no reflection.
    x,y,z=v
    return (-y,z,-x)
def rotation(q):
    return (*basis(q[:3]),q[3])
def keys(tokens,components):
    step=components+1
    require(tokens and len(tokens)%step==0,"Malformed track")
    out=[]
    for i in range(0,len(tokens),step):
        frame=int(tokens[i])
        require(0<=frame<=10000 and (not out or frame>out[-1][0]),"Invalid key time")
        value=finite(tokens[i+1:i+step])
        if components==4:
            value=unit(value)
            if out and sum(x*y for x,y in zip(value,out[-1][1]))<0:value=tuple(-x for x in value)
        out.append((frame,value))
    require(out[0][0]==0,"Track has no first key")
    return out
def parse(text):
    require(len(text)<=1024*1024,"Animation too large")
    tracks={};contacts=[];metadata=[];tail=False;extensions=False
    for raw in text.splitlines():
        line=raw.strip()
        if not line:continue
        if line.startswith("<"):tail=True
        if tail:
            metadata.append(raw);continue
        name,*tokens=line.split(",")
        if name=="extension":
            extensions=True
            require(tokens and tokens[0]=="football","Unknown animation extension")
            contacts.extend(keys_contact(tokens[1:]));continue
        require(not extensions and name in NAMES and name not in tracks,"Unknown/duplicate/late track")
        tracks[name]=keys(tokens,3 if name=="player" else 4)
    require(tuple(tracks)==NAMES,"Unexpected native skeleton track order")
    end=max(row[-1][0] for row in tracks.values())
    require(end>0 and all(f<=end for f,_ in contacts),"Invalid animation length")
    # Metadata is retained as source text, not interpreted as runtime decisions.
    return {"tracks":tracks,"contacts":contacts,"metadata":"\n".join(metadata),"lastFrame":end}
def keys_contact(tokens):
    require(tokens and len(tokens)%4==0,"Malformed football contact")
    out=[]
    for i in range(0,len(tokens),4):
        f=int(tokens[i]);require(f>=0 and (not out or f>out[-1][0]),"Invalid contact frame")
        out.append((f,finite(tokens[i+1:i+4])))
    return out
def skeleton(xml):
    root=ET.fromstring(xml);require(root.tag=="object","Invalid native object")
    nodes={"player":{"name":"player","translation":[0,0,0],"children":[]}}
    def walk(el,parent):
        name=el.findtext("name")
        require(name in NAMES and name!="player" and name not in nodes,"Unexpected skeleton joint")
        xyz=finite(el.findtext("position").split(","));require(len(xyz)==3,"Invalid rest position")
        nodes[name]={"name":name,"translation":basis(xyz),"children":[]}
        nodes[parent]["children"].append(name)
        for child in el.findall("node"):walk(child,name)
    for el in root.findall("node"):walk(el,"player")
    require(set(nodes)==set(NAMES),"Incomplete native rig")
    idx={n:i for i,n in enumerate(NAMES)}
    return [{**nodes[n],"children":[idx[c] for c in nodes[n]["children"]]} for n in NAMES]
def gltf(nodes,clips):
    data=bytearray();views=[];accessors=[];animations=[]
    def add(values,kind):
        width={"SCALAR":1,"VEC3":3,"VEC4":4}[kind]
        flat=[x for row in values for x in row]
        require(len(flat)==len(values)*width,"Invalid accessor width")
        start=len(data);data.extend(struct.pack("<"+"f"*len(flat),*flat))
        views.append({"buffer":0,"byteOffset":start,"byteLength":len(data)-start})
        a={"bufferView":len(views)-1,"componentType":5126,"count":len(values),"type":kind}
        if kind=="SCALAR":a.update(min=[min(flat)],max=[max(flat)])
        accessors.append(a);return len(accessors)-1
    for name,clip in clips.items():
        samplers=[];channels=[]
        for i,node in enumerate(NAMES):
            track=clip["tracks"][node]
            time=add([(f*STEP,) for f,_ in track],"SCALAR")
            translation=node=="player"
            output=add([basis(v) if translation else rotation(v) for _,v in track],"VEC3" if translation else "VEC4")
            samplers.append({"input":time,"output":output,"interpolation":"LINEAR"})
            channels.append({"sampler":i,"target":{"node":i,"path":"translation" if translation else "rotation"}})
        animations.append({"name":name,"samplers":samplers,"channels":channels,
            "extras":{"nativeFrameStepSeconds":STEP,"lastFrame":clip["lastFrame"],
                      "footballContactKeys":[{"time":f*STEP,"position":basis(v)} for f,v in clip["contacts"]],
                      "nativeMetadata":clip["metadata"]}})
    return {"asset":{"version":"2.0","generator":"Tribun native animation diagnostic"},
            "scene":0,"scenes":[{"nodes":[0]}],"nodes":nodes,"animations":animations,
            "buffers":[{"byteLength":len(data),"uri":"data:application/octet-stream;base64,"+base64.b64encode(data).decode("ascii")}],
            "bufferViews":views,"accessors":accessors}
def git(source,*args):
    return subprocess.check_output(["git","-C",str(source),*args])
def sha(b):return hashlib.sha256(b).hexdigest()
def convert(source,out):
    pin=json.loads((HERE/"upstream.json").read_text())
    require(git(source,"rev-parse","HEAD").decode().strip()==pin["revision"],"Upstream pin mismatch")
    def read(path):
        # Read committed blobs, not modified files from a checkout.
        return git(source,"show",pin["revision"]+":"+path)
    obj=read("data/media/objects/players/player.object");nodes=skeleton(obj.decode())
    clips={};sources={}
    for name,path in PILOT.items():
        full="data/media/animations/"+path;b=read(full);clips[name]=parse(b.decode())
        c=clips[name];sources[name]={"path":full,"sha256":sha(b),"channels":len(c["tracks"]),
          "keys":sum(map(len,c["tracks"].values())),"lastKeySeconds":round(c["lastFrame"]*STEP,3),"contactKeys":len(c["contacts"])}
    out.mkdir(parents=True,exist_ok=False)
    model=out/"native-animation-skeleton.gltf"
    model.write_text(json.dumps(gltf(nodes,clips),separators=(",",":"),allow_nan=False))
    license_bytes=read("LICENSE")
    # Keep upstream license locally with derivative, but no converted asset in public CI artifact.
    (out/"UPSTREAM-LICENSE.txt").write_bytes(license_bytes)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"revision":pin["revision"],
      "sourceProjectLicense":pin["license"],"assetRedistributionApproved":False,"meshIncluded":False,
      "rawKeyConversion":True,"runtimeRetargetingVerified":False,"rigSha256":sha(obj),"licenseSha256":sha(license_bytes),
      "gltfSha256":sha(model.read_bytes()),"clips":sources,
      "note":"Raw local rotations; native idle-facing conversion, mirroring, blending, root motion and contact correction are not reproduced. Skeleton animation only, not a ready player mesh."}
    (out/"conversion-report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();print(json.dumps(convert(a.source,a.out),indent=2))
if __name__=="__main__":main()
