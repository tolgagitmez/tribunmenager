# Stage 176 — native alternative action prioritization

Experimental descendant of stage 175. Uses the existing private CPU-only
idle recovery flag. For the active unique ball carrier, require last touch,
low player and ball speed, nearby low ball, open play and AI outfielder.
Observe the first attacking candidate rejected by the native animation
selector at distinct engine ticks. Require three rejections of the same
function type spanning at least 160 native ms, with no gap over 600 ms.
A 500 ms cooldown limits reprioritization. Clear the history on loss of
eligibility, phase change, stale observations and native ResetSituation.
A successful selection of the tracked kind clears its rejection streak.

Prefer an already queued short pass of a different function type, otherwise
a native ball-control candidate with desired movement >=1.2 m/s. Rotate
that candidate to the front while retaining all original commands. If no
such candidate exists, preserve order; do not invent a pass, change
receiver selection, force ball contact, alter animation selection, or
advance the match clock. Existing stage 172 safe outlet recovery remains.
Missed-touch events are diagnostic only; this intervention addresses
repeated selector rejection rather than all possible execution failures.
Promotion is not evidence of actual displacement or contact.

Reports separately count promotion events, candidate outcomes and contact.
Verify against stage 173 stationary episodes and stage 175 actual contacts;
measure time to resumed movement and any regression in pass/shot quality.
Standalone watchdog assertions passed locally; the full pinned engine
patch/build and private match require CI verification. Specific missed
touch and alternative success rates require matched-event evidence.
Main and the Windows launcher are unchanged; new native build required.
