"""Schema tối giản cho gazetteer do người dùng tự tra toạ độ và điền tay.

Không còn geocode tự động (Google/LLM): `lat`/`lon` = None nghĩa là CHƯA tra, địa
danh đó chỉ lên timeline chứ không có marker. Tra toạ độ bằng
`scripts/latlon_check.html` rồi điền thẳng vào `dataset/gazetteer.json`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GazetteerEntry(BaseModel):
    """Một địa danh và toạ độ WGS84 do người dùng điền tay."""

    display: str
    count: int = Field(default=0, ge=0)
    lat: float | None = None
    lon: float | None = None
    note: str = ""
