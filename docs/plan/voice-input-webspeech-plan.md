# Voice input (nói → text) bằng **Web Speech API** — bản frontend-only

> **Trạng thái**: ĐÃ CODE XONG. `continuous = true` (bản `false` nói được một tí đã tắt, đã đổi).
> typecheck + 104 test + build PASS. **Còn lại**: verify bằng giọng thật trên Chrome (Phase 0).
> **Hướng**: dùng `SpeechRecognition` sẵn có của trình duyệt (Chrome/Edge/Safari), `lang="vi-VN"`.
> **Phạm vi**: CHỈ frontend — không thêm service, không model, không đụng GPU, không đổi backend.
> **Quan hệ với plan cũ**: [`voice-input-plan.md`](./voice-input-plan.md) (sherpa-onnx + Zipformer
> 30M self-hosted, GPU) **vẫn giữ nguyên, không xoá** — là phương án tự chủ để dành. Hai plan
> loại trừ nhau ở tầng runtime nhưng dùng chung phần UI/UX ở `Composer`.

## Context — vì sao làm

[`Composer.tsx`](../../apps/frontend/src/features/chat/Composer.tsx) hiện chỉ cho gõ tay. Gõ tiếng
Việt có dấu chậm với giáo viên hỏi nhanh. Mục tiêu: **nút mic cạnh nút Gửi** — bấm để nói, chữ
**đổ dần** vào ô nhập, xem/sửa rồi bấm Gửi. **KHÔNG tự gửi** (tránh gửi nhầm khi nhận sai).

## ⚠️ Đánh đổi — PHẢI ghi vào báo cáo

Plan cũ đã chủ động loại Web Speech API vì tính tự chủ. Chọn lại nó thì phải trung thực:

| Điểm | Thực tế |
|---|---|
| Nơi nhận diện | Chrome/Edge **gửi audio lên server Google**; Safari gửi lên Apple. Không chạy offline. |
| Trình duyệt | Chrome/Edge/Safari **có**; **Firefox KHÔNG** → phải ẩn nút mic khi không hỗ trợ. |
| Bảo mật ngữ cảnh | Bắt buộc **HTTPS hoặc `localhost`**. Dev `localhost:5173` OK; deploy phải có TLS. |
| Mạng | Mất mạng → lỗi `network`, không có fallback. |
| Kiểm soát | Không chỉnh được model/WER, không tự host, phụ thuộc chính sách của Google. |

Đổi lại: `vi-VN` của Google nhận tốt, **tự chấm câu và viết hoa**, tích hợp ~1 buổi thay vì cả
tuần vật lộn CUDA DLL. Cách trình bày thành thật trong báo cáo: *"đã khảo sát 2 hướng, hiện thực
hướng A (Web Speech API) vì chi phí tích hợp thấp; hướng B (Zipformer self-hosted) đã verify được
đường GPU và giữ làm phương án thay thế khi cần tự chủ."*

## `continuous = true` — và cái giá của nó

Bản đầu chạy `continuous = false` (mặc định của API) cho gọn, nhưng **test thật thấy nói được một
tí đã tắt**: engine đóng phiên ngay sau câu đầu tiên. Đã đổi sang `continuous = true`.

Cờ này **không** làm engine chạy mãi — Chrome vẫn tự đóng phiên sau một quãng im lặng (không có
con số chính thức, quan sát được ~5–8 giây, đổi theo phiên bản). Nên hook phải **tự mở phiên mới**
và **tự gom text qua các phiên**. Đó là toàn bộ độ phức tạp thêm vào:

| Cơ chế | Vì sao bắt buộc |
|---|---|
| `wantListeningRef` | Phân biệt "user muốn dừng" với "Chrome tự tắt" — hai thứ bắn ra CÙNG sự kiện `onend` |
| `committedRef` | `event.results` reset rỗng mỗi phiên mới → không chốt trước thì phiên sau đè mất phiên trước |
| Lỗi khác `no-speech` → tắt `wantListening` | Quyền mic bị chặn mà vẫn mở lại phiên = vòng lặp vô hạn |
| Sanity check `MIN_SESSION_MS` (300ms) | Backstop cho trường hợp `onend` bắn tức thì mà không kèm lỗi nào |
| Auto-stop 60s | Không còn giới hạn tự nhiên → mic mở quên tắt cả buổi |

