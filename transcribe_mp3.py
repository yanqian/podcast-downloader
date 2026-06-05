#!/usr/bin/env python3
import argparse
import os
import sys


TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"


def main():
    parser = argparse.ArgumentParser(description="Transcribe one audio file and print the text.")
    parser.add_argument("audio_file", help="Input audio file")
    args = parser.parse_args()

    if not os.path.exists(args.audio_file):
        print(f"Input file not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    from openai import OpenAI

    client = OpenAI()
    with open(args.audio_file, "rb") as f:
        transcript = client.audio.transcriptions.create(
            file=f,
            model=TRANSCRIPTION_MODEL,
            response_format="text",
        )

    print(transcript)


if __name__ == "__main__":
    main()
