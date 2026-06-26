"""Smoke test Google Geocoding API.

Chạy từ thư mục ``apps/agent-service``:
    $env:GOOGLE_MAPS_API_KEY="AIza..."
    python scripts/test_google_geocoding.py "Hồ Hoàn Kiếm, Hà Nội"

Hoặc thêm GOOGLE_MAPS_API_KEY vào file .env ở gốc repository.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Google forward geocoding")
    parser.add_argument("query", nargs="?", default="Hồ Hoàn Kiếm, Hà Nội")
    args = parser.parse_args()

    # Cho phép chạy thuận tiện từ bất kỳ thư mục nào, vẫn đọc .env dùng chung.
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Thiếu GOOGLE_MAPS_API_KEY. Hãy set biến môi trường trước khi chạy.", file=sys.stderr)
        return 2

    response = httpx.get(
        _GEOCODE_URL,
        params={
            "address": args.query,
            "key": api_key,
            "language": "vi",
            "region": "vn",  # chỉ bias ưu tiên VN, KHÔNG lọc cứng (cho phép địa danh nước ngoài)
        },
        timeout=15,
    )
    response.raise_for_status()
    body = response.json()

    # Google trả HTTP 200 kèm status trong body -> phải kiểm tra thủ công.
    status = body.get("status")
    if status == "ZERO_RESULTS":
        print(f"Không tìm thấy địa điểm: {args.query}")
        return 0
    if status != "OK":
        print(f"Google trả status {status}: {body.get('error_message', '')}", file=sys.stderr)
        return 1

    results = body.get("results", [])
    if not results:
        print(f"Không tìm thấy địa điểm: {args.query}")
        return 0

    place = results[0]
    location = place["geometry"]["location"]
    latitude, longitude = location["lat"], location["lng"]
    print(f"Tên: {place.get('formatted_address', args.query)}")
    print(f"Loại: {', '.join(place.get('types', []))}")
    print(f"Tọa độ: {latitude}, {longitude}")
    print(f"Map: https://www.google.com/maps?q={latitude},{longitude}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPStatusError as error:
        print(f"Google trả về HTTP {error.response.status_code}: {error.response.text}", file=sys.stderr)
        raise SystemExit(1) from error
    except httpx.RequestError as error:
        print(f"Không kết nối được Google: {error}", file=sys.stderr)
        raise SystemExit(1) from error
