# Phân tích chi tiết 5 metric RAGAS — bộ `auto_rag_v2`

Ngày lập: 2026-09-17
Nguồn số liệu: `auto_rag_v2.ragas.csv` (100 câu, bản baseline), `retrieval_qa_v2.json` (trường `type`), các bảng rà soát `*_manual*.csv`, `claims.csv`, hai bản chấm lại `ids32` / `ids20`.
Mã nguồn đối chiếu: RAGAS 0.4.3 (`ragas/metrics/_*.py`), `apps/agent-service/scripts/run_ragas_eval.py`, `scripts/ragas_prompts/*.json`, `app/orchestrator/fusion.py`.

Tài liệu này trả lời một câu hỏi: **vì sao mỗi metric cao hoặc thấp**. Mỗi nguyên nhân được đánh dấu mức chắc chắn:

- **[Đã kiểm]**: kiểm được trực tiếp trong mã nguồn, prompt hoặc số liệu.
- **[Suy luận]**: khớp với số liệu nhưng chưa có trace từng verdict để khẳng định.

---

## 1. Toàn cảnh

### 1.1 Điểm và phân bố

| Metric | TB | Trung vị | Độ lệch chuẩn | Số câu = 1.0 | [0.8, 1) | [0.5, 0.8) | < 0.5 | = 0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `context_recall` | **0.9672** | 1.000 | 0.104 | **90** | 1 | 9 | 0 | 0 |
| `context_precision` | 0.8658 | 1.000 | 0.194 | 56 | 14 | 22 | 8 | 0 |
| `faithfulness` | 0.8280 | 0.833 | 0.155 | 26 | 39 | 32 | 3 | 0 |
| `factual_correctness` | 0.8268 | 0.870 | 0.215 | 37 | 30 | 26 | 7 | 2 |
| `answer_relevancy` | 0.8071 | 0.855 | 0.140 | **1** | 63 | 31 | 5 | 0 |

Hai metric có trung vị 1.0 (`context_recall`, `context_precision`) thấp ở TB chỉ vì một nhóm nhỏ câu. Ba metric còn lại có trung vị dưới 0.9: điểm thấp **trải đều trên nhiều câu**, không do vài ca cá biệt.

### 1.2 Theo loại câu hỏi

| Metric | single_query (40) | multi_query (30) | multihop (30) |
|---|---:|---:|---:|
| `context_precision` | **0.9472** | 0.7387 | 0.8842 |
| `context_recall` | **0.9917** | 0.9128 | 0.9889 |
| `factual_correctness` | 0.8180 | 0.8270 | **0.8383** |
| `faithfulness` | 0.8095 | 0.7765 | **0.9042** |
| `answer_relevancy` | **0.8451** | 0.8281 | 0.7356 |

Số câu đạt 1.0 / số câu dưới 0.5:

| Metric | single_query | multi_query | multihop |
|---|---:|---:|---:|
| `context_precision` | 32 / 0 | **6 / 6** | 18 / 2 |
| `context_recall` | 39 / 0 | **22 / 0** | 29 / 0 |
| `factual_correctness` | 16 / 2 | 5 / 2 | 16 / 3 |
| `faithfulness` | 9 / 1 | 1 / 2 | 16 / 0 |
| `answer_relevancy` | 1 / 1 | 0 / 0 | 0 / **4** |

Đặc điểm từng nhóm:

| | single_query | multi_query | multihop |
|---|---:|---:|---:|
| Độ dài câu trả lời TB (ký tự) | 625 | **1544** | 329 |
| Số câu văn TB trong câu trả lời | 5.2 | **11.7** | 3.5 |
| Số mệnh đề TB trong đáp án mẫu | 4.1 | **6.7** | 3.6 |
| Số câu có 10 chunk (chạy nhiều bước) | 1 | 1 | **26** |

### 1.3 Điểm RAGAS so với rà soát nội dung

| Metric | RAGAS | Rà soát | Tương quan thứ hạng (Spearman) giữa hai bên |
|---|---:|---:|---:|
| `factual_correctness` | 0.8268 | 0.9422 | 0.49 |
| `faithfulness` | 0.8280 | 0.9942 | 0.20 |
| `answer_relevancy` | 0.8071 | 0.9933 | **0.02** |
| `context_precision` | 0.8658 | 0.8968 (proxy) | **-0.01** |

Tương quan thấp nghĩa là **câu RAGAS chấm thấp thường không phải câu rà soát thấy có lỗi**. Riêng `answer_relevancy` gần như không liên quan gì tới việc câu trả lời có đủ vế hay không.

### 1.4 Tương quan giữa các metric

Tất cả hệ số Spearman giữa 5 metric đều nằm trong khoảng -0.20 đến 0.24. Các metric **không cùng tăng giảm** theo "chất lượng chung" của từng câu. Điều này khớp với nhận định: phần lớn biến thiên đến từ cơ chế riêng của từng metric và độ ngẫu nhiên của judge, không phải từ việc có câu trả lời tốt và câu trả lời tệ.

---

## 2. `context_recall` — 0.9672, cao nhất

### 2.1 Cách tính [Đã kiểm]

`_context_recall.py`: judge xét **từng ý của đáp án mẫu**, gắn `attributed = 1/0` tuỳ việc các chunk tra về có chứa ý đó không. Điểm bằng `số ý attributed / tổng số ý`.

