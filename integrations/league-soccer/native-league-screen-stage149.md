# Stage 149 — private league match screen
Native-only league status routes to native-league-live.html. Normal leagues
keep existing match screen. The shared MSE player retrieves only allowed HLS
files via same-origin Bearer-authenticated gateway. Tactics use league
round and existing authenticated endpoint; no capability URL or token in
media URL. Native HLS direct URL fallback disabled for authenticated mode.
Private screen disabled by default; TRIBUN_NATIVE_PRIVATE_SCREEN=1 only
on 127.0.0.1 dev server, with private worker output root outside web root.
Never put behind a reverse proxy, tunnel or port forwarding; this is not
public security or commercial rights approval. Rights gate remains blocked.
Only current running attempt is accessible (final buffered media may
finish after worker ends, replay support not yet implemented).
Tests cover allowlists/loopback and routing contracts, not actual native
league screen playback yet. No main changes.
