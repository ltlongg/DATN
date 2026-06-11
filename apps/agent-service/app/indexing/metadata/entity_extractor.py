"""Trích times/actors/locations/events từ một chunk bằng LLM.

Dùng OpenAI Structured Outputs (json_schema STRICT) qua `chat.completions.parse()`:
provider ép constrained-decoding nên output BẢO ĐẢM khớp schema `EntityExtraction`
(đúng 4 khóa, đúng kiểu list[str]) — không cần tự validate/fallback. Yêu cầu model
hỗ trợ strict (gpt-4o-mini trên api.openai.com); gateway DeepSeek không hỗ trợ.

Hàm thuần (chỉ I/O là LLM) để CLI gọi song song.
"""

from __future__ import annotations

from openai import OpenAI

from app.core.config import get_settings
from app.core.llm import get_openai_client
from app.prompts.metadata_extract import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.schemas.metadata import EntityExtraction

__all__ = ["PROMPT_VERSION", "extract_entities"]

_EMPTY = EntityExtraction(times=[], actors=[], locations=[], events=[])


def extract_entities(
    text: str,
    headings: dict[str, str] | None = None,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
) -> EntityExtraction:
    """Trích times/actors/locations/events cho một chunk.

    Raises:
        Exception: lỗi LLM không phục hồi được (CLI bắt và đếm vào lỗi).
    """
    if not text or not text.strip():
        return _EMPTY

    client = client or get_openai_client()
    model = model or get_settings().llm_model

    completion = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(text, headings)},
        ],
        response_format=EntityExtraction,
        # Không set temperature: reasoning models (gpt-5 series) chỉ cho phép default (1),
        # truyền 0 → 400. Schema strict đã ép cấu trúc nên bỏ temperature không ảnh hưởng.
    )
    message = completion.choices[0].message
    if getattr(message, "refusal", None):
        return _EMPTY  # model từ chối -> coi như không trích được
    return message.parsed or _EMPTY