### 2.2 Vì sao cao

1. **Không quan tâm thứ tự và nhiễu.** Chỉ cần ý nằm *ở đâu đó* trong 8–10 chunk. Chunk lạc đề không bị trừ.
2. **Ngữ cảnh rất rộng so với đáp án.** TB khoảng 15.000–18.000 ký tự ngữ cảnh cho một đáp án mẫu 3–7 mệnh đề. Xác suất phủ đủ rất cao.
3. **Bộ dữ liệu được soạn từ chính kho tài liệu.** Đáp án mẫu viết từ các đoạn trong kho, nên chỉ cần tra đúng đoạn là phủ gần như trọn.
4. **Việc chấm dễ.** So từng ý ngắn với văn bản dài là tác vụ đối chiếu đơn giản, judge ít dao động.

### 2.3 Vì sao chưa đạt 1.0

10 câu dưới 1.0: **8 là multi_query** (qa-009, 042, 045, 053, 073, 076, 083, 100), 1 single_query (qa-086), 1 multihop (qa-088).

| Nguyên nhân | Câu | Mức chắc chắn |
|---|---|---|
| Bằng chứng thật sự không có trong ngữ cảnh | qa-045 (đại bản doanh, cơ chế chỉ huy thống nhất), qa-053 ("dân quyền, tự chủ") | [Đã kiểm] bằng rà soát |
| Đáp án mẫu chứa lời lưu ý của người soạn, không phải dữ kiện | qa-042 (mệnh đề 5) | [Đã kiểm] |
| Câu hỏi so sánh hai sự kiện: hạn ngạch 8 chunk chia cho hai vế, một vế thiếu | qa-009, qa-073, qa-076, qa-083, qa-100 | [Suy luận] |
| Judge chấm 0 dù rà soát thấy có bằng chứng | qa-009, 073, 076, 083, 086, 088, 100 (rà soát không trừ điểm) | [Suy luận]: chưa có trace |

**Tương quan âm với độ dài đáp án mẫu** (Spearman -0.35): đáp án mẫu càng dài, càng nhiều ý phải tìm, càng dễ hụt một ý.

**Kết luận:** metric này cao là **thật**, nhưng nó là metric dễ nhất. Điểm cao không có nghĩa là ngữ cảnh sạch, xem mục 3.

---

## 3. `context_precision` — 0.8658

### 3.1 Cách tính [Đã kiểm]

`LLMContextPrecisionWithReference` (`_context_precision.py` dòng 113–126, 140–169):

1. Với **từng chunk**, judge nhận (câu hỏi, đáp án mẫu, chunk) và trả `verdict = 1` nếu chunk hữu ích để đi tới đáp án.
2. Điểm là **average precision** theo thứ tự chunk:

```
score = Σ_k ( precision@k × v_k ) / Σ v_k
```

Hệ quả quan trọng:

- **Chunk vô ích nằm SAU mọi chunk hữu ích không bị trừ.** 56 câu đạt 1.0 nghĩa là mọi chunk hữu ích đều đứng trước chunk vô ích, không có nghĩa là cả 8 chunk đều hữu ích.
- **Chunk vô ích ở vị trí 1 bị phạt rất nặng.** Chỉ chunk 2 hữu ích → 0.50. Chỉ chunk 4 hữu ích → 0.25.

Prompt tiếng Việt khá khắt khe [Đã kiểm]: *"Trả `verdict: 0` nếu đoạn chỉ cùng chủ đề, chứa thông tin bên lề, không đủ để hỗ trợ đáp án"*.

Thứ tự chunk được chấm là thứ tự **best-first sau RRF/rerank**, chưa qua `reorder_for_context` [Đã kiểm: `collect_eval_runs.py` dòng 166–171 lấy `answer_context_chunks(retrieval.chunks)`, còn reorder chỉ áp trong `nodes.py` dòng 619 khi dựng prompt]. Vì vậy metric này **phản ánh đúng chất lượng xếp hạng**, không bị làm méo bởi bước xếp chống "lost in the middle".

### 3.2 Suy ngược verdict từ điểm [Đã kiểm về mặt toán]

Với 8 hoặc 10 chunk và verdict nhị phân, có thể liệt kê mọi chuỗi verdict cho ra đúng điểm quan sát. Kết quả với 44 câu dưới 1.0:

| Nhóm | Số câu < 1.0 | Chunk #1 chắc chắn bị chấm vô ích | Chunk #1 chắc chắn hữu ích |
|---|---:|---:|---:|
| multi_query | 24 | **9** | 15 |
| multihop | 12 | 2 | 10 |
| single_query | 8 | 0 | 8 |

**Mọi câu có điểm dưới 0.6 (trừ qa-058) đều có chunk #1 bị judge chấm vô ích.** Một số chuỗi khớp:

| Câu | Loại | Điểm | Chuỗi verdict khớp (1 = hữu ích) | Số chunk hữu ích |
|---|---|---:|---|---:|
| qa-069 | multi_query | 0.250 | `00010000` | 1–2 |
| qa-083 | multi_query | 0.267 | `00001100` | 2 |
| qa-043 | multihop | 0.310 | `00100010` | 2 |
| qa-034 | multi_query | 0.417 | `00110000` | 2 |
| qa-073 | multi_query | 0.417 | `00110000` | 2 |
| qa-014 | multi_query | 0.443 | `01001010` | 3 |
| qa-039 | multi_query | 0.450 | `01001000` | 2 |
| qa-026 | multi_query | 0.583 | `01100000` | 2 |
| qa-020 | multi_query | 0.583 | `01100000` | 2 |

