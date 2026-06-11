"""Cấu hình chung cho test: đảm bảo `app` import được khi chạy pytest."""

from __future__ import annotations

import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parents[1]  # apps/agent-service
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))
