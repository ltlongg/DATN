"""Mở một bản đồ Google Maps cục bộ với marker cho địa điểm được yêu cầu.

Geocode địa danh qua Google Geocoding API (server-side) rồi render lên Google Maps
JavaScript API (AdvancedMarkerElement + InfoWindow) trong trình duyệt.

Ví dụ:
    python scripts/show_google_map.py "Hồ Hoàn Kiếm, Hà Nội"

Cần `GOOGLE_MAPS_API_KEY` trong .env (bật Geocoding API + Maps JavaScript API cho key).
AdvancedMarkerElement cần Map ID — mặc định dùng "DEMO_MAP_ID"; đặt `GOOGLE_MAPS_MAP_ID`
trong .env để dùng Map ID riêng.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

def geocode(query: str, api_key: str) -> tuple[float, float, str]:
    """Geocode 1 địa danh (region=vn bias, cho phép cả nước ngoài). Trả (lat, lng, formatted_address)."""
    response = httpx.get(
        _GEOCODE_URL,
        params={
            "address": query,
            "key": api_key,
            "language": "vi",
            "region": "vn",  # chỉ bias ưu tiên VN, KHÔNG lọc cứng
        },
        timeout=15,
    )
    response.raise_for_status()
    body = response.json()
    status = body.get("status")
    if status != "OK":
        raise ValueError(f"Google geocode status {status}: {body.get('error_message', '')}")
    results = body.get("results", [])
    if not results:
        raise ValueError(f"Không tìm thấy địa điểm: {query}")

    place = results[0]
    location = place["geometry"]["location"]
    name = place.get("formatted_address") or query
    return float(location["lat"]), float(location["lng"]), name

def page(api_key: str, map_id: str, lat: float, lng: float, name: str) -> bytes:
    values = json.dumps(
        {"key": api_key, "mapId": map_id, "center": {"lat": lat, "lng": lng}, "name": name},
        ensure_ascii=False,
    ).replace("</", "<\\/")
    document = """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Google Maps test</title>
  <style>
    html, body { height: 100%; margin: 0; font: 14px/1.4 system-ui, sans-serif; }
    #map { height: 100vh; width: 100vw; }
    #map-status {
      position: fixed; right: 16px; bottom: 24px; z-index: 2; max-width: 520px;
      padding: 12px 16px; border-radius: 10px; color: #fff; background: #b42318;
      box-shadow: 0 8px 24px rgba(0,0,0,.24);
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <div id="map-status">Đang tải Google Maps…</div>
  <script>
    const status = document.getElementById('map-status');
    function showError(message) {
      status.style.display = 'block';
      status.textContent = `Google Maps lỗi: ${message}`;
    }
    window.gm_authFailure = () =>
      showError('API key bị từ chối. Kiểm tra key, billing, và Maps JavaScript API đã bật.');

    const data = __MAP_DATA__;

    (g => {
      var h, a, k, p = "The Google Maps JavaScript API", c = "google", l = "importLibrary",
        q = "__ib__", m = document, b = window;
      b = b[c] || (b[c] = {});
      var d = b.maps || (b.maps = {}), r = new Set(), e = new URLSearchParams(),
        u = () => h || (h = new Promise(async (f, n) => {
          await (a = m.createElement("script"));
          e.set("libraries", [...r] + "");
          for (k in g) e.set(k.replace(/[A-Z]/g, t => "_" + t[0].toLowerCase()), g[k]);
          e.set("callback", c + ".maps." + q);
          a.src = `https://maps.${c}apis.com/maps/api/js?` + e;
          d[q] = f;
          a.onerror = () => h = n(Error(p + " could not load."));
          m.head.append(a);
        }));
      d[l] ? console.warn(p + " only loads once. Ignoring:", g) :
        d[l] = (f, ...n) => r.add(f) && u().then(() => d[l](f, ...n));
    })({ key: data.key, v: "weekly", region: "VN", language: "vi" });

    async function initMap() {
      const { Map, InfoWindow } = await google.maps.importLibrary("maps");
      const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");

      const map = new Map(document.getElementById('map'), {
        center: data.center,
        zoom: 14,
        mapId: data.mapId,
      });

      const marker = new AdvancedMarkerElement({
        map,
        position: data.center,
        title: data.name,
      });

      const info = new InfoWindow({ content: data.name });
      info.open({ map, anchor: marker });
      marker.addListener('gmp-click', () => info.open({ map, anchor: marker }));

      status.style.display = 'none';
    }

    initMap().catch(err => {
      console.error(err);
      showError(err && err.message ? err.message : 'không khởi tạo được bản đồ');
    });
  </script>
</body>
</html>"""
    return document.replace("__MAP_DATA__", values).encode("utf-8")

def main() -> int:
    parser = argparse.ArgumentParser(description="Hiển thị địa điểm trên Google Maps")
    parser.add_argument("query", nargs="?", default="Hồ Hoàn Kiếm, Hà Nội")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        print("Thiếu GOOGLE_MAPS_API_KEY trong .env để hiển thị map.", file=sys.stderr)
        return 2
    map_id = os.getenv("GOOGLE_MAPS_MAP_ID", "") or "DEMO_MAP_ID"

    lat, lng, name = geocode(args.query, api_key)
    body = page(api_key, map_id, lat, lng, name)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    # Dùng localhost (thay vì 127.0.0.1) để khớp HTTP referrer restriction thường dùng cho dev key.
    url = f"http://localhost:{server.server_port}"
    print(f"Đang mở {name}: {url}")
    print("Nhấn Ctrl+C trong terminal để dừng server.")
    threading.Timer(0.2, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng map server.")
    finally:
        server.server_close()
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, ValueError) as error:
        print(f"Không thể tạo map: {error}", file=sys.stderr)
        raise SystemExit(1) from error
