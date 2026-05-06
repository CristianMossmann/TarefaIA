from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _to_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_camera_source(raw_value: str) -> Any:
    if raw_value.isdigit():
        return int(raw_value)
    return raw_value


@dataclass(frozen=True)
class Settings:
    app_title: str
    db_path: Path
    model_path: str
    confidence_threshold: float
    save_dir: Path
    target_classes: set[str]
    min_consecutive_frames: int
    alert_cooldown_seconds: int
    camera_source: Any
    camera_reconnect_seconds: int
    ollama_url: str
    ollama_model: str
    ollama_timeout: int
    ollama_keep_alive: str
    agent_event_limit: int
    templates_dir: Path
    static_dir: Path


def load_settings() -> Settings:
    _read_dotenv_file(PROJECT_ROOT / ".env")

    static_dir = PROJECT_ROOT / "static"
    templates_dir = PROJECT_ROOT / "templates"
    save_dir = static_dir / "captures"

    static_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)
    save_dir.mkdir(parents=True, exist_ok=True)

    target_classes_raw = os.getenv(
        "TARGET_CLASSES", "person,car,truck,bus,motorcycle"
    )
    target_classes = {
        value.strip() for value in target_classes_raw.split(",") if value.strip()
    }

    camera_source_raw = os.getenv("CAMERA_SOURCE", "0")

    return Settings(
        app_title=os.getenv("APP_TITLE", "AgroVision AI"),
        db_path=PROJECT_ROOT / os.getenv("DB_PATH", "detections.db"),
        model_path=os.getenv("MODEL_PATH", "yolov8n.pt"),
        confidence_threshold=_to_float(
            os.getenv("CONFIDENCE_THRESHOLD", "0.45"), 0.45
        ),
        save_dir=save_dir,
        target_classes=target_classes,
        min_consecutive_frames=_to_int(
            os.getenv("MIN_CONSECUTIVE_FRAMES", "3"), 3
        ),
        alert_cooldown_seconds=_to_int(
            os.getenv("ALERT_COOLDOWN_SECONDS", "20"), 20
        ),
        camera_source=_parse_camera_source(camera_source_raw),
        camera_reconnect_seconds=_to_int(
            os.getenv("CAMERA_RECONNECT_SECONDS", "5"), 5
        ),
        ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
        ollama_timeout=_to_int(os.getenv("OLLAMA_TIMEOUT", "120"), 120),
        ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
        agent_event_limit=_to_int(os.getenv("AGENT_EVENT_LIMIT", "12"), 12),
        templates_dir=templates_dir,
        static_dir=static_dir,
    )


settings = load_settings()
