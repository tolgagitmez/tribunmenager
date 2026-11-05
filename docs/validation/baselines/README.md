# Published stage 1 baseline

`stage1-football-sim.js.gz` contains the exact `football-sim.js` from the delivered
`tribun-menajer-asama1.zip`, without modifications. Its decompressed SHA-256 is
`cb35f481fadf8b0da28c31aa3605b6778dd6575d2d8df2838bd689750f8aed73`.

The published workspace retained uncommitted stage 1 changes; Git HEAD still
names the original v1.27 upload. Consequently HEAD is **not** the baseline for
stage 2 comparisons. `tools/profile-support-continuity.cjs` loads this retained
source in a separate CommonJS module with the unchanged `tactics.js`.

This historical source is evidence, not a second application entry point. The
current application still loads `/football-sim.js` normally.

## Stage 2 baseline for stage 3

`stage2-football-sim.js.gz` preserves the exact stage 2 source delivered in
`tribun-menajer-asama2.zip`. Its decompressed SHA-256 is
`0adbed0bd872eb0430d0327518b6322eda8087c6868d5c37fc46f79f6efa115a`.
The pass-arrival profilers load it as the baseline and current `/football-sim.js`
as the new implementation. The natural fork reconstructs the earlier stage 1
prefix to 3652.25s, then stage 2 to 3655.30s before branching. This mixed prefix
is explicitly recorded; it is not presented as a complete new 90-minute match.

## Stage 3 baseline for stage 4

`stage3-football-sim.js.gz` preserves the exact source delivered in
`tribun-menajer-asama3.zip` and subsequently published by the user. Its decompressed
SHA-256 is `4c9279ad5411460bcbb349fa510ff1267607cc5f2e5292f371e256afe9857a6f`.
`profile-receiver-interception.cjs` uses it directly for both the full matrix and
an independent natural press42 prefix from kickoff to29.183333s. No earlier-stage
mixed prefix or runtime snapshot is required to reproduce that fork.

## Stage 4 baseline for stage 5

`stage4-football-sim.js.gz` preserves the exact source delivered in
`tribun-menajer-asama4.zip` and subsequently published by the user. Its decompressed
SHA-256 is `406526afd60d3d2469e4d320b4a5a801f9680ecdbc6b98de9bf8d20d1c9ab539`.
The bytes were checked against that ZIP before any stage 5 application edit.
`profile-first-control.cjs` loads this baseline separately from the current engine.
Its natural forks reconstruct a complete stage 4 prefix from kickoff, then branch
from identical full player/ball/Map/RNG state. Runtime snapshots are optional;
none are required for the retained reports. Earlier test files and reports remain
historical evidence and were not relaxed to accommodate stage 5.

## Stage 5 baseline for stage 6

`stage5-football-sim.js.gz` preserves the exact source delivered in
`tribun-menajer-asama5.zip` and subsequently published by the user. Its decompressed
SHA-256 is `7038778922feb9f8f24389003b5ddf92fb8c0790280af84ae9818a04198acf60`.
The bytes were checked against that ZIP before stage 6 application edits.
`profile-reception-facing.cjs` uses this source for its matrix and complete natural
prefixes from kickoff. The retained six-second forks branch at tick boundaries
before a real pass release; they require no runtime snapshot or mixed prefix.
