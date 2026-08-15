"""Schema cho nhóm Cấu hình hệ thống (retrieval + synthesize áp dụng LIVE).

`SystemConfigResponse` = 13 field cấu hình + `updated_at` (dùng cho cả GET /api/admin/config
và GET /internal/config — agent-service parse chính schema này). `SystemConfigUpdate` = PATCH
một phần (exclude_unset ở API): mọi field optional, range khớp CHECK ở DB (db.py). Range sai
bị chặn ở tầng Pydantic TRƯỚC khi chạm DB; ràng buộc chéo rerank_top_k <= hybrid_candidate_k
kiểm khi CẢ HAI cùng gửi, còn lại để DB CHECK làm lưới an toàn cuối (map -> 422 ở model layer).
Xem docs/plan/system-config-plan.md.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

class SystemConfigResponse(BaseModel):
    # --- retrieval ---
    rag_top_k: int
    graph_top_k: int
    hybrid_candidate_k: int
    hybrid_rrf_k: int
    rerank_top_k: int
    bm25_top_k: int
    graph_max_seed_entities: int
    graph_max_chunks_per_seed: int
    graph_hub_source_count_threshold: int
    graph_max_context_items: int
    graph_max_path_hops: int
    graph_path_hit_weight: float
    # --- synthesize ---
    llm_temperature: float
    updated_at: datetime

class SystemConfigUpdate(BaseModel):
    # --- retrieval (số nguyên dương) ---
    rag_top_k: int | None = Field(default=None, ge=1)
    graph_top_k: int | None = Field(default=None, ge=1)
    hybrid_candidate_k: int | None = Field(default=None, ge=1)
    hybrid_rrf_k: int | None = Field(default=None, ge=1)
    rerank_top_k: int | None = Field(default=None, ge=1)
    bm25_top_k: int | None = Field(default=None, ge=1)
    graph_max_seed_entities: int | None = Field(default=None, ge=1)
    graph_max_chunks_per_seed: int | None = Field(default=None, ge=1)
    graph_hub_source_count_threshold: int | None = Field(default=None, ge=1)
    graph_max_context_items: int | None = Field(default=None, ge=1)
    graph_max_path_hops: int | None = Field(default=None, ge=1)
    graph_path_hit_weight: float | None = Field(default=None, ge=0)
    # --- synthesize ---
    llm_temperature: float | None = Field(default=None, ge=0, le=2)

    @model_validator(mode="after")
    def _reject_explicit_null(self) -> SystemConfigUpdate:
        # `None` mặc định = "không gửi" (exclude_unset bỏ qua). Nhưng client gửi TƯỜNG MINH
        # `null` -> field vào model_fields_set với giá trị None -> exclude_unset GIỮ lại -> lọt
        # xuống UPDATE ... = NULL trên cột NOT NULL (NotNullViolation, chỉ CheckViolation được
        # map 422). Chặn ngay ở schema -> 422 rõ ràng, không chạm DB.
        nulls = [f for f in self.model_fields_set if getattr(self, f) is None]
        if nulls:
            raise ValueError(f"Field không được là null: {', '.join(sorted(nulls))}")
        return self

    @model_validator(mode="after")
    def _check_rerank_within_pool(self) -> SystemConfigUpdate:
        # Chỉ kiểm được khi cả hai cùng gửi trong payload này; PATCH lẻ (chỉ 1 trong 2) dựa
        # vào DB CHECK làm lưới an toàn cuối (models/config.py map CheckViolation -> 422).
        if (
            self.rerank_top_k is not None
            and self.hybrid_candidate_k is not None
            and self.rerank_top_k > self.hybrid_candidate_k
        ):
            raise ValueError("rerank_top_k không được lớn hơn hybrid_candidate_k")
        return self
