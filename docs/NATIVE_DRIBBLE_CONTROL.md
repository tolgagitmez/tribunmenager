# Stage 183 — native dribble control

A private opt-in descendant of stage 182. For the original native
ball-control touch, estimate player velocity projected onto the touch
direction (65% authored/planned outgoing movement, 35% actual movement).
Apply a bounded speed-only correction to excessive low-ball touches.
Use native combined dribble/control/agility/balance skill, opponent
clearance and movement alignment. Scale the planar ball vector and
associated spin by 0.8–1.0; retain vertical velocity and direction.
The proposed cap is soft: the 20% reduction limit takes precedence.

Requires unique CPU outfield possession and last touch, open play,
ball height <=0.35 m, contact blend <=0.25, opponent clearance >=1.5 m,
and alignment >=0.3. Exclude deliberate knock-ons, traps, passes, shots,
goalkeepers and set pieces. No forced contact, player movement, teleport,
or change to animation choice. The policy can still affect turnover,
dribble pace and outcomes; match validation is mandatory.

TRIBUN_AV_DRIBBLE_CONTROL=1 is private opt-in, default off. Do not
combine with leg blend, turn-brake, or active native close-touch policy.
Baseline and experimental samples log proposed and actual launch speed
separately; the report also measures sampled unique-owner planar ball
distance, with denominators and thresholds 1.25 and 2 metres. This
is a conditional snapshot distribution, not a count of lost possessions
or proof that a particular touch caused a subsequent turnover.

The standalone reproduced DribbleControlScale and 12 assertions compiled
and passed locally using C++17, -Wall -Wextra -Werror. Repository-wide
policy tests, parser tests, full native build and real matches have not
been verified. CI is configured for separate baseline and experimental
private matches; these are not guaranteed identical seeded fixtures.
Review actual retention, pace, goals and turnovers before promotion.
Main and Windows launcher unchanged. New runtime build required.
