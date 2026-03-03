from __future__ import annotations
import base64
from openai import OpenAI

class OpenAIImageClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def edit_image(self, *, image_bytes: bytes, prompt: str, model: str, size: str, quality: str) -> bytes:
        resp = self.client.images.edit(
            model=model,
            prompt=prompt,
            images=[{
                "image_url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("utf-8")
            }],
            size=size,
            quality=quality,
            output_format="png",
        )
        b64 = resp.data[0].b64_json
        return base64.b64decode(b64)
