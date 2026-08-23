#!/usr/bin/env python3
"""Send captured frame to vision model for behavioral analysis."""

import anthropic
import base64
import json
import sys
from pathlib import Path

SECRETS_DIR = Path(__file__).parent / 'secrets'

with open(SECRETS_DIR / 'anthropic.json') as f:
    cfg = json.load(f)
    client = anthropic.Anthropic(api_key=cfg['api_key'])


def analyze_frame(frame_path):
    with open(frame_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Describe what you see in this frame from a live "
                            "insect colony camera. Focus on individual specimen "
                            "positions, movement patterns, and any notable "
                            "behavioral activity."
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64
                    }
                }
            ]
        }],
        max_tokens=300
    )
    return resp.content[0].text


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: analyze.py <frame.jpg>")
        sys.exit(1)
    print(analyze_frame(sys.argv[1]))
