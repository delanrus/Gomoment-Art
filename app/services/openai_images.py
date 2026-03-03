from __future__ import annotations

import base64
import io
from openai import OpenAI

class OpenAIImageClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def edit_image(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        model: str,
        size: str,
        quality: str,
    ) -> bytes:
        # file-like объект с именем
        bio = io.BytesIO(image_bytes)
        bio.name = "input.jpg"

        resp = self.client.images.edit(
            model=model,
            image=[bio],          # ✅ ВАЖНО: передаём как list (array)
            prompt=prompt,
            size=size,
            quality=quality,
            output_format="png",
        )

        b64 = resp.data[0].b64_json
        return base64.b64decode(b64)
