# Stage 138 — integrated recording and season rehearsal
The real two-match benchmark now requires native OpenAL ownership. The shared
AV verifier also checks observed wall duration, native clock, command targets,
fixture hash, trace hash and recomputed roster manifest using the pinned
adapter. Recompute the native season sidecar, then replay both recordings
through the existing durable queue and private season writer in a disposable
database. Verify scores, four-team standings, appearance count, duplicate
rejection and official tables unchanged. Unit tests use synthetic records;
CI runs actual concurrent recordings before replay. A failed capacity trial
must not pass this gate. This is an offline replay, not live league authority,
authenticated manager traffic, or production capacity. Motion evidence is
diagnostic, not a perceptual animation certification. Main untouched.
