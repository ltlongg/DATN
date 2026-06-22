"""Test geocoder hybrid: VN bbox, parse Mapbox v6, fallback LLM — mock, không gọi mạng."""

from __future__ import annotations

import httpx

from app.indexing.geocoding import geocoder as G
from app.schemas.gazetteer import GeocodeOutcome, GeocodeResult


def test_in_vietnam() -> None:
    assert G.in_vietnam(21.0285, 105.8542)  # Hà Nội
    assert not G.in_vietnam(48.8566, 2.3522)  # Paris
    assert not G.in_vietnam(0.0, 0.0)


def test_confidence_from_feature_type() -> None:
    assert G._confidence_from_feature_type("place") == "cao"
    assert G._confidence_from_feature_type("locality") == "cao"
    assert G._confidence_from_feature_type("region") == "vừa"
    assert G._confidence_from_feature_type("country") == "thấp"


def _mock_client(payload: dict, status: int = 200) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda _req: httpx.Response(status, json=payload)))


def test_mapbox_parse_dung_thu_tu_lon_lat() -> None:
    # Mapbox v6 trả coordinates = [lon, lat]; phải map đúng -> lat=10.35, lon=106.66.
    payload = {
        "features": [
            {
                "geometry": {"coordinates": [106.6678, 10.3539]},
                "properties": {"feature_type": "place", "full_address": "Gò Công, Tiền Giang, Việt Nam"},
            }
        ]
    }
    with _mock_client(payload) as c:
        out = G._mapbox_geocode("Gò Công", "pk.test", http_client=c)
    assert out is not None
    assert out.resolved_by == "mapbox"
    assert abs(out.lat - 10.3539) < 1e-6
    assert abs(out.lon - 106.6678) < 1e-6
    assert out.confidence == "cao"
    assert "Gò Công" in out.provider_name


def test_mapbox_khong_co_feature_tra_none() -> None:
    with _mock_client({"features": []}) as c:
        assert G._mapbox_geocode("Địa danh lạ", "pk.test", http_client=c) is None


def test_mapbox_khop_nham_ten_bi_loai() -> None:
    # Mapbox trả "đại khái" tên KHÁC hẳn (Bình Cách -> Cách Mạng Tháng Tám) -> phải bỏ.
    payload = {
        "features": [
            {
                "geometry": {"coordinates": [108.8086, 15.1204]},
                "properties": {"feature_type": "street", "full_address": "Cách Mạng Tháng Tám, Quảng Ngãi, Việt Nam"},
            }
        ]
    }
    with _mock_client(payload) as c:
        assert G._mapbox_geocode("Bình Cách", "pk.test", http_client=c) is None


def test_name_matches_bo_dau_va_i_y() -> None:
    assert G._name_matches("Mĩ Tho", "Mỹ Tho, Đồng Tháp, Việt Nam")  # i/y + dấu
    assert G._name_matches("Gia Định", "Gia Dinh, Thành phố Hồ Chí Minh")  # romanized
    assert G._name_matches("Bà Rịa", "Bà Rịa - Sông Pha, Châu Pha")  # đúng tên dù type=street
    assert not G._name_matches("Chợ Lớn", "Chơ Long, Gia Lai")  # lon != long
    assert not G._name_matches("Sơn Trà", "Trần Quốc Thảo, Phan Rang")


def test_mapbox_ngoai_vietnam_tra_none() -> None:
    payload = {"features": [{"geometry": {"coordinates": [2.3522, 48.8566]}, "properties": {"feature_type": "place"}}]}
    with _mock_client(payload) as c:
        assert G._mapbox_geocode("Paris", "pk.test", http_client=c) is None


def test_mapbox_loi_http_tra_none() -> None:
    with _mock_client({"message": "unauthorized"}, status=401) as c:
        assert G._mapbox_geocode("X", "pk.bad", http_client=c) is None


# --- LLM path (fake client) ---

class _FakeMsg:
    refusal = None

    def __init__(self, parsed: GeocodeResult) -> None:
        self.parsed = parsed


class _FakeCompletions:
    def __init__(self, result: GeocodeResult) -> None:
        self._r = result

    def parse(self, **_kwargs: object) -> object:
        return type("C", (), {"choices": [type("Ch", (), {"message": _FakeMsg(self._r)})()]})()


class _FakeClient:
    def __init__(self, result: GeocodeResult) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions(result)})()


def test_llm_geocode_toa_do_0_la_khong_dinh_vi() -> None:
    r = GeocodeResult(lat=0.0, lon=0.0, confidence="thấp", admin_level="", modern_name="", note="mơ hồ")
    out = G._llm_geocode("Căn cứ vô danh", client=_FakeClient(r), model="m")  # type: ignore[arg-type]
    assert out.lat is None and out.lon is None
    assert out.resolved_by == "none"


def test_llm_geocode_hop_le() -> None:
    r = GeocodeResult(lat=21.0285, lon=105.8542, confidence="cao", admin_level="tỉnh", modern_name="", note="")
    out = G._llm_geocode("Hà Nội", client=_FakeClient(r), model="m")  # type: ignore[arg-type]
    assert out.resolved_by == "llm"
    assert abs(out.lat - 21.0285) < 1e-9


# --- Hybrid orchestration ---

def test_hybrid_dung_mapbox_khi_tim_thay(monkeypatch) -> None:
    mb = GeocodeOutcome(lat=21.0, lon=105.8, confidence="cao", resolved_by="mapbox")
    called = {"llm": False}
    monkeypatch.setattr(G, "_mapbox_geocode", lambda *a, **k: mb)

    def _llm(*_a: object, **_k: object) -> GeocodeOutcome:
        called["llm"] = True
        return GeocodeOutcome()

    monkeypatch.setattr(G, "_llm_geocode", _llm)
    with _mock_client({}) as c:
        out = G.geocode_location("Hà Nội", mapbox_token="pk.x", http_client=c, client=object(), model="m")  # type: ignore[arg-type]
    assert out is mb
    assert called["llm"] is False  # Mapbox trúng -> KHÔNG gọi LLM


def test_hybrid_fallback_llm_khi_mapbox_miss(monkeypatch) -> None:
    sentinel = GeocodeOutcome(lat=10.0, lon=106.0, confidence="vừa", resolved_by="llm")
    monkeypatch.setattr(G, "_mapbox_geocode", lambda *a, **k: None)
    monkeypatch.setattr(G, "_llm_geocode", lambda *a, **k: sentinel)
    with _mock_client({}) as c:
        out = G.geocode_location("Tân Hòa", mapbox_token="pk.x", http_client=c, client=object(), model="m")  # type: ignore[arg-type]
    assert out is sentinel
    assert out.resolved_by == "llm"
