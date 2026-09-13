# Báo cáo đánh giá hệ thống RAG — bộ `auto_rag_v2`

Ngày lập: 2026-09-08 · Sửa lần 1 sau rà soát (`auto_rag_v2.BAOCAO.review.md`)
Bộ dữ liệu: `retrieval_qa_v2.json` (100 câu hỏi lịch sử Việt Nam) · Kết quả chạy: `auto_rag_v2.json`

---

## 1. Tóm tắt

Hệ thống được đánh giá theo hai lớp:

- **Lớp tự động**: RAGAS 0.4.3, năm metric, prompt tiếng Việt. Bản đủ 100 câu được chọn làm baseline.
- **Lớp rà soát nội dung**: chấm lại theo rubric mệnh đề tự định nghĩa, ghi lý do từng câu.

| Metric | RAGAS (baseline) | Rà soát nội dung | Trạng thái bản rà soát |
|---|---:|---:|---|
| `context_precision` | **0.8658** | 0.8968 | **Proxy tự động — không dùng** |
| `context_recall` | **0.9672** | 0.9935 | **Ước tính sơ bộ — chưa xác nhận** |
| `factual_correctness` / độ phủ đáp án mẫu | **0.8268** | 0.92 – 0.96 | Có bảng 473 mệnh đề; rubric còn tranh luận |
| `faithfulness` | **0.8280** | 0.9942 | **Ước tính theo câu, rubric có điểm một phần** |
| `answer_relevancy` | **0.8071** | 0.9933 | Có bảng 192 vế câu hỏi |

**Kết luận thận trọng:**

> Bản RAGAS baseline cho thấy khâu tra cứu đạt điểm cao. Rà soát nội dung phát hiện: một số **lỗi tổng hợp** (tiêu biểu qa-083 bỏ một vế đã có sẵn trong ngữ cảnh), một số **thiếu hụt tra cứu** (qa-045, qa-053 — bằng chứng cần thiết không nằm trong ngữ cảnh tra về), và một số **điểm judge bất thường** (mục 5.1). Chưa đủ dữ liệu để kết luận RAGAS chấm thấp *có hệ thống* trên tiếng Việt, hay xác định nguyên nhân của từng điểm bất thường.

Các điểm ở cột "rà soát nội dung" phản ánh **rubric riêng của báo cáo này**, không phải bộ nhãn chuẩn. Chúng không so sánh trực tiếp được với RAGAS vì đơn vị đếm khác nhau.

---

## 2. Số liệu chính thức để báo cáo

Bản RAGAS đủ 100 câu, được chọn làm baseline:

| Metric | Điểm |
|---|---:|
| `llm_context_precision_with_reference` | 0.8658 |
| `context_recall` | 0.9672 |
| `factual_correctness(mode=recall)` | 0.8268 |
| `faithfulness` | 0.8280 |
| `answer_relevancy` | 0.8071 |

> **Lưu ý:** không có manifest ghi model, prompt hash và tham số sinh của lần chạy, nên không khẳng định được đây là "một lần chạy, prompt đồng nhất". Gọi đúng là **bản gốc đủ 100 câu được chọn làm baseline**.

### Hai bản chấm lại — dùng để điều tra, không dùng làm điểm tổng

| Bản | Vì sao không đại diện |
|---|---|
| `factual_correctness.ids32.csv` | Tập 32 câu được chọn thiên về nhóm điểm thấp (nhưng **không** đúng 32 câu thấp nhất: có thêm qa-011, qa-031, qa-034; thiếu qa-053, qa-083, qa-094). Trung bình vá vào bảng chính sẽ thiên vị. |
| `faithfulness.ids20.csv` | Tương tự — tập chọn có TB trước khi chấm lại **0.6033**, trong khi 20 câu thấp nhất toàn bộ là **0.5884**; không đúng 20 câu thấp nhất (có thêm qa-004, qa-021). Hồi quy về trung bình là **cách giải thích khả dĩ**, chưa phải nguyên nhân đã xác định. |

Hai bản này vẫn hữu ích để soi các ca bất thường; chỉ không dùng để tính điểm tổng hay chứng minh độ ổn định.

---

## 3. Phương pháp và kết quả rà soát nội dung

### 3.1 Độ phủ đáp án mẫu (đối chiếu `factual_correctness`)

**Rubric.** Mỗi mệnh đề = một vế chủ–vị độc lập trong `gold_answer`; liệt kê trong cùng một vế tính là một mệnh đề. Trạng thái: `có` (1) / `một phần` (0,5) / `không` (0). Không trừ vì đáp án nói thêm.

