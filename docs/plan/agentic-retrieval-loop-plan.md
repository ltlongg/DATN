# Agentic Retrieval Loop — plan (plan → execute → resolve)

Trạng thái: **CHƯA code** (bản thiết kế chờ duyệt). Chốt hướng 2026-07-30, **sửa lớn cùng
ngày**: bỏ vòng `reflect` tự-chấm-đủ-chưa, thay bằng **todo list phân rã sẵn**
(plan-and-execute) + **panel tiến trình hiện ra cho người dùng**. **Sửa lần 2 sau review
đối chiếu code + corpus (2026-07-31)** — xem §0.3.

Đây là source-of-truth cho hạng mục này. Đọc kèm `orchestrator-plan.md` (flow gốc),
`retrieval-modes-plan.md` (3 mode + quyết định "chọn tay" nay ĐẢO), `citation-viewer-plan.md`.

---

## 0. Quyết định nền

### 0.1 Chốt sáng 2026-07-30 (giữ nguyên)

1. **Mode do agent tự chọn** (đảo quyết định "user CHỌN TAY" 2026-07-01 ở
   `retrieval-modes-plan.md:262`). Lý do đổi: hướng đồ án chuyển trọng tâm sang **agentic
   orchestration** — routing do LLM điều khiển chính là chất agentic. Node `plan` chọn 1
   trong 2 mode cho cả câu hỏi.
2. **Chỉ còn 2 mode auto: `traditional` (dense + BM25) và `hybrid`** (dense + BM25 + graph).
   Mode `graph` đứng-riêng **BỎ khỏi lựa chọn mặc định**, NHƯNG:
   - **Graph subsystem GIỮ NGUYÊN** — vẫn sống bên trong `hybrid` (`retrieve_hybrid` fuse cả
     `search_graph` + path-finding). Đây là phương án (a) đã chốt; KHÔNG gỡ Neo4j/indexing/
     alias/path-finding. Đóng góp graph của đồ án còn nguyên, chỉ đổi cách bọc.
   - **Code path `retrieve_graph` GIỮ** làm **override thủ công** cho demo/đánh giá (so
     traditional vs graph vs hybrid trên cùng câu). Chỉ ẩn khỏi UI mặc định, không xoá.