**Chốt thiết kế khác với dự đoán ban đầu ở chỗ**: KHÔNG cần state `stopping`, KHÔNG cần timeout
3s, KHÔNG cần đếm burst restart. Lý do ở "Ba điểm thiết kế" ngay dưới — `stop()` tắt `listening`
đồng bộ nên không có trạng thái kẹt để mà cần van xả, và việc tắt `wantListening` ngay trong
`onerror` đã cắt mọi vòng lặp do lỗi, chỉ còn lại đúng một backstop theo thời gian.

## Ba điểm thiết kế làm cả lớp bug biến mất

**1. Dựng lại toàn bộ chuỗi từ `event.results` mỗi lần `onresult`** — không cộng dồn, không đọc
`isFinal`, không ghi theo index. `event.results` là danh sách tích luỹ của cả phiên, nên đọc lại
từ đầu luôn ra chuỗi đúng ở mọi thời điểm. Cách này miễn nhiễm với chuyện một result bị phát lại
khi chuyển interim → final (cộng dồn kiểu `text += transcript` sẽ **nhân đôi chữ**).

**2. Chốt text của phiên vào `committedRef` trong `onend`, TRƯỚC khi mở phiên mới** — vì
`event.results` của phiên mới bắt đầu từ rỗng. `transcript` đẩy ra ngoài luôn là
`committed + phiên hiện tại`, nên câu sau không bao giờ đè câu trước.

**3. Đổ transcript thẳng vào `text` state của `Composer` ngay khi có** — thay vì giữ trong hook
rồi "chốt" lúc `onend`. Nhờ vậy **không có khoảnh khắc nào cần chốt**, nên:
- Không mất chữ cuối. `recognition.stop()` là bất đồng bộ — spec ghi nó *"stop listening and
  **attempt to return a result** using the audio captured so far"*, tức còn một `onresult` nữa
  sau lời gọi. Với thiết kế này, kết quả đó tới lúc nào thì vào ô nhập lúc đó, không cần chờ.
- `stop()` set `listening = false` **ngay**, không chờ `onend` → UI mở khoá tức thì, không có
  trạng thái kẹt, nên **không cần timeout 3s** làm van xả.

## Kiến trúc

```
Composer.tsx  ──bấm mic──>  useSpeechRecognition()  ──>  window.SpeechRecognition (trình duyệt)
     ▲                              │                          │  (trình duyệt tự xin quyền mic,
     └──── transcript (đổ dần) ─────┘                          │   tự thu audio, tự gửi lên cloud)
```

Không WebSocket, không `getUserMedia`, không `AudioContext`, không downsample — trình duyệt lo hết.

Quyết định phụ:
- Hook đặt cạnh feature đang dùng: `src/features/chat/useSpeechRecognition.ts` (cùng chỗ với
  `useChat.ts`, `useConversations.ts`).
- **Toàn bộ nằm trong `Composer`**, không đụng `ChatPanel.tsx`.
- Không thêm biến môi trường, không thêm dependency (`lucide-react` đã có sẵn).

## Phase 0 — GATE: verify tay trên trình duyệt

Mở Chrome ở `http://localhost:5173`, dán vào DevTools console:

```js
const R = window.SpeechRecognition ?? window.webkitSpeechRecognition;
const r = new R();
r.lang = "vi-VN"; r.continuous = true; r.interimResults = true;
r.onresult = (e) => console.log([...e.results].map((x) => `${x.isFinal ? "F" : "i"}:${x[0].transcript}`));
r.onerror = (e) => console.warn("err", e.error);
r.onend = () => console.log("ended");
r.start();
```

**Gate qua khi**: nói *"Cách mạng Tháng Tám năm một chín bốn lăm"* ra đúng chữ có dấu, và quan sát
được `i:` chuyển thành `F:`. Không qua → dừng, quay lại plan cũ.

Nhân tiện quan sát luôn: im lặng vài giây sẽ thấy log `ended` **dù đã bật `continuous`** — đây
chính là hiện tượng buộc hook phải tự mở phiên mới. Con số bao nhiêu giây không quan trọng và
KHÔNG được hard-code: hook chỉ phản ứng với sự kiện `onend`, không đếm im lặng.

