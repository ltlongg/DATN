# Độ dài và cách diễn đạt câu trả lời ảnh hưởng thế nào tới điểm RAGAS — bộ `auto_rag_v2`

Ngày lập: 2026-09-17
Báo cáo liên quan: `auto_rag_v2.BAOCAO.md` (báo cáo tổng), `auto_rag_v2.METRICS.md` (phân tích từng metric)
Nguồn số liệu: `auto_rag_v2.ragas.csv` (100 câu, baseline), `retrieval_qa_v2.json`, `auto_rag_v2.manual_v2.csv`, `auto_rag_v2.faith_manual.csv`, `auto_rag_v2.ar_manual.csv`

---

## 1. Câu hỏi cần trả lời

Khi đọc câu trả lời của hệ thống, có hai nhận xét:

1. **Hệ thống thường trả lời dài và chi tiết hơn đáp án mẫu.**
2. **Hệ thống thường diễn đạt khác đáp án mẫu**, dù nội dung vẫn đúng.

Báo cáo này kiểm tra xem hai đặc điểm đó có phải nguyên nhân làm điểm RAGAS thấp không, và nếu có thì ảnh hưởng tới **metric nào**.

## 2. Kết luận ngắn

| Giả thuyết | `faithfulness` | `factual_correctness` | `answer_relevancy` | `context_precision` / `context_recall` |
|---|---|---|---|---|
| Trả lời dài, chi tiết hơn đáp án mẫu | ✅ **kéo điểm xuống** | ❌ không | ❌ không (còn hơi tăng) | ❌ không liên quan |
| Diễn đạt khác đáp án mẫu nhưng đúng | ? chưa đo được | ✅ **kéo điểm xuống** | ~ yếu | ❌ không liên quan |

- Hai đặc điểm này **giải thích được một phần lớn** điểm thấp của `faithfulness` và `factual_correctness`.
- Chúng **không giải thích** được điểm thấp của `context_precision`, vì metric đó không đọc câu trả lời. Điểm thấp ở đó do chunk lạc đề bị xếp lên đầu, xem `METRICS.md` mục 3.
- Chúng **không giải thích** được điểm thấp của `answer_relevancy`, vì metric đó thấp do cách tính bằng cosine và cách đặt câu hỏi multihop, xem `METRICS.md` mục 6.

---

## 3. Cách đo

### 3.1 Hai chỉ số

Câu trả lời và đáp án mẫu được tách thành từ (chữ thường, bỏ chuỗi mã chunk `tap*_clean-*`).

| Chỉ số | Công thức | Ý nghĩa |
|---|---|---|
| **Mức nói thừa** | `số từ câu trả lời / số từ đáp án mẫu` | Lớn hơn 1: câu trả lời dài hơn đáp án mẫu |
| **Mức giữ cách diễn đạt** | `số cặp từ liền nhau của đáp án mẫu xuất hiện trong câu trả lời / tổng số cặp từ của đáp án mẫu` | Thấp: câu trả lời viết lại theo cách khác |

Chỉ số thứ hai là **ước lượng thô** dựa trên trùng từ. Nó không phân biệt được "diễn đạt khác nhưng đúng" với "thiếu ý". Vì vậy mục 3.2 lọc bớt các câu thiếu ý thật.

### 3.2 Tách ảnh hưởng của lỗi thật

Một câu trả lời thiếu ý sẽ vừa dùng ít từ của đáp án mẫu, vừa bị chấm thấp. Để không nhầm điều đó với "diễn đạt khác", mỗi phép đo được tính trên hai tập:

- **Toàn bộ 100 câu.**
- **Tập đã xác nhận đúng** theo bảng rà soát:
  - 69 câu phủ đủ đáp án mẫu (`FC_manual_v2 = 1`), dùng cho `factual_correctness` và `answer_relevancy`.
  - 94 câu bám nguồn hoàn toàn (`faithfulness_manual = 1`), dùng cho `faithfulness`.

Nếu một metric vẫn giảm theo chỉ số trên **tập đã xác nhận đúng**, thì phần giảm đó là do cách chấm chứ không do lỗi nội dung.

Tương quan dùng Spearman (tương quan theo thứ hạng). Với khoảng 70–100 câu, hệ số có trị tuyệt đối dưới 0.2 được coi là không đáng kể.

