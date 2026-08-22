#!/usr/bin/env python3
"""Frame capture from YouTube live streams via yt-dlp + ffmpeg."""

import subprocess
import sys
import os
import tempfile


def get_stream_url(youtube_url):
    result = subprocess.run(
        ['yt-dlp', '-g', '-f', 'best[height<=720]', youtube_url],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip().split('\n')[0]


def capture_frame(stream_url, output_path):
    subprocess.run([
        'ffmpeg', '-y', '-i', stream_url,
        '-frames:v', '1', '-q:v', '2', output_path
    ], capture_output=True, timeout=15)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 100


if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else None
    if not url:
        print("usage: capture.py <youtube_url>")
        sys.exit(1)
    stream = get_stream_url(url)
    if stream:
        out = tempfile.mktemp(suffix='.jpg')
        if capture_frame(stream, out):
            print(f"captured: {out}")
        else:
            print("capture failed")
    else:
        print("could not resolve stream url")
