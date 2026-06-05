#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen, Request

ITUNES_LOOKUP = "https://itunes.apple.com/lookup"
REQUEST_TIMEOUT_SECONDS = 30


def log(msg: str):
    print(f"[apple-podcast-dl] {msg}")


def extract_ids(apple_url: str):
    """
    Extract show id (id123456...) and episode id (?i=...) from Apple Podcasts URL.
    """
    parsed = urlparse(apple_url)

    # episode id from ?i=987654321
    qs = parse_qs(parsed.query)
    episode_id = None
    if "i" in qs:
        try:
            episode_id = int(qs["i"][0])
        except ValueError:
            pass

    if episode_id is None:
        raise ValueError("Could not find episode id (?i=...) in URL query")

    # show id from path .../id123456789
    m = re.search(r"id(\d+)", parsed.path)
    if not m:
        raise ValueError("Could not find show id (id123456...) in URL path")
    show_id = int(m.group(1))

    return show_id, episode_id


def itunes_lookup_show(show_id: int) -> dict:
    """
    Look up the show and its episodes via iTunes Search API.
    We request entity=podcastEpisode so results include all episodes.
    """
    url = f"{ITUNES_LOOKUP}?id={show_id}&entity=podcastEpisode&limit=200"
    log(f"Fetching iTunes metadata for show: {url}")
    with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        data = resp.read()
    payload = json.loads(data.decode("utf-8"))

    if payload.get("resultCount", 0) == 0:
        raise RuntimeError("iTunes lookup returned no results for this show id")

    return payload


def itunes_lookup_episode(episode_id: int) -> dict:
    """
    Look up one podcast episode directly by its iTunes track id.
    """
    url = f"{ITUNES_LOOKUP}?id={episode_id}"
    log(f"Fetching iTunes metadata for episode: {url}")
    with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        data = resp.read()
    payload = json.loads(data.decode("utf-8"))

    for item in payload.get("results", []):
        if item.get("wrapperType") == "podcastEpisode" and item.get("trackId") == episode_id:
            return item

    raise RuntimeError("iTunes lookup returned no podcast episode for this episode id")


def find_episode_meta(payload: dict, episode_id: int) -> dict:
    """
    From a show lookup result, find the podcastEpisode whose trackId == episode_id.
    """
    results = payload.get("results", [])
    candidates = []
    for item in results:
        if item.get("wrapperType") == "podcastEpisode":
            candidates.append(item)
            if item.get("trackId") == episode_id:
                return item

    # If not found, log debug info and fail
    log(f"Could not find podcastEpisode with trackId={episode_id}")
    if candidates:
        sample_ids = [c.get("trackId") for c in candidates[:10]]
        log(f"Sample episode trackIds from API: {sample_ids}")
    raise RuntimeError("Episode not present in iTunes Search API response")


def sanitize_filename(name: str) -> str:
    name = (name or "episode").strip() or "episode"
    return re.sub(r'[\\/*?:\"<>|]', "_", name)


def guess_extension_from_url(url: str) -> str:
    path = urlparse(url).path
    for ext in (".mp3", ".m4a", ".aac", ".wav", ".ogg"):
        if path.lower().endswith(ext):
            return ext
    return ".mp3"


def download_file(url: str, dest: Path):
    if dest.exists():
        raise FileExistsError(f"Output file already exists: {dest}")

    log(f"Downloading audio:\n  {url}\n  -> {dest}")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    tmp_dest = dest.with_name(dest.name + ".part")
    if tmp_dest.exists():
        tmp_dest.unlink()

    with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp, tmp_dest.open("wb") as f:
        shutil.copyfileobj(resp, f)
    tmp_dest.replace(dest)
    log("Download complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Download an Apple Podcasts episode audio file by episode URL (using iTunes Search API)."
    )
    parser.add_argument("url", help="Apple Podcasts episode URL")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default=".",
        help="Directory to save audio file (default: current directory)",
    )
    args = parser.parse_args()

    # 1. Extract IDs
    try:
        show_id, episode_id = extract_ids(args.url)
        log(f"Show ID: {show_id}, Episode ID: {episode_id}")
    except Exception as e:
        log(f"Error parsing URL: {e}")
        sys.exit(1)

    # 2. Locate the right episode entry
    try:
        ep = itunes_lookup_episode(episode_id)
    except Exception as e:
        log(f"Direct episode lookup failed: {e}")
        log("Falling back to show lookup.")
        try:
            payload = itunes_lookup_show(show_id)
            ep = find_episode_meta(payload, episode_id)
        except Exception as fallback_error:
            log(f"Error finding episode in API response: {fallback_error}")
            sys.exit(1)

    # 3. Get audio URL from episode metadata
    audio_url = ep.get("episodeUrl") or ep.get("previewUrl")
    if not audio_url:
        log(
            "No 'episodeUrl' or 'previewUrl' found in iTunes metadata for this episode. "
            "Cannot determine audio URL."
        )
        log(f"Available keys: {list(ep.keys())}")
        sys.exit(1)

    # 4. Build filename
    title = ep.get("trackName") or ep.get("collectionName") or "episode"
    filename_base = sanitize_filename(title)
    ext = guess_extension_from_url(audio_url)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"{filename_base}{ext}"

    # 5. Download audio
    try:
        download_file(audio_url, dest)
    except Exception as e:
        log(f"Error downloading audio: {e}")
        sys.exit(1)

    log(f"Saved to: {dest.resolve()}")


if __name__ == "__main__":
    main()
