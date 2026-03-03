from __future__ import annotations

import json
from pathlib import Path

from app.config import settings


class WelcomeMediaStore:
    def __init__(self, path: str | None = None):
        self.path = Path(path or settings.WELCOME_MEDIA_STORE_PATH)

    def load(self) -> tuple[str, str] | None:
        if not self.path.exists():
            return None

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        media_type = str(data.get("type", "")).strip().lower()
        file_id = str(data.get("file_id", "")).strip()
        if media_type not in {"photo", "video"} or not file_id:
            return None
        return media_type, file_id

    def save(self, media_type: str, file_id: str) -> None:
        payload = {"type": media_type, "file_id": file_id}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


def resolve_welcome_media() -> tuple[str, str] | None:
    """Приоритет: сохранённая админом медиа -> env-переменные."""
    store_value = WelcomeMediaStore().load()
    if store_value:
        return store_value

    media_type = (settings.WELCOME_MEDIA_TYPE or "").strip().lower()
    media_file_id = (settings.WELCOME_MEDIA_FILE_ID or "").strip()
    if media_type in {"photo", "video"} and media_file_id:
        return media_type, media_file_id

    return None
