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
        # OpenAI SDK ожидает параметр image= (file-like), а не images=[...]
        image_file = io.BytesIO(image_bytes)
        image_file.name = "input.jpg"  # важно: некоторым клиентам нужно имя файла

        resp = self.client.images.edit(
            model=model,
            image=image_file,     # ✅ вот ключевая правка
            prompt=prompt,
            size=size,
            quality=quality,
            output_format="png",
        )

        b64 = resp.data[0].b64_json
        return base64.b64decode(b64)
