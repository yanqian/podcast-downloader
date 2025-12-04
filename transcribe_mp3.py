#!/usr/bin/env python3
import sys
from openai import OpenAI

client = OpenAI()  # uses OPENAI_API_KEY from env

if len(sys.argv) < 2:
    print("Usage: transcribe_mp3.py <audio_file>")
    sys.exit(1)

audio_path = sys.argv[1]

with open(audio_path, "rb") as f:
    transcript = client.audio.transcriptions.create(
        file=f,
        model="gpt-4o-mini-transcribe",  # ✅ speech-to-text model
        response_format="text",          # ✅ return plain text
    )

print(transcript)