Judge thường chỉ công nhận **2–4 trên 8 chunk** là hữu ích. Proxy từ vựng của bản rà soát thì cho 6–8, nên proxy không dùng được (tương quan -0.01).

### 3.3 Kiểm chứng bằng đọc chunk #1 [Đã kiểm]

| Câu | Câu hỏi về | Chunk #1 thực tế nói về |
|---|---|---|
| qa-069 | Bình dân học vụ, xoá mù chữ 1946–1950 | Nông trường quốc doanh 1957–1960, công nghiệp quốc doanh 1960 |
| qa-026 | Triệu Quang Phục ở Dạ Trạch, Ngô Quyền ở Bạch Đằng 938 | Bố trí quân nhà Trần trận Bạch Đằng **1288** |
| qa-083 | Nguyễn Ái Quốc tại Đại hội Tua 1920 và Đại hội V QTCS 1924 | Phong trào dân tộc sau Thế chiến I nói chung |

Judge chấm đúng: các chunk này thật sự lạc đề hoặc chỉ cùng chủ đề. **Đây là lỗi thật của khâu tra cứu.**

Hệ quả dây chuyền ở **qa-026**: chunk #1 về Bạch Đằng 1288 (có Ghềnh Cốc, Trần Quốc Tuấn) chính là nguồn của lỗi *faithfulness* "gán Ghềnh Cốc cho Ngô Quyền". Chunk sai đứng đầu đã kéo câu trả lời sai theo.

### 3.4 Vì sao multi_query thấp (0.74)

`fuse_query_results` (`fusion.py`) gộp các sub-query bằng **RRF theo rank**: `score += 1 / (rrf_k + rank)` cho mỗi lần chunk xuất hiện.

- Chunk xuất hiện trong danh sách của **cả hai** sub-query được cộng hai lần, nên vượt lên đầu. Với câu so sánh hai sự kiện, chunk chung cho cả hai thường là **đoạn tổng quan hoặc cùng từ khoá** (cùng "Bạch Đằng", cùng "Nguyễn Ái Quốc"), không phải đoạn trả lời riêng từng vế. [Suy luận: khớp với ba ví dụ trên, cần log RRF để xác nhận]
- Chunk rank 1 của mỗi sub-query có điểm bằng nhau, và khi hoà thì xếp theo `chunk_id` (`sorted(..., key=(-score, cid))`). Thứ tự giữa hai vế vì thế **phụ thuộc tên file/số chunk**, không phụ thuộc độ liên quan. [Đã kiểm trong mã]
- Sau khi gộp chỉ giữ `multiquery_final_k = 8` chunk cho **hai vế trở lên**. Mỗi vế chỉ còn khoảng 4 suất, trong khi single_query có đủ 8 suất cho một chủ đề. [Đã kiểm trong config]

### 3.5 Vì sao single_query cao (0.95) và multihop ở giữa (0.88)

- **single_query**: một truy vấn, qua reranker, top-8 cùng chủ đề. 32/40 câu đạt 1.0, không câu nào dưới 0.5.
- **multihop**: 26/30 câu chạy nhiều bước và có 10 chunk. `merge_across_steps` đặt **bước sau lên trước** (bước cuối chứa đáp án), nên chunk đầu thường hữu ích. Chunk của bước "tìm mắt xích" nằm sau, không bị trừ. Hai ca thấp (qa-043, qa-037) có chunk #1 vô ích. qa-058 thì chunk #1 hữu ích nhưng chunk 2–8 vô ích (chuỗi khớp duy nhất `1000000011`).

### 3.6 Tóm tắt

| Điểm cao do | Điểm thấp do |
|---|---|
| Công thức không phạt chunk vô ích ở cuối | **Chunk lạc đề đứng #1** (lỗi thật, tập trung ở multi_query) |
| single_query và multihop xếp hạng tốt | RRF cộng điểm cho chunk chung chung xuất hiện ở nhiều sub-query |
| | Hạn ngạch 8 chunk chia cho nhiều vế |
| | Prompt khắt khe: "chỉ cùng chủ đề" tính 0 |

---

## 4. `faithfulness` — 0.8280

### 4.1 Cách tính [Đã kiểm]

`_faithfulness.py`:

1. Tách câu trả lời thành các mệnh đề (prompt `statement_generator`).
2. Judge xét từng mệnh đề với **toàn bộ ngữ cảnh**: `verdict = 1` nếu *"suy ra trực tiếp"* được.
3. Điểm bằng `số mệnh đề verdict 1 / tổng mệnh đề`.

Prompt tiếng Việt [Đã kiểm]: *"Trả `verdict: 0` khi tài liệu không nhắc tới, chỉ có một phần không đủ để khẳng định… Không suy đoán, nhận định chủ quan hay **rút ra kết luận gián tiếp** từ hành vi."*