Toàn bộ 473 mệnh đề liệt kê trong `auto_rag_v2.claims.md` / `.csv`.

| | |
|---|---:|
| Tổng mệnh đề | 473 |
| Được phủ đầy đủ / một phần / không | 431 / 20 / 22 |
| Quy điểm | 441 / 473 |
| Trung bình 100 câu (macro) | **0.9421** |
| Gộp toàn bộ mệnh đề (micro) | **0.9323** |
| Số câu đạt 1.00 | 69 / 100 |

**Ba kịch bản theo quy tắc điểm một phần** (không phải khoảng tin cậy):

| Quy tắc | Điểm |
|---|---:|
| Mọi nhãn "một phần" tính 0 | 0.9230 |
| Tính 0,5 (bản hiện tại) | 0.9421 |
| Mọi nhãn "một phần" tính 1 | 0.9612 |

> **Cách ghi trong báo cáo:** *"Độ phủ đáp án mẫu theo rubric của báo cáo: 0,92 – 0,96 tùy quy tắc điểm một phần, điểm giữa ≈ 0,94."*

**Chưa giải quyết:** bản rà soát `auto_rag_v2.claims.review.md` còn nêu các vấn đề rubric ở qa-016, qa-045, qa-083 và cách tách mệnh đề chưa nhất quán (xem mục 7).

### 3.2 Độ hoàn thành các vế câu hỏi (đối chiếu `answer_relevancy`)

**Rubric.** `số vế câu hỏi được trả lời / tổng số vế`. Danh sách vế của 100 câu hỏi trong `auto_rag_v2.ar_manual.csv`.

| | |
|---|---:|
| Tổng vế câu hỏi | 192 |
| Trả lời được | 190,5 |
| Macro | **0.9933** |
| Micro | **0.9922** |

**Phân bố:** 98 câu đạt 1.00 · **qa-045** = 0,83 (vế "cách chỉ huy" trả lời một nửa: có chỉ huy từng quân thứ, thiếu đại bản doanh và cơ chế chỉ huy thống nhất) · **qa-083** = 0,50 (bỏ hẳn vế Đại hội V Quốc tế Cộng sản 1924; câu trả lời vẫn đúng chủ đề nhưng thiếu một vế).

> **Không so sánh với RAGAS `answer_relevancy`.** RAGAS sinh ngược câu hỏi từ đáp án rồi đo cosine embedding; rubric trên là phán đoán nội dung. Hai construct khác nhau — hiệu số giữa chúng không có ý nghĩa.

### 3.3 `context_recall` — **ước tính sơ bộ, chưa xác nhận**

**Phương pháp.** Đo độ phủ từ vựng của từng mệnh đề đáp án mẫu với 8–10 chunk tra về; các mệnh đề dưới ngưỡng được kiểm bằng tìm chuỗi trực tiếp trong ngữ cảnh. Phân bố ngưỡng: 409 mệnh đề ≥ 0.85 · 61 trong khoảng 0.60–0.85 · 3 dưới 0.60.

| | |
|---|---:|
| Macro | 0.9935 |
| Micro (469/473) | 0.9915 |
| RAGAS | 0.9672 |

**Năm dòng mệnh đề bị trừ** (tổng trừ 4 điểm — hai dòng qa-053 mỗi dòng trừ 0,5):

| Câu | Claim # | Mệnh đề | Trừ |
|---|---:|---|---:|
| qa-045 | 6 | "một quân thứ trung tâm đóng tại đại bản doanh do Phan Đình Phùng trực tiếp chỉ huy" | 1,0 |
| qa-045 | 7 | "các quân thứ giữ liên lạc với đại bản doanh để bảo đảm chỉ huy thống nhất" | 1,0 |
| qa-053 | 4 | "cổ động dân quyền, tự chủ" — không có trong ngữ cảnh | 0,5 |
| qa-053 | 5 | môn "hát" — ngữ cảnh có chương trình Đông Kinh nghĩa thục nhưng khác cách gọi | 0,5 |
| qa-042 | 5 | "không có nghĩa hoạt động chỉ nêu ở một bên vắng mặt ở bên kia" — lời lưu ý của người soạn dataset | 1,0 |

**Giới hạn phải nêu rõ:**

