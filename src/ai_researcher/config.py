"""Configuration loading: YAML presets plus environment overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .sources import Source

PRESETS_DIR = Path(__file__).resolve().parents[2] / "config"


@dataclass
class Config:
    """Everything one run needs."""

    preset: str = "ai"
    sources: list[Source] = field(default_factory=list)
    backend: str = "auto"
    max_entries_per_source: int = 20
    max_new_per_source: int = 8
    state_path: Path = Path("data/seen.json")
    title: str = "Конкуренты — что нового"

    @classmethod
    def load(cls, preset: str = "ai", path: str | Path | None = None) -> Config:
        config_path = Path(path) if path else PRESETS_DIR / f"sources.{preset}.yaml"
        if not config_path.exists():
            available = ", ".join(
                sorted(p.stem.split(".", 1)[1] for p in PRESETS_DIR.glob("sources.*.yaml"))
            )
            raise FileNotFoundError(
                f"config {config_path} not found; available presets: {available or '(none)'}"
            )

        raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        sources = [Source.from_dict(item) for item in raw.get("sources", [])]
        if not sources:
            raise ValueError(f"{config_path} declares no sources")

        return cls(
            preset=str(raw.get("preset", preset)),
            sources=sources,
            backend=os.environ.get("SUMMARIZER_BACKEND", raw.get("backend", "auto")),
            max_entries_per_source=int(raw.get("max_entries_per_source", 20)),
            max_new_per_source=int(raw.get("max_new_per_source", 8)),
            state_path=Path(raw.get("state_path", f"data/seen.{preset}.json")),
            title=str(raw.get("title", "Конкуренты — что нового")),
        )


def available_presets() -> list[str]:
    return sorted(p.stem.split(".", 1)[1] for p in PRESETS_DIR.glob("sources.*.yaml"))
