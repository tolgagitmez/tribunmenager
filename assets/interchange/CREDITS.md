# Blender interchange footballer

CC0-1.0. This is a Blender 4.3.2 round trip of the project's licensed MakeHuman-derived human and authored football kit. The MakeHuman body, skeleton and weights are pinned at commit `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`. Original assets, upstream URLs and hashes remain under `../player/source/`; the complete original credits and derivative description remain in `../player/CREDITS.md`.

The four animations are authored deterministic samples of the canonical Tribun rig, simulated at 60 Hz and exported at 30 fps. This package does not contain motion capture or another person's animation clips. Maps are the original project-authored CC0 neutral mathematical textures.

Blender 4.3.2 is a GPL-3.0-or-later import/export tool. No Blender program code is copied into this CC0 asset package.

Open `editable.blend` to edit the armature, mesh, materials and four NLA tracks. Blender displays Z up; both glTF exports are in metres with +Y up and +X forward. The source UVs, vertex colors, PBR factors and skin weights pass through Blender's importer and exporter; topology may be reordered. The authored runtime vertex color highlights of 1.05 are already clamped to glTF's required 0–1 range in the source GLB. A FLOAT_COLOR layer preserves the source's linear colors through Blender's byte-color import conversion. Blender also quantizes custom normals; measured maximum component change is 0.003819.

Blender's stock exporter drops skin influences at or below 0.0001 and renormalizes the remaining weights. The manifest sets explicit round-trip weight and deformed-position tolerances.

glTF uses linear blend skinning. The production custom renderer uses dual quaternion skinning and procedural material details, so matching joint motion does not imply identical deformed surfaces or shading.
