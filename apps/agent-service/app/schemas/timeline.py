"""Schema cho LLM trích "atomic event" dựng lớp timeline + map.

Dùng làm `response_format` cho OpenAI Structured Outputs (strict json_schema).
Như `EntityExtraction`/`GraphExtraction`: strict mode KHÔNG cho default => mọi
field bắt buộc, LLM phải trả đủ. Dùng chuỗi rỗng "" thay cho "không có" (strict
không cho `None`); khi ghi DB sẽ convert "" -> NULL.

Đơn vị: **1 AtomicEvent = 1 diễn biến cụ thể + mốc thời gian + (các) địa điểm của
mốc đó**. Diễn biến là bắt buộc; thời gian/địa điểm ưu tiên đủ nhưng chấp nhận thiếu
một vế (thiếu thời gian -> chỉ map; thiếu địa điểm -> chỉ timeline). Một sự kiện lớn
nhiều mốc rời -> nhiều AtomicEvent cùng `parent_event` (gom ở reconcile).

Kết quả trả về theo TỪNG CHUNK (`chunk_results`), không phải một danh sách phẳng cho
cả unit: LLM đọc trọn unit để có ngữ cảnh nhưng phải quy mỗi event về đúng chunk chứa
bằng chứng -> provenance ở cấp chunk, UI chỉ hiện timeline của chunk thực sự được dùng.

ĐỊA ĐIỂM tách làm hai vai (v8, xem `prompts/timeline_extract.py`): `locations` chỉ chứa
thứ chấm được MỘT ĐIỂM lên bản đồ, còn mọi thứ "quá to để chấm" (vùng trên cấp tỉnh,
quốc gia, sông, đường, biên giới) dồn vào `location_anchor` — nơi căn khung nhìn và làm
ngữ cảnh geocode. `location_scope` quyết định có chấm marker hay không.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Thang độ chắc chắn dùng chung cho timeline/map (đồng bộ với AliasVerdict).
Confidence = Literal["cao", "vừa", "thấp"]

# Sự kiện xảy ra TẠI các địa danh liệt kê ('sites'), hay TRẢI RỘNG trên vùng
# `location_anchor` ('area'), hay không rõ ở đâu ('none'). Quyết định builder có chấm
# marker hay không: chỉ 'sites' mới sinh marker.
LocationScope = Literal["sites", "area", "none"]

# Địa điểm lấy từ chính câu kể diễn biến ('text') hay suy từ ngữ cảnh đoạn/heading
# ('context'). 'context' vẫn render nhưng nhạt hơn — người đọc biết đó là suy ra.
LocationSource = Literal["text", "context", "none"]

# Thứ hạng confidence (cao > vừa > thấp). Một nguồn DUY NHẤT cho mọi nơi cần so sánh:
# reconcile (chọn bản chắc hơn khi gộp), builder (mắt xích yếu nhất khi render marker),
# build_gazetteer (sắp review). Đừng định nghĩa lại tại chỗ.
CONFIDENCE_RANK: dict[str, int] = {"cao": 3, "vừa": 2, "thấp": 1}

class AtomicEvent(BaseModel):
    """Một diễn biến cụ thể (when–where–what), đủ để chấm 1 điểm timeline và (nếu có
    toạ độ) 1 marker map. Chấp nhận thiếu thời gian (chỉ map) hoặc địa điểm (chỉ timeline)."""

    label: str = Field(
        description=(
            "Tên sự kiện NGẮN, tự chứa (vd 'Ký Hiệp ước Nhâm Tuất', 'Quân Pháp "
            "đánh chiếm thành Gia Định'). Không viết cả đoạn."
        )
    )
    summary: str = Field(
        description=(
            "1–2 câu mô tả diễn biến, dùng làm tooltip. Chỉ dựa vào nội dung đoạn, "
            "không bịa."
        )
    )
    time_start: str = Field(
        description=(
            "Mốc bắt đầu, ISO rút gọn: 'YYYY' | 'YYYY-MM' | 'YYYY-MM-DD' "
            "(vd '1862', '1862-03', '1862-06-05'). Suy năm từ ngữ cảnh nếu câu chỉ "
            "ghi tháng/ngày nhưng năm đã rõ trước đó (anchor inheritance) — khi suy "
            "như vậy hãy hạ `confidence`. Mốc mơ hồ ('đầu năm 1945', 'mùa thu') -> chỉ "
            "ghi mức chắc chắn ('1945'), KHÔNG bịa tháng/ngày. Để '' nếu đoạn không cho "
            "biết thời gian, hoặc chỉ có quan hệ trình tự ('sau đó', 'sau hiệp ước')."
        )
    )
    time_end: str = Field(
        description=(
            "Mốc kết thúc nếu sự kiện là KHOẢNG kéo dài (vd chiến dịch), cùng định "
            "dạng ISO rút gọn. Để '' nếu là một thời điểm."
        )
    )
    locations: list[str] = Field(
        description=(
            "Các địa danh CHẤM ĐƯỢC MỘT ĐIỂM nơi diễn biến xảy ra (surface form, giữ "
            "nguyên như văn bản), theo thứ tự xuất hiện. CHỈ nhận cấp tỉnh/thành trở "
            "xuống (tỉnh, thành phố, huyện, xã, đảo, đồi/cứ điểm, công trình, thành "
            "phố nước ngoài). BỎ HẲN — không đưa vào đây mà cũng KHÔNG đưa sang "
            "`location_anchor`: vùng trên cấp tỉnh ('Nam Kì', 'miền Bắc', 'Tây "
            "Nguyên'), khu quân sự ('Liên khu IV'), quốc gia ('Pháp', 'Nhật Bản'), "
            "sông/đường/biên giới/vĩ tuyến, biển và vịnh lớn. Mỗi phần tử đúng MỘT địa "
            "danh, không gộp danh sách, không kèm ngoặc đơn. [] nếu không có nơi nào "
            "hợp lệ."
        )
    )
    location_anchor: str = Field(
        description=(
            "MỘT địa danh bao trùm, CÙNG tập hợp lệ với `locations` (cấp tỉnh/thành "
            "trở xuống). Dùng làm ngữ cảnh tra toạ độ cho tên vi mô (vd 'A1' + anchor "
            "'Điện Biên Phủ') và căn khung bản đồ. Chọn đơn vị nhỏ nhất bao được toàn "
            "bộ `locations`; nếu phải leo lên trên cấp tỉnh mới bao được thì để '' — "
            "anchor rỗng hợp lệ và tốt hơn một anchor không tra được. KHÔNG cần nằm "
            "trong `locations`."
        )
    )
    location_scope: LocationScope = Field(
        description=(
            "'sites': diễn biến xảy ra ĐÚNG TẠI các nơi trong `locations` -> được chấm "
            "marker. 'area': diễn biến TRẢI RỘNG, các tên trong `locations` chỉ là nơi "
            "tiêu biểu được nhắc -> KHÔNG chấm marker. Cả hai đều ĐÒI `locations` khác "
            "rỗng. 'none': không còn nơi nào hợp lệ sau khi lọc (gồm cả khi đoạn chỉ "
            "nêu vùng quá to)."
        )
    )
    location_source: LocationSource = Field(
        description=(
            "'text': địa điểm nêu ngay trong câu kể diễn biến này. 'context': suy từ "
            "ngữ cảnh đoạn hoặc heading (vd cả mục đang nói về một chiến dịch ở Điện "
            "Biên Phủ). 'none': khi `location_scope` = 'none'."
        )
    )
    parent_event: str = Field(
        description=(
            "Tên sự kiện/chiến dịch LỚN bao trùm mốc này (vd 'Khởi nghĩa Trương "
            "Định', 'Chiến dịch Điện Biên Phủ') để gom các mốc rời về một nhóm. "
            "Để '' nếu sự kiện đứng rời, không thuộc chuỗi nào."
        )
    )
    confidence: Confidence = Field(
        description=(
            "Độ chắc chắn của (thời gian + diễn biến): 'cao' khi mốc ghi rõ trong "
            "đoạn; 'vừa'/'thấp' khi phải suy từ ngữ cảnh hoặc mốc mơ hồ. Render "
            "đậm/nhạt theo trường này."
        )
    )

class ChunkEvents(BaseModel):
    """Sự kiện trích được TỪ MỘT chunk trong unit (khớp marker `ref` của prompt)."""

    chunk_ref: str = Field(
        description=(
            "Đúng giá trị `ref` của thẻ <chunk> chứa bằng chứng cho các event bên "
            "dưới (vd '1', '2'). KHÔNG tự đặt ref mới."
        )
    )
    events: list[AtomicEvent] = Field(
        description=(
            "Các event mà chunk này làm bằng chứng. `[]` nếu chunk không có diễn "
            "biến nào đáng lên timeline (hợp lệ, không phải lỗi)."
        )
    )

class TimelineExtraction(BaseModel):
    """Kết quả trích cho một unit: mỗi chunk đầu vào ĐÚNG MỘT phần tử `chunk_results`.

    Thiếu/trùng/lạ `chunk_ref` -> extractor loại cả unit và trích lại (không nhận
    kết quả một phần, vì cache ghi theo chunk nên phần thiếu sẽ âm thầm mất event).
    """

    chunk_results: list[ChunkEvents]