1. Độ phủ từ vựng ≥ 0.85 **không chứng minh** ngữ cảnh hỗ trợ mệnh đề: vẫn có thể sai chủ thể, quan hệ, thời gian hoặc phủ định.
2. **Chưa có bảng verdict từng claim** (`id, claim_id, verdict, evidence, reason`). Chưa tái lập được tử số/mẫu số bằng kiểm tra từng đơn vị.
3. Có nên đưa lời lưu ý của người soạn (qa-042/5) vào mẫu số hay không là **quyết định rubric còn để ngỏ**.

**Về mức độ đồng thuận với RAGAS:** RAGAS cho `context_recall` < 1.0 ở **10 ID** — qa-009, 042, 045, 053, 073, 076, 083, 086, 088, 100 — chứ không phải 3. Bản rà soát chỉ trùng với RAGAS ở 3 trong số đó (qa-042, 045, 053). Đây là **một số trường hợp đồng thuận**, chưa đủ để kết luận metric này "hiệu chỉnh tốt" hay "đồng thuận hơn các metric khác".

### 3.4 `faithfulness` — ước tính bám nguồn theo câu, rubric có điểm một phần

**Phương pháp.** Ba lớp:

1. **Tự động — số liệu.** Trích 316 số trong 100 đáp án, đối chiếu ngữ cảnh. 3 báo động, 2 là giả (`3.` là dấu đánh số; `20.000` khớp "hơn 20 ngàn" trong nguồn), **1 vi phạm thật** (qa-069).
2. **Tự động — độ phủ từ vựng theo câu.** 647/648 câu đạt ≥ 0.70. *Phương pháp này không phát hiện được lỗi quan hệ* — qa-026 dùng đúng từ trong ngữ cảnh nhưng gán sai nhân vật.
3. **Đọc tay toàn bộ 100 đáp án**, cộng hai lượt rà soát.

**Đơn vị đếm.** Câu trả lời được tách thành câu; hai script dùng bộ lọc khác nhau: bản dò tự động loại câu dưới 4 từ nội dung (**648**), bản chấm cuối không loại (**653**). Bảng dưới dùng 653.

| | |
|---|---:|
| Tổng câu | 653 |
| **Tổng điểm bám ngữ cảnh** | **649 / 653** |
| Macro | 0.9942 |
| Micro | 0.9939 |

**649 là tổng điểm, không phải số câu.** Sáu câu vi phạm: qa-026 và qa-069 trừ 1,0 mỗi câu; qa-041, qa-066, qa-071, qa-092 trừ 0,5 mỗi câu.

| Câu | Trừ | Nội dung |
|---|---:|---|
| **qa-026** | 1,0 | Đặt Ghềnh Cốc vào mục Ngô Quyền (938). Ngữ cảnh 1 ghi rõ *"Ghềnh Cốc đã khiến **Trần Quốc Tuấn** phải chú ý"* (trận Bạch Đằng 1288) |
| **qa-069** | 1,0 | Từ "hơn 2,5 triệu" lên 10 triệu mà viết "tăng thêm **hơn** 7,5 triệu" |
| qa-041 | 0,5 | Ngữ cảnh: *"**Có lẽ** do ở nơi cư trú... rất hiếm quặng đồng"*; đáp án nêu như kết luận chắc chắn |
| qa-092 | 0,5 | Mở đầu giữ "có lẽ", đoạn kết khẳng định "công dụng chủ yếu là chặt, cắt" |
| qa-066 | 0,5 | Ngữ cảnh nêu chủ trương/đề nghị; đáp án khái quát thành "đã được triển khai" |
| qa-071 | 0,5 | Đưa "phép lưỡng thuế" vào nguyên nhân *trước* khởi nghĩa Mai Thúc Loan; ngữ cảnh không xác lập mốc này |

**Giới hạn:**

1. Chưa có quy tắc giải thích **vì sao qa-071 (sai phạm vi thời gian) trừ 0,5 còn qa-026 (sai nhân vật) trừ 1,0**.
2. `faith_manual.csv` chỉ có 100 dòng tổng hợp, **không có danh sách 653 đơn vị kèm đoạn bằng chứng** → chưa tái lập được.
3. Chưa xử lý các điểm nghi vấn mà rà soát trước nêu ở **qa-017** ("Đại La có ưu thế lớn hơn" — phép so sánh chưa được hai đoạn nguồn riêng chứng minh) và **qa-100** ("hai hướng chủ yếu" thay cho hai tác động chiến lược).
4. Lỗi quan hệ/quy kết chỉ phát hiện được bằng đọc; không loại trừ còn sót.

