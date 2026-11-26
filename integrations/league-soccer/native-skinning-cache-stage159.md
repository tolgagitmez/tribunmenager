# Stage 159: native CPU skinning cache
Stages 156–158 AV comparisons still running at review. Pinned upstream
HumanoidBase::UpdateFullbodyModel repeatedly scales original and current
joint positions for each weighted vertex. Cache these same products once
per update in isolated full-render diagnostics, preserving vertex math,
rotation, weights, normals, tangents, bitangents and bind-pose path.
No reduced animation cadence, no removed shading channels. The cache
adds allocations; actual savings may be negative. Measure both modes
using cumulative update-call wall time (not CPU time) including lock
wait, excluding last partial block. Fixed 720p window and 2048 shadow
map, audio/browser, same fixture and seed. Only a single pair; visual
or numerical equivalence and real performance not yet verified. No
promotion or main changes. No claim of drawing-stage bottleneck yet.