### 3.3 Mức độ của hai đặc điểm

| | Trung vị | Khoảng 25%–75% | Thấp nhất – cao nhất |
|---|---:|---:|---:|
| Mức nói thừa | **1.80 lần** | 1.24 – 2.82 | 0.69 – 5.14 |
| Mức giữ cách diễn đạt | 0.60 | 0.49 – 0.68 | 0.29 – 0.97 |

Theo loại câu hỏi (trung vị):

| | Mức nói thừa | Mức giữ cách diễn đạt |
|---|---:|---:|
| multi_query | **2.90 lần** | **0.51** |
| single_query | 2.03 lần | 0.63 |
| multihop | 1.34 lần | 0.65 |

Nhận xét ban đầu là đúng: câu trả lời **dài gần gấp đôi** đáp án mẫu, và chỉ giữ khoảng **60%** cách diễn đạt. multi_query là nhóm nói thừa và viết lại nhiều nhất.

---

## 4. Kết quả: trả lời dài, chi tiết hơn

### 4.1 Tương quan với mức nói thừa

| Metric | Toàn bộ 100 câu | Tập đã xác nhận đúng |
|---|---:|---:|
| `faithfulness` | **-0.33** | **-0.38** (94 câu) |
| `factual_correctness` | 0.03 | -0.07 (69 câu) |
| `answer_relevancy` | 0.19 | 0.07 (69 câu) |
| `context_precision` | -0.07 | — |
| `context_recall` | -0.15 | — |

### 4.2 `faithfulness`: bị ảnh hưởng rõ

Trên 94 câu bám nguồn hoàn toàn theo rà soát, chia làm 3 nhóm theo mức nói thừa:

| Mức nói thừa | Số câu | `faithfulness` RAGAS TB |
|---|---:|---:|
| 0.69 – 1.38 lần | 32 | **0.896** |
| 1.38 – 2.39 lần | 30 | 0.837 |
| 2.39 – 5.14 lần | 32 | **0.780** |

Cả 94 câu đều **không bịa**, nhưng câu dài nhất mất thêm khoảng **0.12 điểm** so với câu ngắn nhất.

Ví dụ:

| Câu | Loại | Mức nói thừa | Số câu văn | `faithfulness` | Rà soát |
|---|---|---:|---:|---:|---:|
| qa-037 | multihop | 0.69 | 2 | 1.00 | 1.00 |
| qa-068 | single_query | 0.75 | 2 | 1.00 | 1.00 |
| qa-086 | single_query | 0.80 | 2 | 1.00 | 1.00 |
| qa-053 | multi_query | 3.38 | 16 | **0.53** | 1.00 |
| qa-070 | multi_query | 3.45 | 15 | **0.67** | 1.00 |
| qa-045 | multi_query | 4.28 | 21 | 0.76 | 1.00 |

**Vì sao.** `faithfulness` so câu trả lời với **ngữ cảnh**, không so với đáp án mẫu. Cho nên vấn đề không phải "thừa so với đáp án mẫu", mà là:

1. **Nhiều mệnh đề thì nhiều cơ hội bị chấm 0.** Điểm là `mệnh đề verdict 1 / tổng mệnh đề`. Judge chấm sai một vài mệnh đề là gần như chắc chắn khi có 15–20 mệnh đề. [Đã kiểm về công thức]
2. **Câu trả lời dài thường có câu diễn giải, kết nối, tổng kết**, như *"Nhờ sự phối hợp này…"* hay *"Đây là yêu cầu nhằm…"*. Prompt chấm cấm *"rút ra kết luận gián tiếp"*, nên các câu này dễ bị chấm 0 dù đúng tinh thần nguồn. [Suy luận: khớp với prompt, chưa có trace]
3. **Judge dao động.** Chấm lại qa-047 thì điểm đổi từ 0.33 lên 0.92. Mệnh đề càng nhiều thì dao động cộng dồn càng lớn. [Đã kiểm về số liệu]

Điều này cũng giải thích thứ tự theo loại câu hỏi: multihop (ngắn) **0.90** > single_query **0.81** > multi_query (dài nhất) **0.78**.

### 4.3 `factual_correctness`: không bị ảnh hưởng