Ví dụ mẫu (few-shot) của prompt NLI: **1 ví dụ verdict 1 và 4 ví dụ verdict 0** [Đã kiểm trong file JSON hiện tại và bản trước commit `509660e`]. RAGAS gốc cũng lệch như vậy.

### 4.2 Khoảng cách với rà soát

- Rà soát thấy **94/100 câu bám nguồn hoàn toàn**. RAGAS chỉ cho 1.0 ở 26 câu.
- Trên chính 94 câu bám nguồn hoàn toàn đó, RAGAS TB chỉ **0.838**, và 17 câu bị chấm dưới 0.7.
- Tương quan thứ hạng với rà soát chỉ 0.20.

Phần lớn điểm bị trừ **không tương ứng với lỗi bịa thật**.

### 4.3 Vì sao thấp

**(a) Câu trả lời dài thì nhiều cơ hội bị chấm 0** [Đã kiểm về số liệu]

| Số câu văn trong câu trả lời | Số câu hỏi | `faithfulness` TB |
|---|---:|---:|
| ≤ 4 | 46 | **0.872** |
| 5–7 | 22 | 0.758 |
| 8–10 | 11 | 0.832 |
| > 10 | 21 | 0.804 |

Spearman với độ dài câu trả lời: **-0.35**, hệ số âm mạnh nhất trong các đặc trưng đã đo. Chỉ cần judge chấm sai 1 mệnh đề là mất 1/N điểm. Câu trả lời 15 mệnh đề gần như chắc chắn có vài mệnh đề bị chấm 0.

Điều này giải thích thứ tự theo nhóm: **multihop 0.90** (TB 3.5 câu văn) > single_query 0.81 (5.2) > **multi_query 0.78** (11.7).

**(b) Câu diễn giải, kết nối, tổng kết bị chấm 0** [Suy luận: khớp với prompt, chưa có trace]

Hệ thống thường thêm câu kết loại *"Nhờ sự phối hợp này…"* hoặc *"Đây là yêu cầu nhằm mở rộng cơ hội học hành…"*. Các câu này đúng tinh thần nguồn nhưng là **khái quát**, không có nguyên văn trong ngữ cảnh. Prompt cấm "rút ra kết luận gián tiếp" nên judge chấm 0. Hệ thống cũng hay dùng từ đồng nghĩa ("nước lũ" thay "nước", "phối hợp địa hình"), cũng dễ bị coi là "chỉ có một phần".

**(c) Judge dao động mạnh giữa hai lần chấm** [Đã kiểm về số liệu]

Chấm lại 20 câu điểm thấp:

| | |
|---|---:|
| TB lần 1 → lần 2 | 0.603 → **0.722** |
| Chênh lệch tuyệt đối TB | 0.136 |
| Chênh lệch lớn nhất | **0.59** (qa-047: 0.33 → 0.92) |
| Số câu lệch ≥ 0.10 | 10 / 20 |

Một câu trả lời bám nguồn hoàn toàn (qa-047, mô tả trận Vụ Quang) có thể nhận 0.33 hoặc 0.92 tuỳ lần chạy. Cần lưu ý tập 20 câu này được chọn từ nhóm điểm thấp, nên một phần mức tăng là hồi quy về trung bình.

**(d) Ví dụ mẫu nghiêng về verdict 0** [Đã kiểm về prompt, **chưa chứng minh là nguyên nhân**]

Tỉ lệ 1:4 có thể khiến judge có xu hướng chấm 0 khi phân vân. Cần thí nghiệm few-shot cân bằng để kiểm.

**(e) Judge là model nhỏ, suy luận thấp** [Đã kiểm với cấu hình hiện tại]

`build_llm` dùng `settings.llm_model` với `reasoning_effort="low"`. `.env` hiện đặt `LLM_MODEL=cx/gpt-5.6-luna`, trùng model sinh câu trả lời. Không có manifest nên **không chắc lần chạy baseline dùng đúng cấu hình này**.

### 4.4 Lỗi thật mà metric bắt được

| Câu | RAGAS | Rà soát | Lỗi |
|---|---:|---:|---|
| qa-092 | **0.29** (thấp nhất) | 0.93 | Kết luận chắc chắn "công dụng chủ yếu là chặt, cắt" từ nguồn chỉ nói "có lẽ" |
| qa-041 | 0.57 | 0.88 | Bỏ "có lẽ" của nguồn |
| qa-066 | 0.64 | 0.96 | Biến chủ trương/đề nghị thành "đã triển khai" |
| qa-069 | 0.78 | 0.75 | Sai phép tính "tăng thêm hơn 7,5 triệu" |
| qa-026 | **0.96** | 0.95 | Gán Ghềnh Cốc cho Ngô Quyền (lỗi nặng nhất) |

Ở qa-069 và qa-026, điểm RAGAS gần bằng rà soát. Nhưng qa-026 là 0.96 (khoảng 45/47 mệnh đề), nên lỗi nặng nhất của cả bộ chỉ làm mất khoảng 4% điểm, **ít hơn nhiều câu không có lỗi** (qa-047: 0.33). Chưa có trace nên không biết hai mệnh đề bị trừ có đúng là mệnh đề sai hay không. Có một cơ chế khiến loại lỗi này khó bị bắt [Suy luận]: từng mảnh thông tin (Ghềnh Cốc, Bạch Đằng) đều *có* trong ngữ cảnh ở chunk #1, còn judge xét mỗi mệnh đề với *toàn bộ* ngữ cảnh, nên việc ghép sai chủ thể dễ lọt.

