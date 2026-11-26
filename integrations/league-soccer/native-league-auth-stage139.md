# Stage 139 — native AV league authorization gateway
Opt-in development endpoint GET/POST /api/league/native-av/tactics.
Bearer token resolves league and team from SQLite, derives the fixture and
side from the server schedule, and requires a running AV queue attempt.
Only local, private per-attempt capability files under a trusted configured
root can be used. No redirects, proxies or user-selected upstream URLs.
Configure TRIBUN_NATIVE_AV_GATEWAY_ROOT to the same private output root as
the AV worker. Disabled by default. Use only an isolated diagnostic league
and keep output outside the static web root. The old diagnostic browser
still auto-submits its own test commands; this gateway is not yet suitable
for real manager matches, and does not expose HLS or authoritative results.
Bearer tokens are the existing development league tokens, not production
account security. Unit tests cover authorization and capability validation;
real HTTP/control integration remains to be tested. No main changes.
