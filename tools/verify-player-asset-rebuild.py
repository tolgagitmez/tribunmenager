#!/usr/bin/env python3
"""Verify a rebuilt CC0 footballer without confusing BLAS rounding with edits.

This is not a replacement for the pinned official source SHA256 checks or
the byte-exact integrity of either package's own manifest. Structural
differences, triangles/joint changes, textures, provenance, and geometry
beyond small float32 tolerances all fail closed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct

import numpy as np

FLOAT64_TOL = 1e-10
FLOAT32_TOL = 2e-6
DERIVED = {"footballer.glb", "skeleton.json", "player-model-data.js"}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_manifest(package: Path):
    data = json.loads((package / "manifest.json").read_text())
    paths = [entry["path"] for entry in data["files"]]
    require(len(set(paths)) == len(paths), "Duplicate paths in manifest")
    for entry in data["files"]:
        rel = Path(entry["path"])
        require(rel.parts[:2] == ("assets", "player") and
                ".." not in rel.parts, f"Unsafe manifest path: {rel}")
        target = package.joinpath(*rel.parts[2:])
        require(target.is_file(), f"Missing license artifact: {target}")
        blob = target.read_bytes()
        require(len(blob) == entry["bytes"], f"Wrong size: {rel}")
        require(sha(blob) == entry["sha256"], f"SHA256 integrity failure: {rel}")
    require(data["license"] == "CC0-1.0", "Unreviewed license")
    require(data["sourceCommit"] ==
            "a8bc2d54ff0ac92e78ff71431b1023eda42bf482",
            "Unreviewed upstream commit")
    return data


def compare_structure(expected, actual, path="$", stats=None):
    """Exact type, key, topology and text checks; tight float64 slack only."""
    if type(expected) is float:
        require(type(actual) is float, f"{path}: floating type changed")
        require(np.isfinite(expected) and np.isfinite(actual),
                f"{path}: non-finite value")
        error = abs(expected-actual)
        require(error <= FLOAT64_TOL, f"{path}: {expected} != {actual}, error {error}")
        if stats is not None:
            stats["maxFloat64Delta"] = max(stats["maxFloat64Delta"], float(error))
        return
    require(type(expected) is type(actual), f"{path}: type changed")
    if isinstance(expected, dict):
        require(expected.keys() == actual.keys(), f"{path}: object keys differ")
        for key in expected:
            compare_structure(expected[key], actual[key], f"{path}.{key}", stats)
    elif isinstance(expected, list):
        require(len(expected) == len(actual), f"{path}: item count differs")
        for i, (a, b) in enumerate(zip(expected, actual)):
            compare_structure(a, b, f"{path}[{i}]", stats)
    else:
        require(expected == actual, f"{path}: content changed")


def compare_float32(expected, actual, name, stats):
    require(len(expected) == len(actual), f"{name}: buffer lengths differ")
    require(len(expected) % 4 == 0, f"{name}: invalid float32 stream")
    a = np.frombuffer(expected, dtype="<f4")
    b = np.frombuffer(actual, dtype="<f4")
    require(bool(np.isfinite(a).all()) and bool(np.isfinite(b).all()),
            f"{name}: nonfinite geometry")
    delta = np.abs(a.astype(np.float64) - b.astype(np.float64))
    max_delta = float(delta.max(initial=0))
    require(max_delta <= FLOAT32_TOL,
            f"{name}: geometry differs by {max_delta}, tolerance {FLOAT32_TOL}")
    stats["maxFloat32Delta"] = max(stats["maxFloat32Delta"], max_delta)
    stats["float32ComponentsChecked"] += int(a.size)


def read_glb(path):
    blob = path.read_bytes()
    require(len(blob)>=28, f"{path}: truncated GLB")
    magic, version, size = struct.unpack_from("<III", blob)
    require(magic==0x46546c67 and version==2 and size==len(blob),
            f"{path}: invalid GLB v2 header")
    position = 12
    chunks = []
    while position < size:
        require(position + 8 <= size, "Incomplete GLB chunk header")
        length, chunk_type = struct.unpack_from("<II", blob, position)
        position += 8
        require(position + length <= size, "Incomplete GLB chunk body")
        chunks.append((chunk_type, blob[position:position+length]))
        position += length
    require(len(chunks)==2 and chunks[0][0]==0x4E4F534A and
            chunks[1][0]==0x004E4942, f"{path}: invalid chunk layout")
    return json.loads(chunks[0][1].decode("utf8").rstrip(" \0")), chunks[1][1]


def compare_glb(packaged, rebuilt, stats):
    a, buffer_a = read_glb(packaged)
    b, buffer_b = read_glb(rebuilt)
    compare_structure(a, b, "$.glTF", stats)
    require(len(buffer_a)==len(buffer_b), "GLB buffer length differs")
    components = {}
    for accessor in a["accessors"]:
        index=accessor["bufferView"]
        old = components.setdefault(index, accessor["componentType"])
        require(old==accessor["componentType"],
                "Mixed component types in one bufferView")
    for i, view in enumerate(a["bufferViews"]):
        offset=view.get("byteOffset", 0)
        length=view["byteLength"]
        old=buffer_a[offset:offset+length]
        new=buffer_b[offset:offset+length]
        require(len(old)==length and len(new)==length,
                f"GLB buffer view {i} out of bounds")
        if components.get(i)==5126:
            compare_float32(old,new,f"GLB.bufferView[{i}]",stats)
        else:
            require(old==new,f"GLB bufferView {i} texture, indices or joints changed")
    stats["glbViewsChecked"] = len(a["bufferViews"])


def read_runtime(path):
    text=path.read_text()
    head="(function(root){const assets="
    end=";root.TribunPlayerAssets=assets;"
    require(text.startswith("'use strict';\n") and head in text and end in text,
            f"{path}: runtime wrapper changed")
    prefix, rest=text.split(head,1)
    asset_json, suffix=rest.split(end,1)
    return prefix, json.loads(asset_json), suffix


def compare_runtime(packaged,rebuilt,stats):
    old_prefix, old, old_suffix = read_runtime(packaged)
    new_prefix, new, new_suffix = read_runtime(rebuilt)
    require(old_prefix==new_prefix and old_suffix==new_suffix,
            "Runtime JS wrapper is not identical")
    require(len(old["lods"])==len(new["lods"]), "Runtime LOD count differs")
    for index, (a,b) in enumerate(zip(old["lods"], new["lods"])):
        if "vertices" in a and "vertices" in b:
            compare_float32(base64.b64decode(a["vertices"],validate=True),
                            base64.b64decode(b["vertices"],validate=True),
                            f"runtime.lods[{index}].vertices",stats)
            a["vertices"]=b["vertices"]="<validated float32>"
        if "indices" in a and "indices" in b:
            require(base64.b64decode(a["indices"],validate=True)==
                    base64.b64decode(b["indices"],validate=True),
                    f"runtime.lods[{index}]: mesh topology differs")
            a["indices"]=b["indices"]="<validated topology>"
    compare_structure(old,new,"$.runtime",stats)


def compare_packages(packaged:Path,rebuilt:Path):
    expected=verify_manifest(packaged)
    actual=verify_manifest(rebuilt)
    require([e["path"] for e in expected["files"]]==
            [e["path"] for e in actual["files"]],
            "Derived manifest file list/order changed")
    stats={"maxFloat64Delta":0.0,"maxFloat32Delta":0.0,
           "float32ComponentsChecked":0,"glbViewsChecked":0}
    a={k:v for k,v in expected.items() if k!="files"}
    b={k:v for k,v in actual.items() if k!="files"}
    compare_structure(a,b,"$.manifest",stats)
    for a,b in zip(expected["files"],actual["files"]):
        name=Path(a["path"]).relative_to("assets/player").as_posix()
        if name not in DERIVED:
            require(a==b, f"Immutable source/license/texture changed: {name}")
    compare_structure(json.loads((packaged/"skeleton.json").read_text()),
                      json.loads((rebuilt/"skeleton.json").read_text()),
                      "$.skeleton",stats)
    compare_runtime(packaged/"player-model-data.js",
                    rebuilt/"player-model-data.js",stats)
    compare_glb(packaged/"footballer.glb",rebuilt/"footballer.glb",stats)
    return stats


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path,default=Path("assets/player"))
    parser.add_argument("--rebuilt", type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(compare_packages(args.package,args.rebuilt),sort_keys=True))