## Phase 1 — Khai báo type `SpeechRecognition`

**Đã kiểm chứng**: `lib.dom.d.ts` của TypeScript 5.9.3 trong `node_modules` của repo **không có**
`SpeechRecognitionEvent`. Thiếu bước này thì `npm run typecheck` gãy.

Tạo `src/types/speech-recognition.d.ts`. File `.d.ts` vẫn là **global script** dù `tsconfig` bật
`"moduleDetection": "force"` (cờ đó chỉ áp cho file *non-declaration*), giống cách
[`vite-env.d.ts`](../../apps/frontend/src/vite-env.d.ts) khai báo `ImportMetaEnv`.

Chỉ khai báo **những gì code thật sự dùng** (`lang`, `continuous`, `interimResults`, `start`,
`stop`, `abort`, `onresult`, `onerror`, `onend`) — không chép cả spec vào cho đủ bộ. Riêng union
mã lỗi thì khai báo đủ 8 giá trị vì `switch` phải so được với mọi mã.

**KHÔNG khai báo `declare var SpeechRecognition`** — làm thế là nói dối TS rằng biến luôn tồn tại,
trong khi Firefox không có. Chỉ khai báo qua `interface Window` để mọi chỗ buộc phải xử lý
`undefined`.

## Phase 2 — Hook `useSpeechRecognition`

`src/features/chat/useSpeechRecognition.ts`, trả ra:

```ts
{ supported: boolean; listening: boolean; transcript: string; error: string | null;
  start(): void; stop(): void }
```

- `supported` tính **bên trong hook** bằng `useState(() => ...)`, KHÔNG ở module scope — tính ở
  module scope thì giá trị bị chốt lúc `import`, và test `delete window.SpeechRecognition` sẽ
  không ăn.
- **Feature detect chứ không sniff `navigator.userAgent`**: UA của Edge/Brave/Cốc Cốc đều chứa
  "Chrome", còn Firefox bật pref lên thì API chạy được thật.
- Tạo instance **mới mỗi phiên** (`beginSession()`, dùng chung cho lần bấm đầu và các lần tự mở
  lại) → không phải lo trạng thái sót lại giữa các phiên.
- `start()` set `listening = true` **đồng bộ**, không cần `onstart`. Không có đường nào gọi
  `start()` hai lần (nút đổi sang "dừng" ngay khi `listening`), nên **không cần guard/try-catch**.
- `onerror`: `no-speech` bỏ qua hoàn toàn (để `onend` mở phiên mới — đây là đường sống của UX nói
  ngập ngừng). Mọi mã còn lại **tắt `wantListening`** rồi mới báo; riêng `aborted` tắt mà không
  báo gì vì do chính ta gọi `abort()`.
- Unmount → clear timer auto-stop, tắt `wantListening`, gỡ handler **trước** rồi `abort()`. Không
  gỡ handler trước thì `onend` sẽ mở phiên mới trên component đã chết.

## Phase 3 — Nút mic trong `Composer`

- Nút đặt **giữa textarea và nút Gửi**. Icon `Mic` (rảnh) / `Square` (đang nghe) từ `lucide-react`
  — `Square` đã dùng ở [`TimelineBar.tsx`](../../apps/frontend/src/features/timeline/TimelineBar.tsx)
  nên nhất quán; **không** dùng `MicOff` vì mic-gạch-chéo đọc như "mic đang tắt", ngược nghĩa.
  Có `aria-label` (*"Nói"* / *"Dừng nói"*) — test tìm nút theo tên, và tốt cho accessibility.
- **`supported === false` → không render nút** (Firefox). Không hiện nút chết bấm không ăn.
- Lưu `baseTextRef.current = text` lúc bấm mic; mỗi lần `transcript` đổi thì
  `setText(base + " " + transcript)` → giữ phần user đã gõ trước đó làm tiền tố.
- `readOnly` textarea khi đang nghe — không cho vừa nói vừa gõ ở MVP.
- **Khoá Gửi + Enter khi đang nghe** — không thì user bấm Gửi giữa chừng sẽ gửi transcript dở.
- **`disabled` (đang stream câu trả lời)** → khoá nút mic; đang nghe mà `disabled` bật lên thì tự
  `stop()` (đường vào: bấm câu hỏi mẫu ở empty-state trong lúc mic đang mở).