### 4.5 Rò rỉ mã chunk không ảnh hưởng

5 câu lộ chuỗi `tap3_clean-0000xx` có `faithfulness` TB **0.829**, bằng 95 câu còn lại (0.828) [Đã kiểm]. Giả thuyết "mã chunk bị tính là mệnh đề bịa" **không đúng** với dữ liệu này.

### 4.6 Tóm tắt

| Điểm cao do | Điểm thấp do |
|---|---|
| Câu trả lời thật sự bám nguồn (rà soát: 94/100 sạch) | Câu trả lời dài, nhiều mệnh đề |
| multihop trả lời ngắn, sát nguồn | Câu kết luận, diễn giải bị coi là "suy luận gián tiếp" |
| | Judge dao động mạnh (lệch tới 0.59) |
| | Few-shot 1:4, judge suy luận thấp (chưa chứng minh) |
| | Một số lỗi thật (qa-092, 041, 066); lỗi nặng nhất (qa-026) chỉ bị trừ khoảng 4% |

---

## 5. `factual_correctness(mode=recall)` — 0.8268

### 5.1 Cách tính [Đã kiểm]

`_factual_correctness.py` dòng 262–292 và 297–302:

```python
reference_response = decompose_and_verify_claims(reference, response)
#   tách CÂU TRẢ LỜI thành claim, kiểm với ĐÁP ÁN MẪU làm tiền đề
response_reference = decompose_and_verify_claims(response, reference)
#   tách ĐÁP ÁN MẪU thành claim, kiểm với CÂU TRẢ LỜI làm tiền đề

tp = sum(reference_response)      # claim của câu trả lời có trong đáp án mẫu
fn = sum(~response_reference)     # claim của đáp án mẫu KHÔNG có trong câu trả lời
score = round(tp / (tp + fn), 2)
```

Có 4 lần gọi LLM mỗi câu: 2 lần tách mệnh đề, 2 lần kiểm.

### 5.2 Vì sao công thức cho điểm khó đoán [Đã kiểm]

`tp` và `fn` đếm trên **hai tập claim khác nhau**:

- **Câu trả lời dài, nhiều chi tiết đúng** → `tp` lớn → điểm được đẩy lên, kể cả khi thiếu vài ý của đáp án mẫu.
- **Câu trả lời ngắn** (multihop, single_query) → `tp` nhỏ → **một verdict sai là tụt mạnh**.
- **`tp = 0` thì điểm = 0** bất kể câu trả lời đầy đủ đến đâu.

Ví dụ **qa-081** (RAGAS 0.00 cả hai lần, rà soát 1.00):

> Câu trả lời: "…đòi **tự do học tập**, đồng thời **thành lập các trường kĩ thuật và trường chuyên nghiệp ở tất cả các tỉnh dành cho người bản xứ**. Đây là yêu cầu nhằm mở rộng cơ hội học hành…"
> Đáp án mẫu: "Bản Yêu sách đòi quyền tự do học tập và yêu cầu thành lập các trường kĩ thuật, chuyên nghiệp ở tất cả các tỉnh cho người bản xứ."

Để ra 0, **mọi** claim của câu trả lời phải bị chấm "không có trong đáp án mẫu", kể cả hai claim trùng gần nguyên văn. Có thể do bước tách trả về rỗng, hoặc claim bị ghép với chi tiết thừa ("điểm 6", "nhằm mở rộng cơ hội") khiến cả claim bị coi là "chỉ đúng một phần". [Suy luận: cần trace]

### 5.3 Vì sao thấp

**(a) Judge dao động** [Đã kiểm]

Chấm lại 32 câu: chênh lệch tuyệt đối TB **0.093**, lớn nhất **0.40**; 11 câu lệch ≥ 0.10. Ví dụ qa-068: 0.00 → 0.40; qa-055 và qa-082: 0.75 → 1.00; qa-089: 0.50 → 0.25.

**(b) Đáp án mẫu ít mệnh đề nên bị khuếch đại** [Đã kiểm về số liệu]

| Câu | Số mệnh đề đáp án mẫu | RAGAS | Rà soát |
|---|---:|---:|---:|
| qa-081 | 2 | 0.00 | 1.00 |
| qa-099 | 2 | 0.25 | 1.00 |
| qa-068 | 3 | 0.00 | 0.83 |
| qa-086 | 3 | 0.60 | 1.00 |

Với 2 mệnh đề, chỉ cần một `fn` thì điểm rơi xuống khoảng 0.5 hoặc thấp hơn.

**(c) Câu trả lời đúng nhưng diễn đạt khác đáp án mẫu** [Suy luận]

qa-099: câu trả lời *"Dương Văn Minh — người được Trần Văn Hương nhường chức Tổng thống — đã tuyên bố đầu hàng không điều kiện khi các đơn vị Quân đoàn II tiến vào Dinh Độc lập lúc 10 giờ 45…"*. Các chi tiết "Quân đoàn II", "10 giờ 45" không có trong đáp án mẫu. Prompt NLI yêu cầu *"nêu rõ … **toàn bộ** mệnh đề"*, nên claim chứa chi tiết thừa bị chấm 0 và `tp` tụt.

