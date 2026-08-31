"""Schema cho LLM trích entity + quan hệ dựng knowledge graph (Neo4j).

Dùng làm `response_format` cho OpenAI Structured Outputs (strict json_schema). Như
`EntityExtraction`, strict mode KHÔNG cho default => mọi field bắt buộc, LLM phải trả
đủ. Khác pass metadata (times/actors/locations/events, surface form): pass này cho ra
entity CÓ KIỂU (1 trong 12 loại) + quan hệ có hướng, đã canonicalize alias theo
prompt domain (app/prompts/graph_extract.py).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EntityType = Literal[
    "Nhân vật",
    "Cộng đồng",
    "Chính thể/Triều đại",
    "Tổ chức",
    "Địa điểm",
    "Văn hóa khảo cổ",
    "Sự kiện",
    "Văn kiện",
    "Tác phẩm",
    "Chủ trương",
    "Tư tưởng/Tôn giáo",
    "Chức danh",
]

class GraphEntity(BaseModel):
    name: str = Field(
        description=(
            "Tên canonical của thực thể, cụm danh từ ngắn (<8 từ). Chỉ gộp alias "
            "khi chính đoạn văn xác nhận chúng là cùng một thực thể."
        )
    )
    type: EntityType = Field(description="Loại thực thể, đúng 1 trong 12 loại.")
    description: str = Field(
        description="Mô tả ngắn ngôi thứ ba, chỉ dựa vào nội dung đoạn."
    )

class GraphRelation(BaseModel):
    source: str = Field(description="Tên entity nguồn (khớp một name trong entities).")
    target: str = Field(description="Tên entity đích (khớp một name trong entities).")
    keyword: str = Field(
        description="Cụm động từ ngắn (vd 'ký kết', 'lãnh đạo', 'đánh chiếm', 'dẫn đến')."
    )
    description: str = Field(description="Mô tả ngắn về quan hệ, dựa vào nội dung đoạn.")

class GraphExtraction(BaseModel):
    entities: list[GraphEntity]
    relations: list[GraphRelation]