**Không dùng con số này để chứng minh RAGAS `faithfulness` chấm thấp có hệ thống.**

### 3.5 `context_precision` — không dùng bản rà soát

Số 0.8968 là **proxy tự động** (chunk coi là hữu ích nếu hỗ trợ ≥ 1 mệnh đề đáp án mẫu ở ngưỡng phủ từ vựng 0.65), không phải phán đoán nội dung. Proxy lệch rõ: qa-055 cho 0.61 trong khi RAGAS cho 1.00, do đáp án mẫu ngắn nên ít chunk vượt ngưỡng dù vẫn hữu ích.

**Dùng số RAGAS: 0.8658.**

---

## 4. Lỗi phát hiện được ở hệ thống

### 4.1 Lỗi nội dung — 7 câu lỗi đáp án + 1 câu mâu thuẫn nguồn

| Câu | Loại |
|---|---|
| qa-026 | Quy sai nhân vật (Ghềnh Cốc → Ngô Quyền thay vì Trần Quốc Tuấn) |
| qa-069 | Sai suy luận số học |
| qa-083 | Bỏ hẳn một vế của câu hỏi (Đại hội V QTCS 1924) dù ngữ cảnh 6 có đủ nội dung |
| qa-041, qa-092 | Mất sắc thái phỏng đoán của nguồn |
| qa-066 | Đẩy chủ trương/đề nghị thành "đã thực hiện" |
| qa-071 | Gán sai phạm vi thời gian cho chính sách |
| *qa-012* | *Lặp lại mâu thuẫn niên đại vốn có trong nguồn (208 TCN vs đầu thế kỉ III TCN) — **lỗi nguồn**, không phải bịa* |

### 4.2 Rò rỉ định danh chunk ra đáp án — 5 câu

`qa-026`, `qa-050`, `qa-076`, `qa-089`, `qa-090` để lọt chuỗi dạng `(tap3_clean-000070, tap3_clean-000071)`. Nhiều khả năng do prompt tổng hợp, nhưng cách render/ẩn trích dẫn ở đầu ra cũng có thể liên quan — cần kiểm tra cả hai.

### 4.3 Vấn đề của bộ dữ liệu đánh giá

- **Đáp án mẫu rộng hơn câu hỏi** ở khoảng 10 câu (qa-013, 030, 033, 037, 075, 079, 084, 085, 096...). Điều này *không* làm mọi metric sai: đo độ phủ toàn gold thì trừ điểm vẫn đúng theo định nghĩa. Vấn đề là **dùng độ phủ gold để kết luận chất lượng trả lời** thì các câu này bị đánh giá thấp oan.
- **Đáp án mẫu chứa lời lưu ý của người soạn** (qa-041, 042, 068, 086, 092). Không nên bỏ hết: mức phỏng đoán ở qa-041/092 là **thuộc tính có nghĩa của nguồn**, cần giữ trong claim hoặc đưa vào tiêu chí riêng. Lời lưu ý chống hiểu sai ở qa-068 có vai trò khác — cần quyết định riêng.
- **qa-053**: đáp án mẫu viết từ đoạn nguồn không nằm trong tập được tra về.

---

## 5. Quan sát về bộ chấm tự động

### 5.1 Bốn điểm FC bất thường, đáng ưu tiên điều tra

Dùng **điểm bản gốc** (baseline). Cột bên phải là bản chấm lại 32 câu, để đối chiếu:

| Câu | FC gốc | FC chấm lại | Đối chiếu nội dung |
|---|---:|---:|---|
| **qa-081** | **0.00** | **0.00** | Đáp án nêu nguyên văn cả hai ý của đáp án mẫu (tự do học tập; trường kĩ thuật, chuyên nghiệp ở tất cả các tỉnh cho người bản xứ) |
| qa-099 | 0.25 | 0.33 | Đáp án mẫu chỉ 2 mệnh đề, đáp án có đủ cả 2 |
| qa-089 | 0.50 | 0.25 | Rà soát cho 8/8 mệnh đề được phủ |
| qa-086 | 0.60 | 0.50 | Rà soát cho 3/3, giữ đúng sắc thái "sẽ rút" |

**qa-081 nhận 0.00 ở cả hai lần chấm.** Đây là **bất thường lặp lại, cần ưu tiên điều tra trace** — không đủ căn cứ khẳng định đã loại trừ yếu tố ngẫu nhiên, vì hai lần chạy chưa được xác nhận là độc lập và cùng cấu hình. Điểm 0 có thể do bước tách mệnh đề trả về rỗng, **hoặc** do mọi verdict đều là 0; chưa phân biệt được nếu không có trace.

