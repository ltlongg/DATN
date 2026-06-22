"""Smoke test Mapbox Geocoding API.

Chạy từ thư mục ``apps/agent-service``:
    $env:MAPBOX_ACCESS_TOKEN="pk..."
    python scripts/test_mapbox_geocoding.py "Ho Chi Minh City"

Hoặc thêm MAPBOX_ACCESS_TOKEN vào file .env ở gốc repository.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Mapbox forward geocoding")
    parser.add_argument("query", nargs="?", default="Hồ Hoàn Kiếm, Hà Nội")
    args = parser.parse_args()

    # Cho phép chạy thuận tiện từ bất kỳ thư mục nào, vẫn đọc .env dùng chung.
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    token = os.getenv("MAPBOX_ACCESS_TOKEN")
    if not token:
        print("Thiếu MAPBOX_ACCESS_TOKEN. Hãy set biến môi trường trước khi chạy.", file=sys.stderr)
        return 2

    response = httpx.get(
        "https://api.mapbox.com/search/geocode/v6/forward",
        params={
            "q": args.query,
            "access_token": token,
            "language": "vi",
            "limit": 1,
        },
        timeout=15,
    )
    response.raise_for_status()

    features = response.json().get("features", [])
    if not features:
        print(f"Không tìm thấy địa điểm: {args.query}")
        return 0

    place = features[0]
    longitude, latitude = place["geometry"]["coordinates"]
    print(f"Tên: {place['properties'].get('full_address', place['properties'].get('name', args.query))}")
    print(f"Tọa độ: {latitude}, {longitude}")
    print(f"Map: https://www.google.com/maps?q={latitude},{longitude}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPStatusError as error:
        print(f"Mapbox trả về HTTP {error.response.status_code}: {error.response.text}", file=sys.stderr)
        raise SystemExit(1) from error
    except httpx.RequestError as error:
        print(f"Không kết nối được Mapbox: {error}", file=sys.stderr)
        raise SystemExit(1) from error
