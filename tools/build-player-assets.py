#!/usr/bin/env python3
"""Build the footballer from pinned MakeHuman CC0 data, without its AGPL code.

Requires Python 3.11+, pinned requirements-player-assets.txt and Node
(only to read our rig reference).
No network access is performed. Source and texture bytes are deterministic;
last-bit floating-point geometry results may differ across NumPy/BLAS/CPU
builds. Verify the licensed source hashes and strict geometry equivalence
with tools/verify-player-asset-rebuild.py, rather than assuming identical
byte streams across different machines.
"""
from __future__ import annotations
import argparse
import base64
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ID = 'tribun-makehuman-footballer-v1'
COMMIT = 'a8bc2d54ff0ac92e78ff71431b1023eda42bf482'
RIG_SHA256 = 'c66a9fcdb884fdf3cda3f7e92fc4c9ebe1dbbec32fa1bfdb0a8c020099125480'
PINNED = {
    'makehuman-base.obj': '8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c',
    'makehuman-default.mhskel': '99f179bce0aa850b45d4191a1d0d234c5851f881c057439470ded3bddf729a24',
    'makehuman-default_weights.mhw': '0f3641d651ae3d00ad6b4ccee43142edb109d3bd909d27d9e4139ef1beed8625',
    'makehuman-LICENSE.md': 'edd99571ca62698f78c943fd4fffb159a413c315fa0d4819d3cec5cadaf8b4f1',
    'makehuman-LICENSE.ASSETS.md': 'f6089cba01cb570a24712b41ab8a586ccd3cc5ef53dc266ca50b95c288956d2c',
}
SOURCE_PATHS = {
    'makehuman-base.obj': 'makehuman/data/3dobjs/base.obj',
    'makehuman-default.mhskel': 'makehuman/data/rigs/default.mhskel',
    'makehuman-default_weights.mhw': 'makehuman/data/rigs/default_weights.mhw',
    'makehuman-LICENSE.md': 'LICENSE.md',
    'makehuman-LICENSE.ASSETS.md': 'LICENSE.ASSETS.md',
}
NAMES = ['pelvis', 'spine', 'chest', 'neck', 'head', 'clavicle.L', 'upper_arm.L',
         'forearm.L', 'hand.L', 'thigh.L', 'shin.L', 'foot.L', 'clavicle.R',
         'upper_arm.R', 'forearm.R', 'hand.R', 'thigh.R', 'shin.R', 'foot.R']
PARENTS = [-1, 0, 1, 2, 3, 2, 5, 6, 7, 0, 9, 10, 2, 12, 13, 14, 0, 16, 17]
MATERIALS = ['skin', 'shirt', 'shorts', 'socks', 'boots', 'hair', 'eye-white', 'iris', 'pupil', 'brows']
COLORS = [[.69,.48,.34], [.075,.29,.68], [.88,.90,.93], [.10,.29,.65], [.055,.065,.08],
          [.065,.042,.027], [.88,.90,.88], [.15,.25,.18], [.005,.007,.009], [.055,.04,.025]]
LICENSED_FILES = ('CREDITS.md', 'LICENSE-CC0.txt', 'SOURCE-LICENSE.md', 'footballer.glb',
                 'manifest.json', 'player-model-data.js', 'skeleton.json',
                 'source/makehuman-base.obj.gz', 'source/makehuman-default.mhskel.gz',
                 'source/makehuman-default_weights.mhw.gz', 'source/provenance.json',
                 'textures/fabric-detail.png', 'textures/skin-detail.png')
