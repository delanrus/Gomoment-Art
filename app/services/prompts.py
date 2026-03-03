from __future__ import annotations
import yaml
from dataclasses import dataclass
from pathlib import Path

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
                default_quality=v.get("default_quality", "low"),
                model=v.get("model", "gpt-image-1-mini"),
            ))
        return out

    def get_holiday(self, key: str) -> HolidayConfig:
        v = self.data["holidays"][key]
        return HolidayConfig(
            key=key,
            title=v["title"],
            fixed_line=v["fixed_line"],
            prompt_template=v["prompt_template"],
            default_quality=v.get("default_quality", "low"),
            model=v.get("model", "gpt-image-1-mini"),
        )

    def list_phrases(self, holiday_key: str) -> list[str]:
        h = self.data["holidays"][holiday_key]
        return list(h.get("phrases", []))

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
