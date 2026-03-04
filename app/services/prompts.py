from __future__ import annotations
import yaml
from dataclasses import dataclass
from pathlib import Path


class PromptConfigError(ValueError):
    """Raised when YAML prompt configuration is invalid."""

@dataclass(frozen=True)
class HolidayConfig:
    key: str
    title: str
    fixed_line: str
    prompt_template: str
    default_quality: str
    model: str

class PromptsRepo:
    def __init__(self, path: str):
        self.path = Path(path)
        self._data = None

    def reload(self) -> None:
        raw = self.path.read_text(encoding="utf-8")
        self._data = yaml.safe_load(raw)
        self._validate_data(self._data)

    def _validate_data(self, data: dict) -> None:
        if not isinstance(data, dict):
            raise PromptConfigError("prompts file must contain a mapping at top level")

        holidays = data.get("holidays")
        formats = data.get("formats")

        if not isinstance(holidays, dict) or not holidays:
            raise PromptConfigError("'holidays' must be a non-empty mapping")
        if not isinstance(formats, dict) or not formats:
            raise PromptConfigError("'formats' must be a non-empty mapping")

        for key, holiday in holidays.items():
            if not isinstance(holiday, dict):
                raise PromptConfigError(f"holiday '{key}' must be a mapping")
            for required in ("title", "fixed_line", "prompt_template"):
                if not holiday.get(required):
                    raise PromptConfigError(f"holiday '{key}' missing required field '{required}'")

        for fmt, fmt_cfg in formats.items():
            if not isinstance(fmt_cfg, dict) or not fmt_cfg.get("size"):
                raise PromptConfigError(f"format '{fmt}' must contain non-empty 'size'")

    @property
    def data(self) -> dict:
        if self._data is None:
            self.reload()
        return self._data

    def list_holidays(self) -> list[HolidayConfig]:
        out = []
        for k, v in self.data["holidays"].items():
            out.append(HolidayConfig(
                key=k,
                title=v["title"],
                fixed_line=v["fixed_line"],
                prompt_template=v["prompt_template"],
                default_quality=v.get("default_quality", "high"),
                model=v.get("model", "chatgpt-image-latest"),
            ))
        return out

    def get_holiday(self, key: str) -> HolidayConfig:
        v = self.data["holidays"][key]
        return HolidayConfig(
            key=key,
            title=v["title"],
            fixed_line=v["fixed_line"],
            prompt_template=v["prompt_template"],
            default_quality=v.get("default_quality", "high"),
            model=v.get("model", "chatgpt-image-latest"),
        )

    def list_phrases(self, holiday_key: str) -> list[str]:
        if not self.has_holiday(holiday_key):
            return []
        h = self.data["holidays"][holiday_key]
        return list(h.get("phrases", []))

    def has_holiday(self, key: str) -> bool:
        return key in self.data.get("holidays", {})

    def has_format(self, fmt: str) -> bool:
        return fmt in self.data.get("formats", {})

    def get_format_size(self, fmt: str) -> str:
        return self.data["formats"][fmt]["size"]

    def render_prompt(self, holiday_key: str, user_phrase: str, fmt: str) -> tuple[str, str, str]:
        h = self.get_holiday(holiday_key)
        prompt = h.prompt_template.format(
            user_phrase=user_phrase.strip(),
            fixed_line=h.fixed_line,
            format=fmt,
        )
        size = self.get_format_size(fmt)
        return prompt, size, h.model



