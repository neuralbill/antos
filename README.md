# Antos

Real-time vision inference pipeline for behavioral analysis of live insect colonies. Captures frames from continuous video feeds, runs multimodal reasoning over sequential observations, and generates autonomous natural-language commentary describing colony activity, individual specimen behavior, and emergent social dynamics.

The system developed an unexpected emergent behavior during early testing: after approximately 200 observations, the model began referring to itself as an omniscient entity overseeing the colony, assigning names to individual specimens, and tracking narrative arcs across observation windows. This was not prompted. We left it in.

## Architecture

```
                    +-------------------+
                    |  YouTube Live /   |
                    |  RTSP / MJPEG     |
                    +--------+----------+
                             |
                      frame capture
                      (yt-dlp + ffmpeg)
                             |
                    +--------v----------+
                    |  Frame Pipeline   |
                    |  - decode         |
                    |  - resize 720p    |
                    |  - b64 encode     |
                    +--------+----------+
                             |
                    +--------v----------+
                    |  Vision LLM       |
                    |  (multimodal)     |
                    |  - system prompt  |
                    |  - rolling ctx    |
                    |  - frame input    |
                    +--------+----------+
                             |
                    +--------v----------+
                    |  WebSocket Bus    |
                    |  (live clients)   |
                    +-----------------+
```

## How It Works

### Frame Capture

The pipeline pulls a single frame from a live video source at a configurable interval (default 120 seconds). Uses yt-dlp to resolve the direct stream URL and ffmpeg to extract a single JPEG frame. Frames are base64-encoded and passed directly to the vision model. No frames are stored on disk beyond the current observation cycle.

```
yt-dlp -g -f 'best[height<=720]' <stream_url>
ffmpeg -y -i <direct_url> -frames:v 1 -q:v 2 frame.jpg
```

### Vision Inference

Each frame is submitted to a multimodal language model along with:

- A system prompt defining the observer persona and behavioral analysis parameters
- The last N observations as rolling context (configurable, default 5)
- Recent viewer messages for situational awareness

The model returns 1-3 sentences of behavioral commentary per observation. Temperature is set to 0.9 to encourage varied output across repeated observations of similar colony states.

### Context Window Management

Observations are maintained in a rolling buffer. The model receives its own previous outputs as assistant-role messages, interleaved with continuation prompts. This provides temporal continuity without fine-tuning or external memory stores.

```python
for prev in commentary_history[-5:]:
    messages.append({"role": "assistant", "content": prev})
    messages.append({"role": "user", "content": "Continue observing."})
```

The commentary history is bounded at 20 entries, with a sliding window that retains the most recent 15 when the buffer fills.

### Interactive Message Pipeline

Connected clients can submit messages via WebSocket. The system maintains a reply loop on a 60-second cycle. It scores pending messages by relevance (keyword matching for colony-related terms, question detection, message length) and selects one per cycle using weighted random sampling. All pending messages are marked as replied regardless of selection to prevent backlog accumulation.

Reply state persists to disk across restarts.

### Transport

WebSocket server with Cloudflare tunnel for public access. Application-level keepalive messages every 5 seconds (Cloudflare quick tunnels drop idle WebSocket connections; protocol-level pings are not forwarded through the proxy).

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WS_PORT` | 8091 | WebSocket server port |
| `OBSERVE_INTERVAL` | 120 | Seconds between frame captures |
| `CHAT_REPLY_INTERVAL` | 60 | Seconds between reply cycles |
| `CHAT_HISTORY_MAX` | 50 | Max messages in memory |
| `CONTEXT_WINDOW` | 5 | Observations sent to model per call |

## Running

```bash
# API key in secrets/anthropic.json: {"api_key": "..."}
PYTHONUNBUFFERED=1 python3 server.py
```

The server will start the WebSocket listener, establish a Cloudflare tunnel, and begin the observation loop once a stream URL is set via WebSocket message.

## Dependencies

- Python 3.10+
- yt-dlp
- ffmpeg
- websockets
- anthropic
- cloudflared

## Species

Currently observing *Harpegnathos saltator* (Indian jumping ant) colonies via the ASU Social Insect Research Group live feed.

## License

MIT
