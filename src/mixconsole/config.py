"""Validated settings: defaults < platform TOML < MIXCONSOLE_* environment."""

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_config_path, user_data_path
from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


def data_root(override: str | Path | None = None) -> Path:
    """Where projects, ``index.sqlite``, ``jobs.sqlite`` and the server token live."""
    if override is not None:
        return Path(override).expanduser()
    configured = load_settings().data_dir
    return configured.expanduser() if configured else user_data_path("mixconsole")


def config_path() -> Path:
    override = os.environ.get("MIXCONSOLE_CONFIG")
    return Path(override) if override else user_config_path("mixconsole") / "config.toml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="forbid", env_prefix="MIXCONSOLE_", env_nested_delimiter="__"
    )
    cache_dir: Path | None = Field(default=None, description="Default: ~/.cache/mixconsole.")
    data_dir: Path | None = Field(
        default=None, description="Projects, library index, job history. Default: user data dir."
    )
    job_ram_mb: int | None = Field(
        default=None, ge=256, description="RAM budget for concurrent jobs (default: 60% of RAM)."
    )
    workers: int = Field(default_factory=lambda: min(4, os.cpu_count() or 1), ge=1, le=32)
    backends: dict[str, str] = Field(default_factory=dict)
    candidates_per_family: int = Field(default=10, ge=1, le=60)
    max_candidates: int = Field(default=60, ge=1, le=600)
    max_drift_ms: float = Field(default=5.0, gt=0)
    max_loudness_dip_lu: float = Field(default=1.5, gt=0)
    max_true_peak_dbtp: float = Field(default=-1.0, le=0)
    max_low_overlap_bars: float = Field(default=1.0, ge=0)
    max_stretch: float = Field(default=0.08, gt=0, le=0.25)
    max_vocal_overlap_beats: float = Field(default=1.0, ge=0)
    stems: Literal["off", "auto", "on"] = Field(
        default="off",
        description=(
            "off: stem families are not applicable and no separation runs. "
            "auto: separate stems (extra + weights needed) but allow stem families only for a "
            "concrete reason (key clash or an unavoidable vocal collision) and when the best "
            "stem candidate beats the best plain one by stems_auto_margin. "
            "on: stem families always compete."
        ),
    )
    stems_auto_margin: float = Field(
        default=0.05, ge=0, le=1, description="Score margin a stem candidate needs in auto mode."
    )
    max_stem_leakage: float = Field(
        default=0.25,
        gt=0,
        le=1,
        description=(
            "Separation-bleed gate for stem seams: the energy-weighted |zero-lag correlation| of "
            "the vocal stem with the drums/bass/other stems over the handoff window. Above "
            "this the candidate fails verification."
        ),
    )
    stems_device: Literal["auto", "cpu", "mps", "cuda"] = "auto"
    offline: bool = Field(
        default=False, description="No downloads; currently all models are local."
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return env_settings, init_settings


def load_settings(path: Path | None = None) -> Settings:
    data: dict[str, Any] = {}
    source = path or config_path()
    if source.is_file():
        data = tomllib.loads(source.read_text(encoding="utf-8"))
    # Preserve the initial BACKEND_BEATS spelling as well as pydantic-settings'
    # JSON BACKENDS and nested BACKENDS__BEATS environment forms.
    overrides = {
        kind: value
        for kind in ("beats", "key", "loudness", "sections", "cues", "vocals")
        if (value := os.environ.get(f"MIXCONSOLE_BACKEND_{kind.upper()}"))
    }
    if overrides:
        data["backends"] = {**data.get("backends", {}), **overrides}
    return Settings(**data)
