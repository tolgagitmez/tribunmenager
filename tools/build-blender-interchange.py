#!/usr/bin/env python3
"""Rebuild the CC0 interchange fixture using Blender's actual glTF importer/exporter.

Run: blender --background --factory-startup --python-exit-code 1 --python tools/build-blender-interchange.py
The source package and canonical rig remain untouched. No network is required.
"""
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/interchange"
CLIPS = [{"name": "idle", "duration": 1}, {"name": "run", "duration": 2},
         {"name": "shoot", "duration": 1.3, "contactTime": .38},
         {"name": "dive-right", "duration": 1.3, "contactTime": .34}]


def fingerprint(file):
    data = file.read_bytes()
    return {"path": str(file.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def preserve_float_colors(meshes):
    """Use float linear colors instead of Blender import's lossy byte sRGB layer.

    Match by source material and bind position, allowing Blender to reorder and
    split vertices. All coincident vertices in each material have equal colors.
    """
    blob = (ROOT / "assets/player/footballer.glb").read_bytes()
    json_size = struct.unpack_from("<I", blob, 12)[0]
    document = json.loads(blob[20:20 + json_size])
    binary = blob[28 + json_size:]
    cache = {}

    def floats(index):
        if index not in cache:
            accessor = document["accessors"][index]
            view = document["bufferViews"][accessor["bufferView"]]
            width = {"VEC3": 3, "VEC4": 4}[accessor["type"]]
            cache[index] = [struct.unpack_from("<" + "f" * width, binary,
                view.get("byteOffset", 0) + accessor.get("byteOffset", 0) +
                i * view.get("byteStride", width * 4)) for i in range(accessor["count"])]
        return cache[index]

    colors = {}
    for primitive in document["meshes"][0]["primitives"]:
        material = document["materials"][primitive["material"]]["name"]
        positions = floats(primitive["attributes"]["POSITION"])
        values = floats(primitive["attributes"]["COLOR_0"])
        for position, color in zip(positions, values):
            key = (material, *[round(v * 10000) for v in position])
            colors.setdefault(key, []).append((position, color))
    for obj in meshes:
        mesh = obj.data
        old = mesh.color_attributes.active_color
        name = old.name if old else "Color"
        if old:
            mesh.color_attributes.remove(old)
        layer = mesh.color_attributes.new(name=name, type="FLOAT_COLOR", domain="CORNER")
        mesh.color_attributes.active_color = layer
        mesh.color_attributes.render_color_index = list(mesh.color_attributes).index(layer)
        for polygon in mesh.polygons:
            material = mesh.materials[polygon.material_index].name
            for loop_index in polygon.loop_indices:
                v = mesh.vertices[mesh.loops[loop_index].vertex_index].co
                position = (v.x, v.z, -v.y)  # Blender Z-up -> glTF Y-up
                bucket = [round(value * 10000) for value in position]
                candidates = []
                for x in (-1, 0, 1):
                    for y in (-1, 0, 1):
                        for z in (-1, 0, 1):
                            candidates.extend(colors.get((material, bucket[0]+x, bucket[1]+y, bucket[2]+z), []))
                found = next((color for source, color in candidates
                              if max(abs(a-b) for a, b in zip(source, position)) < 2e-6), None)
                if found is None:
                    raise RuntimeError("Cannot map original vertex color: " + str(position))
                layer.data[loop_index].color = (*[max(0, min(1, value)) for value in found[:3]], 1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # Deleted factory objects leave orphan mesh/material datablocks behind.
    bpy.data.orphans_purge(do_recursive=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.render.fps = 30
    scene.render.fps_base = 1
    scene.frame_start, scene.frame_end = 0, 60
    with tempfile.TemporaryDirectory(prefix="tribun-interchange-") as temporary:
        source = Path(temporary) / "footballer.canonical.glb"
        subprocess.run(["node", str(ROOT / "tools/bake-licensed-clips.cjs"),
                        "--output", str(source)], cwd=ROOT, check=True)
        canonical = fingerprint(source) if source.is_relative_to(ROOT) else {
            "bytes": source.stat().st_size, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        bpy.ops.import_scene.gltf(filepath=str(source), import_pack_images=True)
    armatures = [obj for obj in scene.objects if obj.type == "ARMATURE"]
    meshes = [obj for obj in scene.objects if obj.type == "MESH"
              and any(modifier.type == "ARMATURE" for modifier in obj.modifiers)]
    if len(armatures) != 1 or len(armatures[0].data.bones) != 19 or not meshes:
        raise RuntimeError("Expected one 19-joint licensed human")
    armature = armatures[0]
    preserve_float_colors(meshes)
    for mesh in meshes:
        # A skinned node is a glTF scene root. The armature modifier retains
        # its skeleton link; clearing Blender object parenting avoids the
        # Khronos NODE_SKINNED_MESH_NON_ROOT warning and ambiguous transforms.
        world = mesh.matrix_world.copy()
        mesh.parent = None
        mesh.matrix_world = world
    armature["license"] = "CC0-1.0"
    armature["source"] = "assets/player/footballer.glb"
    armature["gltf_up_axis"] = "+Y"
    armature["gltf_forward_axis"] = "+X"
    armature["blender_up_axis"] = "+Z"
    armature["blender_forward_axis"] = "+X"
    # glTF import uses Blender's Z-up coordinate space internally. The exporter
    # converts back to Y-up without applying an extra object rotation.
    scene["interchange_unit"] = "metre"
    scene["interchange_up_axis"] = "+Y (glTF), +Z (Blender)"
    scene["interchange_forward_axis"] = "+X"
    scene["canonical_rig_sha256"] = json.loads((ROOT / "assets/player/manifest.json").read_text())["rigReferenceSHA256"]
    scene["simulation_hz"] = 60
    scene["keyframe_fps"] = 30
    scene.frame_set(0)
    # Keep every imported clip in an NLA track. Blender's importer already
    # creates one track per glTF animation; track names retain the clip names.
    tracks = list(armature.animation_data.nla_tracks)
    if sorted(track.name for track in tracks) != sorted(clip["name"] for clip in CLIPS):
        raise RuntimeError("Imported NLA tracks lost clip names: " + str([track.name for track in tracks]))
    armature.animation_data.action = None
    for track in tracks:
        track.mute = False
    # Factory startup leaves an unused default Material after deleting its cube.
    # Keep the editable project as lean as the ten-material exported asset.
    for material in list(bpy.data.materials):
        if material.users == 0:
            bpy.data.materials.remove(material)
    # Pack maps into the editable source; external export writes ordinary PNGs.
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "editable.blend"), compress=True)
    export = dict(export_animations=True, export_animation_mode="NLA_TRACKS",
                  export_force_sampling=True, export_frame_range=False,
                  export_frame_step=1, export_optimize_animation_size=False,
                  export_skins=True, export_yup=True, export_extras=True,
                  export_texcoords=True, export_normals=True,
                  export_image_format="AUTO", export_materials="EXPORT")
    bpy.ops.export_scene.gltf(filepath=str(OUT / "footballer.blender.glb"), export_format="GLB", **export)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "footballer.blender.gltf"),
                              export_format="GLTF_SEPARATE", export_texture_dir="textures", **export)
    validate = r"""
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const validator=require('gltf-validator'),baker=require('./tools/bake-licensed-clips.cjs');
(async()=>{
 const files=['assets/player/footballer.glb','assets/interchange/footballer.blender.glb','assets/interchange/footballer.blender.gltf'];
 const inputs=[{path:'canonical animated intermediate GLB',bytes:baker.bakeLicensedGLB().glb},...files.map(file=>({path:file,bytes:fs.readFileSync(file)}))];
 const reports=[];
 for(const input of inputs){
  const report=await validator.validateBytes(new Uint8Array(input.bytes),{
   uri:path.basename(input.path),maxIssues:1000,
   externalResourceFunction:uri=>Promise.resolve(new Uint8Array(fs.readFileSync(path.join(path.dirname(input.path),decodeURIComponent(uri)))))
  });
  reports.push({path:input.path,bytes:input.bytes.length,sha256:crypto.createHash('sha256').update(input.bytes).digest('hex'),issues:report.issues});
  if(report.issues.numErrors||report.issues.numWarnings)throw Error(input.path+': '+JSON.stringify(report.issues));
 }
 fs.writeFileSync(process.argv[1],JSON.stringify({validator:'Khronos glTF Validator',version:validator.version(),reports},null,2)+'\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    subprocess.run(["node", "-e", validate, str(OUT / "khronos-validation.json")], cwd=ROOT, check=True)
    for filename in ("LICENSE-CC0.txt", "SOURCE-LICENSE.md"):
        shutil.copyfile(ROOT / "assets/player" / filename, OUT / filename)
    (OUT / "CREDITS.md").write_text(
        "# Blender interchange footballer\n\n"
        "CC0-1.0. This is a Blender 4.3.2 round trip of the project's licensed "
        "MakeHuman-derived human and authored football kit. The MakeHuman body, "
        "skeleton and weights are pinned at commit "
        "`a8bc2d54ff0ac92e78ff71431b1023eda42bf482`. Original assets, upstream "
        "URLs and hashes remain under `../player/source/`; the complete original "
        "credits and derivative description remain in `../player/CREDITS.md`.\n\n"
        "The four animations are authored deterministic samples of the canonical "
        "Tribun rig, simulated at 60 Hz and exported at 30 fps. This package does "
        "not contain motion capture or another person's animation clips. Maps are "
        "the original project-authored CC0 neutral mathematical textures.\n\n"
        "Blender 4.3.2 is a GPL-3.0-or-later import/export tool. No Blender "
        "program code is copied into this CC0 asset package.\n\n"
        "Open `editable.blend` to edit the armature, mesh, materials and four NLA "
        "tracks. Blender displays Z up; both glTF exports are in metres with +Y up "
        "and +X forward. The source UVs, vertex colors, PBR factors and skin weights "
        "pass through Blender's importer and exporter; topology may be reordered. "
        "The authored runtime vertex color highlights of 1.05 are already clamped to "
        "glTF's required 0–1 range in the source GLB. A FLOAT_COLOR layer preserves "
        "the source's linear colors through Blender's byte-color import conversion. "
        "Blender also quantizes custom "
        "normals; measured maximum component change is 0.003819.\n\n"
        "Blender's stock exporter drops skin influences at or below 0.0001 "
        "and renormalizes the remaining weights. The manifest sets explicit "
        "round-trip weight and deformed-position tolerances.\n\n"
        "glTF uses linear blend skinning. The production custom renderer uses "
        "dual quaternion skinning and procedural material details, so matching "
        "joint motion does not imply identical deformed surfaces or shading.\n"
    )
    originals = json.loads((ROOT / "assets/player/manifest.json").read_text())
    provenance = json.loads((ROOT / "assets/player/source/provenance.json").read_text())
    generated = [OUT / "editable.blend", OUT / "footballer.blender.glb",
                 OUT / "footballer.blender.gltf", OUT / "footballer.blender.bin",
                 *sorted((OUT / "textures").glob("*.png")), OUT / "CREDITS.md",
                 OUT / "LICENSE-CC0.txt", OUT / "SOURCE-LICENSE.md", OUT / "khronos-validation.json"]
    metadata = {
        "schemaVersion": 1, "blenderVersion": bpy.app.version_string,
        "command": "blender --background --factory-startup --python-exit-code 1 --python tools/build-blender-interchange.py",
        "prerequisites": ["Blender 4.3.2 with bundled io_scene_gltf2", "Node.js 24 or supported project version", "npm ci (pinned Khronos gltf-validator)"],
        "network": "none", "simulationHz": 60, "fps": 30,
        "animationConstruction": "worldJoint = rendererSkinPalette * fullBindMatrix; local = inverse(parentWorldJoint) * worldJoint; baked translation + normalized quaternion LINEAR channels",
        "roundTrip": ["canonical standard animated GLB", "Blender glTF import", "packed editable.blend", "Blender GLB and GLTF_SEPARATE export"],
        "canonicalInput": canonical, "exportOptions": export,
        "sources": [fingerprint(ROOT / "tools/bake-licensed-clips.cjs"),
                    fingerprint(Path(__file__)), fingerprint(ROOT / "humanoid-rig.js"),
                    fingerprint(ROOT / "player-renderer.js"), fingerprint(ROOT / "animation-scenarios.js"),
                    fingerprint(ROOT / "tools/build-player-assets.py"), fingerprint(ROOT / "assets/player/manifest.json"),
                    fingerprint(ROOT / "assets/player/footballer.glb"),
                    fingerprint(ROOT / "assets/player/player-model-data.js")],
        "determinism": "Canonical animation GLB is byte deterministic. Blender geometry, textures and sampled poses are checked numerically. editable.blend embeds Blender session metadata and is verified by its packaged hash, not required to rebuild byte identically."
    }
    (OUT / "rebuild.json").write_text(json.dumps(metadata, indent=2) + "\n")
    manifest = {
        "schemaVersion": 1, "modelId": "tribun-blender-interchange-v1", "license": "CC0-1.0",
        "sourceModel": "assets/player/footballer.glb", "sourceModelSHA256": next(x["sha256"] for x in originals["files"] if x["path"].endswith("/footballer.glb")),
        "sourceCommit": originals["sourceCommit"], "rigReferenceSHA256": originals["rigReferenceSHA256"],
        "sourceProvenance": "assets/player/source/provenance.json",
        "originalPinnedSourceFiles": provenance,
        "editable": "assets/interchange/editable.blend", "glb": "assets/interchange/footballer.blender.glb",
        "gltf": "assets/interchange/footballer.blender.gltf", "bin": "assets/interchange/footballer.blender.bin",
        "blenderVersion": bpy.app.version_string, "unit": "metre", "upAxis": "+Y", "forwardAxis": "+X",
        "toolProvenance": {"name": "Blender", "version": bpy.app.version_string,
                           "license": "GPL-3.0-or-later",
                           "scope": "External importer/exporter only; no Blender program code is copied into the CC0 asset package"},
        "blenderUpAxis": "+Z", "bones": 19, "materials": 10, "textures": 2,
        "simulationHz": 60, "fps": 30, "clips": CLIPS,
        "validationTolerances": {"jointWorldMetres": .00002, "skinMatrixElement": .00002,
                                 "skinnedVertexMetres": .00003, "bindGeometryMetres": .000002,
                                 "uv": .000002, "weights": .00015, "materialFactor": .000002,
                                 "normalComponent": .0042, "vertexColor": .00002},
        "skinning": "glTF linear blend skinning; runtime custom rendering uses dual quaternions",
        "sourceConversions": {"vertexColor": "Source standard GLB already clamps authored runtime highlights of 1.05 to required COLOR_0 range [0,1]; restore linear FLOAT_COLOR layer after Blender byte-color import", "normals": "Blender custom-normal quantization; maximum measured component error 0.003819", "weights": "Stock Blender exporter drops influences <=0.0001 and renormalizes retained weights"},
        "files": [fingerprint(file) for file in [*generated, OUT / "rebuild.json"]]
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    backup = OUT / "editable.blend1"
    if backup.exists():
        backup.unlink()
    print(json.dumps({"interchange": str(OUT), "clips": CLIPS, "files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
