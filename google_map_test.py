from __future__ import annotations

import argparse
import html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8088


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def render_map_page(api_key: str, lat: float, lng: float, zoom: int) -> bytes:
    safe_key = html.escape(api_key, quote=True)
    script_key = quote(api_key, safe="")
    page = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Google Maps API Test</title>
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
      max-width: 360px;
      padding: 10px 12px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.94);
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.18);
      font-size: 14px;
      line-height: 1.35;
    }}
  </style>
</head>
<body>
  <div class="status">
    Google Maps API test<br>
    Center: {lat}, {lng}
  </div>
  <div id="map"></div>

  <script>
    async function initMap() {{
      const {{ Map }} = await google.maps.importLibrary("maps");
      const center = {{ lat: {lat}, lng: {lng} }};
      new Map(document.getElementById("map"), {{
        center,
        zoom: {zoom},
        mapTypeControl: true,
        streetViewControl: true,
        fullscreenControl: true
      }});
    }}

    window.gm_authFailure = function () {{
      document.querySelector(".status").innerHTML =
        "Google Maps API key bi tu choi. Kiem tra key, billing, va Maps JavaScript API.";
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
      key: "{script_key}",
      v: "weekly",
    }});

    initMap().catch((error) => {{
      console.error(error);
      document.querySelector(".status").innerHTML =
        "Khong load duoc Google Maps. Mo DevTools console de xem loi chi tiet.";
    }});
  </script>
</body>
</html>"""
    return page.encode("utf-8")


def make_handler(api_key: str, lat: float, lng: float, zoom: int):
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
            body = render_map_page(api_key, page_lat, page_lng, page_zoom)

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.address_string()} - {format % args}")

    return GoogleMapTestHandler


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Serve a tiny Google Maps JavaScript API test page.")
    parser.add_argument("--api-key", default=os.getenv("GOOGLE_MAPS_API_KEY"))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--lat", type=float, default=21.0285, help="Default: Hanoi latitude.")
    parser.add_argument("--lng", type=float, default=105.8542, help="Default: Hanoi longitude.")
    parser.add_argument("--zoom", type=int, default=13)
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit(
            "Missing Google Maps API key. Run with --api-key YOUR_KEY "
            "or add GOOGLE_MAPS_API_KEY=YOUR_KEY to .env"
        )

    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(args.api_key, args.lat, args.lng, args.zoom),
    )
    url = f"http://{args.host}:{args.port}/"
    print(f"Serving Google Maps test page at {url}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