WEIGHT_PAINT = {'method':'local Jacobi smoothing of the collapsed source skin',
                'iterations':6,'selfWeight':.5,'neighborWeight':.5,
                'radii':{'shoulder':.18,'elbow':.12,'knee':.15},
                'minimumAdjacentBoneWeight':.35,'maximumInfluences':4,
                'adjacency':'original body quad edges, shared source vertices before UV and material splits',
                'stage':'runtime weights only, after bind geometry is fixed',
                'protected':'all source hand influences and vertices within 0.13 m of either wrist',
                'originalWeights':'retained verbatim in the official pinned source archive; runtime weights are an authored derivative'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_source(source, provenance):
    if (provenance.get('repository') != 'https://github.com/makehumancommunity/makehuman'
            or provenance.get('commit') != COMMIT
            or provenance.get('assetLicense') != 'CC0-1.0'):
        raise ValueError('Source provenance does not identify the pinned official CC0 assets')
    records = provenance.get('files', [])
    by_path = {record.get('repositoryPath'): record for record in records}
    if len(records) != len(SOURCE_PATHS) or set(by_path) != set(SOURCE_PATHS.values()):
        raise ValueError('Source provenance must contain each of the five pinned files once')
    for name, digest in PINNED.items():
        data = (source / name).read_bytes()
        if sha(data) != digest:
            raise ValueError(name + ': source hash differs from the pinned official file')
        record = by_path[SOURCE_PATHS[name]]
        url = 'https://raw.githubusercontent.com/makehumancommunity/makehuman/' + COMMIT + '/' + SOURCE_PATHS[name]
        if (record.get('sourceURL') != url or record.get('sha256') != digest
                or record.get('bytes') != len(data)):
            raise ValueError(name + ': provenance URL, size or digest does not match the pinned file')


def unit(v):
    n = np.linalg.norm(v)
    return v / max(n, 1e-12)


def smoothstep(value):
    value = np.clip(value, 0., 1.)
    return value * value * (3. - 2. * value)


def split_polygon(polygon, normal, distance):
    """Split an attribute polygon at an actual plane, preserving skin/UV data."""
    signed = [np.dot(vertex[:3], normal) - distance for vertex in polygon]
    if min(signed) >= -1e-10 or max(signed) <= 1e-10:
        return [polygon]
    halves = [[], []]
    for index, current in enumerate(polygon):
        following = polygon[(index + 1) % len(polygon)]
        a, b = signed[index], signed[(index + 1) % len(polygon)]
        for side, sign in enumerate((1, -1)):
            if sign * a >= -1e-10:
                halves[side].append(current)
        if a * b < -1e-20:
            crossing = current + (following - current) * (a / (a - b))
            for half in halves:
                half.append(crossing)
    return [half for half in halves if len(half) >= 3]


def frame(head, tail):
    y = unit(tail-head)
    ref = np.array([1.,0.,0.]) if abs(y[0]) < .95 else np.array([0.,0.,1.])
    x = unit(ref-y*np.dot(ref,y)); z = np.cross(x,y)
    m = np.eye(4);m[:3,:3] = np.column_stack([x,y,z]);m[:3,3] = head
    return m


def obj(path):
    vertices, uv, groups = [], [], defaultdict(list)
    group = 'default'
    for line in path.read_text().splitlines():
        fields = line.split()
        if not fields: continue
        if fields[0] == 'v': vertices.append([float(x) for x in fields[1:4]])
        elif fields[0] == 'vt': uv.append([float(x) for x in fields[1:3]])
        elif fields[0] == 'g': group = fields[1]
        elif fields[0] == 'f':
            groups[group].append([(int(token.split('/')[0])-1, int(token.split('/')[1])-1 if '/' in token and token.split('/')[1] else 0) for token in fields[1:]])
    return np.asarray(vertices), np.asarray(uv), groups


def reference_frames():
    if sha((ROOT / 'humanoid-rig.js').read_bytes()) != RIG_SHA256:
        raise ValueError('humanoid-rig.js differs from the reviewed rig reference; review the bind pose before rebuilding')
    code = "const R=require('./humanoid-rig');const p={x:0,z:0,face:0,speed:0,action:'idle',actionClock:0};process.stdout.write(JSON.stringify(R.boneFrames(R.update(p,0))))"
    frames = json.loads(subprocess.check_output(['node','-e',code], cwd=ROOT))
    if set(frames) != set(NAMES):
        raise ValueError('Canonical rig must expose exactly the reviewed nineteen bones')
    return {name: tuple(np.asarray(p, dtype=float) for p in frames[name]) for name in NAMES}


def quaternion(matrix):
    """A proper rigid rotation as an xyzw quaternion; no scale is accepted."""
    r = matrix[:3, :3]
    if not np.allclose(r.T @ r, np.eye(3), atol=1e-9) or np.linalg.det(r) < .999999:
        raise ValueError('Bind retarget rotations must be rigid')
    trace = np.trace(r)
    if trace > 0:
        s = np.sqrt(trace + 1.) * 2
        return np.array([(r[2,1]-r[1,2])/s, (r[0,2]-r[2,0])/s,
                         (r[1,0]-r[0,1])/s, s/4])
    i = int(np.argmax(np.diag(r))); j = (i+1)%3; k = (i+2)%3
    s = np.sqrt(1+r[i,i]-r[j,j]-r[k,k])*2
    q = np.zeros(4); q[i] = s/4; q[j] = (r[j,i]+r[i,j])/s
    q[k] = (r[k,i]+r[i,k])/s; q[3] = (r[k,j]-r[j,k])/s
    return q


def qmul(a, b):
    return np.r_[a[3]*b[:3]+b[3]*a[:3]+np.cross(a[:3],b[:3]),
                 a[3]*b[3]-np.dot(a[:3],b[:3])]


def dual_quaternion_skin(points, weights, transforms):
    """Blend rigid frame rotations without losing joint cross section."""
    real = np.asarray([quaternion(t) for t in transforms])
    dual = np.asarray([.5*qmul(np.r_[t[:3,3],0.],q) for t,q in zip(transforms,real)])
    hemisphere = real[weights.argmax(1)]
    signs = np.where(hemisphere @ real.T < 0., -1., 1.)
    weighted = weights * signs
    qr = weighted @ real; qd = weighted @ dual
    norm = np.linalg.norm(qr,axis=1)[:,None]
    # Helper groups outside the visible human have no source skin; they are
    # not emitted, but keeping them finite makes the offline path auditable.
    empty = norm[:,0] < 1e-12
    qr[empty] = [0.,0.,0.,1.]; norm[empty] = 1.
    qr /= norm; qd /= norm
    qd -= qr * np.sum(qr*qd,axis=1)[:,None]
    v = qr[:,:3]; w = qr[:,3:4]
    rotated = points + 2*np.cross(v,np.cross(v,points)+w*points)
    translation = 2*(w*qd[:,:3]-qd[:,3:4]*v+np.cross(v,qd[:,:3]))
    return rotated + translation


def collapse_weights(raw, skeleton, count):
    names = set(NAMES)
    def mapped(name):
        side=name[-2:] if name.endswith(('.L','.R')) else ''
        if name.startswith('upperarm'): return 'upper_arm'+side
        if name.startswith('lowerarm'): return 'forearm'+side
        if name.startswith('upperleg'): return 'thigh'+side
        if name.startswith('lowerleg'): return 'shin'+side
        if name.startswith(('wrist','finger','metacarpal')): return 'hand'+side
        if name.startswith(('toe','foot')): return 'foot'+side
        if name.startswith(('shoulder','clavicle')): return 'clavicle'+side
        if name in ('root','pelvis.L','pelvis.R'): return 'pelvis'
        if name in ('spine04','spine05'): return 'spine'
        if name in ('spine01','spine02','spine03','breast.L','breast.R'): return 'chest'
        if name.startswith('neck'): return 'neck'
        if name=='head': return 'head'
        parent=skeleton['bones'].get(name,{}).get('parent')
        return mapped(parent) if parent else 'head'
    matrix=np.zeros((count,19),dtype=float)
    for name, rows in raw['weights'].items():
        target=mapped(name); assert target in names,(name,target)
        for vertex, weight in rows:
            matrix[vertex,NAMES.index(target)] += weight
    return matrix


def smooth_joint_weights(points, weights, groups, frames):
    """Paint only six joint patches, after the canonical body shape is fixed.

    Source quad edges connect the shared anatomical surface before material
    and UV duplicates exist. Simultaneous Jacobi steps avoid order-dependent
    painting; protected hands/wrists and every vertex outside the patches
    retain their exact source-derived influence vectors.
    """
    neighbors=defaultdict(set)
    for face in groups['body']:
        ids=[corner[0] for corner in face]
        for a,b in zip(ids,ids[1:]+ids[:1]):
            neighbors[a].add(b);neighbors[b].add(a)
    body_ids=np.array(sorted(neighbors),dtype=int)
    protected=(weights[:,8]+weights[:,15])>1e-8
    for side in ('L','R'):
        protected |= np.linalg.norm(points-frames['hand.'+side][0],axis=1)<.13
    mask=np.zeros(len(points),dtype=bool);patches={}
    for side in ('L','R'):
        for kind,parent,child in [('shoulder','clavicle','upper_arm'),('elbow','upper_arm','forearm'),('knee','thigh','shin')]:
            a=NAMES.index(parent+'.'+side);b=NAMES.index(child+'.'+side)
            valid=(np.linalg.norm(points-frames[child+'.'+side][0],axis=1)<WEIGHT_PAINT['radii'][kind])
            valid &= weights[:,a]+weights[:,b]>WEIGHT_PAINT['minimumAdjacentBoneWeight']
            valid &= ~protected
            patch_ids=body_ids[valid[body_ids]]
            mask[patch_ids]=True;patches[kind+'.'+side]=int(len(patch_ids))
    selected=np.flatnonzero(mask)
    result=weights.copy()
    for _ in range(WEIGHT_PAINT['iterations']):
        previous=result;result=previous.copy()
        for vertex in selected:
            row=.5*previous[vertex]+.5*previous[sorted(neighbors[vertex])].mean(axis=0)
            order=np.argsort(-row,kind='stable')[:4]
            result[vertex]=0.;result[vertex,order]=row[order]/row[order].sum()
    changed=np.linalg.norm(result-weights,ord=1,axis=1)>1e-12
    edges=sorted({(min(a,b),max(a,b)) for a in selected for b in neighbors[a]})
    def edge_jump(data):
        return float(np.mean([np.abs(data[a]-data[b]).sum() for a,b in edges])) if edges else 0.
    stats={'parameters':WEIGHT_PAINT,'selectedSourceVertices':int(len(selected)),
           'changedSourceVertices':int(changed.sum()),'jointPatchVertices':patches,
           'protectedHandAndWristVertices':int(protected[body_ids].sum()),
           'maximumWeightSumError':float(np.abs(result[body_ids].sum(axis=1)-1.).max()),
           'meanPatchEdgeWeightL1Before':edge_jump(weights),
           'meanPatchEdgeWeightL1After':edge_jump(result)}
    return result,stats


def skin_geometry(source, uv, groups, skeleton, weights):
    body_ids=sorted({i for face in groups['body'] for i,_ in face})
    body=source[body_ids];ground=float(body[:,1].min());scale=1.88/float(body[:,1].max()-ground)
    def convert(p): return np.array([p[2]*scale,(p[1]-ground)*scale,-p[0]*scale])
    points=np.array([convert(v) for v in source])
    def joint(name):
        ids={i for face in groups['joint-'+name] for i,_ in face}
        return convert(source[list(ids)].mean(0))
    def skeleton_joint(name):
        return convert(source[skeleton['joints'][name]].mean(0))
    ref=reference_frames(); src={}
    pelvis=joint('pelvis');waist=pelvis+np.array([0,.08,0])
    # The source spine-1 helper is below the sternum; its shoulder level is
    # the anatomical counterpart of our chest endpoint, not that helper.
    chest=np.array([joint('l-shoulder')[0],joint('l-shoulder')[1],0.])
    mid=waist+(chest-waist)*.48;neck=joint('neck');head=neck+np.array([0,1.88-neck[1],0])
    src.update(pelvis=(pelvis,waist),spine=(waist,mid),chest=(mid,chest),neck=(chest,neck),head=(neck,head))
    for side, prefix in [('L','l'),('R','r')]:
        sh=joint(prefix+'-shoulder');el=joint(prefix+'-elbow');hand=joint(prefix+'-hand')
        # The hand-2 helper is only 4.5 cm from the wrist. It is not the
        # fingertip: scaling the whole collapsed finger skin by that short
        # segment enlarged the hand almost threefold.
        end=skeleton_joint(skeleton['bones']['finger3-3.'+side]['tail'])
        src.update({f'clavicle.{side}':(joint(prefix+'-clavicle'),sh),f'upper_arm.{side}':(sh,el),
          f'forearm.{side}':(el,hand),f'hand.{side}':(hand,end),
          f'thigh.{side}':(joint(prefix+'-upper-leg'),joint(prefix+'-knee')),
          f'shin.{side}':(joint(prefix+'-knee'),joint(prefix+'-ankle')),
          f'foot.{side}':(joint(prefix+'-ankle'),joint(prefix+'-foot-2'))})
    bone_weights=collapse_weights(weights,skeleton,len(source))
    for i in body_ids:
        total=bone_weights[i].sum()
        if total<1e-12: raise ValueError('No source skin weights for visible vertex '+str(i))
        bone_weights[i]/=total
    # First change proportions in the original source pose. Every limb
    # correction has positive axial scale and NO rotation. Rotation blending
    # is a separate rigid DQ pass, so the source elbow and shoulder cannot be
    # pinched by a weighted average of opposing rotation matrices.
    source_y=np.array([pelvis[1],waist[1],mid[1],chest[1],neck[1],head[1]])
    target_y=np.array([ref['pelvis'][0][1],ref['pelvis'][1][1],ref['spine'][1][1],
                       ref['chest'][1][1],ref['neck'][1][1],ref['head'][1][1]])
    source_x=np.array([pelvis[0],waist[0],mid[0],chest[0],neck[0],head[0]])
    torso_width=np.array([.26/(2*abs(src['thigh.L'][0][2])),1.06,1.12,
                          .44/(2*abs(src['upper_arm.L'][0][2])),1.,.86])
    def torso_morph(p):
        p=np.array(p,copy=True);y=p[...,1].copy()
        p[...,0]-=np.interp(y,source_y,source_x)
        p[...,0]*=1.-.08*smoothstep((y-neck[1])/.10)
        p[...,2]*=np.interp(y,source_y,torso_width)
        p[...,1]=np.interp(y,source_y,target_y)
        below=y<source_y[0]
        p[...,1]=np.where(below,target_y[0]+y-source_y[0],p[...,1])
        return p
    neutral={name:tuple(torso_morph(p) for p in src[name]) for name in NAMES[:5]}
    for side in ('L','R'):
        shoulder=ref['upper_arm.'+side][0]
        for name,anchor in [('upper_arm.'+side,shoulder),('forearm.'+side,None),('hand.'+side,None),
                            ('thigh.'+side,ref['thigh.'+side][0]),('shin.'+side,None),('foot.'+side,None)]:
            if anchor is None:
                previous={'forearm':'upper_arm','hand':'forearm','shin':'thigh','foot':'shin'}[name.split('.')[0]]+'.'+side
                anchor=neutral[previous][1]
            a,b=src[name];c,d=ref[name]
            neutral[name]=(anchor,anchor+unit(b-a)*np.linalg.norm(d-c))
        name='clavicle.'+side;a,b=src[name];c,d=ref[name]
        neutral[name]=(shoulder-unit(b-a)*np.linalg.norm(d-c),shoulder)
    proportioned=np.zeros_like(points);torso_points=torso_morph(points)
    transforms=[];bones=[];axial_scales=[]
    for i,name in enumerate(NAMES):
        a,b=src[name];c,d=neutral[name];target_a,target_b=ref[name]
        if i<5:
            corrected=torso_points
        else:
            axis=unit(b-a);segment_scale=np.linalg.norm(d-c)/np.linalg.norm(b-a)
            corrected=points+(segment_scale-1)*np.outer((points-a)@axis,axis)+(c-a)
            axial_scales.append(float(segment_scale))
        proportioned+=corrected*bone_weights[:,i:i+1]
        rigid=frame(target_a,target_b)@np.linalg.inv(frame(c,d))
        transforms.append(rigid)
        tf=frame(target_a,target_b)
        bones.append({'name':name,'parent':PARENTS[i],'head':target_a.tolist(),'tail':target_b.tolist(),'matrix':tf.T.reshape(-1).tolist(),'inverseBind':np.linalg.inv(tf).T.reshape(-1).tolist()})
    posed=dual_quaternion_skin(proportioned,bone_weights,transforms)
    # The unmodified MakeHuman base is deliberately androgynous. Give the
    # football kit a continuous, neutral athletic chest instead of preserving
    # its breast projections or clipping a few already-packed shirt vertices.
    # Change only the front torso; keep source topology, UVs and skin weights.
    for idx in body_ids:
        p = posed[idx]
        if bone_weights[idx,:4].sum() > .6 and p[0] > 0:
            blend = smoothstep((p[1]-1.00)/.10) * smoothstep((1.53-p[1])/.10)
            side = smoothstep((.19-abs(p[2]))/.04)
            depth = .092 + .013 * np.exp(-((p[1]-1.36)/.14)**2)
            front = .012 + depth * np.sqrt(max(0., 1.-(p[2]/.20)**2))
            p[0] -= max(0., p[0]-front) * blend * side
    runtime_weights,weight_stats=smooth_joint_weights(posed,bone_weights,groups,ref)
    triangles=[]
    for face in groups['body']:
        for n in range(1,len(face)-1): triangles.append([face[0],face[n],face[n+1]])
    normals=np.zeros_like(posed)
    for tri in triangles:
        ids=[a for a,b in tri];a,b,c=posed[ids];n=np.cross(b-a,c-a)
        for idx in ids:normals[idx]+=n
    normals/=np.maximum(1e-12,np.linalg.norm(normals,axis=1))[:,None]
    vertices=[];indices=[];lookup={};material_counts=defaultdict(int)
    sleeve_planes = {}
    for side in ('L', 'R'):
        h,t=ref['upper_arm.'+side]
        direction=unit(t-h)
        sleeve_planes[side]=(direction, np.dot(h + (t-h)*.58, direction))
    # A crew neck follows the central neck rather than cutting a horizontal
    # skin band across both shoulders. Tangents make a deterministic convex
    # collar with shared, interpolated skin/cloth boundary vertices.
    collar_curve=.055/.08**2
    collar_planes=[(np.array([0.,1.,-2*collar_curve*z]),1.565-collar_curve*z*z)
                   for z in np.linspace(-.12,.12,9)]
    def collar_height(z):
        return max(distance-plane[2]*z for plane,distance in collar_planes)
    def material(polygon):
        pos=np.mean([v[:3] for v in polygon],axis=0);w=np.mean([v[8:27] for v in polygon],axis=0);dominant=int(w.argmax());y=pos[1]
        if dominant in (11,18) and y<.24:return None
        if y>=collar_height(pos[2])-1e-10:
            if y>1.76 and (pos[0]<.11 or y>1.83):return 5
            return 0
        if dominant in (5,6,7,8,12,13,14,15):
            plane, distance = sleeve_planes['L' if dominant<9 else 'R']
            return 1 if np.dot(pos,plane)<distance else 0
        if y>1.035:return 1
        if y>.625:return 2
        if y<.43:return 3
        return 0
    def pack_vertex(vertex, mat):
        # Rounded attribute keys join vertices created on a shared edge. UV
        # seams and distinct material IDs intentionally remain separate.
        key=(*np.round(vertex,10),mat)
        if key in lookup:return lookup[key]
        p=vertex[:3].copy();n=unit(vertex[3:6]);source_weights=vertex[8:27];weights=vertex[27:]
        offset={1:.009,2:.009,3:.003}.get(mat,0)
        if mat==1:
            offset*=smoothstep((collar_height(p[2])-p[1])/.018)
            dominant=int(source_weights.argmax())
            if dominant in (5,6,7,8,12,13,14,15):
                plane,distance=sleeve_planes['L' if dominant<9 else 'R']
                offset*=smoothstep((distance-np.dot(p,plane))/.025)
        elif mat==2:offset*=smoothstep((p[1]-.625)/.025)
        elif mat==3:offset*=smoothstep((.43-p[1])/.025)
        p+=n*offset
        order=np.argsort(-weights)[:4];ws=weights[order].copy();ws/=ws.sum()
        color=[1.,1.,1.]
        if mat==0 and p[0]>.12 and 1.67<p[1]<1.735 and abs(p[2])<.04:color=[1.05,.84,.82]
        value=[*p,*n,*vertex[6:8],*order,*ws,mat,*color]
        lookup[key]=len(vertices);vertices.append(value);return lookup[key]
    cuts=[(np.array([0.,1.,0.]),height) for height in (.24,.43,.625,1.035,1.76,1.83)]
    cuts.append((np.array([1.,0.,0.]),.11))
    cuts.extend(sleeve_planes.values())
    for tri in triangles:
        polygons=[[np.r_[posed[idx],normals[idx],uv[tex],bone_weights[idx],runtime_weights[idx]] for idx,tex in tri]]
        collar_signed=np.array([[np.dot(v[:3],plane)-distance for plane,distance in collar_planes]
                                for v in polygons[0]])
        # Avoid subdividing unrelated arm/leg/head triangles along extended
        # collar planes. Only a triangle touching the convex neck opening
        # needs the additional exact cuts.
        collar_crosses=not np.any(collar_signed.max(0)<-1e-10) and not np.all(collar_signed.min(0)>=-1e-10)
        for plane,distance in cuts+(collar_planes if collar_crosses else []):
            polygons=[part for polygon in polygons for part in split_polygon(polygon,plane,distance)]
        for polygon in polygons:
            mat=material(polygon)
            if mat is None:continue
            for corner in range(1,len(polygon)-1):
                face=[polygon[0],polygon[corner],polygon[corner+1]]
                if np.linalg.norm(np.cross(face[1][:3]-face[0][:3],face[2][:3]-face[0][:3]))<1e-12:continue
                row=[pack_vertex(vertex,mat) for vertex in face]
                if len(set(row))==3:indices.extend(row);material_counts[mat]+=1
    def add_mesh(verts, faces, mat, bone, uvs=None):
        start=len(vertices);verts=np.asarray(verts);ns=np.zeros_like(verts)
        for face in faces:
            a,b,c=verts[list(face)];normal=np.cross(b-a,c-a)
            for v in face:ns[v]+=normal
        ns/=np.maximum(1e-12,np.linalg.norm(ns,axis=1))[:,None]
        for i,(p,n) in enumerate(zip(verts,ns)):
            tex=uvs[i] if uvs else [0,0];vertices.append([*p,*n,*tex,bone,0,0,0,1,0,0,0,mat,1,1,1])
        for face in faces:indices.extend(start+i for i in face);material_counts[mat]+=1
    def ellipsoid(center,radii,mat,bone,lat=8,lon=12):
        verts=[];tex=[];faces=[]
        for j in range(lat+1):
            a=-np.pi/2+j*np.pi/lat
            for i in range(lon):
                t=i*2*np.pi/lon;verts.append(np.asarray(center)+np.asarray(radii)*[np.cos(a)*np.cos(t),np.sin(a),np.cos(a)*np.sin(t)]);tex.append([i/lon,j/lat])
        for j in range(lat):
            for i in range(lon):
                a=j*lon+i;b=j*lon+(i+1)%lon;c=(j+1)*lon+(i+1)%lon;d=(j+1)*lon+i
                if j:faces.append((a,c,b))
                if j<lat-1:faces.append((a,d,c))
        add_mesh(verts,faces,mat,bone,tex)
    def canonical_point(p,bone):
        return (transforms[bone]@np.r_[torso_morph(p),1])[:3]
    for prefix in ['l','r']:
        eye=canonical_point(joint(prefix+'-eye'),4)
        ellipsoid(eye,[.013,.012,.012],6,4)
        ellipsoid(eye+np.array([.0114,0,0]),[.002,.0053,.0053],7,4,6,12)
        ellipsoid(eye+np.array([.0131,0,0]),[.001,.0026,.0026],8,4,6,12)
        ellipsoid(eye+np.array([.008,.018,0]),[.004,.003,.018],9,4,5,12)
    for i,name in [(11,'foot.L'),(18,'foot.R')]:
        ankle=ref[name][0];verts=[];tex=[];faces=[];rings=[(-.055,.035,.035),(.005,.057,.065),(.13,.058,.047),(.20,.050,.025),(.235,.008,.009)]
        for j,(x,w,h)in enumerate(rings):
            for k in range(12):
                a=k*np.pi/6;verts.append([ankle[0]+x,.070+np.sin(a)*h,ankle[2]+np.cos(a)*w]);tex.append([j/(len(rings)-1),k/12])
        for j in range(len(rings)-1):
            for k in range(12):
                a=j*12+k;b=j*12+(k+1)%12;c=(j+1)*12+(k+1)%12;d=(j+1)*12+k;faces.extend([(a,b,c),(a,c,d)])
        faces.extend([(0,k+1,k)for k in range(1,11)]);end=(len(rings)-1)*12;faces.extend([(end,end+k,end+k+1)for k in range(1,11)])
        add_mesh(verts,faces,4,i,tex)
        for x in [-.025,.10,.185]:
            for z in [-.037,.037]:ellipsoid([ankle[0]+x,.012,ankle[2]+z],[.010,.012,.010],4,i,4,7)
    data=np.asarray(vertices,dtype='<f4');idx=np.asarray(indices,dtype='<u2' if len(vertices)<65536 else '<u4')
    return data,idx,bones,{'sourceVisibleVertices':len(body_ids),'sourceVisibleQuads':len(groups['body']),'sourceScale':1.88/float(body[:,1].max()-ground),'sourceGroundY':ground,'sourceWeights':'normalized upstream weights collapsed by anatomical ancestry for bind geometry; runtime joint weights are an authored derivative','runtimeWeightPainting':weight_stats,'bindRetarget':'positive axial proportion correction followed by normalized rigid dual quaternion skinning','minimumLimbAxialScale':min(axial_scales),'maximumLimbAxialScale':max(axial_scales),'materials':{MATERIALS[k]:v for k,v in sorted(material_counts.items())}}


def textures(out):
    rng=np.random.default_rng(1301);n=256;y,x=np.mgrid[:n,:n]
    skin=np.clip(246+rng.normal(0,2.0,(n,n))+np.sin(x*.7)*.7,233,253).astype('uint8')
    fabric=np.clip(240+3*np.sin(x*np.pi/2)*np.sin(y*np.pi/2)+rng.normal(0,.8,(n,n)),232,248).astype('uint8')
    for name,gray in [('skin-detail',skin),('fabric-detail',fabric)]:
        Image.fromarray(np.repeat(gray[:,:,None],3,axis=2)).save(out/'textures'/(name+'.png'),optimize=False,compress_level=9)


def export_glb(path, data, indices, bones, out):
    binary=bytearray();views=[];accessors=[]
    def accessor(array,component,typ,minimum=False,target=None):
        nonlocal binary
        while len(binary)%4:binary.append(0)
        offset=len(binary);blob=np.asarray(array).tobytes();binary.extend(blob);view={'buffer':0,'byteOffset':offset,'byteLength':len(blob)}
        if target:view['target']=target
        views.append(view);record={'bufferView':len(views)-1,'componentType':component,'count':len(array),'type':typ}
        if minimum:record.update(min=np.asarray(array).min(0).tolist(),max=np.asarray(array).max(0).tolist())
        accessors.append(record);return len(accessors)-1
    # Standard GLB normalization only: runtime vertex data is kept verbatim.
    # Zero-weight joint labels do not affect skinning; the validator requests 0.
    gltf_joints=np.where(data[:,12:16]==0,0,data[:,8:12]).astype('<u2')
    # Runtime authored highlights can exceed 1, but glTF COLOR_0 cannot.
    gltf_colors=np.clip(data[:,17:20],0,1).astype('<f4')
    attrs={'POSITION':accessor(data[:,:3].astype('<f4'),5126,'VEC3',True,34962),'NORMAL':accessor(data[:,3:6].astype('<f4'),5126,'VEC3',target=34962),'TEXCOORD_0':accessor(data[:,6:8].astype('<f4'),5126,'VEC2',target=34962),'JOINTS_0':accessor(gltf_joints,5123,'VEC4',target=34962),'WEIGHTS_0':accessor(data[:,12:16].astype('<f4'),5126,'VEC4',target=34962),'COLOR_0':accessor(gltf_colors,5126,'VEC3',target=34962)}
    primitives=[];tri=indices.reshape(-1,3)
    for mat in range(len(MATERIALS)):
        rows=tri[data[tri[:,0],16].astype(int)==mat].reshape(-1)
        if len(rows):primitives.append({'attributes':attrs,'indices':accessor(rows.astype('<u2' if len(data)<65536 else '<u4'),5123 if len(data)<65536 else 5125,'SCALAR',target=34963),'material':mat})
    ibm=accessor(np.asarray([b['inverseBind']for b in bones],dtype='<f4'),5126,'MAT4')
    images=[]
    for name in ['skin-detail','fabric-detail']:
        while len(binary)%4:binary.append(0)
        blob=(out/'textures'/(name+'.png')).read_bytes();views.append({'buffer':0,'byteOffset':len(binary),'byteLength':len(blob)});binary.extend(blob);images.append({'bufferView':len(views)-1,'mimeType':'image/png','name':name})
    materials=[]
    for i,name in enumerate(MATERIALS):
        texture=0 if i==0 else 1
        materials.append({'name':name,'doubleSided':False,'pbrMetallicRoughness':{'baseColorFactor':COLORS[i]+[1],'baseColorTexture':{'index':texture},'metallicFactor':0,'roughnessFactor':.60 if i==0 else .83},'extras':{'license':'CC0-1.0'}})
    nodes=[{'name':'Tribun Footballer','children':[2]}, {'name':'Human footballer','mesh':0,'skin':0}]
    global_m=[np.asarray(b['matrix']).reshape(4,4).T for b in bones]
    for i,b in enumerate(bones):
        local=global_m[i] if PARENTS[i]<0 else np.linalg.inv(global_m[PARENTS[i]])@global_m[i]
        n={'name':b['name'],'matrix':local.T.reshape(-1).tolist()};children=[j+2 for j,p in enumerate(PARENTS)if p==i]
        if children:n['children']=children
        nodes.append(n)
    gltf={'asset':{'version':'2.0','generator':'Tribun build-player-assets.py','copyright':'MakeHuman CC0 / Tribun project-authored derivative CC0'},'scene':0,'scenes':[{'nodes':[0,1]}],'nodes':nodes,'meshes':[{'name':ID,'primitives':primitives}],'skins':[{'name':'Tribun 19-bone humanoid','joints':list(range(2,21)),'skeleton':2,'inverseBindMatrices':ibm}],'materials':materials,'textures':[{'source':0,'sampler':0},{'source':1,'sampler':0}],'samplers':[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}],'images':images,'bufferViews':views,'accessors':accessors,'buffers':[{'byteLength':len(binary)}],'extras':{'modelId':ID,'license':'CC0-1.0','sourceCommit':COMMIT,'rigReferenceSHA256':RIG_SHA256,'animationClips':0,'standardNormalization':{'vertexColor':'COLOR_0 clamped to [0,1]','unusedJoints':'zero-weight JOINTS_0 slots set to 0','skinnedMesh':'identity mesh node is a scene root'}}}
    js=json.dumps(gltf,separators=(',',':'),ensure_ascii=False).encode();js+=b' ' *((-len(js))%4);binary+=b'\0'*((-len(binary))%4)
    path.write_bytes(struct.pack('<III',0x46546c67,2,12+8+len(js)+8+len(binary))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(binary),0x004e4942)+binary)