### 5.2 Hai đặc điểm xác định được trong mã nguồn

**(a) Few-shot của prompt NLI lệch 4:1 về `verdict = 0`** — đã kiểm chứng:

```
factual_correctness_n_l_i_statement_prompt_vietnamese.json   verdict=1: 1   verdict=0: 4
faithfulness_n_l_i_statement_prompt_vietnamese.json          verdict=1: 1   verdict=0: 4
```

Đối chiếu `ragas/metrics/_faithfulness.py` dòng 93–125: **upstream RAGAS đang cài cũng lệch đúng 4:1**. Đây là đặc tính của thư viện, không phải lỗi bản dịch tiếng Việt.

> **Chưa chứng minh** tỉ lệ này là *nguyên nhân* của các điểm thấp, cũng chưa chứng minh nó ảnh hưởng riêng với tiếng Việt. Muốn khẳng định cần thí nghiệm có đối chứng.

**(b) `mode="recall"` trộn hai phép tách mệnh đề khác đơn vị** — `_factual_correctness.py` dòng 282–292:

```python
tp = sum(reference_response)     # tách từ RESPONSE, kiểm với gold làm tiền đề
fn = sum(~response_reference)    # tách từ GOLD, kiểm với response làm tiền đề
score = tp / (tp + fn + 1e-8)
```

`decompose_and_verify_claims(a, b)` tách **tham số thứ hai** rồi kiểm với tham số thứ nhất làm tiền đề. Tử số và mẫu số vì thế đếm trên hai tập mệnh đề khác nhau.

> **Chưa chứng minh** điều này làm điểm giảm *có hệ thống*: tùy số claim và verdict, công thức có thể cho điểm cao hơn hoặc thấp hơn.

### 5.3 Chênh lệch giữa hai lần chấm FC — chưa xác định nguyên nhân

Chấm lại 32 câu với cùng đầu vào: chênh lệch tuyệt đối trung bình **0.0928**, lớn nhất **0.40**; 14/32 câu lệch ≥ 0.10; 12 tăng, 11 giảm, 9 không đổi.

> Trước đây báo cáo suy ra "bước tách mệnh đề không ổn định" từ các phân số 0.29 / 0.71 / 0.86. **Suy luận này không đứng vững**: 2/7, 5/7, 6/7 có cùng mẫu số 7 — verdict thay đổi cũng cho kết quả như vậy, và điểm còn bị làm tròn. Chỉ kết luận được: **hai lần chấm cho điểm khác nhau, chưa xác định nguyên nhân.**

### 5.4 Điều không kết luận được

Chênh lệch tổng giữa bản rà soát và RAGAS **không quy hết thành "RAGAS chấm sai"**: hai bên dùng đơn vị đếm khác nhau (RAGAS chấm nhị phân trên cách tách claim của nó; bản rà soát chấm 0/0,5/1 trên cách tách khác). Chỉ 4 trường hợp ở mục 5.1 là đáng điều tra theo nội dung.

---

## 6. Khuyến nghị

### Về đo lường

1. **Nếu cần đo độ phủ đáp án mẫu**: dùng một danh sách gold claim **cố định**, tính `số claim gold được câu trả lời hỗ trợ / tổng gold claim`.
   > **Cảnh báo — sửa khuyến nghị cũ:** chuyển sang `mode="precision"` **không** đo độ phủ gold. Theo mã đang cài, `precision = tp/(tp+fp)` đo tỉ lệ claim của *câu trả lời* được đáp án mẫu hỗ trợ; một câu chỉ trả lời một nửa như qa-083 vẫn có thể đạt precision cao. `mode=None` (F1) cũng dùng chung `tp/fp/fn` nên không khắc phục việc hai vế đếm trên hai tập claim. Giữ precision/F1 làm metric **bổ sung**, có tên và giới hạn rõ ràng.
2. **Cân bằng few-shot NLI về ~50/50**: coi là **thí nghiệm**, chạy cùng tập và cấu hình đối chứng. Không coi 50/50 là giải pháp đã chứng minh.
3. **Lưu manifest** (model, prompt hash, tham số sinh, seed) và **trace từng claim/verdict** cho mỗi lần chạy. Chấm lặp 2–3 lần trên cùng đầu vào để có độ lệch chuẩn.
4. **Ưu tiên điều tra trace qa-081 và qa-099.**
5. Bổ sung bảng `id, claim_id, verdict, evidence, reason` cho `context_recall` và `faithfulness` trước khi chốt điểm hai metric này.