| Mức nói thừa (4 nhóm, 100 câu) | `factual_correctness` TB | Rà soát TB |
|---|---:|---:|
| 0.69 – 1.24 lần | 0.793 | 0.922 |
| 1.24 – 1.80 lần | 0.840 | 0.945 |
| 1.80 – 2.82 lần | 0.825 | 0.949 |
| 2.82 – 5.14 lần | **0.850** | 0.953 |

Câu dài **không** bị điểm thấp hơn. Lý do nằm ở công thức `mode="recall"` [Đã kiểm, `_factual_correctness.py` dòng 282–292]:

```
score = tp / (tp + fn)
tp = số mệnh đề của câu trả lời được đáp án mẫu xác nhận
fn = số mệnh đề của đáp án mẫu không có trong câu trả lời
```

Mệnh đề thừa **không có** trong đáp án mẫu được tính là `fp`, và `fp` **không nằm trong công thức recall**. Câu trả lời dài lại có nhiều mệnh đề đúng hơn, làm `tp` lớn và che bớt `fn`.

Chi tiết thừa chỉ gây hại khi nó **nằm chung một mệnh đề** với ý đúng: cả mệnh đề có thể bị chấm 0 vì đáp án mẫu không nêu *"toàn bộ"* mệnh đề. Trường hợp này thuộc mục 5.

### 4.4 `answer_relevancy`: không bị ảnh hưởng, còn hơi tăng

Câu trả lời dài giữ được nhiều từ khoá của câu hỏi. Vì vậy câu hỏi sinh ngược từ câu trả lời gần câu hỏi gốc hơn. Tương quan dương nhẹ (0.19 trên 100 câu, 0.07 trên tập đã xác nhận đúng).

### 4.5 `context_precision`, `context_recall`: không liên quan

Hai metric này chỉ nhận (câu hỏi, chunk, đáp án mẫu), **không đọc câu trả lời** [Đã kiểm]. Mọi tương quan quan sát được với độ dài câu trả lời chỉ là gián tiếp.

---

## 5. Kết quả: diễn đạt khác đáp án mẫu

### 5.1 Tương quan với mức giữ cách diễn đạt

| Metric | Toàn bộ 100 câu | Tập đã xác nhận đúng |
|---|---:|---:|
| `factual_correctness` | **0.49** | **0.37** (69 câu) |
| `faithfulness` | 0.19 | 0.13–0.17 |
| `answer_relevancy` | 0.07 | 0.20 (69 câu) |
| `context_precision` | 0.34 | — |
| `context_recall` | 0.31 | — |

`context_precision` và `context_recall` có tương quan 0.3 nhưng **không phải quan hệ nhân quả**, vì hai metric này không đọc câu trả lời. Khi tra đúng đoạn nguồn, hệ thống chép sát nguồn, và đáp án mẫu cũng viết từ nguồn đó, nên hai bên trùng từ nhiều. Tra kém thì cả hai điều cùng giảm.

### 5.2 `factual_correctness`: bị ảnh hưởng rõ

Trên 69 câu **đã phủ đủ đáp án mẫu** theo rà soát, chia làm 3 nhóm theo mức giữ cách diễn đạt:

| Mức giữ cách diễn đạt | Số câu | `factual_correctness` RAGAS TB |
|---|---:|---:|
| 0.33 – 0.58 (viết lại nhiều nhất) | 23 | **0.793** |
| 0.58 – 0.69 | 23 | 0.942 |
| 0.69 – 0.97 (chép sát nhất) | 23 | 0.903 |

Cả 69 câu đều **đủ ý**, nhưng nhóm viết lại nhiều nhất mất khoảng **0.10–0.15 điểm** so với hai nhóm còn lại.

Trên toàn bộ 100 câu, mức chênh còn lớn hơn khi chia 4 nhóm: 0.68 ở nhóm thấp nhất, 0.80 ở nhóm kế tiếp, 0.90–0.93 ở hai nhóm cao nhất, vì nhóm này còn lẫn các câu thiếu ý thật.

Ví dụ các câu đúng và đủ nhưng bị chấm thấp:

