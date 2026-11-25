"""Shared bounded-resolution DSP features; untyped upstream APIs isolated here."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from mixconsole.io import Audio

# These packages do not publish complete type stubs. Our public boundaries are typed.
librosa: Any = import_module("librosa")
signal: Any = import_module("scipy.signal")
ndimage: Any = import_module("scipy.ndimage")
FloatArray = NDArray[np.float64]
Float32Array = NDArray[np.float32]


@dataclass
class Features:
    mono: FloatArray
    sr: int
    hop: int
    spectrum: Float32Array  # |STFT| at sr/4, float32 for memory
    chroma: FloatArray
    mfcc: FloatArray
    onset: FloatArray

    @property
    def times(self) -> FloatArray:
        return np.arange(self.spectrum.shape[1], dtype=np.float64) * self.hop / self.sr


def extract(audio: Audio, sr: int) -> Features:
    mono = audio.mean(axis=1, dtype=np.float64)
    rate = sr // 4
    # float32 halves the dominant STFT memory (complex64); downstream reductions are float64.
    y = np.asarray(signal.resample_poly(mono, 1, 4), dtype=np.float32)
    y = np.pad(y, (0, max(0, 8192 - len(y))))
    hop = 128
    spectrum = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop)).astype(np.float32, copy=False)
    onset = np.asarray(
        librosa.onset.onset_strength(S=librosa.amplitude_to_db(spectrum), sr=rate, hop_length=hop),
        dtype=np.float64,
    )
    # CQT is decimated in time; all downstream shared features use this grid.
    padded = np.pad(y, (0, max(0, 4096 - len(y))))
    cqt = np.asarray(
        abs(librosa.cqt(padded, sr=rate, hop_length=512, n_bins=72, fmin=librosa.note_to_hz("C1"))),
        dtype=np.float64,
    )
    chroma_coarse = cqt.reshape(6, 12, -1).sum(axis=0)
    times = np.arange(spectrum.shape[1], dtype=np.float64) * hop / rate
    ct = np.arange(chroma_coarse.shape[1], dtype=np.float64) * 512 / rate
    chroma = np.array(
        [cast(FloatArray, np.interp(times, ct, row)) for row in chroma_coarse], dtype=np.float64
    )
    mel = librosa.feature.melspectrogram(S=spectrum**2, sr=rate, n_fft=2048, n_mels=32)
    mfcc = np.asarray(librosa.feature.mfcc(S=librosa.power_to_db(mel), n_mfcc=8), dtype=np.float64)
    return Features(mono, rate, hop, spectrum, chroma, mfcc, onset)
