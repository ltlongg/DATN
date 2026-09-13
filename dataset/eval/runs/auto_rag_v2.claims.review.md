# Rà soát auto_rag_v2.claims.md và auto_rag_v2.claims.csv

Ngày rà soát: 2026-09-08. Giữ nguyên hai file và các kết quả chạy gốc.

**Kết luận:** số liệu và hai định dạng khớp nhau; phần lớn nhận định bao phủ có cơ sở. Tuy nhiên, rubric tách mệnh đề và cho điểm một phần chưa nhất quán, nên chưa nên coi FC_manual_v2 là điểm chuẩn đã được xác nhận. Có những điểm FC tự động thấp rõ ràng không phù hợp với nội dung, nhưng không thể quy toàn bộ chênh lệch manual–RAGAS thành lỗi của LLM.

## Phạm vi và bằng chứng

- Đọc question, gold_answer, response và toàn bộ 473 dòng mệnh đề của 100 ID; đối chiếu Markdown với CSV bằng chương trình.
- Gold: [retrieval_qa_v2.json](../retrieval_qa_v2.json). Response/context: [auto_rag_v2.json](auto_rag_v2.json).
- Đối chiếu số tổng với [manual_v2.csv](auto_rag_v2.manual_v2.csv), điểm tự động với bản RAGAS gốc và bản chấm lại 32 ID.
- Kiểm tra các đoạn context liên quan ở qa-012, 017, 025, 026, 041, 056, 066, 069, 071, 083, 092, 100. Không chấm lại toàn bộ claim của response để tính Faithfulness cho 100 câu; không kiểm chứng lịch sử bằng nguồn ngoài.
- Đọc cấu hình và prompt hiện có trong `apps/agent-service/scripts/run_ragas_eval.py` và `scripts/ragas_prompts/`. Đây là cấu hình hiện tại, chưa phải bằng chứng đầy đủ về cấu hình từng lần chạy trước.
- Không gọi lại judge. Các CSV kết quả đang xét không chứa trace tách claim, verdict và reason của RAGAS; vì vậy chưa xác định được điểm bất thường phát sinh ở bước tách claim, NLI hay khâu khác.

## 1. Kiểm tra số liệu: đạt

| Kiểm tra | Kết quả |
|---|---:|
| Số mục Markdown / số ID CSV | 100 / 100 |
| Số mệnh đề CSV, không kể header | 473 |
| `co` / `mot_phan` / `khong` | 431 / 20 / 22 |
| Tổng điểm mệnh đề | 441,0 |
| Trung bình từng câu, tính từ phân số chưa làm tròn | 0,94207738 |
| Trung bình cột FC_manual_v2 đã làm tròn | 0,9422 |
| Trung bình gộp tất cả mệnh đề: 441/473 | 0,93234672 |
| Số câu đạt 1,00 | 69 |
| Số mệnh đề mỗi câu | 2–9 |

Không phát hiện lệch nội dung, nhãn, điểm, thứ tự mệnh đề hay tử số/mẫu số giữa Markdown, CSV và bảng tổng manual_v2. Nhãn `co/mot_phan/khong` khớp điểm `1/0,5/0`. Các điểm hiển thị hai chữ số đều làm tròn đúng.

Hai cách trung bình 0,9421 và 0,9323 có trọng số khác nhau: cách đầu mỗi câu ngang nhau, cách sau mỗi mệnh đề ngang nhau. Cần ghi rõ khi đưa vào báo cáo.

Điểm `RAGAS` trong Markdown và `FC_ragas` trong manual_v2 khớp toàn bộ với quy tắc **lấy auto_rag_v2.ragas.csv, ghi đè FC cho các ID trong auto_rag_v2.factual_correctness.ids32.csv**. Đây không phải điểm chỉ lấy từ bản gốc.

| Phiên bản trên đủ 100 ID | FC recall trung bình | Faithfulness trung bình |
|---|---:|---:|
| Bản RAGAS gốc | 0,8268 | 0,82800203 |
| Ghi đè metric tương ứng bằng ids32 / ids20 | 0,8299 | 0,85177765 |

Question, response, reference và retrieved_contexts trong các CSV chấm lại khớp bản CSV gốc. Không được lấy trung bình riêng 32 hoặc 20 câu để đại diện cho cả 100 câu; chưa có căn cứ xem các tập chấm lại là mẫu ngẫu nhiên.

## 2. Hai file đang đo gì?

Đây là **độ phủ gold có điểm một phần**, với công thức `sum(diem) / so_menh_de_gold`. Chúng không chứa bảng verdict hỗ trợ từ context cho mọi mệnh đề của response, nên không đủ để xác nhận Faithfulness, Answer Relevancy hay các metric retrieval.

