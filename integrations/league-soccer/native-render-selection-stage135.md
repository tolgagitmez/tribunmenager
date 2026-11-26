# Stage 135 — repeated render profile selection
Two paired trials (2,1,1,2 GL workers) on one runner; identical frozen
fixtures, two concurrent matches per trial, same capture settings.
Require complete native clock, browser coverage, audio and manager evidence,
and observed SDL swap cadence. Provisional quality gates: >=25 swaps/s,
p95 gap <=80 ms, max gap <=500 ms, browser drops <=1%, encoded gap <=120 ms,
browser progress interval <=3 s. Candidate additionally must retain >=95%
baseline cadence, <=110% baseline p95 gap, save >=5% sampled engine CPU
and not increase total sampled CPU in both pairs. Neither profile is chosen
if the baseline or required evidence is incomplete. Diagnostic recommendation
only; not unique animation frames, visual fidelity or commercial capacity.
No change to main or automatic profile activation. CPU counters are sampled
lower bounds. ABBA mitigates order bias but two trials are not a statistical proof.
