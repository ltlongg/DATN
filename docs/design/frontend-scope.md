# Scope Frontend đã chốt (để build)

> Bản gom gọn từ README.md để bắt tay vào thiết kế/triển khai giao diện.
> README.md vẫn là spec gốc đầy đủ; file này là phần **đã chốt cho MVP** + hướng cải tiến sau.
> Cập nhật dần trên file này, không sửa README.

## Nguyên tắc gom

26 chức năng rời rạc trong README được gom thành **4 module lớn**, mỗi module map gần 1:1 với một vùng giao diện. **3 trang cần vẽ cho MVP.**

```
Xác thực & Phân quyền  (nền tảng)
│
├── GIÁO VIÊN
│   ├─ 1. Hỏi đáp có căn cứ          ┐
│   └─ 2. Trực quan hóa sự kiện      ┘ cùng nằm trên TRANG HỎI ĐÁP
│
└── ADMIN
    ├─ 3. Quản lý kho tri thức        
    └─ 4. Quản trị & Vận hành (sau)   
```

## ⚠️ Nguyên tắc bắt buộc: tách biệt Admin và Teacher

Giao diện admin và giao diện teacher **phải tách biệt rõ ràng**, không trộn lẫn:

- **Khu vực / route riêng**: teacher và admin vào hai vùng khác nhau (ví dụ `/` cho hỏi đáp, `/admin/*` cho quản trị). Không nhét chức năng admin chung trang với hỏi đáp.
- **Điều hướng riêng**: teacher KHÔNG nhìn thấy menu/nút dẫn tới khu admin (Quản lý tài liệu, Quản trị & Vận hành).
- **Gác cổng theo role**: route admin chặn cứng ở cả frontend lẫn backend — teacher truy cập thẳng URL admin vẫn bị từ chối.
- **Admin là vai cộng thêm, không phải trang gộp**: admin dùng được trang Hỏi đáp *như một teacher*, nhưng đó là vào đúng khu teacher; còn chức năng quản trị nằm ở khu admin tách riêng. Hai khu không hiển thị đồng thời trên cùng một màn hình.

## Module chung — Xác thực & Phân quyền

Đăng nhập/đăng xuất, xác định role, chặn teacher vào khu admin, admin dùng được cả 2 vai. 2 role: `admin`, `teacher`. Chưa cần đăng ký công khai / quên mật khẩu.
→ **Trang Đăng nhập** + logic gác cổng.

## GIÁO VIÊN

### Module 1 — Hỏi đáp có căn cứ  *(MVP)*
Nhập câu hỏi → agent phân tích & chọn RAG / GraphRAG / hybrid → trả lời tiếng Việt + citation nguồn → hỏi lại nếu mập mờ → báo "chưa đủ dữ liệu" nếu thiếu (không bịa).
→ Phần **chat** của trang Hỏi đáp.

### Module 2 — Trực quan hóa sự kiện (Map + Timeline)  *(MVP)* ⭐
Bản đồ VN + timeline cùng dùng `event_id`; marker/mốc phân biệt **explicit (đậm) vs inferred (nhạt)** theo `confidence`; click một bên → highlight bên kia; xem chi tiết sự kiện. Chỉ bật khi câu trả lời có đủ data.
→ Phần **map + timeline** của trang Hỏi đáp.

⭐ = điểm contribution chính của đồ án, phải làm chắc.

## ADMIN

### Module 3 — Quản lý kho tri thức (Tài liệu)  *(MVP)*
Xem danh sách (tên, loại, trạng thái index, ngày tạo), thêm (mock → upload PDF/DOCX/TXT thật), xóa, xem trạng thái index, số chunk, re-index.
→ **Trang Quản lý tài liệu.**
- MVP: chỉ thêm metadata mock, **chưa** upload file thật (không vẽ dropzone vội).
- Trạng thái index dạng badge rõ state: đang xử lý / xong / lỗi.

