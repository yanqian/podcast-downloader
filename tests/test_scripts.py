import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apple_podcast_dl
import podcast_pipeline


class ApplePodcastDownloadTests(unittest.TestCase):
    def test_extract_ids_from_episode_url(self):
        url = "https://podcasts.apple.com/us/podcast/show-name/id123456789?i=987654321"

        show_id, episode_id = apple_podcast_dl.extract_ids(url)

        self.assertEqual(show_id, 123456789)
        self.assertEqual(episode_id, 987654321)

    def test_extract_ids_requires_episode_id(self):
        url = "https://podcasts.apple.com/us/podcast/show-name/id123456789"

        with self.assertRaises(ValueError):
            apple_podcast_dl.extract_ids(url)

    def test_sanitize_filename_replaces_path_separators(self):
        self.assertEqual(
            apple_podcast_dl.sanitize_filename('a/b:c*d?"e<f>g|h'),
            "a_b_c_d__e_f_g_h",
        )

    def test_guess_extension_from_url(self):
        self.assertEqual(
            apple_podcast_dl.guess_extension_from_url("https://example.com/audio.m4a"),
            ".m4a",
        )
        self.assertEqual(
            apple_podcast_dl.guess_extension_from_url("https://example.com/audio"),
            ".mp3",
        )


class PodcastPipelineTests(unittest.TestCase):
    def test_validate_existing_chunks_accepts_sequential_nonempty_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            for idx in range(3):
                (work_dir / f"chunk_{idx:03d}.mp3").write_bytes(b"audio")

            podcast_pipeline.validate_existing_chunks(work_dir)

    def test_validate_existing_chunks_rejects_missing_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            (work_dir / "chunk_000.mp3").write_bytes(b"audio")
            (work_dir / "chunk_002.mp3").write_bytes(b"audio")

            with self.assertRaises(RuntimeError):
                podcast_pipeline.validate_existing_chunks(work_dir)

    def test_validate_existing_chunks_rejects_empty_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            (work_dir / "chunk_000.mp3").write_bytes(b"")

            with self.assertRaises(RuntimeError):
                podcast_pipeline.validate_existing_chunks(work_dir)

    def test_transcribe_file_cached_reuses_nonempty_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "chunk_000.m4a"
            transcript_path = Path(tmp) / "chunk_000.txt"
            audio_path.write_bytes(b"audio")
            transcript_path.write_text("cached text\n", encoding="utf-8")

            with mock.patch("podcast_pipeline.transcribe_file") as transcribe_file:
                text = podcast_pipeline.transcribe_file_cached(audio_path, transcript_path)

            self.assertEqual(text, "cached text")
            transcribe_file.assert_not_called()

    def test_transcribe_file_cached_writes_new_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "chunk_000.m4a"
            transcript_path = Path(tmp) / "chunk_000.txt"
            audio_path.write_bytes(b"audio")

            with mock.patch("podcast_pipeline.transcribe_file", return_value="fresh text"):
                text = podcast_pipeline.transcribe_file_cached(audio_path, transcript_path)

            self.assertEqual(text, "fresh text")
            self.assertEqual(transcript_path.read_text(encoding="utf-8"), "fresh text\n")
            self.assertFalse((Path(tmp) / "chunk_000.txt.tmp").exists())


if __name__ == "__main__":
    unittest.main()
