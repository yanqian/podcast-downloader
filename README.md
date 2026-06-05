# Podcast Downloader

Personal scripts for downloading Apple Podcasts episodes and transcribing long audio files with OpenAI's transcription API.

## What Is Here

- `apple_podcast_dl.py` downloads an Apple Podcasts episode from an episode URL.
- `podcast_pipeline.py` splits a long audio file, converts chunks to API-friendly audio, transcribes each chunk, and merges the transcript.
- `transcribe_mp3.py` sends one audio file directly to the transcription API and prints the text.

The checked-in audio files, chunk directories, and transcript files are generated artifacts from prior runs, not source code.

## Requirements

- Python 3.9 or newer
- `ffmpeg` available on `PATH`
- An OpenAI API key in `OPENAI_API_KEY`

Install Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

On macOS, install `ffmpeg` with Homebrew if needed:

```bash
brew install ffmpeg
```

## Usage

Download an Apple Podcasts episode:

```bash
python3 apple_podcast_dl.py "https://podcasts.apple.com/...?...&i=EPISODE_ID" -o artifacts/downloads
```

Transcribe a long audio file with chunking:

```bash
python3 podcast_pipeline.py artifacts/downloads/episode.mp3
```

Choose a custom transcript output path:

```bash
python3 podcast_pipeline.py Ilya-Sutskever.mp3 -o transcript.txt
```

Change chunk length, in seconds:

```bash
python3 podcast_pipeline.py Ilya-Sutskever.mp3 --segment-seconds 300
```

Transcribe a single small file directly:

```bash
python3 transcribe_mp3.py test.wav
```

## Generated Files

`podcast_pipeline.py` creates:

- `<audio_basename>_chunks/` containing chunk `.mp3` files and converted `.m4a` files
- `<audio_basename>_chunks/chunk_000.txt` style cached transcript files for each chunk
- `<audio_basename>_transcript.txt` containing the merged transcript

These files can be large and should usually stay out of Git history.

Keep local audio, chunk, transcript, and sample files under `artifacts/`. That directory is ignored by Git.

If a chunk transcript cache already exists and is non-empty, rerunning the pipeline reuses it instead of calling the transcription API again.

If an existing chunks directory contains missing or empty chunk files, the pipeline stops and asks you to remove that chunks directory before rerunning. If any chunk transcription fails, the script exits instead of writing a partial final transcript.

`apple_podcast_dl.py` does not overwrite an existing output file. Move or remove the existing file before downloading the same episode again.

## Tests

Run the unit tests with:

```bash
python3 -m unittest
```
