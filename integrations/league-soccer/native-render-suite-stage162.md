# Stage 162 — fixed-quality renderer selection suite
Stages 159 and 160 failed at missing upstream include anchor; Stage 161
repair build pending. No proven candidate yet. Patch-only preflight
applies all transformations to pinned upstream and checks diff before
dependency installation; does not replace C++ build. One rebuilt runtime,
same fixture and seed, native 720p window and 2048 shadow map. Measure
all three counters in each match, one feature at a time: skinning
translation cache, logical VAO cache and diffuse bind cache. Require
>=5% cost improvement and no excessive visual regression. Only eligible
features enter combined run, followed by repeated baseline. Require
stable baseline and improved visual cadence relative to both baselines;
no automatic promotion, no resolution/shadow downgrade, no proof of
pixel equality or parallel capacity. All measurements private and
noninteractive. No main changes. Some trials may fail; record results
rather than guess. Up to six sequential matches.