def build(source, out):
    provenance=json.loads((source/'makehuman-provenance.json').read_text())
    verify_source(source, provenance)
    assert 'CC0' in (source/'makehuman-base.obj').read_text()[:500]
    skeleton=json.loads((source/'makehuman-default.mhskel').read_text());weights=json.loads((source/'makehuman-default_weights.mhw').read_text());assert skeleton['license']=='CC0' and weights['license']=='CC0'
    out.mkdir(parents=True,exist_ok=True);(out/'textures').mkdir(exist_ok=True);(out/'source').mkdir(exist_ok=True)
    for name in ['makehuman-base.obj','makehuman-default.mhskel','makehuman-default_weights.mhw']:(out/'source'/(name+'.gz')).write_bytes(gzip.compress((source/name).read_bytes(),mtime=0))
    for old,new in [('makehuman-LICENSE.md','SOURCE-LICENSE.md'),('makehuman-LICENSE.ASSETS.md','LICENSE-CC0.txt')]:shutil.copyfile(source/old,out/new)
    (out/'source/provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    raw,uv,groups=obj(source/'makehuman-base.obj');data,indices,bones,stats=skin_geometry(raw,uv,groups,skeleton,weights)
    textures(out);export_glb(out/'footballer.glb',data,indices,bones,out)
    anatomy={'schemaVersion':1,'standingHeight':1.88,'pelvisHeight':1.03,'shoulderJointSpan':.44,'hipJointSpan':.26,'headBoneHeight':.25,'upperArmLength':.315,'forearmLength':.29,'handBoneLength':.17,'thighLength':.475,'shinLength':.431,'bootLength':.290,'bootWidth':.116,'headWidthScale':.86,'headDepthScale':.92,'bindFrames':'TribunHumanoidRig.boneFrames(idle), without renderer offsets or bone scale','proportionReference':'adult athletic human: 1.88 m standing height, 7.52 head-bone units; shoulder and hip measurements are joint-center spans','sourceProportions':'source head narrowed and depth reduced continuously, limb lengths corrected along their source axes before rigid bind rotation','skinWeights':'authored runtime derivative: anatomical collapse plus local joint painting; pinned upstream originals retained verbatim','runtimeWeightPainting':WEIGHT_PAINT}
    metadata={'id':ID,'version':2,'license':'CC0-1.0','source':'MakeHuman Community hm08 CC0 base mesh','sourceURL':f'https://github.com/makehumancommunity/makehuman/blob/{COMMIT}/makehuman/data/3dobjs/base.obj','sourceCommit':COMMIT,'sourceSHA256':PINNED['makehuman-base.obj'],'rigReferenceSHA256':RIG_SHA256,'credits':'assets/player/CREDITS.md','forwardAxis':'+X','upAxis':'+Y','units':'metres','animationClips':0,'geometry':'source-human-mesh with authored football kit, eyes and boots','runtimeSkeleton':'19-bone collapse of source CC0 skin weights, positive axial proportion correction and rigid DQ bind retarget','anatomicalReference':anatomy}
    assets={'metadata':metadata,'textures':{'skin':'assets/player/textures/skin-detail.png','fabric':'assets/player/textures/fabric-detail.png'},'bones':bones,'lods':[{'name':'human','indexType':'H' if indices.dtype.itemsize==2 else 'I','vertices':base64.b64encode(data.tobytes()).decode(),'indices':base64.b64encode(indices.tobytes()).decode(),'vertexCount':len(data),'triangleCount':len(indices)//3}], 'statistics':stats}
    (out/'player-model-data.js').write_text("'use strict';\n// Built from verified CC0 source by tools/build-player-assets.py.\n(function(root){const assets="+json.dumps(assets,separators=(',',':'),ensure_ascii=False)+";root.TribunPlayerAssets=assets;if(typeof module!=='undefined'&&module.exports)module.exports=assets;})(typeof window!=='undefined'?window:globalThis);\n")
    (out/'skeleton.json').write_text(json.dumps({'modelId':ID,'license':'CC0-1.0','anatomicalReference':anatomy,'bones':bones},indent=2)+'\n')
    credits=f'''# Human footballer asset package\n\nModel ID: `{ID}`.\n\nThe anatomical body is the MakeHuman Community hm08 base mesh at commit `{COMMIT}`. The OBJ header explicitly releases this asset under CC0 in September 2020 and names Data Collection AB, Joel Palmius and Jonas Hauquier. The matching default skeleton and weights explicitly declare CC0. Source program code is not copied. `SOURCE-LICENSE.md` explains the distinction between AGPL program code and CC0 core assets; `LICENSE-CC0.txt` contains the upstream asset licence.\n\nOriginal source files are retained deterministically compressed under `source/`, with exact download URLs and SHA-256 values in `source/provenance.json`. The body source SHA-256 is `{PINNED['makehuman-base.obj']}`.\n\nThe project-authored derivative adds a football kit material layout, clothing offsets, football boots, eyes, brows, a 19-bone collapsed skin, a rig-compatible bind pose and two generated neutral detail textures. The canonical athletic bind is 1.88 m tall, with 0.44 m shoulder-joint span, 0.26 m hip-joint span, 0.475/0.431 m leg segments and 0.315/0.290 m arm segments. The head bone is 0.25 m, hands are 0.17 m and authored boots are 0.29 m long. These are authored adult proportions, not a measured population average. Source skin weights are retained verbatim in the pinned upstream archive and normalized/collapsed by anatomical ancestry for bind geometry. Runtime weights are an authored derivative: six simultaneous Jacobi smoothing rounds, 0.5 self plus 0.5 uniform neighbor mean on original body quad edges before UV/material splitting, then largest-four normalization. Painting is restricted to shoulder (0.18 m), elbow (0.12 m) and knee (0.15 m) patches whose adjacent bone weights sum above 0.35. All source hand influences and vertices within 0.13 m of either wrist are protected. Bind positions, normals, material assignments and UVs use the original collapsed weights and do not change during this painting step. Limb proportions are corrected along the original source axes with positive scale before a separate normalized dual-quaternion blend rotates the source into the canonical bind. No affine rotation blend is used to bake the bind. Head width and depth are reduced continuously and the front chest receives a continuous neutral athletic envelope. Runtime rigid dual-quaternion skinning and local weight painting reduce collapse in measured joint patches; they are not universal corrective anatomy and extreme-pose surface intersections can remain. These added asset components are released under CC0-1.0. They are original mathematical texture maps, not photos or scanned skin. No real footballer likeness, sponsor logo or external portrait is used.\n\n`footballer.glb` is a standard glTF 2.0 binary containing the mesh, skin, 19 joints, embedded textures and materials. It has no motion-capture or baked animation clips. `player-model-data.js` carries the same derived geometry for the existing WebGL renderer. Standard-only GLB normalization clamps vertex color multipliers to the required 0–1 range (runtime authored highlights may reach 1.05), writes joint index 0 for exactly zero-weight slots, and places the identity skinned mesh node at the scene root. Positions, normals, UVs, nonzero skin influences, weights, materials, embedded maps and all joint bind transforms are unchanged; the runtime JavaScript data is retained verbatim. It currently provides one drawable quality level; no multi-LOD performance claim is made.\n\nRebuild offline with `python3 tools/build-player-assets.py --from-package --output /tmp/tribun-player-rebuild`. The packaged originals are unpacked into a temporary input directory and all five pinned file hashes and official provenance URLs are checked before generation. The reviewed rig reference SHA-256 is `{RIG_SHA256}`. A changed rig must be reviewed before updating that pin. The original checked download directory can also be supplied with `--source-dir`. The builder requires Python, numpy, Pillow and Node for the reviewed canonical rig reference. Runtime play needs no builder dependencies.\n'''
    (out/'CREDITS.md').write_text(credits)
    files=[]
    for name in sorted(LICENSED_FILES):
        if name!='manifest.json':
            p=out/name;files.append({'path':(Path('assets/player')/name).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
    manifest={'schemaVersion':1,'modelId':ID,'version':2,'license':'CC0-1.0','sourceCommit':COMMIT,'rigReferenceSHA256':RIG_SHA256,'runtime':'assets/player/player-model-data.js','standardModel':'assets/player/footballer.glb','standardNormalization':{'vertexColor':'COLOR_0 clamped to [0,1]','unusedJoints':'zero-weight JOINTS_0 slots set to 0','skinnedMesh':'identity mesh node is a scene root'},'textures':assets['textures'],'bones':19,'lods':1,'vertices':len(data),'triangles':len(indices)//3,'anatomicalReference':anatomy,'statistics':stats,'files':files}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k]for k in ['modelId','bones','lods','vertices','triangles']}));print('runtime bytes', (out/'player-model-data.js').stat().st_size,'GLB bytes',(out/'footballer.glb').stat().st_size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--from-package', nargs='?', const=ROOT/'assets/player', type=Path,
                        help='Rebuild offline from the packaged compressed source files; optional package directory')
    parser.add_argument('--output', type=Path, default=ROOT/'assets/player')
    args = parser.parse_args()
    if args.source_dir is not None and args.from_package is not None:
        parser.error('--source-dir and --from-package are alternative inputs')
    if args.from_package is None:
        return build(args.source_dir or ROOT/'work/stage13/source', args.output)
    package = args.from_package
    with tempfile.TemporaryDirectory(prefix='tribun-player-source-') as directory:
        source = Path(directory)
        for name in ['makehuman-base.obj', 'makehuman-default.mhskel', 'makehuman-default_weights.mhw']:
            (source/name).write_bytes(gzip.decompress((package/'source'/(name+'.gz')).read_bytes()))
        for old, new in [('SOURCE-LICENSE.md', 'makehuman-LICENSE.md'), ('LICENSE-CC0.txt', 'makehuman-LICENSE.ASSETS.md'), ('source/provenance.json', 'makehuman-provenance.json')]:
            shutil.copyfile(package/old, source/new)
        return build(source, args.output)


if __name__=='__main__':main()
