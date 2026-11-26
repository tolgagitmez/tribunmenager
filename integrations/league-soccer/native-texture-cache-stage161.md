# Stage 161 — diffuse texture binding experiment and repair
Stage 159 build failed because humanoidbase.cpp includes humanoid.hpp,
not humanoidbase.hpp. Use verified unique <cmath> include instead, leaving
the later instrument.py transformation of humanoid.hpp intact. Stage 160
inherits the issue. The fix needs an actual build, not only Python tests.
RenderVertexBuffer already tracks diffuse/normal/specular/illumination IDs.
When only a non-diffuse ID changes, diffuse binding is redundant. Skip
only that unchanged diffuse bind inside a synchronous draw call; preserve
active texture unit reset, geometry order, materials and shader uniforms,
end-of-call unbind. No change to preexisting material batching semantics.
Count transitions and actual binds in both isolated modes, same 720p and
2048 shadow size, other experiments off, actual AV playback. No claim
of GPU timing, pixel equivalence or production improvement. No main.
