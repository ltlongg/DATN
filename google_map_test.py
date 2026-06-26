from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5500


def render_map_page(lat: float, lng: float, zoom: int) -> bytes:
    page = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Google Maps API Test — Việt Nam</title>
  <style>
    html, body {{
      height: 100%;
      margin: 0;
      font-family: Arial, sans-serif;
    }}

    #map {{
      height: 100%;
      width: 100%;
    }}

    .status {{
      position: fixed;
      left: 12px;
      top: 12px;
      z-index: 1;
      max-width: 400px;
      padding: 10px 12px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.94);
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.18);
      font-size: 14px;
      line-height: 1.35;
    }}

    .field-row {{
      display: flex;
      gap: 8px;
      margin-top: 8px;
    }}

    .field-row input {{
      min-width: 0;
      flex: 1;
      padding: 7px 8px;
      border: 1px solid #aaa;
      border-radius: 5px;
      font-size: 13px;
    }}

    .field-row button {{
      padding: 7px 10px;
      border: 0;
      border-radius: 5px;
      background: #1a73e8;
      color: white;
      cursor: pointer;
      white-space: nowrap;
    }}

    .hint {{
      margin-top: 6px;
      font-size: 12px;
      color: #666;
      line-height: 1.4;
    }}

    #message {{
      margin-top: 6px;
      font-size: 13px;
    }}

    .legend {{
      margin-top: 6px;
      font-size: 12px;
      display: none;
    }}

    .legend span {{
      display: inline-block;
      width: 12px;
      height: 3px;
      margin-right: 4px;
      vertical-align: middle;
      border-radius: 2px;
    }}
  </style>
