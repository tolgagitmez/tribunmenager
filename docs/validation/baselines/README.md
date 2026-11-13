# Stage 9 engine retained for stage 10 observation

`stage9-football-sim.js.gz` preserves the exact engine published on the review branch in [commit c64270f4c8a861fb1118fdd49d2b3d46cb7c2fd1](https://github.com/tolgagitmez/tribunmenager/commit/c64270f4c8a861fb1118fdd49d2b3d46cb7c2fd1). Its decompressed SHA-256 is `b29a8f9b49638ec6559bc58df6b9504400eaaaf3b44bd14439d4643c3bd394f3`. Stage 10 leaves `football-sim.js` byte-identical; the passive observer, adapter and presentation files have separate hashes in the test/browser reports.

`tools/profile-attack-chain.cjs` compares the unchanged current engine with the published stage 8 `e16642b50e1d0b7d31cdc375dea7a83af85cf3da194a28362b65007f8420ad2e` source, under identical configurations and observation definitions. The current engine includes the stage 9 task/perception behavior; the baseline does not. This comparison explains their existing attack production rather than claiming that instrumentation improves either engine's quality. The review branch remains subject to match-balance calibration before `main` acceptance.

The natural profile preserves full episode and shot traces in standard JSON, published as a deterministic gzip archive. A separate readable summary records source hashes, raw/archive hashes, per-case normalized aggregates and complete-state observation/replay verification. Compression removes no trace data. The profile's report-generation timestamp is not a simulated-time denominator. Controlled aerial/keeper coverage is a separate selected dataset and is not pooled into natural conversion/save rates.

Earlier matrices retain their own source/configuration/window definitions. Their raw shot totals must not be treated as one experiment or compared without in-play exposure and attack denominators.


Final natural artifacts are [attack-chain-summary.json](../attack-chain-summary.json) and [attack-chain-matrix.json.gz](../attack-chain-matrix.json.gz). The archive preserves all 6,728,052 raw JSON bytes in 447,838 gzip bytes. Raw SHA-256: `853c73c9c0bc5e2c689d810c2556ff07bb4a9e8bb48c69a4c9a739e4c1b409f6`; gzip SHA-256: `d6e5f8b2a15b9d45145e6eafee5d3519b2cc48cd9d9a92e8abcac05d82ce1003`. All eight scenarios for both engines passed observed/plain full-state equality, deterministic replay and descriptor restoration. Each engine contributes 2400 observed seconds; verification repeats are not additional independent matches. Both produced four physical shots, but their in-play exposures differ, so raw totals alone do not describe attack production.

---

# Dokuzuncu aşama için yayımlanmış sekizinci aşama tabanı

`stage8-football-sim.js.gz`, dokuzuncu aşama karşılaştırması için yayımlanmış sekizinci aşama motorunu birebir korur. Açılmış SHA-256 değeri `e16642b50e1d0b7d31cdc375dea7a83af85cf3da194a28362b65007f8420ad2e` olur. Kaynak, GitHub `main` üzerindeki [68d0ea748b8ad15d26f22be920a12836fae4ada9](https://github.com/tolgagitmez/tribunmenager/commit/68d0ea748b8ad15d26f22be920a12836fae4ada9) commit'iyle doğrulanmıştır.

Bu taban ortak temas fiziğini içerir; yeni görev ve oyuncu algısı modüllerini içermez. `tools/profile-team-continuity.cjs` kaynağı ayrı CommonJS modülünde, aynı taktik kaynağıyla yükler. `tools/check-team-continuity-physics.cjs` BallPhysics ve belirtilen 16 canlı yöntemi bununla karşılaştırır. Yerel `695f552` HEAD'i aşama 9 tabanı değildir. Diğer gzip dosyaları ve matrisler aşağıdaki kendi tarihsel deneylerine aittir; farklı aşamaların toplamları tek deney gibi birleştirilmez.

Dokuzuncu aşamanın dört 300 saniyelik karşılaştırması [team-continuity-matrix.json](../team-continuity-matrix.json), olumlu ve olumsuz sonuç yorumu [DOGRULAMA.md](../../../DOGRULAMA.md) içindedir. Yeni deneyin motor kaynağı `b29a8f9b49638ec6559bc58df6b9504400eaaaf3b44bd14439d4643c3bd394f3` olarak raporlanır.

---

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
`tribun-menajer-asama5.zip`. Its decompressed SHA-256 is
`7038778922feb9f8f24389003b5ddf92fb8c0790280af84ae9818a04198acf60`.
The retained workspace source was compared byte-for-byte with that ZIP before
the stage 6 application edit. Git HEAD still names the original v1.27 upload;
it is not the baseline for this comparison. The new reception-facing tests and
profiler load this retained source separately from the current engine. Previous
test files, sources and reports remain historical evidence.

## Stage 6 baseline for stage 7

`stage6-football-sim.js.gz` preserves the exact engine left in the workspace at
the end of the preceding turn. Its decompressed SHA-256 is
`108d47253d775de6638460d5fa90dd6bbe2ab2e1e066b581e17591350c4917b6`.
Before the stage 7 application edit, the workspace bytes were checked against
the local source snapshot `work/tribun-menajer-asama6.zip`. This records local
provenance; it does not establish that the user separately published that ZIP.
The new post-receive-hold tests and `profile-control-exit.cjs` load the retained
stage 6 source separately from the current engine. Git HEAD remains the original
v1.27 upload, and previous tests and reports remain historical evidence.

## Stage 8: local, remote and integrated physical baselines

Three distinct sources were retained before the shared ground-touch change:

| Retained source | Provenance | Decompressed SHA-256 |
| --- | --- | --- |
| `stage7-football-sim.js.gz` | Exact local stage 7 engine at the start of this turn | `c1c1395a97a64f38a4c9704bde953e4f8ff8904f44784462313cfe15c83d694c` |
| `remote-main-82414b9-football-sim.js.gz` | GitHub `main` at commit `82414b9d9ec49f9b295f0a009e257327d3427961` | `8c3b3c1953ca95d02d2b78b5161131b4b1e1523a8b2b56850b4665b8fcadf703` |
| `stage8-integration-base.js.gz` | Local stage 7 plus the reconciled remote receiver-facing behavior, before the shared physical touch model | `16d6d78ac01b5490bbb8a178b4134a2f8c41224ad7091fb1e0b6b37aafa07360` |

The remote branch preserves the receiver's travel direction until proximity or
arrival time calls for opening the body. It includes ground through balls and
limits the opening to ±π/3 from the incoming-ball bearing. The integrated base
retains that behavior alongside local flight identity, preparation freshness,
ground-contact guards and advancing forecast time. Two historical validation
reports present only in the remote branch were also restored; earlier sources
and reports remain historical evidence.

`tests/touch-feasibility.test.cjs` and `tools/profile-touch-feasibility.cjs` load
the retained **integration base**, checking its decompressed SHA-256, so the
comparison isolates the shared touch model from receiver-facing reconciliation.
The local stage 7 source and the remote source remain provenance records; neither
Git HEAD nor either source alone substitutes for that physical baseline. All
retained engines are loaded as separate CommonJS modules for validation. The
application continues to load the current `/football-sim.js`.