**(d) Đáp án mẫu rộng hơn câu hỏi** [Đã kiểm trong rà soát]

Khoảng 10 câu (qa-013, 030, 033, 037, 075, 079, 084, 085, 096…) có đáp án mẫu chứa ý mà câu hỏi không yêu cầu. Câu trả lời đúng trọng tâm vẫn bị tính `fn`.

**(e) Lỗi thật của hệ thống** [Đã kiểm]

| Câu | RAGAS | Rà soát | Lỗi |
|---|---:|---:|---|
| qa-083 | 0.37 | 0.43 | Bỏ hẳn vế Đại hội V QTCS 1924 dù ngữ cảnh có |
| qa-009 | 0.29 | 0.50 | Thiếu nhiều ý: quân các nước thân Mĩ, căn cứ quân sự, cam kết không can thiệp… |
| qa-079 | 0.30 | 0.67 | Thiếu "nhà hào tâm ủng hộ", "Ban Tài chính phụ trách thu chi" |
| qa-035 | 0.29 | 0.88 | Thiếu thuộc tính "thuyền lớn đi biển" |

Ở các câu này, RAGAS và rà soát **cùng hướng**. Đây là phần metric phản ánh đúng.

### 5.4 Vì sao không thấp hơn

- 69/100 câu phủ đủ đáp án mẫu theo rà soát. Trên nhóm này RAGAS TB **0.879**, vẫn cao.
- Với câu trả lời dài (multi_query), `tp` lớn che bớt `fn`. Nhờ vậy multi_query (0.827) không thấp hơn single_query (0.818), dù rà soát cho multi_query thấp hơn (0.912 so với 0.956).

### 5.5 Tóm tắt

| Điểm cao do | Điểm thấp do |
|---|---|
| Phần lớn câu trả lời phủ đủ đáp án mẫu | Công thức trộn hai tập claim; `tp = 0` ra điểm 0 |
| Câu trả lời dài tăng `tp`, che `fn` | Đáp án mẫu 2–3 mệnh đề khuếch đại mỗi verdict sai |
| | Judge dao động (lệch tới 0.40) |
| | Chi tiết thừa làm claim bị chấm 0 |
| | Đáp án mẫu rộng hơn câu hỏi (~10 câu) |
| | Lỗi thật: qa-083, 009, 079, 035 |

---

## 6. `answer_relevancy` — 0.8071

### 6.1 Cách tính [Đã kiểm]

`_answer_relevance.py` dòng 94–127:

1. LLM đọc **câu trả lời** và sinh ngược `strictness = 3` câu hỏi, kèm cờ `noncommittal` (né tránh).
2. Embedding câu hỏi gốc và 3 câu hỏi sinh ra bằng `AITeamVN/Vietnamese_Embedding` (chạy local, đã chuẩn hoá vector).
3. Điểm bằng `TB cosine × (0 nếu cả 3 đều noncommittal, ngược lại 1)`.

Prompt tiếng Việt yêu cầu [Đã kiểm]: *"Câu hỏi phải phản ánh ý chính của câu trả lời và **không được thêm thực thể, thời điểm hay chi tiết không có trong câu trả lời**."*

### 6.2 Vì sao gần như không thể đạt 1.0

- Cosine giữa **hai câu khác chữ** gần như không bao giờ bằng 1. Hai câu hỏi cùng nghĩa, diễn đạt khác thường chỉ đạt khoảng 0.8–0.9. **Chỉ 1/100 câu đạt 1.0.**
- Không câu nào bị cờ `noncommittal` (không có điểm 0), nên toàn bộ biến thiên đến từ cosine.
- Rà soát: 98/100 câu trả lời đủ mọi vế. Trên 98 câu này, RAGAS TB **0.809**, thấp nhất **0.437**. Tương quan thứ hạng với rà soát là **0.02**, tức metric **không đo được mức đầy đủ của câu trả lời** trên bộ này.

Vì vậy 0.81 nên đọc là "mức nền" của cách tính này với model embedding này, không phải "19% câu trả lời lạc đề".

### 6.3 Vì sao multihop thấp (0.74)

Câu hỏi multihop **mô tả gián tiếp** thực thể, còn câu trả lời **gọi thẳng tên**. Câu hỏi sinh ngược bám theo câu trả lời nên chứa tên riêng, khác xa câu hỏi gốc trong không gian embedding.

Ví dụ **qa-038** (thấp nhất, 0.437, rà soát 1.00):

> Câu hỏi gốc: *"**Người thay mặt nhóm người Việt Nam yêu nước gửi bản Yêu sách** của nhân dân An Nam tới Hội nghị Vécxai năm 1919 từng dạy ở trường tư thục nào tại Phan Thiết, và trường ấy do đơn vị nào chu cấp kinh phí?"*
> Câu trả lời: *"Người đó là **Nguyễn Ái Quốc**… dạy học tại trường **Dục Thanh** ở Phan Thiết. Kinh phí… do **Công ty Liên Thành** chu cấp."*

Câu hỏi sinh ngược sẽ có dạng "Nguyễn Ái Quốc từng dạy ở trường nào tại Phan Thiết…": mất cả vế Yêu sách/Vécxai, lại thêm tên riêng. Cosine thấp dù câu trả lời hoàn hảo.

