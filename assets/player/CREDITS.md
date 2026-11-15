# Human footballer asset package

Model ID: `tribun-makehuman-footballer-v1`.

The anatomical body is the MakeHuman Community hm08 base mesh at commit `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`. The OBJ header explicitly releases this asset under CC0 in September 2020 and names Data Collection AB, Joel Palmius and Jonas Hauquier. The matching default skeleton and weights explicitly declare CC0. Source program code is not copied. `SOURCE-LICENSE.md` explains the distinction between AGPL program code and CC0 core assets; `LICENSE-CC0.txt` contains the upstream asset licence.

Original source files are retained deterministically compressed under `source/`, with exact download URLs and SHA-256 values in `source/provenance.json`. The body source SHA-256 is `8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c`.

The project-authored derivative adds a football kit material layout, clothing offsets, football boots, eyes, brows, a 19-bone collapsed skin, a rig-compatible bind pose and two generated neutral detail textures. These added asset components are released under CC0-1.0. They are original mathematical texture maps, not photos or scanned skin. No real footballer likeness, sponsor logo or external portrait is used.

`footballer.glb` is a standard glTF 2.0 binary containing the mesh, skin, 19 joints, embedded textures and materials. It has no motion-capture or baked animation clips. `player-model-data.js` carries the same derived geometry for the existing WebGL renderer. It currently provides one drawable quality level; no multi-LOD performance claim is made.

Rebuild offline with `python3 tools/build-player-assets.py --from-package --output /tmp/tribun-player-rebuild`. The packaged originals are unpacked into a temporary input directory and all five pinned file hashes and official provenance URLs are checked before generation. The reviewed rig reference SHA-256 is `2c024a0fd130d50baa04533ae255a8f72b7dc93c269ef3d0af86ae6771820b3d`. A changed rig must be reviewed before updating that pin. The original checked download directory can also be supplied with `--source-dir`. The builder requires Python, numpy, Pillow and Node for the unchanged rig reference. Runtime play needs no builder dependencies.