| Câu | Loại | Mức giữ cách diễn đạt | Mức nói thừa | `factual_correctness` | Rà soát |
|---|---|---:|---:|---:|---:|
| qa-086 | single_query | 0.42 | 0.80 | **0.60** | 1.00 |
| qa-023 | multi_query | 0.48 | 3.01 | **0.50** | 1.00 |
| qa-100 | multi_query | 0.48 | 2.11 | **0.60** | 1.00 |
| qa-081 | single_query | — | — | **0.00** | 1.00 |
| qa-099 | multihop | — | — | **0.25** | 1.00 |

Đối chứng, các câu chép sát đáp án mẫu đều đạt tối đa: qa-018 (0.95), qa-052 (0.96), qa-027 (0.97) đều được 1.00.

**qa-023.** Đáp án mẫu viết thành một đoạn văn liền. Câu trả lời tách thành các gạch đầu dòng theo từng tầng lớp và diễn đạt lại:

> Đáp án mẫu: *"…Tô Định và chính quyền Đông Hán **đốc thúc cống thuế, đàn áp người chống đối, chèn ép và ràng buộc quan lại bản địa**…"*
>
> Câu trả lời: *"**Nhân dân các quận Giao Chỉ, Cửu Chân, Nhật Nam:** Tô Định cùng chính quyền đô hộ **tăng cường thu cống, thuế, bóc lột và trừng trị thẳng tay** những người chống đối…"*

Nội dung tương đương, nhưng "tăng cường thu cống" khác "đốc thúc cống thuế", lại thêm "các quận Giao Chỉ, Cửu Chân, Nhật Nam" mà đáp án mẫu không có. RAGAS 0.50, rà soát 1.00.

**qa-100.** Câu trả lời sắp xếp theo "hướng Bắc và ven biển miền Trung" và "hướng Đông", có thêm chi tiết "xoá bỏ Quân khu I" và "giải phóng các tỉnh ven biển". Đáp án mẫu diễn đạt theo *tác động* của từng thắng lợi. RAGAS 0.60, rà soát 1.00. (Rà soát lượt trước có nêu nghi vấn cách gọi "hai hướng chủ yếu" ở câu này, xem `BAOCAO.md` mục 3.4.)

**qa-099.** Câu trả lời có thêm "các đơn vị Quân đoàn II", "lúc 10 giờ 45 phút" — đúng nguồn nhưng đáp án mẫu không có. RAGAS 0.25 (chấm lại 0.33), rà soát 1.00.

**Vì sao** [Đã kiểm về prompt, cơ chế là suy luận]: prompt chấm yêu cầu đáp án mẫu *"nêu rõ hoặc diễn đạt tương đương **toàn bộ** mệnh đề"*, và trả 0 khi *"chỉ có một phần không đủ để khẳng định"*.

- Mệnh đề viết lại bằng từ khác dễ bị judge coi là "không nêu rõ".
- Mệnh đề **ghép ý đúng với chi tiết thừa** bị coi là "chỉ có một phần", nên cả mệnh đề nhận 0.
- Đáp án mẫu ngắn (2–3 mệnh đề) nên mỗi verdict sai làm điểm tụt mạnh (qa-081, qa-099, qa-086).

### 5.3 `faithfulness`: chưa đo được bằng chỉ số này

Chỉ số "giữ cách diễn đạt" so với **đáp án mẫu**, còn `faithfulness` so với **ngữ cảnh**. Tương quan yếu (0.13–0.19) là đúng dự đoán: chỉ số này đo sai đối tượng.

Hiện tượng tương tự rất có thể xảy ra giữa câu trả lời và ngữ cảnh: hệ thống dùng từ đồng nghĩa ("nước lũ" thay cho "nước"), hoặc khái quát hoá. Muốn đo cần một chỉ số so câu trả lời với ngữ cảnh, hoặc tốt hơn là trace verdict từng mệnh đề.

### 5.4 `answer_relevancy`: ảnh hưởng yếu

Metric này so câu hỏi sinh ngược với **câu hỏi gốc**, không so với đáp án mẫu, nên cách diễn đạt so với đáp án mẫu gần như không liên quan (0.07 trên 100 câu). Ảnh hưởng chính của cách diễn đạt nằm ở chỗ khác: câu trả lời multihop **gọi thẳng tên** thực thể mà câu hỏi chỉ mô tả gián tiếp. Xem `METRICS.md` mục 6.3.

