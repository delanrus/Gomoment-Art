from __future__ import annotations

import base64
import io
from openai import BadRequestError, OpenAI


class OpenAIBillingLimitError(RuntimeError):
    """Raised when OpenAI rejects request due to exhausted billing balance."""


class OpenAIImageClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def _generate_with_reference_image(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        model: str,
        size: str,
        quality: str,
    ) -> bytes:
        """Generate image via Responses API and pass source photo explicitly as reference image."""
        data_url = f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        response = self.client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Используй загруженное изображение как reference image и основу композиции. "
                                "Сохрани идентичность человека на фото и выполни запрос ниже:\n\n"
                                f"{prompt}"
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": data_url,
                        },
                    ],
                }
            ],
            tools=[
                {
                    "type": "image_generation",
                    "model": model,
                    "size": size,
                    "quality": quality,
                    "output_format": "png",
                }
            ],
        )
        for output in getattr(response, "output", []):
            for content in getattr(output, "content", []):
                if getattr(content, "type", "") == "output_image" and getattr(content, "image_base64", None):
                    return base64.b64decode(content.image_base64)
        raise RuntimeError("Image generation failed: Responses API returned no output_image")

    def _edit_with_images_api(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        model: str,
        size: str,
        quality: str,
    ) -> bytes:
        """Fallback for compatibility: classic Images Edit API."""
        bio = io.BytesIO(image_bytes)
        bio.name = "input.jpg"
        resp = self.client.images.edit(
            model=model,
            image=[bio],
            prompt=prompt,
            size=size,
            quality=quality,
            output_format="png",
        )
        b64 = resp.data[0].b64_json
        return base64.b64decode(b64)

    def edit_image(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        model: str,
        size: str,
        quality: str,
    ) -> bytes:
        try:
            return self._generate_with_reference_image(
                image_bytes=image_bytes,
                prompt=prompt,
                model=model,
                size=size,
                quality=quality,
            )
        except BadRequestError as exc:
            error_code = getattr(exc, "code", None)
            if error_code == "billing_hard_limit_reached":
                raise OpenAIBillingLimitError("OpenAI billing hard limit reached") from exc
            # If reference-image flow is temporarily unavailable, fallback to Images API edit.
            return self._edit_with_images_api(
                image_bytes=image_bytes,
                prompt=prompt,
                model=model,
                size=size,
                quality=quality,
            )
