# Plan: Xem nguồn (Citation Viewer)

> Chốt 2026-07-12. Phạm vi: khung chat phía **người dùng** (giáo viên + admin), KHÔNG đụng
> KB Inspector (admin) đang chạy ổn.
>
> **✅ ĐÃ CODE XONG CẢ 3 PHA (2026-07-12)** — verify end-to-end trên hệ thật, xem §8. Ba điểm
> lệch khỏi plan gốc lúc implement (đều ghi rõ tại chỗ): `SourceDetail` bỏ `source_file`/
> `chunk_index`, `get_chunk` bắt thêm `UndefinedTable`, `Modal` thêm prop `size`.

## 1. Vấn đề

Phần **Nguồn** dưới mỗi câu trả lời hiện là **chữ tĩnh**: breadcrumb heading + nhãn
`lichsu.clean.md:7349-7352`. Không click được, không xem được nội dung. Giáo viên biết câu trả
lời "lấy từ đâu" nhưng **không kiểm chứng được** — trong khi grounding là điểm bán hàng chính
của đồ án, và text nguồn đã nằm sẵn trong `rag_chunks`.

Hai thứ tách bạch, đừng lẫn:

- **Nợ cũ**: [orchestrator-plan.md:493](orchestrator-plan.md#L493) đã chốt *"Quote nếu có chỉ
  lấy đoạn ngắn từ chunk text, không bắt LLM tự bịa quote"*, prompt synthesize đã dặn LLM đúng
  vậy ([synthesize.py:40](../../apps/agent-service/app/prompts/synthesize.py#L40)), schema có
  field `quote`, UI có sẵn chỗ render blockquote — **chỉ thiếu đoạn code điền vào**:
  [nodes.py:330](../../apps/agent-service/app/orchestrator/nodes.py#L330) hardcode `quote=None`.
  Nhiều khả năng rơi rụng chung với `validate_citations` (node đã "TẠM BỎ", xem
  [graph.py:11](../../apps/agent-service/app/orchestrator/graph.py#L11)) — đó vốn là chỗ tự
  nhiên để trích quote.
- **Tính năng mới**: hover xem trích đoạn, click xem full nguồn. **KHÔNG plan nào từng nói tới**
  (README.md:49 chỉ ghi mơ hồ "Xem citation hoặc nguồn tài liệu liên quan"). Đây là thiết kế
  mới, không phải khôi phục thứ đã duyệt.

## 2. Chốt thiết kế

Hai tầng tương tác, **cùng dùng chung một `chunk_id`**:

| Hành vi | Hiển thị | Nguồn dữ liệu | Network |
|---|---|---|---|
| **Hover** lên chip `[n]` | Trích đoạn ngắn (~240 ký tự đầu chunk) | `citation.quote` (đã có trong payload) | **Không** |
| **Click** vào chip `[n]` | Modal: full text chunk + tiêu đề mục + `dòng 375–378` | `GET /api/chat/sources/{chunk_id}` | 1 request, lazy |

Vì sao chia đôi vậy: quote đi kèm SSE nên hover **tức thì, offline, không tốn request**; còn full
chunk (~700 token) thì **không** nên nhồi vào mọi citation của mọi message — vừa phình payload
SSE vừa phình `messages.citations` JSONB lưu vĩnh viễn. Fetch lười lúc click là đúng chỗ.

**Quyết định phụ:**

- **Quote = 240 ký tự đầu chunk**, cắt ở ranh giới từ, thêm `…`. Hằng số trong code
  (`CITATION_QUOTE_CHARS`), KHÔNG đưa vào `system_config` (chưa có nhu cầu admin chỉnh; thêm field
  vô dụng là vi phạm nguyên tắc `system-config-plan.md` tự đặt ra).
- **KHÔNG dùng LLM chọn câu liên quan nhất** để làm quote. Đắt, chậm, và mở đường cho bịa. Chấp
  nhận đánh đổi: quote đầu chunk **có thể không chứa đúng fact** LLM đã dùng — đó chính là lý do
  tồn tại của tầng click-xem-full.
- **Bỏ blockquote inline** hiện tại ở [CitationList.tsx:25-29](../../apps/frontend/src/features/chat/CitationList.tsx#L25-L29).
  Có hover + click rồi thì inline chỉ làm danh sách nguồn dài lê thê. (Đằng nào block này cũng
  **chưa từng hiện** vì `quote` luôn `None`.)
- **Mobile/touch không có hover** → click là đường duy nhất, và click luôn có sẵn ở mọi thiết bị.
  Không làm long-press.
- Message **cũ** trong DB không có `quote` → hover hiện *"Nhấn để xem nguồn"* thay vì trích đoạn.
  Không backfill, không migration.

## 3. Bố cục khối Nguồn (chốt 2026-07-12 sau khi nhìn UI thật)

Bản hiện tại **thô và lặp**: 6 dòng, mỗi dòng wrap 2 hàng, breadcrumb
`Thời kì thuộc địa › 7. Phong trào Cần vương ›` lặp **6/6 dòng**, tên file `lichsu.clean.md`
lặp 6 lần. Khối nguồn cao gần bằng câu trả lời và tranh mất sự chú ý với chính nội dung.

**Ba thay đổi, theo thứ tự tác động:**

1. **BỎ HẲN tên file khỏi UI.** Cả kho chỉ có **đúng 1 file** → in tên nó 6 lần là 6 lần nói một
   điều ai cũng biết. `.clean.md` còn là chi tiết pipeline nội bộ, không phải tên sách — với giáo
   viên đó là rác. (Vẫn giữ `source_file` trong payload/DB; chỉ **không render**. Khi nào kho có
   nhiều tài liệu thật — xem "Bước 1" ở `CLAUDE.md` — thì hiện lại **tên tài liệu**
   (`documents.name`), KHÔNG bao giờ hiện tên file.)
2. **Số dòng chuyển vào MODAL.** Ở danh sách, `375-378` không nói lên gì (không ai đếm dòng file
   markdown). Trong modal, đặt cạnh full text thì cùng con số đó thành **provenance thật**: *"đoạn
   này nằm ở dòng 375–378 của tài liệu"*. Đổi chỗ là đổi hẳn ý nghĩa.
3. **GỘP citation theo mục** (`heading_path`), breadcrumb chung rút ra **1 dòng chân**.

> Điểm 3 **không phải để đẹp — không gộp thì SAI**. Bỏ tên file + số dòng (điểm 1&2) khiến `[1]`
> và `[3]` (cùng mục "Lê Thành Phương", chunk khác nhau) render ra **hai dòng trông y hệt nhau**,
> không còn gì phân biệt. Gộp là hệ quả bắt buộc của việc bỏ hai thứ kia.

```
NGUỒN                                    6 trích đoạn · 4 mục

  Khởi nghĩa của Lê Thành Phương ở Phú Yên (1885-1887)      [1] [3]
  Khởi nghĩa của Lê Trực và Nguyễn Phạm Tuân ở Quảng Bình   [2] [4]
  Khởi nghĩa Bãi Sậy                                        [5]
  Kết thúc phong trào Cần Vương                             [6]

  ── Thời kì thuộc địa › 7. Phong trào Cần vương
```

**Luật gộp (thuần, tách hàm riêng để test — không I/O):**

- Đơn vị tương tác vẫn là **từng citation** (chip `[n]`), KHÔNG phải nhóm. Hover/click chip nào ra
  chunk nấy. Nhóm chỉ là cách **xếp chỗ**.
- `n` = **thứ tự gốc trong mảng `citations`** (1-based), giữ nguyên để khớp với `[n]` LLM có thể
  nhắc trong câu trả lời. Gộp KHÔNG được đánh số lại.
- Gom theo `heading_path` **đầy đủ, so khớp chính xác**. Nhóm xếp theo chip nhỏ nhất trong nhóm →
  thứ tự đọc vẫn `[1] [2] [3]…` từ trên xuống.
- **Dòng chân = tiền tố chung dài nhất** của mọi `heading_path`; tiêu đề nhóm = **phần còn lại**
  sau khi trừ tiền tố đó. **Giữ dòng chân** (không bỏ): khi nguồn rải nhiều chương thì tiền tố
  chung ngắn lại/rỗng, các nhóm tự tách ra theo chương — lúc đó nó có việc thật để làm.
- Biên cần xử lý: tiền tố chung **rỗng** (nguồn rải rác) → không render dòng chân, tiêu đề nhóm =
  full path. Tiền tố chung **nuốt trọn** `heading_path` (mọi citation cùng một mục lá) → tiêu đề
  nhóm rỗng → lùi lại 1 cấp, để cấp cuối làm tiêu đề. `heading_path` **rỗng** → gom vào nhóm
  *"Không rõ mục"*, chip vẫn hover/click bình thường.
- Header khối: `{tổng chip} trích đoạn · {số nhóm} mục`. Chỉ 1 nhóm → bỏ phần `· N mục`.

## 4. Phân quyền endpoint mới — điểm cần chốt rõ

`models/inspect.py::get_chunk` đã có sẵn, nhưng router
[inspect.py:27](../../apps/backend/app/api/inspect.py#L27) gác `require_admin` **toàn router** →
giáo viên gọi là 403. Nên **thêm endpoint riêng cho luồng chat**, KHÔNG hạ quyền router admin.

**Chốt: bất kỳ user đã đăng nhập đều đọc được chunk bất kỳ** (`get_current_user`, không
`require_admin`). Lý do: corpus là SGK lịch sử, không phải dữ liệu mật; và user vốn đã moi được
nội dung đó ra qua việc hỏi. Thêm rào chỉ tăng phức tạp mà không tăng bảo mật thật.

> Phương án chặt hơn (**KHÔNG chọn**): chỉ cho phép `chunk_id` từng xuất hiện trong `citations`
> của conversation mà user sở hữu. Tốn thêm 1 query join `messages`, và vẫn không chặn được gì
> có ý nghĩa. Ghi lại phòng khi sau này corpus có tài liệu nội bộ/nhạy cảm — lúc đó mới cần.

## 5. Ba pha (làm tuần tự, verify từng pha)

### Pha 1 — Trả nợ `quote` (agent-service)
Không đụng backend, không đụng frontend. Sau pha này quote đã chảy tới DB và FE tự render
blockquote cũ → **verify được ngay** bằng mắt trước khi làm tiếp.

- `app/orchestrator/nodes.py`
  - Thêm `CITATION_QUOTE_CHARS = 240` + helper `_make_quote(text: str) -> str | None`
    (strip → rỗng thì `None`; ngắn hơn ngưỡng thì trả nguyên; dài hơn thì cắt ở ranh giới từ + `…`).
  - `_build_citation`: `quote=_make_quote(chunk.text)` thay cho `quote=None`.
- Test: `tests/test_orchestrator_*.py` — quote ngắn giữ nguyên; quote dài bị cắt và kết thúc `…`;
  chunk rỗng/whitespace → `None`; **không cắt giữa từ**.

### Pha 2 — Bố cục mới + hover (frontend, không network)
Gộp §3 và hover vào **một pha**: bỏ tên file/số dòng mà chưa gộp nhóm thì UI **sai** (dòng trùng
nhau), nên hai việc này không tách ra được.

- `src/features/chat/groupCitations.ts` (**mới**, thuần, không I/O): `groupCitations(citations)` →
  `{ groups: [{ title, chips: [{ n, citation }] }], commonPath: string[] }`. Toàn bộ luật ở §3.
- `src/features/chat/CitationList.tsx`: render theo nhóm + dòng chân `commonPath`. Bỏ tên file, bỏ
  số dòng, **bỏ blockquote inline**. Chip `[n]` là `<button>` (focus được, chuẩn bị cho Pha 3), bọc
  Radix Tooltip (`@radix-ui/react-tooltip` **đã cài sẵn**, không thêm dependency): nội dung =
  `citation.quote`, fallback *"Nhấn để xem nguồn"*.
- Test `groupCitations` (phần dễ sai nhất, test kỹ hơn UI): 2 citation cùng `heading_path` → 1 nhóm
  2 chip; số chip giữ **thứ tự gốc**, không đánh số lại; tiền tố chung rỗng → `commonPath` rỗng +
  tiêu đề nhóm full path; mọi citation cùng một mục lá → tiêu đề nhóm không rỗng (lùi 1 cấp);
  `heading_path` rỗng → nhóm *"Không rõ mục"*.
- Test UI: hover chip có quote → tooltip chứa quote; không quote → tooltip chứa fallback; **không
  còn chuỗi `lichsu.clean.md` nào** trong DOM khối nguồn.

### Pha 3 — Click xem full nguồn (backend + frontend)
**Backend:**
- `app/schemas/chat.py`: `SourceDetail` = `chunk_id`, `text`, `heading_path`, `start_line`,
  `end_line`. **Không** trả `referencing_events` (thông tin KB Inspector, user không cần).
  **Lệch plan gốc (lúc code)**: bỏ luôn `source_file` + `chunk_index` — modal KHÔNG hiện tên
  file (§3 điểm 1) và không dùng `chunk_index`, trả field không client nào đọc thì chính là
  rác API.
- `app/api/chat.py`: `GET /sources/{chunk_id}` → `/api/chat/sources/{chunk_id}`, dùng
  `get_current_user`. Tái dùng `models.inspect.get_chunk` qua `anyio.to_thread`. Không thấy → 404
  `not_found`. Bảng `rag_chunks` chưa tồn tại → `UndefinedTable` → 404 (pattern `cost.py`), KHÔNG
  để 500 thô. **Lệch plan gốc (lúc code)**: `UndefinedTable` bắt ngay trong
  `models/inspect.py::get_chunk` (đúng tầng data access, giống `cost.py`) chứ không bắt ở API →
  KB Inspector dùng chung hàm này cũng hết 500 thô trên DB trống, đổi thành 404 (tốt hơn).
- Test: 200 đúng shape; 404 chunk lạ; 401 khi chưa đăng nhập; **teacher gọi được** (khác
  `/api/admin/kb/chunks` vẫn phải 403 với teacher — giữ nguyên).

**Frontend:**
- `src/api/chat.ts`: `getSource(chunkId)`.
- `components/Modal.tsx`: thêm prop `size` (`md` mặc định | `lg`) — **lệch plan gốc (lúc code)**:
  `max-w-md` sẵn có quá hẹp cho khối văn bản dài, chữ vỡ dòng liên tục. Thêm 1 prop rẻ hơn nhân
  bản boilerplate Dialog.
- `src/features/chat/SourceModal.tsx` (mới): Radix Dialog qua `components/Modal.tsx` **đã có**.
  Header = tiêu đề mục (cấp cuối `heading_path`) + `dòng {start_line}–{end_line}` — **đây là chỗ
  DUY NHẤT số dòng được hiện** (§3 điểm 2). Breadcrumb đầy đủ để dạng phụ, mờ. **Không** in tên
  file. Body = full text chunk, cuộn được. Fetch bằng TanStack Query, key `["source", chunkId]` →
  cache, mở lại không gọi lại. `Spinner` lúc load, thông báo lỗi khi 404.
- `CitationList.tsx`: click chip `[n]` → mở modal với `chunk_id` tương ứng.
- Test: click chip → gọi đúng `chunkId`; header hiện `dòng 375–378`; loading/error render đúng.

## 6. KHÔNG làm (chốt luôn để khỏi trôi scope)

- **Không** highlight chính xác câu/đoạn LLM đã dùng bên trong chunk (cần offset mapping từ answer
  ngược về source — việc lớn, độ chính xác không đảm bảo).
- **Không** đọc `lichsu.clean.md` lúc runtime để hiện ngữ cảnh quanh `start_line`/`end_line`. Chunk
  text là đủ. (Nếu sau này muốn "xem thêm ngữ cảnh trước/sau" thì nối chunk kề theo `chunk_index`,
  không đụng file.)
- **Không** deep-link từ chat sang KB Inspector (`/admin/kb/chunks`) — điều hướng chéo đã bị bỏ có
  chủ đích ở Item 1 `admin-restructure-plan.md`, và giáo viên vốn không vào được trang admin.
- **Không** khôi phục node `validate_citations` trong pha này. Quote lấy trực tiếp từ chunk đã
  retrieve nên không phụ thuộc node đó. Việc riêng, plan riêng.
- **Không** gộp chunk kề nhau thành 1 chip (vd `[1]`+`[3]` cùng mục, dòng 375-378 và 386-388 →
  một nguồn duy nhất). Nghe hợp lý nhưng **kề về dòng ≠ liền mạch về nội dung**, và gộp xong thì
  modal hiện text nào? Giữ 1 chip = 1 chunk = 1 đơn vị retrieval thật.
- **Không** đổi cách hiển thị ở KB Inspector (admin). Ở đó `chunk_id`/`source_file`/số dòng là
  thông tin **đúng nghiệp vụ** — admin cần soi kho. Chỉ khối Nguồn phía người dùng mới giấu.

## 7. Verify

1. Hỏi 1 câu có nguồn → khối Nguồn gộp theo mục, **không còn chữ `lichsu.clean.md`**, breadcrumb
   chung chỉ xuất hiện **1 lần** ở dòng chân.
2. Hover chip thấy trích đoạn; click thấy full text đúng đoạn corpus + `dòng 375–378` ở header.
3. Hỏi câu mà nguồn **rải nhiều chương** → tiền tố chung ngắn/rỗng → nhóm tự tách theo chương,
   không vỡ layout.
4. Reload lại phiên cũ → quote vẫn còn (đã nằm trong `messages.citations` JSONB).
5. Mở lại **message cũ trước Pha 1** → không vỡ, hover hiện fallback, click vẫn xem được full.
6. Login teacher: `/api/chat/sources/{id}` **200**, `/api/admin/kb/chunks` vẫn **403**.

## 8. Kết quả (2026-07-12) — đã chạy thật, không chỉ test

**Test tự động**: agent-service 212 pass (thêm 6 test `_make_quote` + quote trong citation),
backend +5 test `tests/test_sources.py`, frontend 35 pass (thêm 12 test `groupCitations` + 9 test
`CitationList` gồm hover/click/lỗi). Typecheck + `vite build` sạch. mypy agent-service không phát
sinh lỗi mới (4 lỗi cũ ở `cleaner.py`/`llm_chunker.py` có từ trước, không đụng tới).

**Chạy thật** (agent :9000 + backend :8000, Postgres/Qdrant/Neo4j remote, hỏi *"Khởi nghĩa Trương
Định diễn ra như thế nào?"* bằng tài khoản teacher):

- Event `citations` về **2 citation, cả 2 đều CÓ `quote`** — dài 239/237 ký tự (≤ 240 + `…`), cắt
  đúng ranh giới từ, không sót khoảng trắng trước `…`.
- Quote **lưu được vào `messages.citations`** (JSONB) → reload phiên cũ vẫn còn, không cần backfill.
- `GET /api/chat/sources/lichsu_clean-000001` (teacher): **200**, trả đúng 5 field, toàn văn
  **2590 ký tự** — gấp ~11 lần quote, xác nhận quyết định KHÔNG nhồi full text vào SSE là đúng.
- Biên bảo mật: chunk lạ **404**, không token **401**, teacher gọi `/api/admin/kb/chunks` vẫn
  **403** (mở đường xem nguồn KHÔNG nới lỏng router admin).
- Cả 2 citation của câu hỏi này cùng `heading_path` → rơi đúng vào biên "tiền tố chung nuốt trọn
  path" → gộp 1 nhóm tiêu đề *"Diễn biến"*, dòng chân *"Thời kì thuộc địa › 1. Khởi nghĩa Trương
  Định(1859-1864)"*. Biên này đã có test riêng.

**Còn lại cho người dùng**: nhìn mắt trên trình duyệt (hover/click ở UI thật) — phần API và dữ
liệu đã verify xong.

> **Bẫy test đã gặp, ghi lại kẻo dẫm lại**: trong Vitest, `beforeEach(() => vi.mocked(fn).
> mockReset())` (hoặc `mockClear()`) áp lên module automock rồi để mock **reject** sẽ làm
> rejection thoát ra thành *unhandled error* → fail test dù UI lỗi render đúng. Cách né: đừng
> clear ở `beforeEach`; test nào cần đếm số lần gọi thì tự `mockClear()` **trong** test đó (test
> resolve nên không dính). Ngoài ra jsdom thiếu `ResizeObserver` mà Radix Popper (Tooltip) cần →
> `vi.stubGlobal` stub tối thiểu.
