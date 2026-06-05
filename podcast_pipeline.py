#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"


def log(msg: str):
    print(f"[podcast-pipeline] {msg}")


def run_ffmpeg(cmd: list[str]):
    """Run ffmpeg/ffprobe with basic error handling."""
    log("Running: " + " ".join(cmd))
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        log("ffmpeg error:")
        sys.stderr.write(result.stderr.decode("utf-8", errors="ignore"))
        raise RuntimeError("ffmpeg command failed")
    return result


def require_command(name: str):
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command not found on PATH: {name}")


def require_openai_api_key():
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")


def get_openai_client():
    require_openai_api_key()
    from openai import OpenAI

    return OpenAI()


def validate_existing_chunks(work_dir: Path):
    chunk_files = sorted(work_dir.glob("chunk_*.mp3"))
    if not chunk_files:
        return

    expected_names = [f"chunk_{idx:03d}.mp3" for idx in range(len(chunk_files))]
    actual_names = [path.name for path in chunk_files]
    if actual_names != expected_names:
        raise RuntimeError(
            f"Existing chunk files in {work_dir} are incomplete or not sequential. "
            "Remove the chunks directory and rerun the script."
        )

    empty_files = [path.name for path in chunk_files if path.stat().st_size == 0]
    if empty_files:
        raise RuntimeError(
            f"Existing chunk files are empty: {', '.join(empty_files)}. "
            "Remove the chunks directory and rerun the script."
        )


def split_into_chunks(input_path: Path, work_dir: Path, segment_seconds: int = 600):
    """
    Split the original audio into N chunks (~segment_seconds each).
    Output files: work_dir/chunk_000.mp3, chunk_001.mp3, ...
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    pattern = work_dir / "chunk_%03d.mp3"

    if any(work_dir.glob("chunk_*.mp3")):
        validate_existing_chunks(work_dir)
        log("Chunks already exist and look complete, skipping splitting.")
        return

    cmd = [
        "ffmpeg",
        "-i",
        str(input_path),
        "-f",
        "segment",
        "-segment_time",
        str(segment_seconds),
        "-c",
        "copy",
        str(pattern),
    ]
    run_ffmpeg(cmd)
    log("Splitting completed.")


def convert_chunk_to_m4a(chunk_mp3: Path) -> Path:
    """
    Convert a chunk MP3 to safe M4A:
      - mono (1 channel)
      - 16 kHz sample rate
      - 48 kbps AAC
    Returns the path to the m4a file.
    """
    m4a_path = chunk_mp3.with_suffix(".m4a")

    if m4a_path.exists():
        log(f"{m4a_path.name} already exists, skipping conversion.")
        return m4a_path

    cmd = [
        "ffmpeg",
        "-i",
        str(chunk_mp3),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "aac",
        "-b:a",
        "48k",
        str(m4a_path),
    ]
    run_ffmpeg(cmd)
    return m4a_path


def transcribe_file(audio_path: Path, model: str = TRANSCRIPTION_MODEL) -> str:
    """Call OpenAI audio transcription API on a single file and return text."""
    log(f"Transcribing {audio_path.name} ...")
    client = get_openai_client()
    with audio_path.open("rb") as f:
        resp = client.audio.transcriptions.create(
            file=f,
            model=model,
            response_format="text",
        )
    return resp


def transcribe_file_cached(
    audio_path: Path,
    transcript_path: Path,
    model: str = TRANSCRIPTION_MODEL,
) -> str:
    """Return a chunk transcript, reusing a cached text file when available."""
    if transcript_path.exists():
        cached = transcript_path.read_text(encoding="utf-8").strip()
        if cached:
            log(f"{transcript_path.name} already exists, skipping transcription.")
            return cached

    text = transcribe_file(audio_path, model=model).strip()
    tmp_path = transcript_path.with_name(transcript_path.name + ".tmp")
    tmp_path.write_text(text + "\n", encoding="utf-8")
    tmp_path.replace(transcript_path)
    return text


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end podcast transcription pipeline: split -> convert -> transcribe -> merge."
    )
    parser.add_argument("input", help="Input audio file (mp3/m4a/etc)")
    parser.add_argument(
        "-o",
        "--output",
        help="Output transcript file (default: <basename>_transcript.txt)",
    )
    parser.add_argument(
        "--segment-seconds",
        type=int,
        default=600,
        help="Chunk length in seconds (default: 600 = 10 minutes)",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        log(f"Input file not found: {input_path}")
        sys.exit(1)

    try:
        require_command("ffmpeg")
        require_openai_api_key()
    except Exception as e:
        log(str(e))
        sys.exit(1)

    base = input_path.stem
    work_dir = input_path.parent / f"{base}_chunks"
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_path.with_name(f"{base}_transcript.txt")
    )

    log(f"Input:  {input_path}")
    log(f"Chunks dir: {work_dir}")
    log(f"Output transcript: {output_path}")

    # 1) Split into chunks
    split_into_chunks(input_path, work_dir, segment_seconds=args.segment_seconds)

    # 2) Convert each chunk to safe m4a
    chunk_mp3_files = sorted(work_dir.glob("chunk_*.mp3"))
    if not chunk_mp3_files:
        log("No chunk_*.mp3 files found after splitting. Something went wrong.")
        sys.exit(1)

    chunk_m4a_files: list[Path] = []
    for mp3 in chunk_mp3_files:
        m4a = convert_chunk_to_m4a(mp3)
        chunk_m4a_files.append(m4a)

    # 3) Transcribe each chunk in order and append to final transcript
    log("Starting transcription of all chunks...")
    all_text_parts: list[str] = []
    for idx, m4a_path in enumerate(sorted(chunk_m4a_files)):
        chunk_transcript_path = m4a_path.with_suffix(".txt")
        try:
            text = transcribe_file_cached(m4a_path, chunk_transcript_path)
            header = f"\n\n===== CHUNK {idx:02d} ({m4a_path.name}) =====\n\n"
            all_text_parts.append(header + text.strip())
        except Exception as e:
            log(f"Error transcribing {m4a_path.name}: {e}")
            sys.exit(1)

    if not all_text_parts:
        log("No chunks were successfully transcribed.")
        sys.exit(1)

    # 4) Write final merged transcript
    output_path.write_text("".join(all_text_parts), encoding="utf-8")
    log(f"Done. Final transcript saved to: {output_path}")


if __name__ == "__main__":
    main()
