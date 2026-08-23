# antos

Frame capture and vision inference for live insect colony streams.

Pulls frames from YouTube live feeds via yt-dlp, runs multimodal analysis,
outputs behavioral descriptions.

## Usage

```bash
python3 capture.py <youtube_live_url>
python3 analyze.py <frame.jpg>
```

## Dependencies

- Python 3.10+
- yt-dlp
- ffmpeg
- anthropic