### Module 4 — Quản trị & Vận hành 
Một khu "Admin nâng cao", nhiều tab 
- Hội thoại & chất lượng (conversation logs + answer quality monitoring)
- Chi phí (cost dashboard: token, LLM, embedding, cảnh báo ngưỡng)
- Người dùng & quota (tạo/khóa GV, đổi role, quota câu hỏi/chi phí)
- Cấu hình hệ thống (chọn model/embedding, temperature, bật/tắt RAG/GraphRAG/hybrid, version & rollback prompt, ngưỡng hỏi lại / từ chối)

## 3 trang cần vẽ cho MVP

1. **Đăng nhập** (chung)
2. **Hỏi đáp** (teacher + admin) — chat + map + timeline + citation + confidence
3. **Quản lý tài liệu** (admin) — list + thêm/xóa + trạng thái

Admin nâng cao (Module 4) chỉ cần 1 dòng "Sắp ra mắt" trong menu.

## Hướng thiết kế đã chốt

- **Layout trang Hỏi đáp**: chat-first. Mặc định là khung chat ở giữa; map + timeline **chỉ bung ra khi** câu trả lời có sự kiện đủ time/location. Hợp với nguyên tắc "honest về uncertainty" — không ép sinh marker khi thiếu data.
- **Khi bung → split-screen** (KHÔNG floating): **chat bên trái (~45–50%), map bên phải, timeline ngang đáy**. Chọn split-screen vì câu trả lời lịch sử dài + citation cần cột văn bản nền đặc, cuộn được, dễ đọc; đồng thời map không bị panel chat che markers, dễ responsive hơn floating.

```
Mặc định (chưa có data):        Khi câu trả lời CÓ sự kiện:
┌────────────────────┐          ┌──────────────┬──────────────┐
│                    │          │   CHAT       │   BẢN ĐỒ VN  │
│     CHAT giữa      │  ──────► │  answer+nguồn │   ●  ●  ○  ● │
│  [____ hỏi ____]   │          │  [__ hỏi __]  │              │
│                    │          ├──────────────┴──────────────┤
│                    │          │ TIMELINE ●─●─●─●──►          │
└────────────────────┘          └─────────────────────────────┘
```

- Quy tắc hiển thị: thiếu địa điểm → chỉ timeline; thiếu thời gian → chỉ map; không đủ data → không render visualization.
- **Tool thiết kế**: thử cả Google Stitch và Claude (artifacts) rồi so sánh, chốt một, vẽ nốt theo cùng style.
- Tông màu gợi ý: đỏ trầm #A4161A accent, nền be/kem ấm, heading serif + body sans-serif (học thuật, đáng tin).

## Cải tiến sau MVP (chưa làm — ý tưởng làm dày trải nghiệm GV)

- **A. Hội thoại nhiều lượt + lịch sử phiên** — hỏi nối tiếp giữ ngữ cảnh, xem lại phiên cũ. Phô diễn GraphRAG tốt nhất; gần như cần để giống app thật.
- **B. Khám phá chủ động (Explore mode)** — duyệt map + timeline theo giai đoạn mà không cần hỏi, click để đào sâu. Điểm nhấn demo, hợp trình chiếu trên lớp.
- **C. Mang kết quả ra dùng** — copy/xuất câu trả lời, tạo dàn ý bài giảng.
- **D. Đánh giá câu trả lời (👍/👎)** — nhẹ, nuôi dữ liệu cho Answer Quality Monitoring.
- **E. Chế độ xem toàn màn / immersive (floating-over-map)** — map full màn, chat + timeline nổi đè lên (panel nền đặc, timeline mỏng không che markers). Đẹp khi demo/trình chiếu trên lớp, nhưng chỉ là chế độ tùy chọn; mặc định MVP vẫn split-screen.

## UI nhỏ nhưng cần có cho MVP (dễ quên)

- Trạng thái "đang suy nghĩ" / streaming khi agent route + retrieve (vài giây).
- Empty state lần đầu: gợi ý câu hỏi mẫu (tận dụng 4 ví dụ trong README §5).
- Phân biệt rõ marker explicit vs inferred trên UI (đậm/nhạt).