### Về hệ thống

1. Sửa prompt tổng hợp để không rò định danh chunk (5 câu); kiểm tra cả khâu render trích dẫn.
2. Xử lý câu hỏi nhiều vế — qa-083 bỏ hẳn một vế đã có sẵn trong ngữ cảnh.
3. Giữ sắc thái phỏng đoán của nguồn ("có lẽ", "giả thuyết") — qa-041, qa-092.
4. Không khái quát chủ trương/đề nghị thành sự việc đã thực hiện — qa-066.

### Về bộ dữ liệu

1. Rà lại phạm vi đáp án mẫu so với câu hỏi (~10 câu hiện rộng hơn).
2. Quyết định cách xử lý lời lưu ý của người soạn: giữ mức phỏng đoán (qa-041, 092) như thuộc tính của nguồn; xem lại vai trò của lời lưu ý chống hiểu sai (qa-068).
3. Kiểm tra qa-053 — đáp án mẫu viết từ đoạn nguồn không được tra về.

---

## 7. Giới hạn của báo cáo

1. **Bản rà soát do một mô hình ngôn ngữ thực hiện theo rubric tự định nghĩa.** Hai file `*.review.md` là **hai lượt rà soát**, không phải hai giám khảo độc lập chấm mù — không dùng chúng làm bằng chứng đồng thuận liên giám khảo.
2. **Cách tách mệnh đề chưa nhất quán.** qa-001 tách "dùng đá cuội" và "ghè đẽo rìa cạnh" thành hai dòng trong khi qa-002 gộp; quan hệ cha–con tách riêng ở qa-013 nhưng gộp ở qa-075. Hệ quả về trọng số: qa-085 chỉ có 3 mệnh đề nên thiếu chức danh "Tổng Bí thư" mất 16,7%; ở qa-053 mỗi nhóm thiếu (môn "hát"; "dân quyền/tự chủ") mất 0,5/6 ≈ 8,3%, cả câu mất 1/6 ≈ 16,7%.
3. **`context_recall` và `faithfulness` của bản rà soát là ước tính**, chưa có bảng bằng chứng từng đơn vị để tái lập.
4. **`context_precision` của bản rà soát là proxy tự động — không dùng.**
5. Các mức "tin cậy" trong báo cáo là **nhận định của người viết**, chưa hiệu chuẩn bằng bộ nhãn độc lập.
6. Không có manifest cấu hình cho các lần chạy RAGAS.
7. Các điểm rubric còn để ngỏ (qa-016, qa-034, qa-041, qa-042, qa-045, qa-068, qa-083, qa-086, qa-092, qa-093) chưa được chốt — xem `auto_rag_v2.claims.review.md`.

---

## 8. Danh mục file

| File | Nội dung |
|---|---|
| `auto_rag_v2.json` | Kết quả chạy: câu hỏi, ngữ cảnh tra về, câu trả lời |
| `auto_rag_v2.ragas.csv` | **Bản RAGAS baseline** — 5 metric, 100 câu |
| `auto_rag_v2.factual_correctness.ids32.csv` | Chấm lại FC 32 câu — *chỉ để điều tra ca bất thường* |
| `auto_rag_v2.faithfulness.ids20.csv` | Chấm lại faithfulness 20 câu — *tập chọn thiên lệch, không dùng làm điểm tổng* |
| `auto_rag_v2.claims.md` / `.csv` | **473 mệnh đề đáp án mẫu** kèm trạng thái phủ — phụ lục chính. *Cột "RAGAS" trong file này hiển thị điểm bản ghép (gốc + ids32), không phải điểm baseline* |
| `auto_rag_v2.ar_manual.csv` | 192 vế câu hỏi kèm trạng thái trả lời |
| `auto_rag_v2.faith_manual.csv` | Tổng hợp faithfulness theo câu — *chưa có bảng bằng chứng từng đơn vị* |
| `auto_rag_v2.cprec_manual.csv` | Proxy context_precision — *không dùng* |
| `auto_rag_v2.manual.review.md` | Rà soát lượt 1 (bảng chấm tay đầu tiên) |
| `auto_rag_v2.claims.review.md` | Rà soát lượt 2 (bảng 473 mệnh đề) |
| `auto_rag_v2.BAOCAO.review.md` | Rà soát lượt 3 (bản báo cáo lần đầu) — cơ sở của bản sửa này |
