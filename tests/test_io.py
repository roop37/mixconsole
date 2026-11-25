"""Real synthetic file round trips and optional external decoder coverage."""

import hashlib
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from mixconsole.io import AudioError, file_sha256, load_audio, pcm_sha256, write_audio
from mixconsole.testing.synth import generate_track


@pytest.mark.parametrize("suffix", [".wav", ".flac"])
def test_round_trip_and_deterministic_file_bytes(tmp_path, suffix):
    samples, _ = generate_track(bars=1, seed=5)
    first = write_audio(tmp_path / f"first{suffix}", samples)
    second = write_audio(tmp_path / f"second{suffix}", samples)
    assert first.read_bytes() == second.read_bytes()
    loaded = load_audio(first)
    assert loaded.sample_rate == 44100
    assert loaded.samples.dtype == np.float32
    assert loaded.samples.shape == samples.shape
    np.testing.assert_allclose(loaded.samples, samples, atol=2**-23 if suffix == ".flac" else 0)
    assert loaded.file_sha256 == hashlib.sha256(first.read_bytes()).hexdigest()
    assert loaded.pcm_sha256 == hashlib.sha256(loaded.samples.astype("<f4").tobytes()).hexdigest()
    assert loaded.duration == len(samples) / 44100


def test_file_hash_differs_but_pcm_hash_same_across_lossless_containers(tmp_path):
    # PCM16-representable samples survive PCM24 and float32 containers exactly.
    samples = (np.arange(200, dtype=np.float32).reshape(100, 2) - 100) / 32768
    wav = load_audio(write_audio(tmp_path / "a.wav", samples))
    flac = load_audio(write_audio(tmp_path / "a.flac", samples))
    assert wav.file_sha256 != flac.file_sha256
    assert wav.pcm_sha256 == flac.pcm_sha256


@pytest.mark.parametrize("source_rate", [22050, 44100, 48000])
def test_mono_resampling_preserves_frequency_and_duration(tmp_path, source_rate):
    t = np.arange(source_rate, dtype=np.float32) / source_rate
    mono = 0.2 * np.sin(2 * np.pi * 440 * t)
    path = tmp_path / "mono.wav"
    sf.write(path, mono, source_rate, subtype="FLOAT")
    decoded = load_audio(path)
    assert decoded.samples.shape == (44100, 2)
    np.testing.assert_array_equal(decoded.samples[:, 0], decoded.samples[:, 1])
    peak = np.argmax(np.abs(np.fft.rfft(decoded.samples[:, 0])))
    assert peak == 440


def test_pcm_hash_handles_noncontiguous_samples():
    samples = np.arange(400, dtype=np.float32).reshape(200, 2)[::2]
    assert pcm_sha256(samples) == pcm_sha256(np.ascontiguousarray(samples))


@pytest.mark.parametrize(
    "bad",
    [
        np.zeros((0, 2), dtype=np.float32),
        np.zeros(3, dtype=np.float32),
        np.zeros((3, 1), dtype=np.float32),
        np.zeros((3, 2), dtype=np.float64),
        np.full((3, 2), np.nan, dtype=np.float32),
    ],
)
def test_rejects_invalid_audio(tmp_path, bad):
    with pytest.raises(AudioError):
        write_audio(tmp_path / "bad.wav", bad)
    with pytest.raises(AudioError):
        pcm_sha256(bad)


def test_output_format_and_flac_clipping_rejected(tmp_path):
    samples = np.zeros((2, 2), dtype=np.float32)
    with pytest.raises(AudioError, match="extension"):
        write_audio(tmp_path / "bad.mp3", samples)
    samples[0, 0] = 1.1
    with pytest.raises(AudioError, match="PCM24"):
        write_audio(tmp_path / "bad.flac", samples)


def test_missing_empty_and_nonfinite_input(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_audio(tmp_path / "missing.wav")
    for name, audio in [("empty", np.zeros((0, 2))), ("nan", np.full((2, 2), np.nan))]:
        path = tmp_path / f"{name}.wav"
        sf.write(path, audio, 44100, subtype="FLOAT")
        with pytest.raises(AudioError, match=r"non-empty|finite"):
            load_audio(path)


def test_unsupported_format_without_ffmpeg(tmp_path, monkeypatch):
    path = tmp_path / "bad.audio"
    path.write_bytes(b"not audio")
    monkeypatch.setattr("mixconsole.io.shutil.which", lambda _: None)
    with pytest.raises(AudioError, match="needs ffmpeg"):
        load_audio(path)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="optional ffmpeg is not installed")
def test_ffmpeg_aac_fallback_and_multichannel(tmp_path):
    samples, _ = generate_track(bars=1)
    wav = write_audio(tmp_path / "input.wav", samples)
    compressed = tmp_path / "encoded.m4a"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(wav), "-c:a", "aac", str(compressed)],
        check=True,
    )
    decoded = load_audio(compressed)
    assert decoded.samples.shape[1] == 2
    assert decoded.sample_rate == 44100
    assert abs(decoded.duration - len(samples) / 44100) < 0.05
    assert np.max(np.abs(decoded.samples)) > 0.05
    assert load_audio(compressed).pcm_sha256 == decoded.pcm_sha256
    multi = tmp_path / "surround.wav"
    sf.write(multi, np.tile(samples, (1, 3)), 44100, subtype="FLOAT")
    assert load_audio(multi).samples.shape == samples.shape
    corrupt = tmp_path / "corrupt.bin"
    corrupt.write_bytes(b"not audio")
    with pytest.raises(AudioError, match="could not decode"):
        load_audio(corrupt)


def test_file_hash_stream(tmp_path):
    path = tmp_path / "bytes.bin"
    path.write_bytes(b"abc")
    assert file_sha256(path) == hashlib.sha256(b"abc").hexdigest()
