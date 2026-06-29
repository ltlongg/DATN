"""Seed 2 user demo cho dev: admin@example.com / teacher@example.com.

Idempotent: bỏ qua user đã tồn tại. CHỈ dùng cho dev/demo — production phải tạo user
qua flow thật, không hardcode mật khẩu.

    python scripts/seed_users.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402
from app.models.user import create_user, get_user_by_email  # noqa: E402
from app.schemas.common import Role  # noqa: E402

_SEED_USERS: list[tuple[str, str, Role, str]] = [
    ("admin@example.com", "Admin Demo", "admin", "admin123"),
    ("teacher@example.com", "Teacher Demo", "teacher", "teacher123"),
]


def main() -> None:
    for email, name, role, password in _SEED_USERS:
        if get_user_by_email(email) is not None:
            print(f"  bỏ qua (đã có): {email}")
            continue
        create_user(email=email, name=name, role=role, password_hash=hash_password(password))
        print(f"  tạo: {email} ({role})")
    print("Seed user demo xong.")


if __name__ == "__main__":
    main()
