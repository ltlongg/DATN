r"""Seed managed_prompts + version 1 (production) từ hằng system prompt trong code.

Chạy 1 lần để bootstrap Item 2 (quản lý prompt). Idempotent: key đã có -> bỏ qua, không tạo
trùng. Sau seed, admin sửa/version/promote qua UI; agent đọc version production lúc chạy
(get_active_prompt) và luôn fallback về hằng code nếu DB thiếu.

Nhóm:
  - ONLINE    : build_query, synthesize (orchestrator dùng mỗi câu trả lời — ĐÃ wiring runtime)
  - GUARDRAIL : guardrails_input (ĐÃ wiring runtime)
  - INDEXING  : graph/metadata/timeline/geocode/alias (đăng ký + version được, nhưng CHƯA nối
                runtime vào script indexing — chỉ hiệu lực khi re-index, wiring HOÃN)

Ví dụ (PowerShell):
    $env:PYTHONIOENCODING="utf-8"
    cd apps/agent-service
    .\venv\Scripts\python.exe scripts/seed_prompts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_AGENT_SERVICE = Path(__file__).resolve().parents[1]
if str(_AGENT_SERVICE) not in sys.path:
    sys.path.insert(0, str(_AGENT_SERVICE))

from app.prompts import alias_judge, build_query, geocode, graph_extract  # noqa: E402
from app.prompts import guardrails_input, metadata_extract, synthesize, timeline_extract  # noqa: E402
from app.tools.prompts.prompt_store import seed_prompt  # noqa: E402

# (key, grp, title, description, content). key = định danh runtime (khớp get_active_prompt).
_REGISTRY: list[tuple[str, str, str, str, str]] = [
    ("build_query", "ONLINE", "Dựng truy vấn",
     "Rewrite câu hỏi + trích thực thể + phân tuyến (mỗi câu trả lời).",
     build_query.SYSTEM_PROMPT),
    ("synthesize", "ONLINE", "Tổng hợp câu trả lời",
     "Sinh câu trả lời có căn cứ từ chunk/graph đã truy hồi (mỗi câu trả lời).",
     synthesize.SYSTEM_PROMPT),
    ("guardrails_input", "GUARDRAIL", "Kiểm duyệt đầu vào",
     "Phân loại + chặn câu hỏi vi phạm trước khi xử lý.",
     guardrails_input.SYSTEM_PROMPT),
    ("graph_extract", "INDEXING", "Trích thực thể & quan hệ",
     "Offline: trích entity có kiểu + quan hệ cho GraphRAG (chưa nối runtime).",
     graph_extract.SYSTEM_PROMPT),
    ("metadata_extract", "INDEXING", "Trích metadata chunk",
     "Offline: trích times/actors/locations/events surface form (chưa nối runtime).",
     metadata_extract.SYSTEM_PROMPT),
    ("timeline_extract", "INDEXING", "Trích sự kiện timeline",
     "Offline: trích atomic event (when–where–what) cho timeline/map (chưa nối runtime).",
     timeline_extract.SYSTEM_PROMPT),
    ("geocode", "INDEXING", "Geocode địa danh",
     "Offline: suy toạ độ địa danh khi Google không có (chưa nối runtime).",
     geocode.SYSTEM_PROMPT),
    ("alias_judge", "INDEXING", "Phân giải alias",
     "Offline: phán định hai tên có cùng một thực thể không (chưa nối runtime).",
     alias_judge.SYSTEM_PROMPT),
]


def main() -> None:
    created = 0
    for key, grp, title, desc, content in _REGISTRY:
        if seed_prompt(key, grp, title, desc, content):
            created += 1
            print(f"[seed] tạo mới: {key} ({grp})")
        else:
            print(f"[seed] đã có, bỏ qua: {key}")
    print(f"[seed] xong — {created} prompt mới / {len(_REGISTRY)} tổng.")


if __name__ == "__main__":
    main()