8/12 câu có `answer_relevancy` thấp nhất là multihop: qa-038, 043, 013, 079, 063, 093, 077, 064. Mẫu hình này khớp, nhưng muốn khẳng định cần xem 3 câu hỏi sinh ngược. [Suy luận]

### 6.4 Các yếu tố khác

| Yếu tố | Spearman với `answer_relevancy` | Diễn giải |
|---|---:|---|
| Độ dài câu hỏi gốc | **-0.32** | Câu hỏi dài, nhiều điều kiện thì câu hỏi sinh ngược ngắn gọn hơn, cosine giảm |
| Độ dài câu trả lời | +0.17 | Câu trả lời dài giữ được nhiều từ khoá của câu hỏi, sinh ngược sát hơn |
| Số vế câu hỏi | +0.11 | Không đáng kể |

multi_query (câu trả lời TB 1544 ký tự) vì thế không bị thấp như multihop, dù câu hỏi cũng dài.

### 6.5 Lỗi thật mà metric bắt được (một phần)

**qa-083** (bỏ một nửa câu hỏi) nhận 0.53, thấp thứ 7. Tuy vậy nhiều câu trả lời hoàn hảo còn bị chấm thấp hơn. Metric có phản ứng với lỗi thật nhưng **không tách được lỗi thật khỏi nhiễu**.

### 6.6 Tóm tắt

| Điểm cao do | Điểm thấp do |
|---|---|
| Không có câu trả lời né tránh | Cosine có trần tự nhiên dưới 1 |
| Câu trả lời dài giữ nhiều từ khoá câu hỏi | multihop: câu hỏi mô tả gián tiếp, câu trả lời gọi tên thẳng |
| | Câu hỏi gốc dài, nhiều điều kiện |
| | Chỉ một lỗi thật (qa-083) |

---

## 7. Tổng hợp: đâu là lỗi hệ thống, đâu là đặc tính cách chấm

| Metric | Phần phản ánh **chất lượng hệ thống** | Phần do **cách chấm** |
|---|---|---|
| `context_recall` | Thiếu bằng chứng ở qa-045, qa-053; multi_query hụt một vế | Lời lưu ý người soạn (qa-042); vài verdict 0 chưa kiểm |
| `context_precision` | **Chunk lạc đề đứng đầu ở multi_query** (9/24 câu); RRF ưu tiên chunk chung chung; hạn ngạch 8 chunk cho nhiều vế | Prompt khắt khe với chunk "cùng chủ đề" |
| `faithfulness` | qa-092, 041, 066 (mất sắc thái, khái quát hoá) | Câu trả lời dài bị phạt; câu kết luận bị chấm 0; judge lệch tới 0.59; lỗi quy kết (qa-026) chỉ bị trừ nhẹ |
| `factual_correctness` | qa-083, 009, 079, 035 thiếu ý | Công thức trộn hai tập claim; đáp án mẫu ngắn; judge lệch tới 0.40; đáp án mẫu rộng hơn câu hỏi |
| `answer_relevancy` | qa-083 bỏ một vế | Trần cosine; multihop bị phạt vì cách đặt câu hỏi; tương quan với rà soát ≈ 0 |

**Kết luận chính:**

1. **Lỗi hệ thống rõ nhất nằm ở khâu xếp hạng chunk cho câu hỏi nhiều vế.** `context_precision` của multi_query là tín hiệu đáng tin nhất trong 5 metric: kiểm chứng được bằng đọc chunk, và dẫn trực tiếp tới lỗi nội dung ở qa-026.
2. **`faithfulness`, `factual_correctness` và `answer_relevancy` thấp chủ yếu do cách chấm.** Rà soát nội dung cho 0.94–0.99, và tương quan với RAGAS thấp.
3. **`context_recall` cao là thật**, nhưng đây là metric dễ đạt nhất và không nói gì về độ sạch của ngữ cảnh.

---

## 8. Việc nên làm tiếp

### Hệ thống

1. **Xếp hạng lại sau RRF cho multi_query**: chạy reranker trên tập đã gộp, dùng câu hỏi gốc thay vì từng sub-query, trước khi cắt `multiquery_final_k`. Kiểm lại qa-069, 083, 026, 034, 073.
2. **Đảm bảo hạn ngạch cho từng vế** khi gộp (ví dụ ít nhất 3 chunk mỗi sub-query) thay vì chỉ theo tổng điểm RRF.
3. **Xem lại cách phá hoà theo `chunk_id`** trong `fuse_query_results`.
4. Prompt tổng hợp: giữ "có lẽ" của nguồn, không khái quát chủ trương thành việc đã làm, trả lời đủ mọi vế (qa-083).

### Đo lường