---

## 6. Hệ quả khi đọc điểm

1. **Điểm `faithfulness` thấp của multi_query (0.78) không có nghĩa là multi_query bịa nhiều hơn.** Rà soát cho multi_query 0.986. Phần lớn khoảng cách là do câu trả lời dài gấp khoảng 3 lần đáp án mẫu.
2. **Điểm `factual_correctness` phạt cách viết, không chỉ phạt nội dung.** Một câu trả lời đúng và đủ có thể nhận 0.5–0.8 chỉ vì viết lại hoặc kèm chi tiết.
3. **So sánh hai phiên bản hệ thống phải giữ nguyên phong cách trả lời.** Nếu phiên bản mới trả lời ngắn hơn hoặc chép sát nguồn hơn, `faithfulness` và `factual_correctness` sẽ tăng **dù chất lượng nội dung không đổi**.
4. **Không nên tối ưu hệ thống theo hai metric này bằng cách rút gọn câu trả lời một cách máy móc.** Làm vậy tăng điểm nhưng có thể làm mất chi tiết có ích cho người dùng.

---

## 7. Đề xuất

### Về đo lường

1. **Báo cáo kèm độ dài.** Mỗi lần chạy nên ghi mức nói thừa TB, và báo `faithfulness` theo nhóm độ dài để thấy phần do độ dài.
2. **Trace từng mệnh đề** cho `faithfulness` và `factual_correctness`: câu nào bị chấm 0, lý do judge đưa ra. Đây là cách duy nhất để khẳng định các mục [Suy luận] ở trên (câu diễn giải bị chấm 0, chi tiết thừa làm hỏng mệnh đề).
3. **Bổ sung độ phủ trên danh sách mệnh đề cố định** của đáp án mẫu (473 mệnh đề trong `claims.csv`). Judge chỉ cần trả lời "câu trả lời có nêu ý này không", ít bị ảnh hưởng bởi chi tiết thừa hơn `mode=recall`.
4. **Nới prompt NLI cho diễn đạt tương đương:** thêm ví dụ mẫu có verdict 1 cho trường hợp viết lại bằng từ đồng nghĩa, và cho trường hợp mệnh đề có thêm chi tiết không mâu thuẫn. Chạy như một thí nghiệm có đối chứng.
5. **Thử chấm với câu trả lời đã chuẩn hoá** (bỏ markdown, bỏ câu kết luận chung) trên một tập nhỏ, để đo phần điểm mất do phong cách trình bày.

### Về hệ thống

1. **Giảm câu diễn giải, tổng kết không có trong nguồn** ở prompt tổng hợp. Việc này vừa tăng `faithfulness` vừa giảm rủi ro khái quát sai (qa-066).
2. **Cân nhắc giới hạn độ dài theo loại câu hỏi**, nhất là multi_query (hiện dài gấp khoảng 2.9 lần đáp án mẫu). Nên giữ đủ ý từng vế thay vì cắt máy móc.
3. **Ưu tiên dùng lại cách diễn đạt của nguồn** với các dữ kiện quan trọng (tên, số liệu, thời gian, mức độ chắc chắn như "có lẽ").

---

## Phụ lục — Cách tái lập

```python
import re, pandas as pd

def tok(s):
    return re.findall(r"\w+", re.sub(r"tap\d_clean-\d+", "", s.lower()))

def bigrams(t):
    return set(zip(t, t[1:]))

R, G = tok(response), tok(reference)
muc_noi_thua = len(R) / len(G)
muc_giu_dien_dat = len(bigrams(R) & bigrams(G)) / max(1, len(bigrams(G)))
```

- `response`, `reference`: cột cùng tên trong `auto_rag_v2.ragas.csv`.
- Tập đã xác nhận đúng: `FC_manual_v2 == 1` trong `auto_rag_v2.manual_v2.csv`; `faithfulness_manual == 1` trong `auto_rag_v2.faith_manual.csv`.
- Chia nhóm bằng `pd.qcut` (3 hoặc 4 nhóm bằng nhau về số câu).
- Tương quan: Spearman, tính bằng tương quan Pearson trên thứ hạng (`Series.rank()`).
