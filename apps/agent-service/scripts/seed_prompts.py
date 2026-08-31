r"""Seed managed_prompts + version 1 (production) từ hằng system prompt trong code.

Chạy 1 lần để bootstrap Item 2 (quản lý prompt). Idempotent: key đã có -> bỏ qua, không tạo
trùng. Sau seed, admin sửa/version/promote qua UI; agent đọc version production lúc chạy
(get_active_prompt) và luôn fallback về hằng code nếu DB thiếu.

Nhóm:
  - ONLINE    : plan, resolve, synthesize (orchestrator dùng mỗi câu trả lời — ĐÃ wiring runtime)
  - GUARDRAIL : guardrails_input (ĐÃ wiring runtime)
  - INDEXING  : graph/metadata/timeline/alias (đăng ký + version được, nhưng CHƯA nối
                runtime vào script indexing — chỉ hiệu lực khi re-index, wiring HOÃN)

⚠️ Seed CHỈ tạo key mới. Sửa hằng prompt trong code rồi chạy lại script trần thì KHÔNG có tác
dụng gì — `get_active_prompt` đọc bản production trong DB, hằng code lúc đó chỉ còn là
fallback khi DB hỏng. Muốn đẩy code lên production phải dùng `--publish`: tạo version mới +
archive bản cũ, đúng như nút promote ở UI admin. Không có bước này thì sửa prompt xong tưởng
đã chạy, thực tế agent vẫn dùng bản cũ — hỏng IM LẶNG.

Ví dụ (PowerShell):
    $env:PYTHONIOENCODING="utf-8"
    cd apps/agent-service
    .\venv\Scripts\python.exe scripts/seed_prompts.py                        # seed key mới
    .\venv\Scripts\python.exe scripts/seed_prompts.py --publish --key plan
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_AGENT_SERVICE = Path(__file__).resolve().parents[1]
if str(_AGENT_SERVICE) not in sys.path:
    sys.path.insert(0, str(_AGENT_SERVICE))

from app.prompts import alias_judge, graph_extract, plan, resolve  # noqa: E402
from app.prompts import guardrails_input, metadata_extract, synthesize, timeline_extract  # noqa: E402
from app.tools.prompts.prompt_store import publish_prompt_version, seed_prompt  # noqa: E402

# (key, grp, title, description, content). key = định danh runtime (khớp get_active_prompt).
_REGISTRY: list[tuple[str, str, str, str, str]] = [
    ("plan", "ONLINE", "Phân tích câu hỏi",
     "Rewrite câu hỏi + phân tuyến + phân rã truy vấn tìm kiếm (mỗi câu trả lời).",
     plan.SYSTEM_PROMPT),
    ("resolve", "ONLINE", "Trích mắt xích",
     "Trích một dữ kiện trung gian từ chunk vừa truy hồi, để tra tiếp bước sau "
     "(chỉ chạy ở câu hỏi nhiều chặng).",
     resolve.SYSTEM_PROMPT),
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
    ("alias_judge", "INDEXING", "Phân giải alias",
     "Offline: phán định hai tên có cùng một thực thể không (chưa nối runtime).",
     alias_judge.SYSTEM_PROMPT),
]

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Đẩy hằng prompt trong CODE lên production (tạo version mới, archive bản cũ). "
        "Không có cờ này thì chỉ seed key mới — prompt đã tồn tại giữ nguyên bản trong DB.",
    )
    parser.add_argument(
        "--key",
        action="append",
        help="Chỉ xử lý key này (lặp lại được). Mặc định: tất cả.",
    )
    args = parser.parse_args()

    registry = _REGISTRY
    if args.key:
        wanted = set(args.key)
        registry = [row for row in _REGISTRY if row[0] in wanted]
        missing = wanted - {row[0] for row in registry}
        if missing:
            parser.error(f"key không có trong registry: {', '.join(sorted(missing))}")

    created = published = 0
    for key, grp, title, desc, content in registry:
        if seed_prompt(key, grp, title, desc, content):
            created += 1
            print(f"[seed] tạo mới: {key} ({grp})")
            continue
        if not args.publish:
            print(f"[seed] đã có, bỏ qua: {key}")
            continue
        version_no = publish_prompt_version(key, content, note="publish từ hằng code")
        if version_no is None:
            print(f"[publish] {key}: production đã khớp code, không tạo version mới")
        else:
            published += 1
            print(f"[publish] {key}: -> version {version_no} (production)")
    print(
        f"[seed] xong — {created} prompt mới, {published} version publish / {len(registry)} key."
    )

if __name__ == "__main__":
    main()
