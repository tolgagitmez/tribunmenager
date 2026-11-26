# Stage 174 — transient decision restart boundaries

Experimental descendant of stage 173; main and the Windows launcher remain unchanged.
Uses the existing private CPU-only idle recovery flag, including the WSL GPU route.
Team and player observers detect changes in match phase or open play (in play and not set piece).
On a sampled edge, discard transient combination, triangle, timed attack, rebound support,
transition, team pressure and attacking run plans; the player's idle recovery timer is cleared
before preprocessing. Retain native referee/taker, formation, animation, ball, score and stamina.
A goalkeeper retaining the ball in open play is not by itself a restart.
The observer does not force the clock forward or force any ball contact. It cannot detect an
entire stop/restart that occurs between controller observations. Stage 173's sampled inactivity,
wall trace and video diagnostics remain independent; log entries indicate observed reset, not
proof of recovery. A new engine build is necessary because the patch changed.

Verification: attack-policy assertions cover repeated open and stopped samples, kickoff,
set-piece return, halftime and phase change with no intermediate sample. CI applies the
patch to pinned upstream, builds and runs a real private match. Review reset log timestamps,
phase, both team IDs and open state; correlate with the stage 173 carrier/clock diagnostics.
Require no clock or video stalls and no unexplained carrier inactivity near observed restarts;
a single successful match does not establish a general cure. Specific corner, free-kick,
throw-in and goalkeeper restart scenarios need real-match coverage. No production promotion.