</head>
<body>
  <div class="status">
    <strong>Google Maps — Việt Nam</strong>
    <span style="font-size:11px;color:#888;margin-left:6px">region=VN · language=vi</span><br>
    <span style="font-size:12px;color:#555">Center: {lat}, {lng}</span>
    <form id="key-form">
      <div class="field-row">
        <input id="api-key" type="password" autocomplete="off" spellcheck="false"
               placeholder="Google Maps API key" required autofocus>
        <button type="submit">Tải map</button>
      </div>
      <div class="field-row">
        <input id="map-id" type="text" autocomplete="off" spellcheck="false"
               placeholder="Map ID (tùy chọn — để vẽ ranh giới hành chính mới)">
      </div>
    </form>
    <div class="hint">
      <strong>Map ID</strong> cần Vector rendering được bật trong Cloud Console →
      Map Management → chọn map → Rendering type: Vector.<br>
      Để trống nếu chưa có Map ID.
    </div>
    <div id="message"></div>
    <div class="legend" id="legend">
      <span style="background:#E74C3C"></span>Tỉnh/thành (mới)&nbsp;&nbsp;
      <span style="background:#2980B9"></span>Quận/huyện (mới)
    </div>
  </div>
  <div id="map"></div>

  <script>
    const message = document.getElementById("message");

    async function initMap(mapId) {{
      message.textContent = "Đang tải Google Maps...";
      const {{ Map }} = await google.maps.importLibrary("maps");
      const center = {{ lat: {lat}, lng: {lng} }};

      const mapOptions = {{
        center,
        zoom: {zoom},
        mapTypeControl: true,
        streetViewControl: true,
        fullscreenControl: true,
      }};

      if (mapId) {{
        // Vector mode: FeatureLayer hoạt động nhưng styles bị bỏ qua
        // Để ẩn đường, cấu hình trong Cloud Console → Map Styles
        mapOptions.mapId = mapId;
      }} else {{
        // Raster mode: styles có tác dụng, dùng để ẩn đường/transit/POI
        mapOptions.renderingType = "RASTER";
        mapOptions.styles = [
          {{ featureType: "road", stylers: [{{ visibility: "off" }}] }},
          {{ featureType: "transit", stylers: [{{ visibility: "off" }}] }},
          {{ featureType: "poi", stylers: [{{ visibility: "off" }}] }},
        ];
      }}

      const map = new Map(document.getElementById("map"), mapOptions);

      if (mapId) {{
        // Data-Driven Styling: vẽ ranh giới hành chính mới (34 tỉnh/thành sau sáp nhập 2025)
        // Yêu cầu Map ID với Vector rendering được bật trong Cloud Console
        try {{
          const provinceLayer = map.getFeatureLayer("ADMINISTRATIVE_AREA_LEVEL_1");
          provinceLayer.style = {{
            strokeColor: "#E74C3C",
            strokeWeight: 2.0,
            fillColor: "#E74C3C",
            fillOpacity: 0.05,
          }};

          const districtLayer = map.getFeatureLayer("ADMINISTRATIVE_AREA_LEVEL_2");
          districtLayer.style = {{
            strokeColor: "#2980B9",
            strokeWeight: 1.0,
            fillColor: "#2980B9",
            fillOpacity: 0.02,
          }};

          document.getElementById("legend").style.display = "block";
          message.textContent = "✓ Map tải xong. Ranh giới hành chính mới đang hiển thị.";
        }} catch (e) {{
          message.textContent = "Map tải xong nhưng FeatureLayer lỗi — kiểm tra Map ID và bật Vector rendering.";
          console.warn("FeatureLayer error:", e);
        }}
      }} else {{
        message.textContent = "✓ Map tải xong (region=VN). Thêm Map ID để vẽ ranh giới hành chính mới.";
      }}
    }}

    function loadGoogleMaps(apiKey, mapId) {{
      window.gm_authFailure = function () {{
        message.textContent = "API key bị từ chối. Kiểm tra key, billing, và Maps JavaScript API đã được bật.";
      }};

      (g => {{
      var h, a, k, p = "The Google Maps JavaScript API", c = "google", l = "importLibrary",
        q = "__ib__", m = document, b = window;
      b = b[c] || (b[c] = {{}});
      var d = b.maps || (b.maps = {{}}), r = new Set(), e = new URLSearchParams(),
        u = () => h || (h = new Promise(async (f, n) => {{
          await (a = m.createElement("script"));
          e.set("libraries", [...r] + "");
          for (k in g) e.set(k.replace(/[A-Z]/g, t => "_" + t[0].toLowerCase()), g[k]);
          e.set("callback", c + ".maps." + q);
          a.src = `https://maps.${{c}}apis.com/maps/api/js?` + e;
          d[q] = f;
          a.onerror = () => h = n(Error(p + " could not load."));
          a.nonce = m.querySelector("script[nonce]")?.nonce || "";
          m.head.append(a);
        }}));
      d[l] ? console.warn(p + " only loads once. Ignoring:", g) :
        d[l] = (f, ...n) => r.add(f) && u().then(() => d[l](f, ...n));
      }})({{
        key: apiKey,
        v: "weekly",
        region: "VN",
        language: "vi",
      }});

      initMap(mapId).catch((error) => {{
        console.error(error);
        message.textContent = "Không load được Google Maps. Mở DevTools console để xem lỗi.";
      }});
    }}

    document.getElementById("key-form").addEventListener("submit", event => {{
      event.preventDefault();
      const apiKey = document.getElementById("api-key").value.trim();
      const mapId = document.getElementById("map-id").value.trim();
      if (!apiKey) return;

      document.getElementById("api-key").disabled = true;
      document.getElementById("map-id").disabled = true;
      event.currentTarget.querySelector("button").disabled = true;
      loadGoogleMaps(apiKey, mapId);
    }});
  </script>
</body>
</html>"""
    return page.encode("utf-8")


def make_handler(lat: float, lng: float, zoom: int):
    class GoogleMapTestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path not in {"/", "/map"}:
                self.send_error(404, "Not found")
                return

            query = parse_qs(parsed.query)
            page_lat = float(query.get("lat", [lat])[0])
            page_lng = float(query.get("lng", [lng])[0])
            page_zoom = int(query.get("zoom", [zoom])[0])
            body = render_map_page(page_lat, page_lng, page_zoom)

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.address_string()} - {format % args}")

    return GoogleMapTestHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a tiny Google Maps JavaScript API test page.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--lat", type=float, default=21.0285, help="Default: Hanoi latitude.")
    parser.add_argument("--lng", type=float, default=105.8542, help="Default: Hanoi longitude.")
    parser.add_argument("--zoom", type=int, default=13)
    args = parser.parse_args()

    try:
        server = ThreadingHTTPServer(
            (args.host, args.port),
            make_handler(args.lat, args.lng, args.zoom),
        )
    except PermissionError as error:
        raise SystemExit(
            f"Cannot open http://{args.host}:{args.port}/: {error}\n"
            "Try another port, for example: python google_map_test.py --port 5500"
        ) from error
    url = f"http://{args.host}:{args.port}/"
    print(f"Serving Google Maps test page at {url}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
