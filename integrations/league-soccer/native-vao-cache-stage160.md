# Stage 160 — native VAO binding cache
Stages 156–159 comparison jobs still running when reviewed. The upstream
RenderVertexBuffer compares the current resolved VAO handle with the
next logical VAO ID, which can rebind on consecutive entries for the
same ping-pong logical buffer. Separate logical ID from resolved handle
within one synchronous queue call, reset every call. No reorder, culling,
texture or shading change, no geometry reduction; default retains old
comparison. Count actual bind calls, entries and consecutive repeated
logical IDs per 256 queue calls. Both modes measured with native 720p
window, 2048 shadow, full audio/browser and same frozen fixture/seed.
One pair, no independent visual equivalence proof; normalized bind count
is not GPU time or actual FPS. No promotion or changes to main.