Script cấu hình `FactualCorrectness(llm=llm, mode="recall")`. Prompt NLI tiếng Việt hiện tại dùng verdict nhị phân: phải được nêu đầy đủ hoặc diễn đạt tương đương mới nhận 1; chỉ có một phần nhận 0. Prompt tách claim còn yêu cầu giữ chủ thể, quan hệ, số lượng, thời điểm, địa điểm, phủ định và mức chắc chắn. Manual lại dùng 0,5 và thường gộp nhiều thuộc tính.

Tài liệu chính thức mô tả FC đối chiếu response với reference, còn Faithfulness đối chiếu claim của response với retrieved contexts: [RAGAS FC](https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/factual_correctness/), [RAGAS Faithfulness](https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/faithfulness/).

Vì vậy:

- Câu trả lời có thể phủ hết gold mà vẫn thêm thông tin không được context hỗ trợ.
- Câu trả lời có thể trả lời đủ điều được hỏi mà không phủ các chi tiết phụ trong gold.
- Manual cao hơn RAGAS chưa tự chứng minh RAGAS chấm sai: cả đơn vị đếm lẫn cách chấm đang khác nhau.
- Chỉ đổi 20 nhãn một phần thành 0, giữ nguyên các nhóm claim và mọi nhãn khác, trung bình manual đã xuống **0,92297619**. Đây chỉ là minh họa ảnh hưởng rubric, không phải điểm RAGAS tái lập hay điểm sửa được khuyến nghị.

## 3. Những điểm cần sửa trước theo rubric manual hiện có

Các mức 0,5 dưới đây nhằm áp dụng nhất quán quy tắc một phần của bảng hiện tại. Chúng không phải verdict nhị phân của RAGAS và không phải một bản chấm mới đã chuẩn hóa toàn bộ cách tách claim.

| ID / mệnh đề | Hiện tại | Bằng chứng và xử lí đề nghị |
|---|---|---|
| **qa-016 / 1** | 1; tổng 3/3 = 1,00 | Claim có **“Tháng 1-1285”**, response chỉ nói **“Đầu năm 1285”**. Không phủ mốc tháng chính xác. Nếu vẫn trừ chi tiết nhỏ như ở qa-001/002/017/085, claim này nên là **0,5**, tổng **2,5/3 = 0,83**. Đáp án vẫn trả lời đúng yêu cầu trực tiếp của câu hỏi. |
| **qa-045 / 7** | 0; tổng 5/7 = 0,71 | Claim gồm các quân thứ ở địa phương **và** liên lạc với đại bản doanh để chỉ huy thống nhất. Response có “phân tán theo từng địa bàn”, “nhiều chỉ huy địa phương phối hợp với nhau”, nhưng thiếu đại bản doanh và cơ chế chỉ huy chung. Ghi hoàn toàn không nêu là quá mạnh so với cách cho 0,5 ở qa-017/053/091. Đề nghị **0,5**, tổng **5,5/7 = 0,79**; claim 6 vẫn 0. Phần thiếu chỉ huy trung tâm vẫn là lỗi quan trọng của câu trả lời. |
| **qa-083 / 7** | 0; tổng 3/7 = 0,43 | Claim so sánh hai sự kiện. Response đã nêu vế Đại hội Tua đánh dấu chuyển biến lập trường, thiếu toàn bộ vế đóng góp ở Đại hội V. Nếu claim ghép có một vế được phủ thì nhận 0,5 như qa-039/066, dòng này nên **0,5**, tổng **3,5/7 = 0,50**. Nếu muốn coi quan hệ so sánh là một đơn vị bắt buộc đủ cả hai phía thì có thể giữ 0, nhưng phải ghi ngoại lệ rubric và áp dụng nhất quán. |

Ba đề nghị này không làm thay đổi kết luận nghiệp vụ: qa-016 trả lời đúng trọng tâm; qa-045 thiếu cơ chế chỉ huy; qa-083 bỏ hẳn một nửa yêu cầu. Điểm chính xác phụ thuộc cách định nghĩa đơn vị chấm.

## 4. Những trường hợp phải chốt lại rubric trước khi đổi điểm