1. **Lưu trace từng verdict** (claim, verdict, lý do) cho `faithfulness`, `factual_correctness`, `context_precision`, và 3 câu hỏi sinh ngược của `answer_relevancy`. Không có trace thì các mục [Suy luận] ở trên không kiểm được.
2. **Lưu manifest** mỗi lần chạy: judge model, `reasoning_effort`, hash prompt, commit.
3. **Chấm lặp 3 lần** trên cùng đầu vào, báo cáo TB ± độ lệch chuẩn. Với độ dao động hiện tại (0.09–0.14), khác biệt dưới khoảng 0.05 giữa hai cấu hình là không có ý nghĩa.
4. **Thử judge mạnh hơn hoặc `reasoning_effort` cao hơn**, và judge khác model sinh câu trả lời.
5. **Thí nghiệm few-shot NLI cân bằng** (khoảng 50/50), so trên cùng 100 câu.
6. **`answer_relevancy`**: tính thêm cosine giữa câu hỏi gốc và các câu hỏi diễn đạt lại *do người viết* để biết mức trần thực tế của model embedding, rồi đọc điểm so với trần đó.
7. **`factual_correctness`**: dùng thêm độ phủ trên danh sách claim cố định của đáp án mẫu (473 mệnh đề đã có trong `claims.csv`), không dùng `mode=recall` làm con số duy nhất.

---

## Phụ lục A — Các câu điểm thấp nhất theo từng metric

### `context_precision`

| Câu | Loại | Điểm | Chunk hữu ích (suy ngược) |
|---|---|---:|---:|
| qa-069 | multi_query | 0.250 | 1–2 / 8 |
| qa-083 | multi_query | 0.267 | 2 / 8 |
| qa-043 | multihop | 0.310 | 2 / 8 |
| qa-034 | multi_query | 0.417 | 2 / 8 |
| qa-073 | multi_query | 0.417 | 2 / 8 |
| qa-014 | multi_query | 0.443 | 3 / 8 |
| qa-039 | multi_query | 0.450 | 2 / 8 |
| qa-037 | multihop | 0.500 | 1–4 / 8 |

### `context_recall`

| Câu | Loại | Điểm |
|---|---|---:|
| qa-009 | multi_query | 0.50 |
| qa-053 | multi_query | 0.50 |
| qa-045 | multi_query | 0.67 |
| qa-086 | single_query | 0.67 |
| qa-088 | multihop | 0.67 |
| qa-100 | multi_query | 0.67 |
| qa-042, 076, 083 | multi_query | 0.75 |
| qa-073 | multi_query | 0.80 |

### `faithfulness`

| Câu | Loại | RAGAS | Chấm lại | Rà soát | Số câu văn |
|---|---|---:|---:|---:|---:|
| qa-092 | multi_query | 0.29 | 0.38 | 0.93 | 7 |
| qa-047 | single_query | 0.33 | **0.92** | 1.00 | 6 |
| qa-023 | multi_query | 0.47 | 0.54 | 1.00 | 16 |
| qa-083 | multi_query | 0.50 | — | 1.00 | 5 |
| qa-053 | multi_query | 0.53 | 0.66 | 1.00 | 16 |
| qa-061 | single_query | 0.56 | 0.56 | 1.00 | 6 |
| qa-041 | single_query | 0.57 | 0.71 | 0.88 | 4 |
| qa-019 | single_query | 0.57 | 0.57 | 1.00 | 5 |

### `factual_correctness`

| Câu | Loại | RAGAS | Chấm lại | Rà soát | Mệnh đề đáp án mẫu |
|---|---|---:|---:|---:|---:|
| qa-081 | single_query | 0.00 | 0.00 | 1.00 | 2 |
| qa-068 | single_query | 0.00 | 0.40 | 0.83 | 3 |
| qa-099 | multihop | 0.25 | 0.33 | 1.00 | 2 |
| qa-009 | multi_query | 0.29 | 0.31 | 0.50 | 8 |
| qa-035 | multihop | 0.29 | 0.50 | 0.88 | 4 |
| qa-079 | multihop | 0.30 | 0.22 | 0.67 | 6 |
| qa-083 | multi_query | 0.37 | — | 0.43 | 7 |
| qa-023 | multi_query | 0.50 | 0.40 | 1.00 | 7 |
| qa-089 | single_query | 0.50 | 0.25 | 1.00 | 8 |

### `answer_relevancy`

| Câu | Loại | RAGAS | Rà soát |
|---|---|---:|---:|
| qa-038 | multihop | 0.437 | 1.00 |
| qa-043 | multihop | 0.468 | 1.00 |
| qa-013 | multihop | 0.474 | 1.00 |
| qa-021 | single_query | 0.478 | 1.00 |
| qa-079 | multihop | 0.487 | 1.00 |
| qa-063 | multihop | 0.517 | 1.00 |
| qa-083 | multi_query | 0.527 | **0.50** |
| qa-093 | multihop | 0.563 | 1.00 |

---

## Phụ lục B — Cách tái lập số liệu

- Điểm theo loại: ghép `auto_rag_v2.ragas.csv` với `retrieval_qa_v2.json` theo `id`, nhóm theo `type`.
- Số mệnh đề đáp án mẫu: đếm dòng theo `id` trong `auto_rag_v2.claims.csv`.
- Số câu văn trong câu trả lời: tách theo dấu `.!?` và xuống dòng, bỏ đoạn dưới 3 từ.
- Suy ngược verdict `context_precision`: liệt kê mọi chuỗi nhị phân độ dài `len(retrieved_contexts)` (8 hoặc 10) có ít nhất một số 1, tính average precision theo công thức ở mục 3.1, giữ chuỗi có sai số dưới 1e-4 so với điểm quan sát. Mọi câu đều có ít nhất một chuỗi khớp.
- Tương quan: Spearman (tương quan Pearson trên thứ hạng).