- Đang nghe: nút đổi màu + `animate-pulse`. Lỗi: một dòng chữ nhỏ màu đỏ dưới ô nhập.

## Phase 4 — Test

`src/features/chat/Composer.test.tsx` — theo nếp
[`ChatPanel.test.tsx`](../../apps/frontend/src/features/chat/ChatPanel.test.tsx): `// @vitest-environment jsdom`
dòng đầu, `afterEach(cleanup)`, không có setup file toàn cục.

**jsdom không có `SpeechRecognition`** → mặc định rơi vào nhánh không hỗ trợ; phải cắm fake vào
`window` trước khi `render`. Fake phải **bất đồng bộ đúng như thật**: `stop()` không được gọi
`onend` ngay trong thân hàm, mà phải cho phép test bắn `onresult` cuối rồi mới `onend` — fake đồng
bộ sẽ **xanh trên cả code sai**.

Hook so `Date.now()` để phát hiện phiên đóng bất thường nhanh, nên test phải **lái được đồng hồ**
(`vi.spyOn(Date, "now")`), và ca auto-stop 60s cần `vi.useFakeTimers()` + `fireEvent` thay cho
`userEvent` để không vướng timer giả.

Ca test (14 ca):
1. Không hỗ trợ → **không có** nút mic; ô nhập vẫn gửi được như cũ.
2. Bấm mic → tạo recognition, nút đổi sang "Dừng nói", **Gửi bị khoá**, textarea `readOnly`.
3. Cấu hình engine: `lang = "vi-VN"`, `interimResults`, `continuous` — fake khởi tạo **ngược lại**
   để ca này chứng minh hook có ghi đè thật.
4. `onresult` phát lại cùng result → **không nhân đôi** (điểm thiết kế 1).
5. Có sẵn text gõ tay → chữ đọc ra **nối sau**, không xoá phần đã gõ.
6. Chrome tự đóng phiên giữa chừng → **mở phiên mới**, và chữ phiên trước **không mất** khi phiên
   mới trả result (điểm thiết kế 2).
7. `onend` bắn tức thì (dưới 300ms) → dừng hẳn, báo lỗi thiết bị, **không quay vòng**.
8. Bấm dừng → UI mở khoá **ngay**, và `onresult` tới **sau** `stop()` vẫn vào ô nhập (điểm thiết
   kế 3 — mất chữ cuối).
9. `not-allowed` → báo lỗi quyền mic và **KHÔNG** mở lại phiên.
10. `no-speech` → **không** báo lỗi, vẫn mở phiên mới.
11. Quá 60s → tự dừng.
12. Nói xong sửa tay rồi Gửi → `onSend` nhận đúng chuỗi.
13. `disabled` bật lên khi đang nghe → mic tự tắt.
14. Unmount khi đang nghe → `abort()` được gọi.

## Verify end-to-end

1. Phase 0 pass (nghe ra đúng chữ tiếng Việt trên Chrome).
2. `npm run dev` → bấm mic → nói một câu, **im vài giây rồi nói tiếp câu hai** → cả hai câu cùng
   nằm trong ô nhập, không đè nhau → bấm dừng → sửa tay → Gửi chạy như cũ.
3. Ca lỗi: chặn quyền mic (Chrome → ổ khoá → Micro → Block) → báo lỗi rõ, **không quay vòng xin
   lại**; đổi route khi đang nghe → mic tắt hẳn (đèn mic của trình duyệt tắt).
4. Mở Firefox → **không thấy nút mic**, phần còn lại của composer nguyên vẹn.
5. `npm run typecheck` + `npm run test` + `npm run build` PASS.

## Nâng cấp về sau

**Chrome on-device** — gỡ điểm yếu "gửi audio lên Google" bằng
`SpeechRecognition.available?.({ langs: ["vi-VN"], processLocally: true })` + `install()` +
`processLocally = true`. **Phải feature-detect** và **phải nghe thử bằng giọng thật** rồi mới kết
luận — chưa ai trong repo verify tiếng Việt on-device.

## Ngoài phạm vi

- Text-to-speech đọc câu trả lời.
- Tự gửi khi im lặng (VAD) — cố ý không làm, tránh gửi nhầm.
- Chọn ngôn ngữ khác `vi-VN` trong UI.