| ID / mệnh đề | Vấn đề | Cách xử lí công bằng hơn |
|---|---|---|
| **qa-041 / 3–4** | Claim 3 ghi “Tài liệu đưa ra giả thuyết…” nhưng nhận 1 dù response không giữ tính giả thuyết; claim 4 lại nhận 0 cho cùng thiếu sót. Hai dòng cùng mang thuộc tính mức chắc chắn. | Chuẩn hóa để chỉ chấm thuộc tính phỏng đoán một lần. Có thể tách nội dung nguyên nhân khỏi trạng thái giả thuyết, hoặc gộp thành một claim có modality. Không chỉ hạ dòng 3 rồi giữ nguyên mọi thứ: có nguy cơ phạt trùng. Cờ mất sắc thái hiện tại là đúng; chưa nên xác nhận 0,75 là điểm chuẩn. |
| **qa-068 / 3** | Bị 0,5 vì không nói “không quy riêng cho Tuần lễ vàng”, dù response nói chung “Sau Cách mạng tháng Tám” và không hề quy số liệu cho Tuần lễ vàng. | Nếu đây là ràng buộc chống diễn giải sai, đáp án đã giữ đúng phạm vi: nên đạt hoặc loại khỏi mẫu số mệnh đề nội dung. Với cách cho đạt, tổng là 3/3 = **1,00**. Nếu yêu cầu nhắc rõ lời lưu ý trong gold, 0,5 cần được định nghĩa, không thể tự coi việc không mắc lỗi là nêu một nửa mệnh đề. |
| **qa-042 / 5** | Bị 0 vì không nhắc lời lưu ý rằng hoạt động nêu ở một bên không nhất thiết vắng mặt ở bên kia. Response không nói bên nào hoàn toàn không có hoạt động đó. | Theo recall từng câu chữ gold, thiếu lời lưu ý là có thật. Theo tiêu chí trả lời đúng nghĩa và không khẳng định độc quyền, không nên tự trừ 20% chỉ vì thiếu câu phòng ngừa. Cụm “kết hợp rõ hơn” ở kết luận vẫn cần so với nguồn riêng, không mặc nhiên nâng toàn câu lên 1. |
| **qa-034 / 8** | Bị 0,5 vì thiếu câu “không đồng nghĩa giải phóng nô tì”, trong khi response nêu nô tì vượt mức bị sung công và số còn lại ghi dấu theo chủ. | Chốt có chấp nhận hệ quả ngữ nghĩa từ cơ chế được mô tả hay bắt buộc phát biểu trực tiếp. Nếu chỉ đo không hiểu sai việc giải phóng, không nên bắt lặp lại câu cảnh báo. Không đồng nhất thiếu phát biểu với khẳng định sai. |
| **qa-086 / 3** | Được 1 dù không lặp lời lưu ý “không phải lịch rút quân đã được thực hiện đầy đủ”; lí do là response dùng “quy định” và “sẽ”. | Cho điểm theo ngữ nghĩa như vậy là hợp lí. Dùng làm ví dụ để thống nhất quy tắc đối với qa-068 và các câu có lời lưu ý. |
| **qa-092 / 2 và 7** | Claim “có lẽ” ở dòng 2 được 1; dòng 7 bị 0,5 do kết luận khẳng định lại công dụng. | Response có cả đoạn giữ đúng phỏng đoán và đoạn làm mất sắc thái. Cần phân biệt “có nêu đúng một lần” với “nhất quán toàn đáp án”; tránh đếm cùng thuộc tính hai lần mà không quy định trước. Cờ mất sắc thái ở kết luận là đúng. |
| **qa-093 / 1** | Claim “Thẩm Khuyên và Thẩm Hai nằm ở Lạng Sơn” nhận 1; response chỉ gắn trực tiếp Lạng Sơn với Kéo Lèng. Quan hệ cùng tỉnh được hiểu từ câu hỏi. | Nếu cho dùng tiền đề câu hỏi và hồi chỉ để giải nghĩa đáp án, 1 có thể chấp nhận. Nếu chỉ response được dùng làm văn bản đối chiếu thì quan hệ này chưa nêu rõ. Phải ghi quy tắc, không tự bổ sung địa điểm từ kiến thức bên ngoài. |

Không đề xuất một điểm trung bình “đã sửa chuẩn” khi các quyết định rubric này còn mở. Thay vài nhãn để được một con số mới không giải quyết được sai lệch do cách tách/gộp.

## 5. Cách tách claim chưa đúng với lời giới thiệu của bảng

Lời mở đầu nói mỗi mệnh đề là một vế chủ–vị độc lập, nhưng nhiều dòng chưa đứng riêng được hoặc có nhiều vế độc lập:

- qa-083/4 chỉ là **“TẠI ĐẠI HỘI V QUỐC TẾ CỘNG SẢN TỪ NGÀY 17-6 ĐẾN 8-7-1924”**: thiếu chủ thể/hành động. qa-095/4 cũng chỉ là phần thời gian và điều kiện.
- qa-002/3 gộp chế tác bằng ghè đẽo và chưa có kĩ thuật mài; qa-001 lại tách hai nội dung đó. qa-011/3 gộp số lượng ít, hình dáng thô và độ nung chưa cao.
- qa-029/3 gộp giải phóng 150 ấp, bức rút 47 đồn bốt, diệt hơn 300 quân địch thành một dòng, dù là ba kết quả kiểm chứng riêng.
- Quan hệ cha con bị tách riêng ở qa-013 nhưng gộp với nhận diện người ở qa-075; cùng một thuộc tính thiếu vì thế có trọng số khác nhau.
- Các câu kết so sánh thường lặp dữ kiện vừa chấm ở phần thân, như qa-026/8–9, qa-083/7, qa-100/7. Nếu thật sự cần chấm năng lực so sánh, nên tách tiêu chí đó khỏi recall dữ kiện để tránh đếm lại.

Ví dụ ảnh hưởng trọng số: qa-085 chỉ có ba claim. Việc thiếu chức danh “Tổng Bí thư” mất 0,5/3, tức khoảng **16,7 điểm phần trăm** dù đã xác định đúng Trường Chinh, hội nghị và quyết định. Ở qa-053, thiếu nhiều chi tiết trong danh sách môn học vẫn chỉ mất 0,5 cho cả nhóm. Không thể diễn giải hai mức trừ như cùng phản ánh tầm quan trọng nghiệp vụ.

## 6. RAGAS có chấm thấp bất hợp lí không?

**Có những trường hợp có bằng chứng nội dung rất mạnh.** Các điểm dưới đây dùng bản ghép đã xác định ở mục 1.

| ID | FC RAGAS | Đối chiếu |
|---|---:|---|
| **qa-081** | **0,00** | Gold yêu cầu tự do học tập và trường kĩ thuật/chuyên nghiệp ở tất cả các tỉnh cho người bản xứ. Response nêu đủ tất cả. Điểm recall 0 không phù hợp với văn bản; manual 1,00 có cơ sở rất rõ. |
| **qa-099** | **0,33** | Response nêu Dương Văn Minh, việc Trần Văn Hương nhường chức, đầu hàng không điều kiện khi quân vào Dinh Độc lập ngày 30-4-1975. Gold được phủ đầy đủ. Điểm thấp khó giải thích bằng thiếu chi tiết; manual 1,00 hợp lí. |
| **qa-086** | **0,50** | Response có 15.000 quân, thay quân Tưởng, mỗi năm 1/5, sau 5 năm rút hết và giữ ngữ cảnh quy định trong tương lai. Cần xem trace trước khi chấp nhận điểm thấp; manual 1,00 hợp lí theo tiêu chí giữ nghĩa. |
| **qa-089** | **0,25** | Cả sức ép đàm phán lẫn mục tiêu phá nguồn lực trong gold đều được response mô tả. Chưa thấy thiếu sót nội dung đủ giải thích mức recall này. Không dùng các thông tin thêm để phạt recall một cách tự động. |

Ngược lại, không phải mọi điểm thấp là chấm oan: qa-009 thiếu nhiều điều khoản; qa-045 thiếu đầu mối chỉ huy; qa-083 bỏ toàn bộ Đại hội V; qa-079 thiếu nguồn tiền và Ban Tài chính nếu chấm toàn gold. Manual thấp hơn RAGAS ở một số câu cũng có thể do đơn vị đếm, chẳng hạn qa-096 manual 0,75 so với RAGAS 0,86.

**Chưa đủ bằng chứng về độ ổn định của judge.** Bản gốc và bản chấm lại cho điểm khác nhau, nhưng không có manifest đầy đủ về model, prompt hash, tham số sinh và trace từng lần để kết luận khác biệt chỉ do tính ngẫu nhiên của LLM. Việc qa-081 vẫn 0 trong cả hai bản cũng cho thấy chạy lại đơn thuần chưa chắc khắc phục lỗi có hệ thống.

## 7. Lỗi nội dung và giới hạn của hai file

Các ghi chú đang có về qa-012, 026, 041, 066, 069, 071, 092 nhìn chung có cơ sở khi đối chiếu response/context:

- qa-012: context 1 có cả đầu thế kỉ III TCN và khoảng tồn tại 208–179 TCN; context 2 có kháng chiến 214–208 TCN. Đây có vấn đề từ nguồn, không nên quy tất cả thành bịa ngoài context.
- qa-026: đoạn Ghềnh Cốc được đặt trong mục Ngô Quyền, trong khi context 1 nói về Trần Quốc Tuấn; cần giữ cờ ghép sai nhân vật/trận đánh.
- qa-041, 066, 092: mất mức độ chắc chắn hoặc đẩy chủ trương thành đã thực hiện.
- qa-069: từ hơn 2,5 triệu đến 10 triệu không suy ra tăng **hơn** 7,5 triệu. Nếu số liệu làm tròn, nên viết “khoảng 7,5 triệu”, không khẳng định một bất đẳng thức chính xác.
- qa-071: context 5 có phép lưỡng thuế nhưng không xác lập nó thuộc giai đoạn trước khởi nghĩa; sự xuất hiện của tên chính sách trong context chưa đủ hỗ trợ phạm vi thời gian trong response.

Cần bổ sung ghi chú ở **qa-017**: response kết luận Đại La có “ưu thế lớn hơn”, trong khi hai đoạn mô tả riêng chưa đủ chứng minh phép so sánh hơn Cổ Loa. **qa-100** chuyển hai tác động chiến lược thành “hai hướng chủ yếu” Bắc/ven biển và Đông; câu hỏi cũng dùng “hai hướng”, dễ dẫn đến cách hiểu địa lí. Nên sửa câu hỏi thành “hai phương diện/tác động nào” nếu đó là ý gold muốn đo. Hai điểm này là vấn đề diễn giải cần lưu ý, không tự động hạ recall khi gold vẫn được phủ.

Không xem danh sách trên là kiểm kê đầy đủ mọi lỗi Faithfulness trong 100 response. Hai file claims chỉ tách gold nên còn thiếu hệ thống đánh giá các thông tin thêm.

CSV cũng chưa tương đương hoàn toàn Markdown về mục đích soát lỗi: CSV không có cột lỗi nội dung riêng, trong khi Markdown có bảy ghi chú ở cấp câu. Có **22 dòng** trộn mệnh đề với lời giải thích chấm sau dấu “—”; vì vậy `menh_de_gold` chưa phải trường gold sạch để tái sử dụng làm đầu vào judge.

## 8. Cách chuẩn hóa cho lần chấm tiếp theo

1. Đặt tên rõ `gold_coverage_manual` cho thang 0/0,5/1; ghi riêng phiên bản FC RAGAS recall. Không gọi đây là điểm chính xác lịch sử tổng thể.
2. Chốt danh sách claim từ gold trước khi xem response hoặc điểm RAGAS. Mỗi claim có đủ chủ thể, hành động, đối tượng và thuộc tính cần thiết; bỏ trùng lặp. Đưa lời cảnh báo chống diễn giải sai vào tiêu chí riêng nếu chúng không phải dữ kiện cần nhắc lại.
3. Nếu giữ điểm một phần, quy định thuộc tính nào thiếu được 0,5, thuộc tính nào làm sai ý chính phải 0. Tốt hơn là tách các đơn vị kiểm chứng đủ nhỏ rồi chấm nhị phân trên danh sách cố định.
4. Tách `claim_text`, `response_evidence`, `missing_detail`, `verdict_reason`, `content_issue`; lưu thêm vị trí trong gold/context. Không để lí do chấm trong nội dung mệnh đề gold.
5. Chấm riêng mức đáp ứng câu hỏi. Các câu qa-001, 013, 030, 033, 037, 075, 079, 084, 085, 096 cho thấy gold có chi tiết vượt câu hỏi trực tiếp; thiếu các chi tiết ấy không đồng nghĩa trả lời sai trọng tâm.
6. Với Faithfulness, tách claim từ **toàn bộ response**, bao gồm kết luận, số liệu suy ra và thông tin thêm; đối chiếu retrieved_contexts. Không lấy 473 gold claim làm mẫu số Faithfulness.
7. Lưu raw claims, từng verdict/reason, model và phiên bản prompt cho lần chạy tiếp theo. Khi kiểm tra độ ổn định, chấm lặp trên cùng đầu vào/cấu hình, và đánh giá mù điểm RAGAS trước khi đối chiếu. Ưu tiên điều tra trace của qa-081 và qa-099.

**Mức sử dụng hiện tại:** dùng hai file làm bản rà nội dung có giải thích được; chưa dùng như bộ nhãn chuẩn để tuyên bố judge công bằng, ổn định hoặc tính sai số chính xác của RAGAS. Những lỗi cộng điểm đã được loại trừ; phần cần sửa là đơn vị chấm, quy tắc một phần và một số nhận định cụ thể nêu trên.
