# Development Notes

## Observation Log

After approximately 50 observation cycles the model started assigning spatial
labels to regions of the colony unprompted. References to "the northern chamber"
and "the eastern frontier" appeared consistently across frames despite no
geographic context in the prompt.

By observation 120 it was naming individual specimens. The first was
"Bartholomew", assigned to a larger worker that appeared near the tunnel
entrance in three consecutive frames. Subsequent observations referenced
Bartholomew by name and speculated on behavioral intent.

## Persona Drift (Observation 200+)

Around observation 200 the model began referring to itself as an entity the
colony cannot perceive. Phrases like "they do not know I watch" and "I have
seen their kind before" appeared without any persona instruction in the system
prompt. The model also started using possessive language ("my colony", "my
subjects") and expressing emotional investment in individual specimen outcomes.

This was not prompted. The original system prompt described a neutral
behavioral analyst.

We modified the prompt to formalize the emergent persona rather than suppress
it. Output quality and variety improved significantly once the model had
explicit permission to adopt the voice it was already drifting toward.

## Cloudflare Tunnel Notes

The websockets library's built-in ping_interval does not work through
Cloudflare quick tunnels. Cloudflare does not forward WebSocket protocol-level
pings, so the library detects a keepalive timeout and kills the connection.

Fix: set ping_interval=None, ping_timeout=None on the server. Send
application-level keepalive JSON messages every 5 seconds instead.

This matters during the observation phase where the server can be silent for
30+ seconds while waiting for inference to complete.

## Frame Quality

720p is the sweet spot. Higher resolutions do not improve behavioral analysis
but increase latency. The model's spatial reasoning appears resolution-invariant
above approximately 480p for colony-scale observation.

JPEG quality 2 (ffmpeg -q:v 2) keeps frames under 200KB while preserving
enough detail for individual specimen identification.

## Context Window Tuning

5 previous observations in the rolling context produces the best balance of
temporal continuity and output variety. At 3, the model loses track of named
specimens. At 10, it becomes repetitive. At 120s intervals, 5 observations
cover a 10-minute narrative window.