3. ~~**Vì sao multi-step KHÔNG trùng graph**: `shortestPath` chỉ chạy khi ≥2 seed có tên nên
   câu multi-hop một-tên-ẩn-cầu-nối graph KHÔNG giải được.~~ **SAI — đã bác bằng code
   2026-07-31.** Chỉ **path-finding (C2)** bị gác `len(seeds) >= 2`
   ([graph_store.py:349](../../apps/agent-service/app/tools/graph_rag/graph_store.py#L349)).
   Nhánh **mở rộng 1-hop chạy cho MỌI seed, kể cả seed đơn độc**: `_EXPAND_SEED`
   ([graph_store.py:121-131](../../apps/agent-service/app/tools/graph_rag/graph_store.py#L121-L131))
   dùng `OPTIONAL MATCH (seed)-[r:REL]-(:Entity)`, không có điều kiện số seed. Mà quan hệ
   "kế tục / chỉ huy / kế nhiệm" — đúng loại mắt xích multi-hop cần — chính là **cạnh 1-hop**.

   **Hệ quả (không né):** với 1 seed tên riêng, `hybrid` hiện tại đã kéo về cả chunk nguồn
   của cạnh 1-hop từ seed đó, tức **có sẵn cơ hội trả lời câu multi-hop trong MỘT lượt**.
   B4 (multi-step) vì vậy **mất phần lớn lý lẽ tiên nghiệm**; giá trị của nó giờ **hoàn toàn
   phụ thuộc số đo** ở §10 (đếm bao nhiêu câu multi-hop `hybrid` hiện tại đã trả lời được).
   Đây là **cổng go/no-go của B4**, xem §9.
4. **Multi-step ≠ multi-step *reasoning* bị gạch ở `retrieval-modes-plan.md:265`**: cái bị
   gạch là suy luận nhiều lượt tổng quát. Ở đây là **iterative RETRIEVAL** có trần bước
   chặt (mặc định 2). Ghi rõ để không tự mâu thuẫn với plan cũ.

### 0.2 ĐẢO chiều 2026-07-30 (bản sửa này) — bỏ `reflect`, dùng todo list

5. **Bỏ node `reflect`** (vòng "đã đủ trả lời chưa? → nếu chưa, tự nghĩ sub-query mới").
   Thay bằng **`plan` phân rã sẵn thành todo list có thứ tự + phụ thuộc**, thực thi tuần tự,
   mỗi bước phụ thuộc có một **bước trích mắt xích** (`resolve`) điền vào bước sau.

   **Lý do đảo** (ghi kỹ để sau khỏi quay lại):
   - **Đổi một phán đoán mờ lấy một trích xuất kiểm chứng được.** `reflect` bắt LLM trả lời
     *"đã đủ chưa?"* — chủ quan, không có cách nào biết nó đúng hay bịa. `resolve` hỏi
     *"đọc context này, người kế tục Phan Đình Phùng tên gì?"* — có căn cứ trong text, rỗng
     thì biết ngay là rỗng.
   - **Chữa luôn lỗ thiết kế của `reflect`**: bản cũ cho reflect đọc mỗi `heading_path` +
     quote 240 ký tự ĐẦU chunk (`CITATION_QUOTE_CHARS`) rồi bắt phán "đủ chưa". Chunk thật
     ~2.6K ký tự, đáp án câu khó gần như luôn nằm ở GIỮA → reflect under-confident, lặp thừa.
     `resolve` đưa full text vào được vì output chỉ là một cái tên.
   - **Số bước biết trước** → budget tính được lúc plan, không phải trần mù; và **render
     được panel tiến trình `n/N bước`** (§7.3) — `reflect` không có N nên cùng lắm hiện
     spinner câm.
   - **Tái lập được khi bảo vệ** (§11.2 lo đúng chuyện này): todo list là artefact xem được,
     không phải một biến `sufficient` chạy ngầm.
   - Chi phí LLM **không đổi so với thiết kế `reflect`** (xem bảng §2) — `resolve` thay chỗ
     `reflect`, output ngắn hơn nhiều nên rẻ + nhanh hơn thật.
     ⚠️ **Nói cho chuẩn** (sửa 2026-07-31): "không đổi" đúng ở **SỐ CALL**, và mốc so là
     thiết kế `reflect` — **KHÔNG phải** code hiện tại. So với code đang chạy, câu đơn tuy
     vẫn 2 call nhưng **output token tăng**: `PlanOutput` (thêm `selected_mode` + `steps[]`
     với `id`/`label`/`queries`/`resolve`/`depends_on`) dài hơn `BuildQueryOutput` hẳn một
     bậc. Tức chi phí **có tăng**, chỉ là tăng ở token chứ không ở số lượt gọi.

   Pattern này trong tài liệu là **plan-and-execute / least-to-most decomposition**, đối lập
   với **self-ask with search** (chính là `reflect`). Viết luận văn dùng tên này.

6. **Cái `reflect` làm được mà todo KHÔNG làm được — và cách bù** (không giấu nhược điểm):
   - **Kế hoạch tĩnh không tự sửa.** Bước 1 không tìm thấy gì thì list vẫn hồn nhiên đi tiếp
     với chỗ trống chưa điền → truy vấn rác → chunk nhiễu → tệ hơn cả không làm gì.
     **Bù**: guard bằng CODE (không cần LLM) — `resolve` trả rỗng/`confidence="thấp"` →
     **dừng list ngay**, đánh dấu bước "một phần", đi thẳng sang trả lời với những gì đang có
     (§4.5).
   - **Sai lan truyền.** Bước 1 trích nhầm tên → bước 2 tra nhầm người → **sai một cách tự
     tin, kèm citation đầy đủ** — dạng sai nguy hiểm nhất cho đồ án lịch sử. **Bù**:
     `resolve` bắt buộc trả kèm `confidence` (thang `cao/vừa/thấp` dùng xuyên hệ thống) +
     `source_chunk_ids`; đáp án trung gian vào prompt `synthesize` như **fact có nguồn**,
     KHÔNG phải sự thật hiển nhiên.
   - **`plan` phải đoán độ sâu trước khi thấy dữ liệu.** Chấp nhận được với corpus SGK này
     (thực tế hiếm quá 2 hop), nhưng cap cứng `retrieval_max_steps` + prompt phải có luật
     "câu đơn → 1 bước" thật chặt, nếu không LLM tách 5 bước cho câu đáng lẽ 1.

7. **Multi-query và multi-step gộp làm MỘT cấu trúc**, không phải hai cơ chế rời: mỗi bước
   todo **chứa được nhiều query chạy song song**. Câu đơn = 1 bước 1 query; câu nhiều ý =
   1 bước N query; câu multi-hop = 2 bước. Xem §2.

8. **Thêm panel tiến trình cho NGƯỜI DÙNG** (§7.3) — không phải hạng mục trang trí:
   todo tuần tự làm TTFT xấu đi thấy rõ (2 lượt retrieve nối đuôi), panel này là thuốc giải,
   lấp khoảng chờ bằng thông tin thật thay vì con quay.

### 0.3 Sửa lần 2 — review đối chiếu code + corpus (2026-07-31)

Bản 0.1/0.2 viết xong chưa đối chiếu lại với code đang chạy và với `lichsu.clean.md`. Lần
soát này tìm ra 4 loại lỗi khác hẳn nhau, ghi lại để sau khỏi lặp:

| # | Loại | Nội dung | Sửa ở |
|---|---|---|---|
| 1 | **Bug production** (không phải lỗi plan) | `retrieve_hybrid` đánh rơi chunk nguồn graph — trái với docstring của chính nó | §9 **B0** |
| 2 | **Sai dữ kiện lịch sử** | ví dụ multi-hop mẫu dùng Cao Thắng làm "người kế tục Phan Đình Phùng" — Cao Thắng mất 1893, PĐP mất 1895 | §2.0 |
| 3 | **Khẳng định sai về hệ thống của chính mình** | "graph không giải được câu 1-seed" — 1-hop expand vẫn chạy | §0.1 mục 3 |
| 4 | **Blocker luồng** | `advance()` trả `"retrieve"` mà không ai tăng `current_step` | §4.5 |

Lỗi #4 nghĩa là **plan bản cũ đem code là vỡ ngay**: `advance()` return `"retrieve"` kèm chú
thích "(node retrieve tự tăng)" ở §4.5, trong khi §4.2 lại để `retrieve` đọc
`state["current_step"]` chứ không ghi. Dù chọn nhánh nào thì `after_retrieve` cũng đọc sai
bước. **Cách sửa đã chốt: thêm node `advance_step` — điểm ghi DUY NHẤT** của cả
`current_step`, để guard chỉ có một chỗ ghi và test một chỗ. (Vòng 1 cho nó ghi thêm
`retrieval_step_count`; vòng 2 **bỏ hẳn** biến đó — xem bảng dưới, mục 3.)

Ngoài ra bản này siết lại 3 thứ vốn viết lỏng: **luật `entities` chuyển từ prompt sang guard
code** (§2.1), **gộp chunk giữa các bước KHÔNG cộng RRF** (§4.2), và **thêm trần
`final_context_k`** trước synthesize (§8) — trước đó không có, 2 bước là context vào
synthesize phình gấp đôi mà không ai chặn.

#### Soát vòng 2 (cùng ngày) — 9 điểm, trong đó 3 điểm bắt lỗi do chính vòng 1 tạo ra

| # | Nội dung | Sửa ở |
|---|---|---|
| 1 | **Luật `entities` tự mâu thuẫn**: vòng 1 thêm guard nhưng **giữ nguyên** luật cũ "kiến thức model → `entities`" (§2.1 + prompt §5) — sinh rồi dọn. Và guard so với `resolved.values()` **tại plan-time**, lúc đó `resolved` còn rỗng → guard không chạy được | §2.1, §4.1, §5 |
| 2 | **Bước có `resolve` nhưng 0 chunk vẫn cho bước sau chạy** với `<1>` chưa điền — đúng "truy vấn rác" §0.2 mục 6. Ghi chú "`has_context` đã chặn" của vòng 1 **sai**: nó chỉ chạy ở cuối list | §4.3 |
| 3 | `retrieval_step_count` + `stop_reason="max_steps"` là **guard chết** (validator đã cap, `current_step` đơn điệu); `cfg` trong pseudo-code còn chưa định nghĩa | §3.3, §4.5 |
| 4 | **`retrieval_max_steps` không được nâng lên 3**: guard §4.3 đọc `retrieval` **tích luỹ** → từ 3 bước là `resolve` đọc context lượt trước mà tưởng của mình | §8, §4.1 |
| 5 | **B0 chưa đủ**: B1 thêm 2 lần cắt nữa, invariant Rule B phải tái áp **sau lần cắt cuối của node** | §4.2.1, §9-B0 |
| 6 | **`final_context_k` định nghĩa mập mờ** → test `len(retrieval.chunks) <= k` sẽ phá Rule B lần 2 | §8 |
| 7 | **Hợp đồng SSE thiếu**: id, ai tạo dòng hệ thống, `status` cũ còn dùng không, tick xanh sớm khi còn `resolve`, kết dòng lúc error/abort | §7.3.1 |
| 8 | Dòng validate "2/5 · soạn lại" **không bao giờ xảy ra** (§6 chỉ retry khi 0 hợp lệ) | §7.3 |
| 9 | Đường persist `steps` đi qua **7 chỗ**, vòng 1 mới ghi 3 | §7.3, §12 |

Lỗi 1, 2, 3 là **do vòng 1 gây ra**, không phải tồn tại từ trước — bài học: thêm guard mà
không gỡ luật cũ, và viết ghi chú trấn an ("`has_context` đã chặn") mà không lần lại đường đi,
còn tệ hơn là để nguyên.

---

## 1. Kiến trúc đích

```
START
  → guard_input
  → plan            (1 LLM call: route + selected_mode + steps[] todo list)
  → (route_intent) → { retrieve | clarify | honest_answer | direct_response }
  → retrieve        (chạy SONG SONG mọi query của BƯỚC hiện tại, RRF gộp, tích luỹ)  ←──┐
  → (after_retrieve)                                                                    │
        ├─ bước KHÔNG có `resolve`            → advance_step                            │
        ├─ có `resolve` & ≥1 chunk            → resolve_step                            │
        └─ có `resolve` & 0 chunk → DỪNG list → (has_context)     [§4.3]                │
  → resolve_step    (1 LLM call: trích mắt xích từ context vừa lấy)                     │
  → (after_resolve)                                                                     │
        ├─ trích được → điền placeholder bước sau → advance_step                        │
        └─ rỗng / confidence thấp → DỪNG list → (has_context)                           │
  → advance_step    (NODE, không phải edge fn — điểm GHI duy nhất của current_step)     │
  → (after_advance)                                                                     │
        ├─ còn bước & chưa dừng → retrieve ─────────────────────────────────────────────┘
        └─ hết → (has_context) → synthesize | honest_answer
  → synthesize
  → validate_citations                     (B5 — reinstate, xem §6)
  → (after_validate)
        ├─ có citation hợp lệ → build_visualization
        ├─ confidence="không đủ dữ liệu" → honest_answer
        └─ 0 citation & còn attempt → synthesize (retry, emit `regenerating`)
  → build_visualization → END
```

So flow hiện tại (`graph.py`): `build_query` mở rộng thành `plan`; `retrieve` fan-out +
tích luỹ; thêm `resolve_step` + `advance_step` + `validate_citations`. Các node terminal
(`clarify`/`direct_response`/`honest_answer`) giữ nguyên.

> **`advance_step` phải là NODE, không được là conditional edge.** LangGraph conditional edge
> là hàm THUẦN chỉ trả tên đích — nó **không ghi được state**. Bản trước để `advance()` vừa
> quyết định nhánh vừa (ngầm hiểu) tăng bước là trộn hai việc, và đó chính là blocker §0.3 #4.
> Tách ra: `advance_step` (node, ghi `current_step += 1` — và **chỉ** biến đó, §4.5) →
> `after_advance` (edge fn, chỉ đọc).

---

## 2. Todo list: một cấu trúc, ba loại câu

`plan` sinh `steps[]` — danh sách có thứ tự. Mỗi bước có **nhiều query chạy song song**
(trục ngang) và có thể **phụ thuộc bước trước** (trục dọc).

```jsonc
// Câu multi-hop (khung MINH HOẠ CƠ CHẾ — ví dụ THẬT chưa chốt, xem §2.0)
steps: [
  { id: 1, label: "Xác định <mắt xích>",
    queries: [{ query: "<mô tả mắt xích, chỉ dùng từ trong câu hỏi>",
                entities: ["<tên riêng có TRONG câu hỏi>"] }],
    resolve: "tên của <mắt xích>" },

  { id: 2, label: "Hoạt động của người đó", depends_on: 1,
    queries: [{ query: "<1> hoạt động sau đó", entities: ["<1>"] },
              { query: "<1> bị Pháp xử lý thế nào", entities: ["<1>"] }] }
]
```

### 2.0 Ví dụ multi-hop: cái cũ SAI, cái mới CHƯA có — và đó là một số đo

Bản trước dùng ví dụ **"Người kế tục Phan Đình Phùng làm gì sau đó?" → Cao Thắng**. Ví dụ
này hỏng ở **ba tầng**, đã kiểm bằng corpus:

1. **Sai dữ kiện lịch sử.** `lichsu.clean.md:265` — "Phan Đình Phùng (1847 - 1895), và một
   cộng sự đắc lực của ông là tướng **Cao Thắng (1864 - 1893)**"; `:338` — PĐP hy sinh
   28/12/1895. Cao Thắng **mất trước 2 năm** → không thể là người kế tục.
2. **Câu hỏi có thể KHÔNG có đáp án trong corpus.** `:339` — Hương Khê tan rã đầu 1896 ngay
   sau khi PĐP mất, corpus **không nêu ai kế tục**. Tức đã chọn một ca **honest fallback**
   rồi đem minh hoạ luồng multi-hop **thành công**. Sai từ gốc.
3. **Kể cả nếu đúng thì vẫn không phải multi-hop.** `:314` — "Phan Đình Phùng **giao quyền
   chỉ huy cho Cao Thắng** để ra Bắc": hai mắt xích nằm gọn trong **một đoạn** → một lượt
   retrieval là ra.

**Hai điều kiện BẮT BUỘC của ví dụ thay thế** (thiếu một là vô giá trị):
- **(a) có đáp án thật trong corpus** — không phải ca honest fallback trá hình;
- **(b) không chunk nào chứa sẵn CẢ HAI mắt xích** — nếu có, một lượt retrieval giải xong và
  ví dụ chỉ chứng minh… rằng không cần multi-step.

#### ✅ Ví dụ CHÍNH THỨC (chốt 2026-07-31, đã verify bằng script trên chunk thật)

> **"Người trở thành thủ lĩnh tối cao của nghĩa quân Yên Thế sau khi Đề Nắm bị giết là ai,
> và về sau người đó bị ai sát hại, nhằm mục đích gì?"**

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| (a) có đáp án | ✅ đủ **cả 3 vế** | `lichsu_clean-000031`: *"…trong đó có **Đề Nắm bị giết** vào tháng 4-1892. Để cứu vãn tình thế, **Đề Thám** đã đứng ra tổ chức lại phong trào và **trở thành thủ lĩnh tối cao** của nghĩa quân Yên Thế."* · `lichsu_clean-000035`: *"…**Đề Thám bị hai tên thủ hạ Lương Tam Kỳ giết hại** tại một khu rừng cách chợ Gồm 2 km, **nộp đầu cho Pháp lấy thưởng**."* |
| (b) không chunk nào chứa cả 2 mắt xích | ✅ giao **rỗng** | chunk chứa "Đề Nắm" = {31, 32}; chứa "thủ lĩnh tối cao" = {31}; chứa vụ sát hại = {35}. Không giao |

**Vì sao đây là ca ẩn-cầu-nối thật, không phải multi-hop giả**: **tên "Đề Thám" KHÔNG xuất
hiện trong câu hỏi**. Query dựng đúng luật §2.1 (chỉ dùng chữ trong câu hỏi: "Đề Nắm", "thủ
lĩnh tối cao", "Yên Thế") **không khớp từ vựng** với chunk 35 — chunk đó không hề nhắc "Đề
Nắm". Phải biết tên "Đề Thám" trước thì mới tra được vế sau.

**Lưu ý trung thực khi đo §10-d**: ba chunk trên **cùng nằm trong mục "Diễn biến" của Yên
Thế**, nên một lượt retrieval top-8 vẫn **có thể** vớ được cả hai (cùng chủ đề "Yên Thế"/"Đề
Thám"). (b) chỉ bảo đảm *không chunk nào chứa sẵn cả hai mắt xích* — **không** bảo đảm hybrid
một lượt sẽ thất bại. Đó chính là thứ §10-d phải ĐO, không phải giả định.

**Đã dò và TRƯỢT (2026-07-31)** — ghi lại để khỏi dò lại:

| Ứng viên | Kết quả | Vì sao trượt |
|---|---|---|
| Người kế tục Phan Đình Phùng | ✗ | trượt cả (a) lẫn (b) — xem trên |
| Vua ban chiếu Cần Vương bị đày đi đâu (→ Hàm Nghi → Algeria) | ✗ (b) | chunk `lichsu_clean-000081` chứa đủ "vua Hàm Nghi" + "Cần Vương" + "đi đày tại Algeria" |
| Người kế nhiệm Nguyễn Thiện Thuật ở Bãi Sậy (→ Nguyễn Thiện Kế → Côn Đảo) | ✗ (b) | cùng một chunk (`giao quyền cho em` và `đày đi Côn Đảo`) |
| Người kế nhiệm Trần Phú làm Tổng Bí thư | ✗ (a) | "Trần Phú" xuất hiện đúng 1 chunk và chunk đó không nói ông làm Tổng Bí thư |

> **Bốn lần trượt trước đó không phải công cốc** — nó cho thấy corpus SGK **kể theo nhân
> vật/sự kiện nên hai mắt xích liên quan thường nằm cạnh nhau**, tức câu multi-hop thật là
> **hiếm**. Ví dụ Yên Thế qua được là nhờ hai mắt xích rơi vào **hai giai đoạn cách nhau 21
> năm** (1892 và 1913) nên bị tách mục. **Cổng go/no-go của B4 (§9) vì vậy vẫn giữ nguyên**:
> điều kiện 1 đã đạt (có ví dụ), còn điều kiện 2 (§10-d — hybrid một lượt có giải được
> không) **vẫn phải đo**, và với ví dụ này thì đo được ngay.

- **Placeholder `<N>`** trong `query`/`entities` = giá trị `resolve` của bước `N`. Thay
  bằng CODE (`str.replace`), không nhờ LLM. Bước không còn placeholder nào chưa điền mới
  được chạy.
- `resolve` rỗng ⇒ bước đó chỉ truy hồi, không trích gì, không tốn LLM call.
- `depends_on` chỉ để kiểm tra tính hợp lệ + vẽ UI; thứ tự thực thi là thứ tự `id`.

### 2.1 Luật làm giàu truy vấn — `query` gác bằng PROMPT, `entities` gác bằng CODE

Vấn đề thật, phát hiện khi soát ví dụ cũ (2026-07-30): `plan` rất dễ **chèn kiến thức nội
tại** — câu hỏi không hề nhắc "Hương Khê", model tự thêm vào. Ở ví dụ đó tình cờ đúng; nếu
model nhớ nhầm tên cuộc khởi nghĩa thì cụm từ sai đó đi thẳng vào BM25, kéo về chunk sai với
**điểm từ vựng cao**, và không ai biết.

**Bản 2026-07-31 lần 1 tự mâu thuẫn — đã gỡ.** Lần đó thêm guard code loại `entities` không
có nguồn, **nhưng vẫn giữ nguyên** luật cũ "kiến thức model tự thêm → bỏ vào `entities`" ở
đây và trong prompt §5. Tức: bảo model sinh ra, rồi viết code loại đi. **Vừa tốn token vừa
đẻ warning vô nghĩa.** Chốt lại đúng MỘT luật cho cả hai chỗ.

> 🔴 **§2.1 ĐÃ BỊ THAY (2026-08-03) — đọc phần dưới như bản ghi lịch sử, không phải luật đang
> chạy.** Luật hiện hành: mốc đối chiếu `entities` là **`standalone_query`** (câu model vừa
> viết lại) chứ không phải câu người dùng gõ, nên tên giải ra từ lịch sử hội thoại là **HỢP
> LỆ** nếu đã viết vào câu đó. Kèm theo: **fallback token-match đã XOÁ** (`entity_index.
> token_match` + tham số `query` của `match_seed_entities`/`search_graph` không còn), nên
> `retrieve` truyền thẳng `[]` chứ không đổi thành `None` nữa, và `selected_mode` chọn theo
> "trong `standalone_query` có tên riêng hay không". Lý do: ba đường downstream (synthesize,
> resolve, mọi truy vấn tìm kiếm) vốn đã tin `standalone_query` — bắt riêng đường seed graph
> khớp câu gốc chỉ khoá một cửa trong bốn, mà cái giá là câu nối tiếp mất sạch seed đúng lúc
> đã biết chắc "ông ấy" là ai. Chi tiết: `app/orchestrator/planning.py` (docstring đầu module)
> + `app/prompts/plan.py` (`plan-v6`).

#### Luật (chốt 2026-07-31 lần 2)

| Vế | Nguồn hợp lệ | Cưỡng chế |
|---|---|---|
| `query` | câu hỏi hiện tại · lịch sử hội thoại · `<N>` | **prompt + few-shot** (không guard code) |
| `entities` | **chỉ câu hỏi hiện tại** (nguyên văn) · hoặc placeholder `<N>` | **guard CODE, loại thẳng** |

Với `entities`, **cả ba đường còn lại đều CẤM**:
- ✗ kiến thức nội tại của model (tên khởi nghĩa, niên hiệu, địa danh nó "nhớ");
- ✗ lấy từ lịch sử hội thoại;
- ✗ prompt dạy model sinh rồi để code dọn.

**Vì sao `query` và `entities` khác nhau** (bất đối xứng này là có lý, không phải tuỳ tiện):
rewrite `standalone_query` hợp lệ **buộc phải đổi chữ** — giải đại từ, thêm chủ ngữ từ
history — nên không có cách nào so token mà không giết ca đúng. Còn `entities` là **danh từ
riêng**: hợp lệ thì phải xuất hiện **nguyên văn**. Kiểm được, và kiểm chính xác.

#### Validate CHIA HAI THỜI ĐIỂM (bản lần 1 sai chỗ này)

Bản lần 1 viết guard so `entities` với "câu hỏi ∪ history ∪ `resolved.values()`" **ngay tại
node `plan`**. **Chạy không được**: lúc `plan` chạy thì `resolved` còn rỗng — chưa bước nào
`resolve` cả. Phải tách:

```
Plan-time (node `plan`, §4.1):
    mỗi phần tử entities phải THOẢ MỘT trong hai:
      - literal có trong câu hỏi hiện tại (so sánh sau strip(), không phân biệt hoa-thường)
      - hoặc là placeholder "<N>" hợp lệ (N < id bước hiện tại và bước N có `resolve`)
    không thoả  ->  LOẠI phần tử + ghi warning (không loại im lặng, còn đo được §10)

Execute-time (node `retrieve`, §4.2):
    thay "<N>" bằng resolved[N]
```

> ⚠️ **Guard trả `[]` là GIẾT GRAPH — phải trả `None`.**
> [`match_seed_entities`](../../apps/agent-service/app/tools/graph_rag/graph_store.py#L172-L184)
> phân biệt hai thứ trông giống nhau:
> `seed_mentions=None` → **token-match từ `query`** (fallback tất định, chiến lược 2);
> `seed_mentions=[]` → `is not None` nên đi nhánh 1 với danh sách rỗng → **0 seed, graph tắt
> hẳn**.
> Nên khi guard lọc sạch, `retrieve` phải truyền `None`, **không** truyền `[]`.

**Nhờ đúng cái fallback đó mà luật "cấm entity từ history" gần như không mất gì**: lượt sau
("Ông ấy mất năm nào?") tuy không còn entity literal nào, nhưng `standalone_query` **đã giải
đại từ từ history** rồi mới đi vào `retrieve_hybrid` → `token_match` tự tìm ra "Phan Đình
Phùng" trong chính chuỗi query. Mất seed do LLM cấp, **không** mất seed.

**Và mất mát do cấm kiến thức nội tại cũng gần bằng không** — chính vì §0.1 mục 3: bỏ "Hương
Khê" khỏi seed thì graph **1-hop từ "Phan Đình Phùng" vẫn ra Hương Khê** qua KG. Làm giàu
bằng trí nhớ model ở đây **trùng lặp với việc graph vốn đã làm**, chỉ khác: graph làm bằng
**dữ liệu đã index**, model làm bằng **trí nhớ không kiểm chứng được**.

### 2.2 Số query trong một bước: MODEL quyết, không phải luật cứng

Plan **không ép** tách nhiều query. Model được phép trả **1 query cho câu nhiều ý** nếu nó
thấy một truy vấn phủ đủ — đó là câu trả lời hợp lệ, không phải lỗi.

Lý do để model được quyền dè dặt: multi-query **không tốn thêm LLM call**, nhưng tốn thật ở
**tầng truy hồi** — mỗi query là một lượt embed + Qdrant + BM25 + rerank (+ graph nếu
hybrid). 3 query = gấp 3 khối lượng đó. Chạy song song nên độ trễ không nhân 3, nhưng chi
phí thì có. Cap cứng: `max_queries_per_step` (§8).

> **Hệ quả cho B1** (§9): nếu thực đo cho thấy model hầu như chọn 1 query, giá trị của B1
> giảm hẳn. **Đo trước khi kết luận** — đếm phân bố `len(step.queries)` trên bộ câu eval,
> đừng mặc định multi-query luôn tốt.

| Loại câu | steps | LLM call |
|---|---|---|
| Đơn ("Trương Định hy sinh năm nào") | 1 bước × 1 query | plan + synth = **2** |
| Nhiều ý ("nguyên nhân, diễn biến, kết quả…") | 1 bước × 3 query // | plan + synth = **2** |
| Multi-hop ("người kế tục X làm gì") | 2 bước, bước 1 có `resolve` | plan + resolve + synth = **3** |

**Câu thường không trả giá gì**: không có bước nào `resolve` ⇒ không có LLM call giữa vòng,
tổng vẫn 2 call y hệt hiện tại.

> **KHÔNG độn bước cho oai.** Câu đơn hiện đúng 1 bước truy hồi. Tách 5 bước cho câu 1 hop
> là tự bịa tính agentic — hội đồng hỏi một câu dễ là lộ ngay trên panel §7.3.

---

## 3. Thay đổi schema (agent-service)

### 3.1 `schemas/ask.py`

**`BuildQueryOutput` → đổi tên `PlanOutput`** (giữ alias import cũ 1 release nếu ngại vỡ
test):

```python
class StepQuery(BaseModel):
    query: str                                   # câu tìm kiếm độc lập (có thể chứa "<N>")
    entities: list[str] = Field(default_factory=list)   # seed cho mode hybrid

class PlanStep(BaseModel):
    id: int                                      # 1-based, thứ tự thực thi
    label: str                                   # nhãn tiếng Việt hiện lên UI (§7.3)
    queries: list[StepQuery]                     # chạy SONG SONG trong cùng bước
    resolve: str = ""                            # mô tả mắt xích cần trích; rỗng = không trích
    depends_on: int | None = None                # id bước cung cấp mắt xích

class PlanOutput(BaseModel):
    standalone_query: str                        # GIỮ — fallback + câu gốc rewrite
    mentioned_entities: list[str] = []           # GIỮ — seed toàn cục (union vào mọi query)
    route: RouteDecision                         # GIỮ
    selected_mode: Literal["traditional", "hybrid"] = "hybrid"   # MỚI — auto mode
    steps: list[PlanStep] = []                   # MỚI — rỗng ⇒ 1 bước từ standalone_query
```

**`StepResolveOutput`** (schema mới, thay `ReflectOutput` đã bỏ):

```python
class StepResolveOutput(BaseModel):
    value: str = ""                              # mắt xích trích được ("" = không thấy)
    confidence: Literal["cao", "vừa", "thấp"] = "thấp"
    source_chunk_ids: list[str] = []             # căn cứ, đưa vào prompt synthesize
```

**`AskRequest.mode`**: `RetrievalMode` → `Literal["auto","traditional","graph","hybrid"] =
"auto"`. `auto` = plan tự chọn; giá trị cụ thể = **override** (ép `selected_mode`, bỏ qua
bước chọn của plan; `graph` chỉ dùng cho eval).

**`AskResponse.retrieval_mode`** giữ `Literal["traditional","graph","hybrid","none"]` — plan
chọn 1 lần/câu nên vẫn là 1 giá trị có nghĩa cho event `done` + admin logs.

### 3.2 `schemas/retrieval.py`
`RetrievalMode` giữ nguyên `Literal["traditional","graph","hybrid"]` (nội bộ retrieve). Thêm
`"auto"` **KHÔNG** ở đây — `auto` chỉ là input, resolve thành 1 trong 3 trước khi tới retrieve.

### 3.3 `orchestrator/state.py` (`AgentState`)

```python
override_mode: Literal["auto","traditional","graph","hybrid"]  # từ request.mode (đổi tên requested_mode)
selected_mode: RetrievalMode              # plan set (hoặc = override nếu override != auto)
steps: list[PlanStep]                     # todo list
current_step: int                         # index bước đang chạy (0-based) — CHỈ `advance_step` ghi
resolved: dict[int, str]                  # step_id -> giá trị đã trích (điền placeholder)
resolved_facts: list[dict]                # {step_id, label, value, confidence, source_chunk_ids}
step_states: list[dict]                   # trạng thái cho UI + persist (§7.3)
stop_reason: str                          # "" | "unresolved"   (BỎ "max_steps" — xem §4.5)
# retrieval_step_count — ĐÃ BỎ (guard chết, trùng với validator + current_step; §4.5)
# retrieval: RetrievalResult — GIỮ, nhưng retrieve node TÍCH LUỸ (union dedupe) qua các bước
```

`retrieval` không dùng reducer add (RetrievalResult không cộng được) — node `retrieve` tự
merge kết quả mới vào `state["retrieval"]` cũ (union theo `chunk_id`, giữ rrf_score cao nhất,
concat + dedupe `graph_context`). Xem §4.2.

---

## 4. Node logic (`orchestrator/nodes.py`)

### 4.1 `plan` (thay `build_query`)
- Prompt mở rộng (§5). Output `PlanOutput`.
- Resolve mode: `selected = override_mode if override_mode != "auto" else parsed.selected_mode`.
- `steps = parsed.steps or [PlanStep(id=1, label="Tìm trong tài liệu",
  queries=[StepQuery(query=parsed.standalone_query, entities=parsed.mentioned_entities)])]`.
  `mentioned_entities` toàn cục → union vào `entities` mọi query (seed cho hybrid).
- **Validate bằng code, không tin LLM** — bộ luật (sai bất kỳ luật nào → **hạ về 1 bước** +
  warning; thà chạy đơn giản còn hơn chạy sai):
  1. `len(steps) <= cfg.retrieval_max_steps` — **đọc từ config, KHÔNG hardcode 2** (bản trước
     hardcode nên knob thành trang trí). Kèm theo: **`retrieval_max_steps > 2` là lỗi cấu
     hình, từ chối thẳng** — kiến trúc tích luỹ hiện chỉ an toàn ở 2 bước, xem §8.
  2. `len(step.queries) <= cfg.max_queries_per_step`, cắt phần thừa.
  3. `depends_on` phải trỏ tới id **có thật** và **nhỏ hơn** id bước hiện tại.
  4. **`<N>` chỉ hợp lệ khi bước `N` có `resolve` khác rỗng** và `N < id` bước đang xét.
  5. **Bước CUỐI không được có `resolve`.** Không ai tiêu thụ giá trị đó → tốn đúng 1 LLM
     call vứt đi. Vi phạm → xoá `resolve` của bước cuối (không cần hạ cả list).
  6. **Bước 1 không được chứa placeholder** — không có gì điền vào nó.

  > Luật 4+6 là thứ **ép** bất biến "khi tới `resolve_step` thì đã tích luỹ ít nhất một lượt
  > retrieval" thành đúng-vì-bị-ép, thay vì đúng-do-may. Không có chúng thì một plan hỏng
  > (bước 1 có `<2>`) vẫn chạy được và `resolve` đọc context rỗng.
- **Kiểm luật §2.1 — CHIA ĐÔI theo VẾ, và với `entities` thì chia theo THỜI ĐIỂM**:
  - `query`: **KHÔNG guard code.** Đã cân nhắc chặn "từ lạ trong `query`" (so token query với
    câu hỏi) và bỏ: tiếng Việt có biến thể chính tả/dấu, và rewrite `standalone_query` vốn
    hợp lệ **buộc phải đổi chữ** (giải đại từ, thêm chủ ngữ từ history) → chặn máy móc giết
    cả ca đúng. Thuộc **prompt + few-shot** (§5), kiểm bằng **soi DebugPanel lúc eval**.
  - `entities`: **guard code loại thẳng, TẠI PLAN-TIME** — mỗi phần tử phải hoặc là literal
    **có trong câu hỏi hiện tại**, hoặc là placeholder `<N>` hợp lệ. **KHÔNG** so với history,
    **KHÔNG** so với `resolved.values()` (lúc `plan` chạy thì `resolved` còn rỗng — bản trước
    viết vậy là guard không chạy được). Việc thay `<N>` là **execute-time**, ở `retrieve`.
    Loại sạch → truyền **`None`** xuống retriever, **không** truyền `[]`. Xem §2.1.
- Ghi `record_usage(task="plan", ...)` (đổi từ `"build_query"` — §8 lưu ý admin token).
- Emit event `steps` cho FE (§7.3).
- Fallback lỗi: mode=`hybrid`, 1 bước từ `standalone_query`, `route="needs_retrieval"`, warning.

> ### ✅ ĐÃ CODE 2026-08-01 — hai luật của §4.1 siết lại khi làm thật
>
> 1. **`depends_on` trỏ sai → XOÁ FIELD, không hạ cả list** (khác luật 3 ở trên). Lý do: field
>    này **không điều khiển gì lúc chạy** — thứ tự thực thi là thứ tự `id`, còn việc chờ mắt
>    xích là do placeholder quyết. Vứt một todo list chạy được vì một field chỉ dùng để kiểm
>    tra + vẽ UI là phản ứng thái quá. Vẫn ghi warning để đo được.
> 2. **Luật 5 viết tổng quát hơn**: xoá `resolve` của **bước không có ai tham chiếu `<id>`**,
>    thay vì chỉ cấm ở bước cuối. Cùng một lý lẽ ("không ai tiêu thụ ⇒ tốn một LLM call vứt
>    đi") nhưng bắt thêm ca bước-giữa-bị-bỏ-quên, và ca bước cuối tự rơi vào (không có bước
>    nào sau nó). Ca hay gặp nhất trong thực tế: bước 2 bị cắt vì `max_steps`, `resolve` của
>    bước 1 mồ côi theo.
> 3. Luật 6 (bước 1 không placeholder) **không cần code riêng**: nó là hệ quả của luật 4 —
>    ở bước 1 tập "bước trước có `resolve`" là rỗng nên mọi placeholder đều mồ côi.
> 4. **Đánh số lại id phải REMAP placeholder + `depends_on`** (bản trước không nói). LLM hay
>    trả id lệch; đổi `7,9` thành `1,2` mà quên remap thì `<7>` thành mồ côi và một todo list
>    hợp lệ bị hạ về 1 bước.

### 4.2 `retrieve` (fan-out trong 1 bước + RRF cross-query + tích luỹ)
- `mode = state["selected_mode"]`; `step = state["steps"][state["current_step"]]`;
  **KHÔNG tự tăng `current_step`** — biến đó chỉ `advance_step` ghi (§4.5); `retrieve` chỉ ĐỌC.
  (`retrieve` **có** ghi `stop_reason` khi 0 chunk ở bước cần `resolve` — §4.3.)
- **Điền placeholder** `<N>` từ `state["resolved"]` vào mọi `query`/`entities` của bước.
- Chạy **song song mọi query trong bước**:
  ```python
  results = await asyncio.gather(*[_retrieve_one(q, mode, cfg) for q in step.queries])
  ```
  `_retrieve_one`: `traditional` → `retrieve_traditional(q.query, ...)`;
  `hybrid` → `retrieve_hybrid(q.query, seed_mentions=q.entities, ...)`;
  `graph` (override) → `retrieve_graph(...)`.
- **RRF cross-query** (mới, ở tầng node — mỗi retriever đã rerank NỘI BỘ, giờ gộp giữa các
  query theo RANK trong từng result): `score[cid] += 1/(rrf_k + rank_trong_result_đó)`,
  dedupe `chunk_id`, sort giảm dần, cắt `multiquery_final_k` (§8 — trùng giá trị
  `rerank_top_k`, KHÔNG phải ràng buộc phải bằng).
  `graph_context` = concat toàn bộ result + dedupe.
- **Tích luỹ qua bước — KHÔNG cộng RRF giữa các bước** (sửa 2026-07-31). Bản trước nói "union,
  giữ chunk điểm cao nhất", tức ngầm so `rrf_score` của bước 1 với bước 2. **Sai về thang đo**:
  điểm RRF của một bước là tổng trên **số query của riêng bước đó** — bước 1 có 1 query, bước
  2 có 3 query thì bước 2 có điểm cao hơn **chỉ vì đông query hơn**, không phải vì liên quan
  hơn. Luật đúng: **giữ nguyên thứ tự trong từng bước, nối danh sách, dedupe theo `chunk_id`
  (lần xuất hiện đầu thắng)** — không có phép cộng nào giữa hai thang.
- **Thứ tự nối: bước SAU trước, bước trước sau.** Với multi-hop, bước 1 chỉ là **mắt xích**
  còn đáp án thật nằm ở **bước cuối** — xếp bước 1 lên đầu là đẩy phần phụ lên trước phần
  chính. Điều này quan trọng vì `reorder_for_context`
  ([reorder.py:16](../../apps/agent-service/app/tools/reorder.py#L16)) nhận list **best-first**
  rồi mới xen kẽ về hai đầu; sai thứ tự vào là sai luôn vị trí ra. **Đã cân nhắc** giao hẳn
  việc sắp xếp cho `reorder_for_context` và **bỏ**: hàm đó thuần vị trí, không biết chunk nào
  thuộc bước nào.
- **Trần `final_context_k` sau khi gộp** (§8, MỚI). `multiquery_final_k` chỉ cắt **trong
  một bước**; 2 bước × 8 = ~16 chunk vào synthesize, **gấp đôi hiện tại** → tăng token, tăng
  độ trễ, và tăng rủi ro lost-in-the-middle **đúng lúc `reorder_for_context` phải gánh nặng
  nhất**. Cắt sau khi nối, trước khi trả state. Trần này **chỉ đếm answer-context chunk** —
  định nghĩa chính xác ở §8.

#### 4.2.1 Tái áp invariant Rule B — B0 sửa `retrieve_hybrid`, B1 phá lại nếu không làm gì

**B0 (§9) là chưa đủ.** Nó vá đúng lần cắt trong `retrieve_hybrid`, nhưng B1 thêm **hai lần
cắt nữa ở tầng node**, và cả hai đều đứng sau B0:

```
retrieve_hybrid  ──[cắt rerank_top_k]──►  (B0 vá ở đây)
   node retrieve ──[cắt multiquery_final_k]──►   ← có thể rơi citation-only
                 ──[cắt final_context_k    ]──►   ← có thể rơi citation-only
```

**Invariant phải áp SAU LẦN CẮT CUỐI CÙNG của node `retrieve`**, không phải sau B0:

```
retrieval.chunks  =  answer-context chunks (đã cắt final_context_k)
                  ∪  source chunks của graph_context   (provenance, KHÔNG bị cắt)
```

**Ba luật đi kèm** (chốt lại cho khỏi lẫn hai loại chunk):
1. Chunk **graph candidate** (lọt RRF) — tham gia rerank **bình thường**, là answer-context.
2. Chunk **citation-only** — **chỉ** làm provenance; **KHÔNG** tính vào `final_context_k`.
3. Chunk citation-only **KHÔNG đưa toàn văn vào `[ĐOẠN TÀI LIỆU]`** của prompt:
   ```python
   chunks_for_prompt = reorder_for_context(
       [c for c in retrieval.chunks if not c.debug.get("citation_only")]
   )
   ```
   Field `debug={"citation_only": True}` **đã có sẵn**
   ([retriever.py:202](../../apps/agent-service/app/tools/hybrid/retriever.py#L202)), không
   cần thêm gì.

> ⚠️ **Luật 3 là THAY ĐỔI HÀNH VI, không phải khôi phục** — gọi đúng tên để đừng núp dưới
> nhãn "sửa bug B0". Code hiện tại **có** đưa toàn văn citation-only vào prompt
> ([nodes.py:266](../../apps/agent-service/app/orchestrator/nodes.py#L266) không lọc gì).
> **Vì sao đổi vẫn an toàn**: prompt synthesize render `graph_context` **kèm `(nguồn:
> chunk_id…)`** ([synthesize.py:161-175](../../apps/agent-service/app/prompts/synthesize.py#L161-L175))
> và system prompt đã cho phép *"lấy chunk_id XUẤT HIỆN trong hai khối trên, **kể cả chunk_id
> nguồn của khối quan hệ**"* ([synthesize.py:31-32](../../apps/agent-service/app/prompts/synthesize.py#L31-L32)).
> Tức LLM trích được id đó **mà không cần thấy toàn văn** → invariant citation còn nguyên, chỉ
> bỏ đi phần chiếm chỗ (chunk ~2.6K ký tự vốn không lọt top).
> **Lý do đổi**: 2 bước làm context phình gấp đôi, mà citation-only là loại chunk *đã bị xếp
> hạng thấp* — nhét toàn văn vào là trả giá lost-in-the-middle cho thứ chưa chắc dùng.

**Nếu `resolve` cần thông tin graph** → đưa `graph_context` vào prompt `resolve` **giống cách
synthesize làm**, KHÔNG lấy toàn văn citation-only chunk làm nội dung thay thế.
- Emit `step`: **`done` nếu bước lấy được ≥1 chunk, `partial` nếu 0 chunk** (đồng bộ §7.3 —
  bản trước §4.2 ghi luôn `done` còn §7.3 ghi 0 chunk là `partial`, hai chỗ đá nhau).
  Detail = "Dense + BM25 · N đoạn" / "Không tìm thấy đoạn phù hợp". Trả `retrieval`,
  `retrieval_mode=mode`, warnings, debug (per-query counts).

> ### ✅ ĐÃ CODE 2026-08-01 — guard đặt ở `retrieve`, không ở `after_retrieve`
>
> Bản dưới cho `after_retrieve` đọc `state["retrieval"].chunks` — tức tập **TÍCH LUỸ**. Đúng ở
> 2 bước nhưng chỉ vì bước duy nhất được `resolve` là bước 1 (lúc đó tích luỹ ≡ lượt hiện
> tại); nó là loại đúng-do-may mà §8 đã phải viết hẳn một mục để cảnh báo.
>
> Code thật: **node `retrieve` tự set `stop_reason`** dựa trên số chunk của **RIÊNG bước
> mình** (nó có sẵn con số đó trước khi merge), `after_retrieve` chỉ đọc `stop_reason`. Cùng
> hành vi ở 2 bước, nhưng guard thành **per-step thật** — đúng đường nâng lên 3 bước mà §8 đã
> phác. Nói cho chuẩn: điều này KHÔNG tự động mở khoá 3 bước (`Settings` vẫn `le=2`), chỉ là
> gỡ sẵn một trong hai chỗ chặn.

### 4.3 `after_retrieve` (conditional edge)
```python
def after_retrieve(state) -> str:
    step = state["steps"][state["current_step"]]
    if not step.resolve:
        return "advance_step"
    if not state["retrieval"].chunks:        # bước CẦN resolve nhưng không có gì để đọc
        return has_context(state)            # -> DỪNG list (stop_reason đã set ở `retrieve`)
    return "resolve_step"
```

**Lỗ đã bịt (sửa 2026-07-31 lần 2).** Bản trước viết `if step.resolve and chunks: →
resolve_step; else → advance_step` và kèm ghi chú "`has_context` vốn đã chặn ca rỗng". **Ghi
chú đó sai và nguy hiểm hơn im lặng**: `has_context` chỉ chạy **ở CUỐI list**, không chạy
giữa hai bước. Đường đi thật của bản cũ:

```
bước 1 có `resolve`, retrieve ra 0 chunk
  -> after_retrieve   -> advance_step        (vì mệnh đề `and` false)
  -> after_advance    -> retrieve  (bước 2)
  -> bước 2 chạy với `<1>` CHƯA ĐƯỢC ĐIỀN     <-- truy vấn rác
```

Đúng là **truy vấn rác** mà §0.2 mục 6 đặt ra để ngăn. Luật đúng — khi `retrieve` ra **0
chunk** ở một bước **có `resolve`**, chính node `retrieve` phải:

1. `stop_reason = "unresolved"`;
2. emit `step` bước hiện tại state=`partial` (detail "Không tìm thấy đoạn phù hợp");
3. emit `step` các bước **còn lại** state=`skipped`;
4. **không** chạy bước sau — đi thẳng `has_context`.

Rồi `has_context` xử nốt: **chưa có chunk nào** → `honest_answer`; **có context tích luỹ từ
bước trước** → `synthesize` phần có căn cứ (và §4.7 nêu rõ vế nào chưa tra được).

> Ở **V1 chỉ bước 1 được `resolve`** (validator cấm `resolve` ở bước cuối, §4.1), nên ca này
> hầu như luôn rơi vào nhánh đầu → `honest_answer`. Nói trước để lúc demo không tưởng là hỏng.

**Còn vế tiết kiệm call thì vẫn đúng nhưng đừng ghi công quá tay**: context rỗng thì `resolve`
chắc chắn trả `value=""`, nên bỏ qua nó tiết kiệm **đúng một** LLM call. Cái MỚI thật sự ở
đây là **chặn bước sau chạy bừa**, không phải khoản tiết kiệm đó.

### 4.4 `resolve_step` (node mới — thay `reflect`)
- Prompt (§5): đưa **`standalone_query`** + `step.resolve` (mô tả mắt xích cần trích) +
  **full text** các chunk vừa lấy của bước này → hỏi `StepResolveOutput`. Cho full text được
  vì output chỉ là một chuỗi ngắn — đây chính là điểm `reflect` làm sai (§0.2).

  > ⚠️ **Sửa 2026-08-01: bản trước ghi "câu GỐC" và code làm đúng theo đó — SAI.** Prompt
  > `resolve` không có khối lịch sử hội thoại, nên câu nối tiếp ("người kế nhiệm **ông ấy** bị
  > ai sát hại?") vào đây là đại từ không còn đường nào giải; model đúng luật phải trả rỗng →
  > `stop_reason="unresolved"` → **mất hop 2 trong một ca lẽ ra chạy được**. Và nó khiến
  > `resolve_step` thành node online DUY NHẤT suy luận trên bản câu hỏi khác với bản đã dùng
  > để đi tìm (`retrieve` + `synthesize` đều dùng `standalone_query`).
  > Ba node còn giữ `state["question"]` là CỐ Ý, không phải bỏ sót: `guard_input` phải soi
  > đúng chữ người dùng gõ, `direct_response`/`clarify` đang đáp lại chính câu đó.
- Ghi `record_usage(task="resolve", ...)`.
- `value` không rỗng & `confidence != "thấp"` **& còn ít nhất một `source_chunk_ids` hợp lệ**
  → `resolved[step.id] = value`, thêm vào `resolved_facts`, emit `step` (state=`done`,
  detail = `"{label} → {value}"`).

  > ⚠️ **Vế nguồn thêm 2026-08-01, bản trước THIẾU và đó là lỗ thật.** Bản trước chỉ gác
  > `value` + `confidence`, còn id bịa thì lọc im lặng ở bước dựng `ResolvedFact` — nên
  > `value="Chu Văn Tấn", confidence="cao", source_chunk_ids=["id-bịa"]` vẫn **được chấp
  > nhận**, vẫn lái truy vấn bước 2, và vẫn vào prompt synthesize (lúc đó là một khẳng định
  > TRẦN, không nguồn — đúng thứ §0.2 mục 6 đặt `source_chunk_ids` ra để chặn). Không kiểm
  > được `value` bằng nguồn nào thì coi như không tìm thấy.
  >
  > **Tập id hợp lệ = chunk đưa vào prompt ∪ chunk nguồn của `graph_context`**, không phải
  > mỗi `retrieval.chunks`: prompt cho phép trích id ở cả hai chỗ, và `graph_context` có thể
  > trỏ tới chunk không hydrate được (`fusion._with_provenance` chỉ bù `if cid in pool`). So
  > hẹp hơn ngữ cảnh thật là loại nhầm id hợp lệ — mà guard này DỪNG cả todo list, nên loại
  > nhầm là mất luôn một hop.
  >
  > Id bịa bị loại hiện ở `internals` dòng "Nguồn bịa (bị loại)", KHÔNG đẩy vào `warnings`
  > (warnings hiện cho NGƯỜI DÙNG ở `MessageBubble`, đây là chuyện của admin).
- Ngược lại → `stop_reason="unresolved"`, emit `step` (state=`partial`, detail = "chưa xác
  định được {resolve}").
- Fallback lỗi: coi như không trích được (`stop_reason="unresolved"`) + warning — **không**
  im lặng bỏ qua, vì im lặng thì lúc demo không phân biệt được "không cần resolve" với
  "resolve chết".

### 4.5 `after_resolve` (edge) + `advance_step` (NODE) + `after_advance` (edge)

**Đây là chỗ bản trước vỡ** (§0.3 #4): `advance()` cũ vừa là edge fn (chỉ trả tên đích, ghi
state được) vừa được kỳ vọng tăng bước, còn chú thích lại đá sang "retrieve tự tăng" trong
khi §4.2 chỉ cho `retrieve` ĐỌC. Dù chọn nhánh nào, `after_retrieve` cũng đọc sai bước.

```python
# --- edge fn: chỉ ĐỌC ---
def after_resolve(state) -> str:
    if state["stop_reason"] == "unresolved":
        return has_context(state)      # DỪNG list, trả lời với cái đang có (hoặc honest)
    return "advance_step"

# --- NODE: điểm GHI DUY NHẤT của current_step ---
def advance_step(state) -> dict:
    return {"current_step": state["current_step"] + 1}

# --- edge fn: chỉ ĐỌC, chạy SAU khi advance_step đã ghi ---
def after_advance(state) -> str:
    if state["stop_reason"]:
        return has_context(state)
    if state["current_step"] < len(state["steps"]):
        return "retrieve"
    return has_context(state)
```

- **Một điểm ghi ⇒ một chỗ test.** Không còn cảnh "ai tăng, tăng mấy lần" phải suy từ đường đi.
- `after_advance` so `current_step < len(steps)` (không phải `+1 <`) vì `advance_step` **đã**
  tăng rồi — sai chỗ này là bỏ mất bước cuối.

#### BỎ `retrieval_step_count` và `stop_reason="max_steps"` (sửa 2026-07-31 lần 2)

Bản trước cho `advance_step` tăng **hai** biến và `after_advance` gác **hai** điều kiện. Thừa:

- validator §4.1 đã cap `len(steps) <= retrieval_max_steps` **ngay tại `plan`**;
- `current_step` chỉ tăng ở một chỗ và tăng **đơn điệu**, nên số lượt `retrieve` đã chạy luôn
  bằng `current_step + 1` — `retrieval_step_count` là **biến phái sinh**;
- ⇒ điều kiện `retrieval_step_count < retrieval_max_steps` **không bao giờ chặn được cái gì**,
  và `stop_reason="max_steps"` **không có đường xảy ra**. Guard chết + nhánh chết.

Nhân tiện, một danh sách **tĩnh** thì hai bộ đếm cùng quản là thừa theo định nghĩa; và
`cfg` trong pseudo-code bản trước **còn chưa được định nghĩa ở đâu cả**.

> ⚠️ **Bỏ có CHỦ Ý, không phải quên** (ghi lại để đời sau khỏi "sửa nhầm"): `retrieval_step_count`
> vốn là guard runtime **độc lập với validator** — bỏ nó nghĩa là validator sai thì vòng lặp
> chạy tự do, không còn phanh thứ hai. Với V1 (`steps` sinh MỘT lần ở `plan`, tĩnh, cap cứng
> 2 — §8) rủi ro đó coi như 0. **Nếu sau này `steps` thành động** (thêm/sửa bước lúc đang
> chạy) thì phải dựng lại guard đếm lượt, đừng dựa vào `len(steps)` nữa.

### 4.6 `has_context` — GIỮ nguyên (`retrieval.chunks` rỗng → honest_answer).

### 4.7 `synthesize` — thêm **fact trung gian có nguồn**: `resolved_facts` vào prompt dưới
dạng "đã xác định được: X (độ tin cậy …, nguồn …)", KHÔNG phải sự thật hiển nhiên. Nếu
`stop_reason="unresolved"` → prompt nêu rõ vế nào chưa tra được.

### 4.8 `honest_answer` — dùng `stop_reason` + bước dừng dở để nêu **phần nào chưa đủ dữ
liệu** thay vì thông điệp chung (đúng tinh thần honest domain lịch sử).

---

## 5. Prompt (`prompts/` + managed prompt)

- **`build_query.py` → `plan.py`** (key managed prompt: **giữ `"build_query"`** để không phải
  reseed DB, chỉ update content + bump version). Bổ sung:
  - Luật tách `steps`: chỉ tách **nhiều bước** khi có **mắt xích ẩn** phải tra rồi mới hỏi
    tiếp được. Nhiều ý biết trước tất cả → **1 bước**. Câu đơn → **1 bước**. Nói thẳng
    trong prompt: "tách thừa bị coi là lỗi".
  - **Luật số query (§2.2)**: số query trong một bước **do model quyết**. Chỉ tách khi các ý
    thật sự cần từ khoá khác nhau; **1 query cho câu nhiều ý là hợp lệ** nếu phủ đủ. Ghi rõ
    trong prompt rằng mỗi query tốn một lượt truy hồi thật (embed + BM25 + rerank).
  - **Luật làm giàu truy vấn (§2.1)** — sửa 2026-07-31 lần 2, **prompt cũ dạy NGƯỢC luật**:
    - `query`: chỉ dùng từ ngữ có trong câu hỏi hiện tại / lịch sử hội thoại / `<N>`.
    - `entities`: **chỉ chép lại tên riêng XUẤT HIỆN NGUYÊN VĂN trong câu hỏi hiện tại**, hoặc
      placeholder `<N>`. **KHÔNG** thêm tên model tự biết (tên khởi nghĩa, niên hiệu, địa danh
      liên quan…), **KHÔNG** lấy từ lượt hội thoại trước. Không có tên riêng nào → **để rỗng**,
      đó là câu trả lời hợp lệ.
    - ❌ **Bỏ hẳn câu cũ "kiến thức model tự biết thêm → bỏ vào `entities`"** — đó chính là
      chỗ dạy model làm việc mà guard §4.1 sẽ loại. Sinh rồi dọn = tốn token + warning rác.
    - Few-shot phải có 1 ví dụ minh hoạ đúng chỗ này (câu có tên riêng model "biết thêm" →
      output vẫn **không** đưa tên đó vào `entities`), vì đây là lỗi model rất dễ mắc.
  - Luật `resolve`: chỉ đặt khi bước sau thật sự cần giá trị đó; mô tả cụ thể cái cần trích.
  - Luật placeholder: bước phụ thuộc viết `<N>` đúng chỗ cần điền.
  - Luật `selected_mode`: quan hệ giữa ≥2 thực thể / nhiều tên riêng / "liên hệ giữa X và
    Y" → `hybrid`; tra cứu định nghĩa/mốc đơn → `traditional`.
  - Luật `label`: tiếng Việt, ngắn, **giáo viên đọc hiểu** (hiện thẳng lên UI §7.3) — không
    phô thuật ngữ kỹ thuật.
  - Few-shot **theo bậc build, KHÔNG dạy trước** (sửa 2026-07-31):
    - **B1–B3**: chỉ 2 ví dụ — câu đơn (1 bước), nhiều ý (1 bước 3 query). **KHÔNG có ví dụ
      multi-step.** Vì B1 ép `steps[:1]` bằng code (§9), dạy model tách 2 bước rồi cắt bằng
      code là **vừa tốn token vừa làm nhiễu chính phép đo §10** (phân bố số bước đo được sẽ
      là hành vi bị cắt, không phải hành vi thật).
    - **B4**: mới thêm ví dụ multi-hop (2 bước, bước 1 có `resolve`) — và ví dụ đó phải là
      câu **đã thoả (a)+(b)** của §2.0, không bịa.
  - Bump `BUILD_QUERY_PROMPT_VERSION`.
- **`resolve.py`** (hằng mới + key managed `"resolve"`, thêm vào `scripts/seed_prompts.py`):
  "chỉ trích cái CÓ trong context, không suy đoán"; "không thấy → trả `value` rỗng, KHÔNG
  đoán bừa"; "chỉ chắc khi context nói thẳng → `confidence=cao`; suy từ ngữ cảnh → `vừa`;
  mơ hồ → `thấp`"; bắt buộc kèm `source_chunk_ids`.
- **`synthesize.py`**: thêm luật "nếu một phần câu hỏi KHÔNG có căn cứ trong context → nói rõ
  phần đó chưa đủ dữ liệu, KHÔNG lấp liếm" (bịt lỗ `confidence` một-giá-trị cho câu nhiều ý)
  + cách dùng `resolved_facts`. Bump version.
- Tất cả prompt online vẫn qua `get_active_prompt(key, fallback=HẰNG)` — fallback code khi
  DB thiếu/lỗi (giữ nguyên cơ chế).

> ### ⚠️ Sửa hằng prompt trong code KHÔNG tự tới runtime — phát hiện khi verify B2 (2026-07-31)
>
> `get_active_prompt` đọc bản **production trong Postgres**; hằng code chỉ còn là **fallback
> khi DB hỏng**. Mà `seed_prompt` **idempotent theo KEY** — key `build_query` đã tồn tại từ
> lần seed đầu nên chạy lại `seed_prompts.py` **không cập nhật gì cả**.
>
> **Hậu quả quan sát được**: sau khi code xong B1+B2, chạy thử `plan` thì `steps` LUÔN rỗng,
> `label` luôn là default, `selected_mode` luôn "hybrid" — vì LLM vẫn nhận **prompt cũ** (bản
> chưa hề biết `steps`/`selected_mode`). Toàn bộ B1+B2 **inert**, và **không có lỗi nào được
> ném ra** — schema mới chỉ lặng lẽ nhận giá trị default.
>
> **Đã sửa**: thêm `prompt_store.publish_prompt_version()` (tạo version mới + archive bản cũ
> + `clear_cache`, cùng ngữ nghĩa nút promote ở UI admin) và cờ
> `scripts/seed_prompts.py --publish [--key ...]`. Không tạo version rác: content trùng
> production → trả None, không insert.
>
> **Luật từ nay**: đổi hằng prompt ONLINE/GUARDRAIL trong code ⇒ **bắt buộc** chạy
> `seed_prompts.py --publish --key <key>` (hoặc promote qua UI admin), nếu không thay đổi đó
> không có tác dụng. Đây là bẫy chung cho MỌI prompt online, không riêng B1/B2.

---

## 6. Vòng validate-citations (B5 — reinstate)

> ### ✅ ĐÃ CODE 2026-07-31 — đúng thiết kế dưới, thêm 3 điểm chốt lúc làm
>
> 1. **Thứ tự nhánh trong `after_validate` KHÔNG được đảo**: `confidence="không đủ dữ liệu"`
>    phải xét TRƯỚC khi đếm citation. LLM tự khai không trả lời được thì soạn lại cũng vô
>    ích — đặt sau thì một câu "không đủ dữ liệu" **có** citation hợp lệ sẽ đi thẳng sang
>    `build_visualization`, tức bỏ qua nhánh honest.
> 2. **`honest_answer` chỉ chốt dòng `synthesize:1` khi `synthesize_attempt_count == 0`.**
>    Đến từ `after_validate` hết lượt thì các dòng soạn/đối chiếu đã có trạng thái thật rồi;
>    đạp lại là xoá mất chuyện đã xảy ra.
> 3. **Lượt soạn lại phát LẠI event `steps`** với danh sách dài hơn (thêm `synthesize:2`/
>    `validate:2`). Kéo theo: `SseCollector` **phải MERGE theo id thay vì thay thế** — bản
>    đầu thay thế, và nếu để nguyên thì mọi dòng đã `done` bị đạp về `pending` khi retry, tức
>    reload mất sạch. Frontend `mergeDeclaration` vốn đã merge nên không phải sửa.
>
> **Hai test cũ bị thay** (cả hai tự ghi "TẠM BỎ" trong thân, tức chúng chốt hành vi tạm):
> `test_unknown_chunk_id_dropped_no_retry` và `test_confidence_insufficient_no_longer_forces_honest`
> → thay bằng 5 test phủ đủ 4 nhánh `after_validate` + ca dedupe.

Tái sinh node đã "TẠM BỎ" ở `graph.py:11`. Hạ tầng đã có sẵn (event `regenerating` chạy
thông cả 3 tầng, `synthesize_attempt_count`, prompt `is_retry`, `SseCollector` xoá token giữ
TTFT) — chỉ thiếu node + cạnh. Lưu ý: `synthesize_max_attempts` hiện **khai báo nhưng KHÔNG
node nào đọc** (`config.py:106`; `nodes.py` chỉ tăng counter) — đúng nghĩa code chết.

**Ưu tiên đã nâng** (2026-07-30): trước xếp cuối cùng như việc kỹ thuật thầm lặng; nay panel
tiến trình (§7.3) biến nó thành **bước "Đối chiếu trích dẫn với nguồn" nhìn thấy được** trên
UI → giá trị demo tăng hẳn, làm ngay sau multi-hop — **hoặc THAY multi-hop** nếu B4 trượt
cổng go/no-go (§9).

> **Nhãn phải nói đúng việc** (2026-07-31): nhãn cũ *"Kiểm chứng kết quả"* / dòng phụ
> *"Đã xác minh 5/5"* nghe như đã đối chiếu **nội dung** với nguồn. Nó **không** làm việc đó —
> chỉ kiểm `chunk_id` có thuộc tập đã retrieve. Xem §7.3 mục 2.

- **`validate_citations`**: tách logic lọc đang nằm trong `build_visualization`
  (`nodes.py:437-441`, `if cid in chunks_by_id`) ra node riêng. Lọc `used_chunk_ids` ⊆
  chunk đã retrieve, dedupe, giữ order. KHÔNG gọi LLM (reflection bằng CODE, không phải LLM
  judge — ghi rõ hạn chế: chỉ kiểm hình thức "id có thuộc tập retrieve", không kiểm ngữ nghĩa
  grounding).
- **`after_validate`** conditional:
  - `confidence == "không đủ dữ liệu"` → `honest_answer`.
  - có ≥1 citation hợp lệ → `build_visualization`.
  - 0 citation hợp lệ & `synthesize_attempt_count < synthesize_max_attempts` → `synthesize`
    (retry; `synthesize` đã emit `regenerating` khi `attempt>0`).
  - 0 citation & hết attempt → `honest_answer`.
- `build_visualization` bỏ phần lọc (đã chuyển sang validate), chỉ dựng Citation + build viz.

**Đánh đổi (có chủ ý)**: TTFT giữ mốc chữ đầu lượt 1 dù bị xoá (`sse_collector.py:35-37`);
worst-case đôi chi phí synthesize — chỉ khi 0 citation, hiếm.

---

## 7. Backend + Frontend

### 7.1 Backend (`apps/backend`)
- `schemas/chat.py` `AskRequest.mode`: `Literal["auto","traditional","graph","hybrid"] = "auto"`.
- `services/agent_client.py` `AgentAskRequest`: truyền `mode` (đã có, đổi default `auto`).
- `api/chat.py`: truyền `body.mode` — không đổi logic khác.
- Token/logs: task mới `"plan"`/`"resolve"` tự xuất hiện trong breakdown theo task
  (`token_service` group theo `task`, không hardcode) — **kiểm** chỗ nào liệt kê cứng 3 task
  `build_query/synthesize/guardrail_input` (xem `admin-restructure-plan.md:135`) để nới.
  `retrieval_mode` trong logs giờ = mode agent chọn.
- **Cột mới `messages.steps` JSONB** (persist panel tiến trình, §7.3). ~~`messages` là bảng
  backend tự quản → sửa thẳng `CREATE TABLE` trong `db.py` rồi drop+tạo lại, **KHÔNG viết
  ALTER migration** (đúng luật CLAUDE.md; hiện chưa có data thật cần giữ).~~
  > **ĐÃ CODE 2026-07-31 — dùng `ALTER`, KHÔNG drop.** Câu gạch trên đặt giả thiết "chưa có
  > data thật cần giữ"; tới lúc làm thì `messages` đã có lịch sử hội thoại thật của
  > `admin@example.com`. Và ngay trong `db.py`, cột `ttft_ms` đã thêm bằng
  > `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — cùng bảng, cùng tình huống, nên theo tiền lệ
  > đó. Thêm cột có `DEFAULT '[]'` thì ALTER không đắt hơn drop chút nào, mà giữ được data.
  ⚠️ **Thêm cột KHÔNG chỉ là sửa `db.py`** (bổ sung 2026-07-31 — bảng đụng chạm bản trước bỏ
  sót cả ba chỗ). Phải sửa đồng thời trong
  [conversation.py](../../apps/backend/app/models/conversation.py):
  `class Message` (:28) thêm field · `_MSG_COLS` (:73) thêm tên cột — **quên chỗ này thì
  `SELECT` không lấy cột, reload mất sạch panel mà không lỗi gì cả** · `add_message` (:144)
  thêm tham số + vào `INSERT`. Thiếu bất kỳ chỗ nào là hỏng **im lặng**, không phải hỏng ồn.
- `sse_collector.py`: thêm nhánh gom `steps`/`step` → `message_fields()["steps"]`.

### 7.2 Frontend (`apps/frontend`) — phần chung
- `types`: `RetrievalMode` thêm `"auto"` (hoặc type riêng cho selector).
- ~~`Composer.tsx`: dropdown "Tự động" + "Traditional"/"Hybrid", ẩn "Graph".~~
  **ĐỔI QUYẾT ĐỊNH 2026-07-31 (user chốt): BỎ HẲN ô chọn mode khỏi UI.**
  - **Lý do**: B2 đã cho agent tự chọn. Để lại dropdown bên cạnh là **nửa vời** — vừa nói
    "agent tự điều phối" vừa bắt giáo viên chọn "Vector" hay "Kết hợp", tức bắt họ biết nội
    tạng hệ thống mới dùng được. Bỏ luôn thì thông điệp agentic mới sạch.
  - **Bỏ ở UI, GIỮ ở API** (đúng tinh thần §0.1 mục 2 "chỉ ẩn khỏi UI mặc định, không xoá"):
    `AskRequest.mode` ở cả 2 service vẫn nhận `auto|traditional|graph|hybrid`, mặc định
    `auto`. Gọi thẳng qua curl/Swagger vẫn so được traditional vs graph vs hybrid trên cùng
    một câu — **đường ablation cho luận văn còn nguyên**, `retrieve_graph` không thành code chết.
  - **Đã xoá ở FE** (không để prop chết): `MODE_OPTIONS` + `<select>` + prop `mode`/
    `onModeChange` ở `Composer`; state `mode` ở `ChatPanel`; tham số `mode` xuyên
    `useChat.ask()` và `AskPage.handleSend()`; field `mode` trong `AskBody`; type
    `RetrievalMode` (hết chỗ dùng sau khi bỏ 4 chỗ trên).
  - **FE không gửi `mode` nữa** ⇒ dựa vào default `"auto"` của backend. Đổi default đó là đổi
    hành vi toàn hệ thống, không phải một dòng UI.
- Debug panel (admin): hiện `selected_mode` + toàn bộ `steps` + query đã điền placeholder +
  điểm RRF + timing. **Không gộp với panel §7.3** — hai đối tượng khác nhau: panel tiến
  trình là của người dùng (ngôn ngữ giáo viên), DebugPanel là của admin (số liệu thô).

### 7.3 Frontend — panel tiến trình (MỚI)

> ### ✅ ĐÃ CODE 2026-07-31 — nhưng PHẠM VI CO LẠI so với bản viết dưới
>
> ~~B4 đã bỏ (cổng go/no-go trượt 2 lần, xem §9) và B5 chưa làm~~ — **cả hai đã code xong**
> (B5 ngày 2026-07-31, B4 ngày 2026-08-01), nên 4 gạch đầu dòng dưới đây đều **đã hết hiệu
> lực**; giữ lại làm bản ghi lịch sử của phạm vi từng bị co lại:
> - ~~state `skipped`~~ → đã dựng, đi kèm nhãn trợ năng riêng ("đã bỏ qua") và gạch ngang
>   nhãn bước, để phân biệt được với `pending` ("chưa chạy tới").
> - ~~dòng phụ `resolve`~~ → `resolve_detail`/`resolve_missing_detail`. **Chip nguồn thì
>   CHƯA**: `source_chunk_ids` của mắt xích hiện chỉ vào prompt synthesize + `internals`
>   (tầng 2, admin), không thành chip bấm được ở tầng 1.
> - ~~dòng `validate:N`~~ → đã có từ B5. Danh sách là `1 + N + 2`.
> - ~~nhánh `plan` nhiều bước~~ → `plan_detail` nay dẫn bằng số BƯỚC khi >1
>   ("Phát hiện 2 ý phụ thuộc nhau · tra 2 bước"), chỉ rơi về đếm truy vấn song song khi
>   đúng 1 bước.
>
> **Thêm 2 thứ không có trong bản viết** (phát sinh khi code, đều là để nói thật hơn):
> - **state thứ tư `pending`** — dòng đã khai báo trong `steps` nhưng chưa chạy tới. Không
>   có nó thì danh sách 3 dòng hiện ra một lúc sẽ phải cùng quay spinner, tức nói dối là cả
>   3 đang chạy. Agent **không bao giờ emit** `pending`; nó là mặc định phía nhận. Sau khi
>   stream đóng, `pending` đọc là **"bước này không chạy"** — đúng vai `skipped` định làm.
> - **`guard_input` tự khai báo dòng `plan`** khi chặn. Không thì dòng frontend dựng sẵn bị
>   hạ về `partial` trống trơn, nhìn như hệ thống hỏng chứ không như câu hỏi bị từ chối.
>
> File thật: `agent-service/app/orchestrator/progress.py` (thuần, 19 test) ·
> `backend/app/services/sse_collector.py` · `frontend/src/features/chat/ProgressPanel.tsx`
> \+ `StepRow.tsx` + `chatReducer.ts`.

Tham chiếu cách trình bày (không bê nguyên): danh sách bước dọc đánh số, mỗi bước **tiêu đề
ngắn + dòng phụ nói KẾT QUẢ**, header đếm `n/N bước · thời gian`, nút **Ẩn tiến trình**.
Đặt **trong bong bóng assistant, phía trên phần trả lời** (`MessageList`/`Bubble`).

**Bốn điều chỉnh bắt buộc so với UI tham chiếu:**

1. **BỐN trạng thái, không phải hai.** UI tham chiếu chỉ có chờ/tick-xanh, kể cả khi dòng phụ
   ghi "chỉ xác minh được 1/2". Với domain lịch sử KHÔNG chấp nhận được:
   | State | Màu | Khi nào |
   |---|---|---|
   | `running` | xám, spinner | đang chạy |
   | `done` | xanh, tick | tìm/trích được đầy đủ |
   | `partial` | **hổ phách** | `resolve` rỗng hoặc `confidence="thấp"`; retrieve 0 chunk |
   | `skipped` | xám nhạt | bị bỏ vì `stop_reason="unresolved"` (dừng list sớm — §4.3/§4.5) |
2. **Dòng phụ do CODE ghép, TUYỆT ĐỐI không thêm LLM call "người dẫn chuyện".** Dữ liệu đã
   có sẵn: `retrieve` biết số chunk + mode, `resolve` biết giá trị trích được, graph biết
   quan hệ. Template chuỗi là đủ — và quan trọng hơn, **nó không bịa được**.
   ```
   plan      → "Phát hiện 2 ý phụ thuộc nhau · cần multi-hop"  |  "Câu hỏi đơn · 1 bước"
   retrieve  → "Dense + BM25 chạy song song · 8 đoạn"           |  "Không tìm thấy đoạn phù hợp"
   resolve   → "Người kế nhiệm → <tên>"   (+ chip nguồn, click ra SourceModal có sẵn)
   validate  → "5/5 liên kết nguồn hợp lệ"  |  "3/5 liên kết nguồn hợp lệ"
             → "0/5 liên kết nguồn hợp lệ · soạn lại"      (CHỈ khi 0 hợp lệ)
   ```
   ⚠️ **Dòng phụ phải khớp logic retry** (sửa 2026-07-31 lần 2). Bản trước viết *"2/5 trích
   dẫn không khớp · **soạn lại**"* — **không bao giờ xảy ra**: `after_validate` (§6) chỉ retry
   khi **0** citation hợp lệ; với 3 id đúng + 2 id sai thì hệ thống **đi tiếp**, không soạn
   lại. Sửa **chữ trên UI**, KHÔNG sửa logic (V1 giữ luật đơn giản đã chốt). Chữ "soạn lại"
   chỉ được xuất hiện ở đúng ca `0/N`.
   ⚠️ **Chữ dùng cho `validate` phải khớp việc nó thật sự làm** (sửa 2026-07-31). Bản trước
   viết *"Đã xác minh 5/5 trích dẫn"* — **overclaim**, vì §6 của chính plan này ghi rõ node
   đó chỉ kiểm **hình thức**: `chunk_id` có thuộc tập đã retrieve hay không, **không** kiểm
   câu văn có thật sự được chunk đó chống lưng. Chữ "xác minh" trên UI người dùng mà thực
   chất là membership check là loại phóng đại tệ nhất — nó làm người đọc **tin hơn mức đáng
   tin**, đúng thứ domain lịch sử không cho phép. Dùng "khớp nguồn đã truy hồi".
3. **Trạng thái khởi đầu khác UI tham chiếu.** Họ có "0/4 bước" trước khi chạy vì biết kịch
   bản sẵn; mình chỉ biết danh sách **sau khi `plan` trả về**. Nên: render ngay 1 dòng
   *"Phân tích câu hỏi"* state `running`, danh sách **nở ra** khi `plan` xong. Không giả vờ
   biết trước.
4. **Không độn bước** (nhắc lại §2) — số dòng của câu đơn **phụ thuộc bậc build**, xem bảng
   ngay dưới. Bản trước ghi "câu đơn hiện đúng 3 dòng" cạnh công thức "1 + N + 2" (= 4 dòng
   khi N=1) — hai chỗ đá nhau; và thứ tự liệt kê `validate → synthesize` cũng **ngược luồng
   thật** (§1: `synthesize` → `validate_citations`).

**Danh sách hiển thị — đếm theo bậc build:**

| Giai đoạn | Công thức | Câu đơn (N=1) | Thứ tự |
|---|---|---|---|
| **Trước B5** (chưa có `validate_citations`) | `1 + N + 1` | **3 dòng** | `plan` → N bước → `synthesize` |
| **Từ B5 trở đi** | `1 + N + 2` | **4 dòng** | `plan` → N bước → `synthesize` → `validate_citations` |

Test regression "câu đơn không độn bước" (§10) phải chốt **theo giai đoạn**: 3 dòng trước
B5, 4 dòng sau — không phải một con số cố định.

**Hành vi**: mở khi đang chạy; **tự gập** khi xong thành một dòng `Đã hoàn thành · N/N bước ·
12.4s`; click mở lại. Thời gian trôi đo **client-side** từ lúc mở stream — không cần backend
đổi gì (TTFT ở `messages.ttft_ms` là chỉ số khác, cho admin, giữ nguyên).

> **Sau reload KHÔNG hiện lại thời gian** (chốt V1, 2026-07-31 lần 2): thời gian đo
> client-side nên không thể dựng lại `12.4s` trừ khi nhét `duration` vào JSONB. V1 chấp nhận:
> **reload thấy đủ các bước + kết quả, không có thời gian** — dòng gập ghi `Đã hoàn thành ·
> N/N bước`, bỏ vế thời gian. **Không thêm cột, không thêm field.** Nói trước để lúc test
> không tưởng là bug.

#### 7.3.1 Hợp đồng SSE — chốt đủ để code được (sửa 2026-07-31 lần 2)

Bản trước chỉ đưa 2 event mẫu cho **todo retrieval step**, còn 5 câu hỏi bỏ ngỏ — không code
được: ba dòng hệ thống do ai tạo, id là gì, `status` event cũ còn dùng không, retrieve xong mà
còn `resolve` thì `done` hay chưa, và các luồng terminal kết dòng `running` thế nào.

**(1) `id` — không gian tên, không va chạm.** Ba dòng hệ thống có id cố định; todo dùng tiền tố:
```
"plan"  ·  "todo:1"  ·  "todo:2"  ·  "synthesize:1"  ·  "validate:1"
```
Retry synthesize (§6) dùng **`synthesize:2`, `validate:2`** — id mới, KHÔNG ghi đè dòng cũ.
Người dùng thấy được là hệ thống đã soạn lại, đúng tinh thần honest; và reducer không cần luật
"reset dòng đang done".

**(2) Ai tạo dòng nào.** **Backend/agent tạo TẤT CẢ** qua event `step`, FE **không tự sinh
dòng nào** — trừ đúng một ngoại lệ: dòng `plan` state `running` render ngay lúc mở stream
(§7.3 mục 3, vì lúc đó chưa có gì để emit). Lý do: dòng nào cũng phải persist được vào
`messages.steps`; FE tự sinh thì reload mất.

**(3) `status` event cũ — GIỮ, khác vai.** `status` (`nodes.py:259`, `{"node","msg"}`) là
**log kỹ thuật cho DebugPanel admin**, `step` là **tiến trình cho người dùng**. Không gộp,
không thay thế — §7.2 đã tách hai đối tượng này rồi.

**(4) Bước có `resolve` thì retrieve xong VẪN `running`.** Đây là lỗi của bản trước: §4.2 cho
`retrieve` emit `done`, rồi `resolve` emit `done`/`partial` cho **cùng một id** → trong lúc
`resolve` đang chạy, UI **hiện tick xanh cho việc chưa xong**.
```
Bước CÓ `resolve`:
  retrieve xong  -> state="running", detail "Đã tìm thấy N đoạn"     (KHÔNG phải done)
  resolve xong   -> state="done"  (kèm giá trị)  |  "partial"
Bước KHÔNG `resolve`:
  retrieve xong  -> state="done" (N>0)  |  "partial" (N=0)
```

**(5) Terminal / lỗi — luật FE, không thêm event.** `clarify`, `direct_response`,
`honest_answer`, `error`, hoặc user bấm dừng: **reducer chuyển MỌI dòng đang `running` thành
`partial`** khi stream đóng mà chưa có `done` cho dòng đó. Không cần event mới — `error` và
việc stream kết thúc là đủ tín hiệu. Ghi thẳng vào đây vì luật này **quyết định `chatReducer`
viết thế nào**, để mở là mỗi người code một kiểu.

**Event (agent-service emit, backend proxy nguyên):**
```
event: steps   data: {"steps":[{"id":"plan","label":"Phân tích câu hỏi","kind":"system"},
                               {"id":"todo:1","label":"Xác định người kế nhiệm","kind":"retrieve"},
                               ...]}
event: step    data: {"id":"todo:1","state":"done","detail":"Người kế nhiệm → <tên trích được>",
                      "source_chunk_ids":["..."]}
```
> **Chốt thêm khi code (2026-07-31), bản trên còn bỏ ngỏ:**
> 1. **`steps` KHÔNG mang `state`** — chỉ `id`/`label`/`kind`. State đi riêng qua `step` để
>    một dòng cập nhật nhiều lần mà không phải gửi lại cả danh sách; nhét vào cả hai chỗ là
>    hai nguồn sự thật cho cùng một thứ.
> 2. **`steps` CÓ chứa dòng `plan`**, dù frontend đã tự dựng dòng đó. Merge phải **giữ
>    state/detail của id đã có**, nếu không dòng `plan` đang `running` bị đạp về `pending`
>    rồi mới `done` — nháy ngược một nhịp. Và có nó thì backend mới persist được đủ.
> 3. **`step` với id không khai báo → BỎ QUA ở CẢ HAI tầng** (`SseCollector.feed` và
>    `chatReducer`), không mọc dòng ma.
> 4. **Luật đóng stream ở mục 5 phải áp Ở CẢ HAI TẦNG.** Frontend hạ `running`→`partial`
>    lúc stream đóng, còn backend phải hạ đúng như vậy TRƯỚC KHI LƯU
>    (`SseCollector._closed_steps`) — không thì bản đang xem và bản lưu lệch nhau, reload ra
>    spinner quay vĩnh viễn. `pending` **giữ nguyên**, không hạ: "không chạy" ≠ "chạy dở".
> 5. **`error` cũng phải tắt `streaming`** ở reducer. Trước B3 nhánh lỗi để `streaming`
>    treo `true` vĩnh viễn — không ai thấy vì bong bóng lỗi che hết phần phụ thuộc nó.

**An toàn ngược, đã kiểm cả hai tầng** — FE cũ / backend cũ gặp event mới không vỡ:
- `askStream.ts:195` — `switch` bỏ qua event lạ (comment "event lạ -> bỏ qua (không vỡ)")
- `sse_collector.py:41` — `feed` là chuỗi `elif`, event lạ rơi ra ngoài vô hại

**Persist**: lưu `steps` vào `messages.steps` (§7.1) để reload vẫn thấy chuỗi suy luận —
JSON nhỏ, và là tài sản lúc bảo vệ. Không lưu thì mất sạch sau refresh.

⚠️ **Đường persist đi qua 7 chỗ — thiếu chỗ nào cũng hỏng IM LẶNG** (không exception, chỉ là
reload không thấy gì). Liệt kê thẳng vì đây đúng là loại việc hay sót:

| # | Chỗ | Việc |
|---|---|---|
| 1 | backend `core/db.py` | cột `messages.steps` JSONB (drop+tạo lại, không ALTER) |
| 2 | backend `models/conversation.py` | `class Message` (:28) thêm field |
| 3 | backend `models/conversation.py` | **`_MSG_COLS` (:73)** — quên là `SELECT` không lấy cột |
| 4 | backend `models/conversation.py` | `add_message` (:144) thêm tham số + vào `INSERT` |
| 5 | backend `schemas/chat.py` | **`MessageOut` (:34) thêm `steps`** — quên là API trả về không có, dù DB có đủ |
| 6 | frontend `api/chat.ts` types | `Message` + `ChatItem` thêm `steps` |
| 7 | frontend `chatReducer.ts` | **`messageToItem()` (:68) map `m.steps`** — quên là load hội thoại cũ ra panel rỗng |

**Test chốt cả đường**: gọi API conversation detail sau khi lưu → **`steps` phải quay về đủ**.
Một test đầu-cuối ở đây rẻ hơn dò 7 chỗ bằng mắt.

**File FE**: `features/chat/ProgressPanel.tsx` (+ `StepRow.tsx`), state trong `chatReducer`
(thuần → test được: nhận `steps` rồi loạt `step` → snapshot cuối đúng).

---

## 8. Config mới (`core/config.py`, `Settings`)

```python
retrieval_max_steps: int = 2          # V1: HẰNG SỐ 2, validator TỪ CHỐI > 2 (xem dưới)
multiquery_final_k: int = 8           # cắt sau RRF cross-query, TRONG một bước
final_context_k: int = 10             # MỚI — trần số ANSWER-CONTEXT chunk (xem định nghĩa dưới)
max_queries_per_step: int = 4         # chặn plan tách quá nhiều query trong 1 bước
```

- **`multiquery_final_k = 8` chỉ TRÙNG GIÁ TRỊ với `rerank_top_k`, không phải ràng buộc**
  (sửa 2026-07-31 — bản trước viết "mặc định = `rerank_top_k`", đọc như thể hai knob buộc
  phải bằng nhau). Chúng độc lập; chỉnh cái này không kéo theo cái kia.

#### `final_context_k` — định nghĩa CHÍNH XÁC (sửa 2026-07-31 lần 2)

> **`final_context_k` = trần số **answer-context chunk** đưa vào `[ĐOẠN TÀI LIỆU]` của prompt.
> **KHÔNG** tính citation-only chunk (chunk kéo theo chỉ để làm provenance, xem §9-B0/§4.2).

Nghĩa là **`len(retrieval.chunks)` HOÀN TOÀN CÓ THỂ > `final_context_k`** — và đó là đúng,
không phải rò rỉ. Phải ghi rõ vì nếu không, một test rất tự nhiên như
`assert len(retrieval.chunks) <= final_context_k` sẽ **phá Rule B lần thứ hai** — đúng cái
bug B0 vừa sửa. Test đúng phải là:

```python
answer_ctx = [c for c in retrieval.chunks if not c.debug.get("citation_only")]
assert len(answer_ctx) <= cfg.final_context_k
```

Vì sao cần knob này: `multiquery_final_k` cắt theo **BƯỚC**, nên 2 bước là ~16 chunk vào
synthesize — gấp đôi hiện tại mà không ai chặn (§4.2).

> ### ✅ ĐÃ CODE 2026-08-01 — "từ chối >2" nằm ở `Settings`, không ở validator plan
>
> `retrieval_max_steps: int = Field(default=2, ge=1, le=2)`. Đặt ràng buộc ở pydantic nghĩa là
> cấu hình sai **chết lúc khởi động service**, không phải lúc câu hỏi đầu tiên chạy qua
> validator — người chỉnh biết ngay mình chỉnh vào chỗ chưa hỗ trợ, và không tốn dòng code
> nào để nói điều đó. Validator plan vì vậy chỉ còn việc cắt `steps[:max_steps]`.

#### `retrieval_max_steps` — V1 CHỐT CỨNG 2, KHÔNG phải knob nâng được

Bản trước viết *"Nâng lên 3 chỉ khi đo được câu thật cần"*. **Rút lại**: kiến trúc
*một `retrieval` tích luỹ* hiện nay **chỉ an toàn ở đúng 2 bước**, và lý do rất cụ thể —
guard ở §4.3 đọc `state["retrieval"].chunks`, tức **kết quả TÍCH LUỸ**, không phải chunk của
lượt hiện tại:

```
Nếu cho 3 bước:
  bước 1: retrieve OK              -> retrieval.chunks có dữ liệu
  bước 2: retrieve ra 0 chunk, có `resolve`
          -> retrieval.chunks VẪN không rỗng (còn chunk bước 1)
          -> guard §4.3 không nhận ra, `resolve` chạy
          -> `resolve` đọc context của LƯỢT TRƯỚC mà tưởng của mình   <-- sai âm thầm
```

Ở 2 bước thì ca này **không tồn tại**: validator cấm `resolve` ở bước cuối (§4.1 luật 5), nên
bước duy nhất được `resolve` là bước 1 — và ở bước 1, "tích luỹ" ≡ "lượt hiện tại".

**V1 vì vậy:** `retrieval_max_steps = 2` **và validator từ chối mọi giá trị > 2** (không im
lặng kẹp xuống — báo lỗi cấu hình, để người chỉnh biết là mình chỉnh vào chỗ chưa hỗ trợ).

> **Đường nâng lên 3 rẻ hơn vẻ ngoài** — ghi sẵn để sau khỏi tưởng phải thiết kế lại:
> `retrieve` **vốn đã có** kết quả riêng của bước (nó tính xong rồi mới merge vào state).
> Chỉ cần chuyền kết quả đó (`active_retrieval`) sang `after_retrieve` thay vì đọc state tích
> luỹ. Tức là **đổi guard sang per-step**, không phải viết lại vòng lặp. Vẫn để V1 cap cứng 2
> vì chưa có gì chứng minh cần 3 (§10-d còn chưa đo), nhưng đừng ghi sổ đây là việc lớn.

**V1: để hằng trong `Settings` THUẦN — KHÔNG đi qua `RuntimeConfig`** (sửa 2026-07-31). Bản
trước ghi "agent đọc qua `RuntimeConfig` như các knob retrieval hiện có", nhưng `RuntimeConfig`
([runtime_config.py:33](../../apps/agent-service/app/core/runtime_config.py#L33)) **chính là
đường đọc `system_config` qua `GET /internal/config`** của backend. Nhét 4 knob mới vào đó
là kéo theo **DDL + endpoint + UI admin** — đúng thứ `system-config-plan.md` đang cố tách ra
để không đụng orchestrator đang chạy ổn định. Đưa vào `RuntimeConfig` **sau**, khi nhóm Cấu
hình hệ thống được code, và như một hạng mục có chủ đích chứ không phải hiệu ứng phụ.

> Với `retrieval_max_steps = 2`: bước 1 → `resolve` → bước 2 → hết list → `synthesize`.
> Trần này **đủ cho corpus SGK** (hiếm quá 2 hop). ~~Nâng lên 3 chỉ khi đo được câu thật
> cần.~~ — **đã rút lại**, xem phần "V1 CHỐT CỨNG 2" ngay trên.

---

## 9. Thứ tự build (mỗi bậc merge + demo độc lập)

### B0 — Sửa bug đánh rơi chunk nguồn graph trong `retrieve_hybrid` ⚠️ **LÀM TRƯỚC, COMMIT RIÊNG**

**Đây là bug trong code ĐANG CHẠY, không phải hạng mục của plan này.** Xếp vào đây vì mọi bậc
sau đều dựng trên `retrieve_hybrid`, và vì nó phải được sửa **tách hẳn** khỏi B1.

**Bug** — [retriever.py](../../apps/agent-service/app/tools/hybrid/retriever.py):
- [:171](../../apps/agent-service/app/tools/hybrid/retriever.py#L171) — `if chunk_id not in
  top_fused_set`: chunk nguồn của `graph_context` mà **lọt** top RRF thì **KHÔNG** được đưa
  vào `citation_ids`.
- [:211-212](../../apps/agent-service/app/tools/hybrid/retriever.py#L211-L212) — `fused_chunks`
  đem rerank rồi `[:rerank_k]` — **cắt luôn**, kể cả chunk đó.
- [:214](../../apps/agent-service/app/tools/hybrid/retriever.py#L214) — chỉ cộng lại
  `citation_chunks`, mà nó **không nằm trong đó**.

**Vì sao là bug chứ không phải đánh đổi có chủ ý**: docstring của chính file đó
([:7-11](../../apps/agent-service/app/tools/hybrid/retriever.py#L7-L11)) cam kết điều
**ngược lại** — *"kể cả khi chúng không lọt top RRF — để mọi fact graph dùng đều có chunk
tương ứng trong context (validator không drop nguồn)"*, và *"PHẦN CỘNG THÊM, không bị
`hybrid_candidate_k` hay `rerank_top_k` cắt"*. Đây là **sai so với ý định đã ghi thành văn**.

**Rule B thủng đúng ở ca ngược đời**: chunk **quá tốt** nên lọt top RRF thì **mất** bảo vệ;
chunk **kém hơn** nằm ngoài top RRF lại **được giữ**.

**Sửa**: union `graph_context.source_chunk_ids` vào tập cuối **SAU lần cắt cuối cùng**, không
phải trước. Hai test tối thiểu:
1. chunk nguồn graph **lọt** top_fused nhưng **rớt** sau rerank → vẫn có mặt trong
   `result.chunks` (ca bug hiện tại);
2. chunk nguồn graph **ngoài** top_fused → vẫn có mặt (ca hiện đang đúng — chốt để không
   sửa hỏng).

> **Commit RIÊNG, trước khi động vào B1.** Nó độc lập hoàn toàn với plan này; để lẫn vào B1
> thì sau này không truy được lỗi nào do đâu — B1 đổi cả cách gộp chunk, một regression về
> citation sẽ không biết là do B0 hay B1.

⚠️ **B0 KHÔNG đóng được vấn đề này một mình.** B1 thêm hai lần cắt nữa (`multiquery_final_k`,
`final_context_k`) ở tầng node, đứng **sau** chỗ B0 vá — cả hai đều rơi citation-only chunk
nếu không làm gì. **Invariant phải được tái áp trong node `retrieve`, xem §4.2.1** (kèm luật
"citation-only không tính vào `final_context_k`" và "không đưa toàn văn vào prompt").

### B1 → B5

- **B1 — Steps song song** (rẻ, thấy hiệu quả ngay): `PlanOutput.steps` với **đúng 1 bước**
  (ép `steps[:1]` bằng code, và **prompt B1 không dạy multi-step** — §5),
  `retrieve` fan-out + RRF cross-query, **guard `entities` plan-time** (§2.1), **tái áp
  invariant Rule B + lọc `citation_only` khỏi prompt** (§4.2.1 — phần này KHÔNG được để trôi
  sang B4, vì hai lần cắt mới xuất hiện ngay ở B1). Chưa có `resolve`, chưa multi-hop,
  auto-mode CHƯA (giữ default hybrid). Demo: câu "nguyên nhân/diễn biến/kết quả" phủ đủ ý
  (soi DebugPanel).
- **B2 — Auto mode**: `selected_mode` từ plan; `override_mode`; FE default "Tự động" + ẩn
  graph khỏi selector. Demo: câu quan hệ → agent chọn hybrid; câu định nghĩa → traditional.
- **B3 — Panel tiến trình** (§7.3): event `steps`/`step` + `ProgressPanel` + persist. Làm
  **trước** phần khó vì rẻ, độc lập, và là thứ demo được ngay với B1/B2.
  **✅ XONG 2026-07-31** — phạm vi co lại (không `resolve`, không `validate:N`, không
  `skipped`), xem khối ghi chú đầu §7.3. Test: agent 287 · backend 179 (+4 fail
  `test_activity.py` có sẵn, lỗi môi trường) · frontend 75.
- **B4 — Multi-step todo** ⚠️ khó nhất **và có CỔNG GO/NO-GO**: `resolve_step` + placeholder
  (điền execute-time) + `advance_step`/`after_resolve`/`after_advance` + **guard 0-chunk dừng
  list** (§4.3) + tích luỹ chunk + prompt `resolve` + few-shot multi-hop.
  **✅ XONG 2026-08-01** — cổng đạt ở lần đo 2 (khối ngay dưới). Test: agent 372 · backend 186
  (+4 fail `test_activity.py` có sẵn, lỗi môi trường) · frontend 90.

  > ### ⛔→✅ CỔNG: TRƯỢT 2026-07-31, **ĐẠT 2026-08-01** — B4 **ĐÃ CODE**
  >
  > **Lần đo 1 (2026-07-31) — trượt.** Hai điều kiện:
  > 1. Có ≥1 câu multi-hop thoả (a)+(b) của §2.0 → ✅ ĐẠT (câu Yên Thế).
  > 2. `hybrid` hiện tại chưa giải được → ❌ TRƯỢT: hybrid MỘT lượt lấy về **2/2 mắt xích**
  >    (hạng 1 và hạng 6).
  >
  > Kết luận lúc đó — không code B4 — là **đúng với dữ liệu lúc đó**, và việc dừng lại để đo
  > chính là thứ đã ngăn một tuần code cho vấn đề chưa quan sát được.
  >
  > **Lần đo 2 (2026-08-01) — đạt.** Quét toàn corpus tìm ứng viên theo đúng cấu trúc
  > (cạnh `anchor -> bridge` trong MỘT chunk; anchor và bridge co-occur đúng chunk đó; tồn tại
  > chunk khác chứa bridge nhưng KHÔNG chứa anchor, ở mục khác) → 42 ứng viên qua lọc. Câu
  > chốt:
  >
  > > **"Người lãnh đạo chi bộ Đảng trong khởi nghĩa Bắc Sơn về sau giữ chức vụ gì, tham gia
  > > đảng ủy chiến dịch nào?"**
  >
  > | Cách chạy | hop1 `lichsu_clean-000103` (Bắc Sơn 1940) | hop2 `lichsu_clean-000245` (Đảng ủy Chiến dịch Trần Hưng Đạo 1950) |
  > |---|---|---|
  > | Hybrid MỘT lượt, seed `["khởi nghĩa Bắc Sơn"]` | hạng **1/9** | **không có mặt** |
  > | Bước 2 sau khi trích được "Chu Văn Tấn" | — | hạng **2/8** |
  >
  > **Vì sao ca này trượt còn Yên Thế thì không** (khác biệt là CẤU TRÚC, không phải may rủi):
  > chunk hop2 nói về Chiến dịch Trần Hưng Đạo, **không chứa chữ "Bắc Sơn" nào** → truy vấn
  > dựng từ vốn từ câu hỏi không có đường chạm tới. Ở Yên Thế thì chunk hop2 vẫn nhắc "Yên
  > Thế"/"Đề Thám" nên dense/BM25 vớ được. Kiểm bằng text: 10 chunk chứa "Bắc Sơn", 2 chunk
  > chứa "Chu Văn Tấn", **giao đúng 1** = chính chunk hop1.
  >
  > **Graph cũng không cứu được, và đây là chỗ §0.1 mục 3 chưa nói tới**: `_EXPAND_SEED`
  > ([graph_store.py:122-133](../../apps/agent-service/app/tools/graph_rag/graph_store.py#L122-L133))
  > trả `source_chunk_ids` của **seed** và của **các cạnh gắn vào seed**, KHÔNG trả chunk list
  > của node HÀNG XÓM. Chunk 245 thuộc cạnh *Chu Văn Tấn ↔ Chiến dịch Trần Hưng Đạo* — 2 hop
  > từ seed "khởi nghĩa Bắc Sơn", ngoài tầm. Đo thật: 12 `graph_context` item, không có 245.
  > Tức 1-hop expand phủ được câu 1-seed **khi mắt xích 2 nằm trên cạnh của chính seed**, và
  > đó chính là ranh giới của nó.
  >
  > ⇒ Điều kiện 2 ĐẠT → code B4. **Ba điểm khác thiết kế gốc, xem §4.1/§4.3/§8.**
- **B5 — Validate-citations loop**: §6. Wire lại `synthesize_max_attempts`/`regenerating`
  đang chết; panel có thêm dòng "Đối chiếu trích dẫn với nguồn". Demo: ép LLM bịa id → thấy
  `regenerating` + soạn lại.
  **✅ XONG 2026-07-31** — xem khối ghi chú đầu §6. Danh sách panel từ đây là `1 + N + 2`
  (câu đơn 4 dòng). Test: agent 297 · backend 180 (+4 fail `test_activity.py` có sẵn) ·
  frontend 77.

Dừng ở bậc nào cũng có sản phẩm chạy được. **B0 tách riêng, làm đầu tiên**; B1→B2→B3 làm
trước cho chắc; B4 đắt + rủi ro cao nhất **và có thể bị loại ở cổng go/no-go** — trong đó
kịch bản "đo xong rồi bỏ B4" là **kết quả hợp lệ**, không phải thất bại: nó chứng minh graph
retrieval đã phủ, và đó cũng là một kết luận viết được vào luận văn.

---

## 10. Test

- **Unit thuần (không DB/LLM)**: `after_retrieve`/`after_resolve`/**`advance_step` (node —
  test nó tăng ĐÚNG cả hai biến)**/`after_advance`/`after_validate`/`has_context`; RRF
  cross-query **trong một bước** (mock nhiều result → thứ tự tất định); **gộp giữa các bước**
  (bước sau đứng trước, dedupe giữ lần đầu, **KHÔNG cộng điểm** — §4.2); **`final_context_k`
  chỉ đếm answer-context** (§8 — citation-only vẫn còn trong `retrieval.chunks`, đây là test
  chống phá Rule B lần 2); **invariant Rule B sau lần cắt cuối** (§4.2.1); **`chunks_for_prompt`
  lọc `citation_only`**; **điền placeholder** `<N>` (có/thiếu/lồng nhau); **validator 6 luật
  của plan** (§4.1: quá `retrieval_max_steps` / `retrieval_max_steps > 2` → lỗi cấu hình /
  `depends_on` trỏ sai / `<N>` mồ côi / `resolve` ở bước cuối / placeholder ở bước 1 → hạ về
  1 bước; thừa query → cắt còn `max_queries_per_step`); **guard `entities` plan-time** (không
  có nguyên văn trong **câu hỏi hiện tại** → loại + warning; lấy từ history → **cũng loại**;
  `<N>` hợp lệ → giữ; **lọc sạch thì truyền `None` chứ không `[]`** — §2.1);
  **`after_retrieve` khi 0 chunk + có `resolve`** → `stop_reason="unresolved"`, bước sau
  `skipped`, **KHÔNG chạy bước sau** (§4.3); `validate_citations` lọc/dedupe.
- **Eval thủ công (không phải unit test)** — đo trên bộ câu cố định trước khi chốt B1/B4.
  **Sửa 2026-07-31: bản trước chỉ đo HÀNH VI PLANNER, không đo KẾT QUẢ** — tức đo được
  "model có ngoan không", **không** đo được "có tốt hơn không". Bổ sung nhóm (c)+(d):

  | # | Đo gì | Loại | Chốt bậc nào |
  |---|---|---|---|
  | (a) | phân bố `len(step.queries)` — model có thật chọn multi-query không (§2.2) | hành vi | B1 |
  | (b) | tỉ lệ `query` chứa từ **không có** trong câu hỏi — mức vi phạm §2.1 | hành vi | B1 |
  | (c) | **chất lượng câu trả lời trước/sau B1** trên cùng bộ câu — có/không phủ đủ ý, có/không sai fact | **kết quả** | B1 |
  | (d) | **số câu multi-hop mà `hybrid` HIỆN TẠI đã trả lời đúng** (chưa cần B4) | **kết quả** | **cổng B4** |

  > **(d) là số đo quan trọng nhất cả danh sách.** Kết hợp với §0.1 mục 3 (graph 1-hop chạy
  > cho cả seed đơn) và §2.0, nó là **cổng go/no-go của B4** (§9). Đo bằng cách chạy chính bộ
  > câu multi-hop qua `mode=hybrid` override — đường `retrieve_graph`/`hybrid` thủ công
  > **giữ lại chính là để làm việc này** (§0.1 mục 2).

#### ✅ ĐÃ ĐO — kết quả (2026-07-31, dữ liệu thật, embedding/reranker local, KHÔNG gọi LLM)

Câu Yên Thế §2.0, `mode=hybrid`, `seed_mentions` = tên có nguyên văn trong câu hỏi
(`["Yên Thế", "Đề Nắm"]`), `rerank_top_k=8`:

| Cách chạy | HOP1 `…-000031` | HOP2 `…-000035` | Kết luận |
|---|---|---|---|
| **A. Hybrid MỘT lượt** (hành vi trước B1) | hạng **1** | hạng **6** | **2/2 mắt xích** — đã đủ |
| **B. Multi-query 1 bước** (B1, 2 query) | hạng **1** | hạng **2** | 2/2, nhưng **thứ hạng tốt hơn hẳn** |

**Hệ quả 1 — B4 TRƯỢT CỔNG.** Hybrid một lượt **đã kéo về đủ cả hai mắt xích**, tức khâu mà
multi-step định sửa (truy hồi không tới được vế sau) **không hỏng**. Cảnh báo ở §0.1 mục 3 và
ở chính §2.0 ("(b) không bảo đảm hybrid một lượt sẽ thất bại — đó là thứ phải ĐO") **đúng**.
⇒ **KHÔNG code B4** cho tới khi có câu mà hybrid thật sự trượt.

**Hệ quả 2 — B1 có giá trị đo được, và đúng chỗ quan trọng.** Multi-query không thêm mắt xích
mới, nhưng đẩy HOP2 từ **hạng 6/11 lên hạng 2/11**. Hạng 6 rơi đúng **giữa** context — chỗ
LLM chú ý kém nhất và cũng là chỗ `reorder_for_context` dồn chunk yếu vào. Sau B1, HOP2 nằm ở
**đầu** prompt. Đây là lợi ích thật của B1, khác hẳn "tìm thêm được tài liệu".

> **Đọc cho chuẩn, đừng overclaim**: đo này là đo **RETRIEVAL**, không đo câu trả lời. "Lấy về
> đủ 2 chunk" ≠ "trả lời đúng" — LLM vẫn phải tự nối hai mắt xích. Nhưng phần B4 định sửa
> chính là retrieval, và retrieval đang không hỏng.

> ⚠️ **ĐÍNH CHÍNH hàng B ở bảng trên** (sau khi đo tiếp hành vi `plan` thật): 2 sub-query
> dùng ở hàng B là **do người viết tay**, không phải do model sinh. Đo lại với output THẬT của
> `plan`: câu Yên Thế model trả **đúng 1 query** (= cả câu hỏi) ⇒ với riêng câu này, B1 cho
> kết quả **y hệt hàng A**, HOP2 vẫn ở hạng 6. Hàng B chứng minh "multi-query CÓ THỂ đẩy hạng
> lên nhiều", **không** chứng minh "B1 tự động làm được thế cho câu này".

#### Eval hành vi `plan` — §10 (a) + (b) + auto-mode B2 (2026-07-31, 6 câu, LLM thật)

| Câu | `selected_mode` | Kỳ vọng | #query | entities |
|---|---|---|---|---|
| Yên Thế (multi-hop) | hybrid | hybrid ✅ | **1** | `Yên Thế`, `Đề Nắm` |
| Hương Khê (nguyên nhân/diễn biến/kết quả) | hybrid | hybrid ✅ | **3** | `khởi nghĩa Hương Khê` |
| Hiệp ước Patenôtre ký năm nào | traditional | traditional ✅ | 1 | `Hiệp ước Patenôtre` |
| Phong trào Cần Vương là gì | traditional | traditional ✅ | 1 | `Phong trào Cần Vương` |
| Quan hệ Phan Bội Châu – Hoàng Hoa Thám | hybrid | hybrid ✅ | 1 | cả 2 tên |
| "Cảm ơn bạn nhé!" | — | smalltalk ✅ | — | rỗng |

- **(B2) auto-mode: 5/5 đúng.** Câu quan hệ/nhiều tên riêng → `hybrid`; tra cứu mốc/định
  nghĩa đơn → `traditional`.
- **(a) multi-query: 1/5 câu tách >1 query.** Model **dè dặt** đúng như §2.2 cho phép — chỉ
  tách khi các ý thật sự cần từ khoá khác nhau (Hương Khê). Đây là số đo mà §11 mục 6 đòi
  ("đo phân bố trước khi kết luận multi-query có đáng không"): **giá trị của B1 tập trung ở
  câu liệt-kê-nhiều-ý, không trải đều mọi câu**.
- **(b) vi phạm luật entity: 0/6.** Không câu nào model nhét tên tự nghĩ ra. Đáng chú ý nhất:
  câu Yên Thế **không** có `Đề Thám` trong entities dù model chắc chắn "biết" — đúng luật
  §2.1. Guard code chưa phải loại gì trên bộ câu này.

  Tất cả đọc từ DebugPanel/`llm_usage`, chấm tay, **không tự động hoá** — bộ câu nhỏ, chấm
  tay trung thực hơn một cái LLM judge tự chấm bài mình.
- **Node với mock**: `plan` parse `PlanOutput`; `retrieve` fan-out gọi đúng số retriever
  theo `len(step.queries)` + đúng retriever theo mode; `resolve_step` mock có/không trích
  được → nhánh đúng (`unresolved` → dừng list, KHÔNG chạy bước sau).
- **Flow (`test_orchestrator_flow.py` / `_stream.py`)**: CẬP NHẬT — nhiều mock hiện giả định
  `build_query` + không có bước. Thêm case: nhiều ý (2 call), multi-hop (3 call), dừng sớm
  do unresolved, override mode, retry citation.
- **SSE**: `steps`/`step` emit đúng thứ tự; `SseCollector` gom vào `message_fields`.
- **FE**: `chatReducer` nhận `steps` + loạt `step` → snapshot đúng; `ProgressPanel` render
  đủ **4** state; câu đơn hiện đúng **3 dòng trước B5 / 4 dòng từ B5** (regression chống độn
  bước — chốt theo bậc, xem bảng §7.3).
- **Regression**: câu đơn vẫn 2 LLM call (không vô tình bật `resolve`).

---

## 11. Rủi ro (phải xử, không phải "khó")

1. **`plan` phải đoán độ sâu trước khi thấy dữ liệu** — rủi ro cố hữu của plan-and-execute
   (đổi từ rủi ro "LLM tự chấm đủ chưa" của `reflect`). Giảm hại: cap `retrieval_max_steps`;
   validate steps bằng code; prompt có luật "tách thừa là lỗi" + few-shot câu đơn.
2. **`plan` chèn kiến thức nội tại vào `query`** (§2.1) — model tự thêm tên khởi nghĩa/địa
   danh nó "nhớ"; nhớ sai thì cụm từ sai vào thẳng BM25, kéo chunk sai với điểm cao, **im
   lặng**. Giảm hại: prompt + few-shot riêng cho lỗi này.
   ⚠️ Vế `query` **chỉ chặn được bằng prompt, KHÔNG có guard runtime** (lý do: §4.1) → phải
   đo thủ công lúc eval (§10-b). Vẫn là rủi ro hở nhiều nhất trong bản plan này —
   **nhưng đã hẹp lại** so với bản trước: vế `entities` nay **cấm hẳn kiến thức nội tại
   (và cả history), có guard code loại thẳng ở plan-time** (§2.1), và đó là vế mà kiến thức
   nội tại hay chui vào nhất. Lưu ý cái giá đã tính: cấm entity từ history **không** làm hỏng
   lượt hội thoại sau, vì `standalone_query` đã giải đại từ và `match_seed_entities` có
   token-match fallback — **với điều kiện truyền `None` chứ không `[]`** (§2.1).

2b. **B4 có thể là công thừa** (rủi ro MỚI, 2026-07-31) — graph 1-hop đã phủ quan hệ
   kế tục/chỉ huy (§0.1 mục 3), và corpus SGK kể theo nhân vật nên hai mắt xích hay nằm cùng
   chunk (§2.0). Giảm hại: **cổng go/no-go bằng số đo** trước khi viết dòng code B4 nào
   (§9, §10-d). Đây là rủi ro *phạm vi*, không phải rủi ro *kỹ thuật* — và cách xử duy nhất
   đúng là đo, không phải làm rồi mới biết.
3. **Sai lan truyền qua `resolve`** — xem §0.2 mục 6: `confidence` + `source_chunk_ids` bắt
   buộc, `thấp` → không đi tiếp; fact trung gian vào synthesize như fact CÓ NGUỒN.
4. **Đánh giá phi tất định** — todo list đã dễ tái lập hơn `reflect` nhiều (artefact xem
   được, số bước biết trước). Vẫn giữ **override mode thủ công** cho demo so sánh; cân nhắc
   bộ eval câu cố định.
5. **Chi phí/độ trễ multi-hop** — 2 lượt retrieve nối đuôi. Bù bằng: câu thường không có
   `resolve` (0 call thêm) + **panel tiến trình lấp khoảng chờ** (§0.2 mục 8).
6. **Multi-query có thể là tính năng thừa** — nếu model hầu như chọn 1 query (§2.2), B1 gần
   như không đem lại gì mà vẫn tốn code + test. Đo phân bố trước khi đầu tư tiếp.
7. **Task telemetry nở thêm** (`plan`/`resolve`) — kiểm mọi chỗ liệt kê task cứng ở backend/FE.
8. **Tương thích dữ liệu cũ** — usage cũ task=`build_query`; sau đổi thành `plan` →
   breakdown lịch sử có cả 2 nhãn. Chấp nhận (dev data). Key managed prompt vẫn giữ
   `"build_query"` nên DB prompt không churn.
9. **Panel lộ điểm yếu** — mặt trái của việc hiện tiến trình: câu trả lời dở giờ **nhìn thấy
   được là dở ở bước nào**. Đây là tính năng chứ không phải lỗi (honest), nhưng phải chuẩn
   bị: dòng phụ viết cho giáo viên đọc, không đổ lỗi kỹ thuật ra màn hình người dùng.
10. **Đóng góp luận văn** — graph vẫn load-bearing trong hybrid (**1-hop expand chạy cho mọi
   seed**, path-finding thêm khi ≥2 seed); câu chuyện mới = "graph retrieval có cấu trúc +
   agentic plan–execute điều phối". Nói CHUẨN khi bảo vệ: graph giải câu quan-hệ-2-thực-thể
   **và cả câu 1-seed qua cạnh 1-hop**; validate là self-correction **hình thức** (KHÔNG phải
   LLM judge, KHÔNG phải kiểm grounding ngữ nghĩa).
   ⚠️ **KHÔNG được nói "todo list giải câu multi-hop-ẩn-cầu-nối, graph thì không"** — câu đó
   sai theo §0.1 mục 3, và là loại sai dễ bị hỏi vặn nhất (mở `graph_store.py` ra là thấy).
   Chỉ nói được điều đó **nếu** số đo §10-d chứng minh, và lúc đó phải trưng số ra.

---

## 12. Đụng chạm file (tóm tắt)

| File | Thay đổi | Bậc |
|---|---|---|
| `tools/hybrid/retriever.py` | **union chunk nguồn graph SAU lần cắt cuối** (bug §9-B0) | **B0** |
| `schemas/ask.py` | `PlanOutput`+`PlanStep`+`StepQuery`+`StepResolveOutput`; `AskRequest.mode` thêm `auto` | B1–B4 |
| `orchestrator/state.py` | `selected_mode`/`steps`/`current_step`/`resolved`/`resolved_facts`/`step_states`/`stop_reason`; đổi `requested_mode`→`override_mode` (**KHÔNG** có `retrieval_step_count` — §4.5) | B1–B4 |
| `orchestrator/nodes.py` | `build_query`→`plan` (+ validator §4.1, guard `entities` plan-time, `[]`→`None`); `retrieve` fan-out+RRF+gộp-không-cộng-điểm+`final_context_k`+**tái áp Rule B §4.2.1**; **`chunks_for_prompt` lọc `citation_only`** (:266); `resolve_step`; **`advance_step` (NODE)**; `validate_citations`; edge fns; emit `steps`/`step` | B1–B5 |
| `orchestrator/graph.py` | thêm node (`resolve_step`,**`advance_step`**,`validate_citations`) + conditional edges (`after_retrieve`/`after_resolve`/**`after_advance`**/`after_validate`) | B1–B5 |
| `orchestrator/runner.py` | `initial_state` field mới | B1 |
| `prompts/build_query.py`(→`plan.py`) / `resolve.py`(mới) / `synthesize.py` | prompt + version; few-shot multi-step **chỉ thêm ở B4** (§5) | B1–B4 |
| `scripts/seed_prompts.py` | seed prompt `resolve` | B4 |
| `core/config.py` | `retrieval_max_steps`/`multiquery_final_k`/**`final_context_k`**/`max_queries_per_step` — `Settings` thuần, **KHÔNG** `RuntimeConfig` (§8) | B1/B4 |
| backend `schemas/chat.py`,`api/chat.py`,`services/agent_client.py` | mode `auto`; task mới | B2 |
| backend `core/db.py`, `services/sse_collector.py` | cột `messages.steps` JSONB; gom event `steps`/`step` | B3 |
| backend **`models/conversation.py`** | **`Message` (:28) + `_MSG_COLS` (:73) + `add_message` (:144)** — thiếu là hỏng IM LẶNG (§7.3 bảng 7 chỗ) | B3 |
| backend **`schemas/chat.py`** | **`MessageOut` (:34) thêm `steps`** — DB có mà API không trả | B3 |
| frontend `askStream.ts`, `ProgressPanel.tsx`(mới), `StepRow.tsx`(mới) | handler event `steps`/`step` + panel; id `plan`/`todo:N`/`synthesize:N`/`validate:N` (§7.3.1) | B3 |
| frontend **`chatReducer.ts`** | reducer nhận `steps`/`step`; **`messageToItem` (:68) map `m.steps`**; **stream đóng → mọi dòng `running` thành `partial`** (§7.3.1 mục 5) | B3 |
| frontend `api/chat.ts` types | `Message` + `ChatItem` thêm `steps` | B3 |
| frontend **`ChatPanel.tsx:25`** | **đổi default `useState<RetrievalMode>("hybrid")` → `"auto"`** — default KHÔNG ở `Composer` | B2 |
| frontend `Composer.tsx`, `types`, DebugPanel | nhãn "Tự động", ẩn graph, hiện steps | B2 |
| tests (agent + backend + FE) | cập nhật + case mới (**+2 test citation graph ở B0**) | B0–B5 |
