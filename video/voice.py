"""Local, offline speech service for the Steno explainer video.

Uses macOS `say -o` to synthesize narration, then ffmpeg to convert to WAV.
No cloud TTS and no network calls: everything happens on this machine. This
is the iteration voice (plan section 1); Kokoro, also running locally, is
reserved for the final pass and is not wired in here.

Caching: manim-voiceover's SpeechService.get_cached_result already keys on a
hash of input_data (which includes the narration text and the voice name),
so repeated renders of an unchanged beat reuse the cached audio file instead
of re-running `say`. This module also stamps a short text hash into the
generated filename so cached files are easy to identify on disk.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from manim import logger
from manim_voiceover._typing import VoiceoverData
from manim_voiceover.services.base import PathLike, SpeechService, path_to_string


def _require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(
            f"Required local binary '{name}' was not found on PATH. "
            "This project is local-only: install it (e.g. via brew) rather "
            "than falling back to a network service."
        )


class SayService(SpeechService):
    """SpeechService backed by the macOS `say` command.

    Renders narration text to an AIFF file with `say -o`, then converts it
    to WAV with ffmpeg (manim-voiceover reads whatever audio format is on
    disk). Caching is by text hash: the hash is embedded in the cache
    filename, and manim-voiceover's own cache index (keyed on input_data)
    skips re-synthesis entirely when the same text and voice are requested
    again.
    """

    def __init__(self, voice: str = "Samantha", rate_wpm: int = 175, **kwargs: object) -> None:
        _require_binary("say")
        _require_binary("ffmpeg")
        self.voice = voice
        self.rate_wpm = rate_wpm
        super().__init__(**kwargs)

    @staticmethod
    def _text_hash(text: str, voice: str, rate_wpm: int) -> str:
        payload = f"{voice}|{rate_wpm}|{text}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    def generate_from_text(
        self,
        text: str,
        cache_dir: PathLike | None = None,
        path: PathLike | None = None,
        **kwargs: object,
    ) -> VoiceoverData:
        if cache_dir is None:
            cache_dir = self.cache_dir
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        input_data = {
            "input_text": text,
            "service": "say",
            "voice": self.voice,
            "rate_wpm": self.rate_wpm,
        }

        cached_result = self.get_cached_result(input_data, cache_dir)
        if cached_result is not None:
            return cached_result

        text_hash = self._text_hash(text, self.voice, self.rate_wpm)

        if path is None:
            audio_path = f"say-{text_hash}.wav"
        else:
            audio_path = path_to_string(path)

        wav_path = cache_dir / audio_path
        aiff_path = cache_dir / f"say-{text_hash}.aiff"

        if not wav_path.exists():
            logger.info(f"Synthesizing with `say` (voice={self.voice}): {text[:60]!r}")
            subprocess.run(
                [
                    "say",
                    "-v",
                    self.voice,
                    "-r",
                    str(self.rate_wpm),
                    "-o",
                    str(aiff_path),
                    text,
                ],
                check=True,
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(aiff_path),
                    "-ar",
                    "44100",
                    "-ac",
                    "1",
                    str(wav_path),
                ],
                check=True,
            )
            aiff_path.unlink(missing_ok=True)

        json_dict: VoiceoverData = {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
        }
        return json_dict


__all__ = ["SayService"]
