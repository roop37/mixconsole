"""Canonical audio I/O: float32 stereo, 44.1 kHz, frame-major samples.

SoundFile decodes mono/stereo files, with polyphase resampling when needed.
Other formats and multichannel layouts use an optional ffmpeg subprocess.
PCM hashes cover little-endian float32 interleaved canonical samples only;
file hashes cover the original bytes. Decoder/resampler versions can affect
PCM across environments; repeatability assumes the same software environment.
"""

import hashlib
import math
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf  # pyright: ignore[reportMissingTypeStubs]
from numpy.typing import NDArray
from scipy.signal import resample_poly  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

SAMPLE_RATE = 44_100
Audio = NDArray[np.float32]


class AudioError(ValueError):
    """Audio could not be decoded or does not satisfy the canonical format."""


@dataclass(frozen=True)
class AudioData:
    """Decoded samples and both kinds of content identity."""

    samples: Audio
    pcm_sha256: str
    file_sha256: str
    sample_rate: int = SAMPLE_RATE

    @property
    def duration(self) -> float:
        """Duration of decoded audio in seconds."""
        return len(self.samples) / self.sample_rate


def file_sha256(path: str | Path) -> str:
    """Hash file bytes incrementally, without decoding."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _validate(samples: Audio) -> None:
    if samples.dtype != np.float32 or samples.ndim != 2 or samples.shape[1] != 2:
        raise AudioError("expected float32 audio with shape (frames, 2)")
    if len(samples) == 0 or not np.isfinite(samples).all():
        raise AudioError("audio must be non-empty and contain only finite samples")


def pcm_sha256(samples: Audio) -> str:
    """SHA-256 of 44.1 kHz stereo PCM as C-order little-endian float32 bytes."""
    _validate(samples)
    return hashlib.sha256(samples.astype("<f4", copy=False).tobytes(order="C")).hexdigest()


def _decode_ffmpeg(path: Path) -> Audio:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise AudioError("this format/layout needs ffmpeg; install it and retry")
    command = [
        executable,
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(path.resolve()),
        "-map",
        "0:a:0",
        "-ac",
        "2",
        "-ar",
        str(SAMPLE_RATE),
        "-threads",
        "1",
        "-f",
        "f32le",
        "pipe:1",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise AudioError(f"ffmpeg could not decode {path.name}: {detail}") from exc
    if len(result.stdout) % 8:
        raise AudioError("ffmpeg returned incomplete stereo PCM frames")
    return np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2).astype(np.float32, copy=True)


def load_audio(path: str | Path) -> AudioData:
    """Decode a local file; duplicate mono, preserve stereo, downmix other layouts via ffmpeg."""
    source = Path(path)
    digest = file_sha256(source)
    try:
        raw, rate = sf.read(source, dtype="float32", always_2d=True)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    except (sf.LibsndfileError, ValueError):
        samples = _decode_ffmpeg(source)
    else:
        samples = np.asarray(raw, dtype=np.float32)  # pyright: ignore[reportUnknownArgumentType]
        sample_rate = rate
        if samples.shape[1] > 2:
            samples = _decode_ffmpeg(source)
        else:
            if samples.shape[1] == 1:
                samples = np.repeat(samples, 2, axis=1)
            if sample_rate != SAMPLE_RATE and len(samples):
                divisor = math.gcd(sample_rate, SAMPLE_RATE)
                samples = np.asarray(
                    resample_poly(samples, SAMPLE_RATE // divisor, sample_rate // divisor, axis=0),  # pyright: ignore[reportUnknownArgumentType]
                    dtype=np.float32,
                )
    samples = np.ascontiguousarray(samples, dtype=np.float32)
    return AudioData(samples=samples, pcm_sha256=pcm_sha256(samples), file_sha256=digest)


def write_audio(path: str | Path, samples: Audio) -> Path:
    """Write deterministic WAV (float32) or FLAC (PCM24) at 44.1 kHz.

    FLAC quantizes to 24-bit PCM; values outside [-1, 1) are rejected, not clipped.
    Parent directories must already exist.
    """
    _validate(samples)
    destination = Path(path)
    suffix = destination.suffix.lower()
    if suffix == ".wav":
        # libsndfile adds a wall-clock timestamp to the PEAK chunk for float WAV.
        # Write a standard IEEE float RIFF header so identical PCM yields identical bytes.
        payload = samples.astype("<f4", copy=False).tobytes(order="C")
        with destination.open("wb") as stream:
            stream.write(b"RIFF" + struct.pack("<I", 36 + len(payload)) + b"WAVE")
            stream.write(
                b"fmt " + struct.pack("<IHHIIHH", 16, 3, 2, SAMPLE_RATE, SAMPLE_RATE * 8, 8, 32)
            )
            stream.write(b"data" + struct.pack("<I", len(payload)))
            stream.write(payload)
        return destination
    if suffix == ".flac":
        format_name, subtype = "FLAC", "PCM_24"
        if np.any(samples < -1) or np.any(samples >= 1):
            raise AudioError("FLAC PCM24 samples must be in [-1, 1)")
    else:
        raise AudioError("output extension must be .wav or .flac")
    sf.write(destination, samples, SAMPLE_RATE, format=format_name, subtype=subtype)  # pyright: ignore[reportUnknownMemberType]
    return destination
