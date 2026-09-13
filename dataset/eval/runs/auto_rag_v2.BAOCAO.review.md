# Rà soát auto_rag_v2.BAOCAO.md

Ngày 2026-09-08. Không sửa báo cáo gốc. Đã đọc toàn bộ báo cáo, tính lại các bảng từ CSV, đối chiếu cấu trúc claim, kết quả gốc/chấm lại, mã RAGAS 0.4.3 đang cài và các prompt của dự án.

**Kết luận: chưa đúng hết; cần sửa các kết luận chính trước khi dùng làm báo cáo chính thức.** Nhiều phép cộng đúng, nhưng có lỗi đếm, trộn phiên bản điểm và suy luận nguyên nhân vượt bằng chứng. Các mức tin cậy “Cao/Trung bình” hiện là nhận định của người viết, chưa được hiệu chuẩn bằng bộ nhãn độc lập.

## 1. Context recall 0,9935 và 469/473 chưa hợp lệ

Mục 3.3 liệt kê “bốn mệnh đề” nhưng đối chiếu với claims.csv là **năm dòng**:

| ID | STT claim | Nội dung |
|---|---:|---|
| qa-045 | 6 | Quân thứ trung tâm, đại bản doanh, Phan Đình Phùng chỉ huy |
| qa-045 | 7 | Quân thứ địa phương liên lạc đại bản doanh, chỉ huy thống nhất |
| qa-053 | 4 | Mục tiêu giáo dục, có dân quyền và tự chủ |
| qa-053 | 5 | Danh sách nội dung học, có môn hát |
| qa-042 | 5 | Lời lưu ý về việc không suy ra hoạt động vắng mặt |

Hai dòng qa-053 bị trình bày thành một hàng trong bảng báo cáo. Số hiện tại khớp chính xác với cách chỉ tính một dòng thiếu ở qa-053:

`1 - (2/7 + 1/6 + 1/5)/100 = 0,99347619`, làm tròn thành 0,9935.

Nếu cả năm claim trên bị coi là không được hỗ trợ đầy đủ và tất cả claim khác được hỗ trợ, chấm nhị phân sẽ cho **468/473 = 0,98942918** và macro **0,99180952**. Đây là phép tính có điều kiện để chỉ ra lỗi mẫu số, **không phải điểm context recall mới đã được xác nhận**. Hai claim qa-053 có phần được hỗ trợ; muốn tính điểm một phần phải ghi verdict/rubric cụ thể. Lời lưu ý qa-042 cũng cần quyết định có thuộc mẫu số không.

Không thấy bảng verdict context recall từng claim hay mã tính các ngưỡng 409/61/3 trong các file/script đã kiểm tra. Độ phủ từ vựng ≥0,85 không chứng minh “gần chắc chắn” được ngữ cảnh hỗ trợ: vẫn có thể sai chủ thể, quan hệ, thời gian hoặc phủ định. Vì vậy chưa đủ căn cứ gắn độ tin cậy “Cao”.

**Đề nghị:** tạm ghi context recall manual là “ước tính sơ bộ, chưa xác nhận”; bổ sung bảng `id, claim_id, verdict, evidence, reason` trước khi chốt điểm.

## 2. Bảng FC mục 5.1 trộn điểm bản vá với bản chính thức

| ID | Bản gốc mà mục 2 chọn | Bảng 5.1 hiện ghi / bản ids32 |
|---|---:|---:|
| qa-081 | 0,00 | 0,00 |
| qa-089 | **0,50** | 0,25 |
| qa-099 | **0,25** | 0,33 |
| qa-086 | **0,60** | 0,50 |

Các trường hợp này vẫn đáng điều tra theo nội dung. Tuy nhiên phải dùng đúng phiên bản hoặc thêm hai cột “gốc/chấm lại”. Đặc biệt, phụ lục claims.md cũng đang hiển thị FC bản ghép; cần chú thích để người đọc không nhầm với số chính thức.

## 3. Kết luận về retrieval và lỗi hệ thống quá tuyệt đối

Mục 1 viết “các thiếu sót ... nằm ở khâu tổng hợp, không phải khâu tra cứu”. Điều này không phù hợp với qa-045 và qa-053 mà báo cáo tự xác định thiếu bằng chứng cần thiết trong retrieved contexts. Đó là thiếu sót retrieval so với gold, dù response còn có vấn đề tổng hợp.

qa-083 là ví dụ rõ về tổng hợp: retrieved context 6 có nội dung Đại hội V năm 1924 nhưng response bỏ hẳn. Không thể từ trường hợp này quy toàn bộ lỗi cho tổng hợp.

**Câu thay thế:** “Retrieval có độ phủ cao theo RAGAS, nhưng vẫn thiếu bằng chứng ở một số câu như qa-045/053. Khâu tổng hợp cũng có lỗi độc lập, tiêu biểu qa-083 bỏ một vế đã có trong ngữ cảnh.”

Mục 3.3 nói context recall là metric “duy nhất” đồng thuận vị trí lỗi cũng chưa được chứng minh. RAGAS context recall dưới 1 ở **10 ID**, không chỉ ba ID nêu trong báo cáo: qa-009, 042, 045, 053, 073, 076, 083, 086, 088, 100. FC cũng cùng nhận điểm thấp với manual ở các câu như qa-083 (gốc 0,37; manual 0,43). Chỉ nên nói có một số trường hợp đồng thuận; chưa có phân tích đủ để gọi là hiệu chỉnh tốt hay duy nhất.

## 4. Faithfulness 0,9942: phép cộng đúng, ý nghĩa chưa được chứng minh đầy đủ

- CSV có tổng `tong_cau = 653`, tổng `cau_bam_ngu_canh = 649`; macro tính từ phân số là **0,99416450**, làm tròn **0,9942**. Trung bình cột đã làm tròn là 0,99417. Micro 649/653 làm tròn **0,9939**. Các số này tính đúng.
- Nhưng **649 là quy điểm**, vì qa-041/066/071/092 bị trừ 0,5 mỗi câu, qa-026/069 bị trừ 1. Không được gọi 649 là số nguyên các câu bám nguồn đã xác nhận. “Sáu vi phạm” nhưng tổng mất bốn điểm không mâu thuẫn nếu công bố rõ rubric này.
- Phương pháp dò tự động dùng 648 câu, bảng cuối dùng 653: chưa giải thích quy tắc phân đoạn và năm đơn vị chênh lệch.
- faith_manual.csv chỉ có **100 dòng tổng hợp**, không chứa danh sách 653 câu/claim cùng đoạn bằng chứng tương ứng. Vì vậy chưa tái lập được tử số và mẫu số bằng việc kiểm tra từng đơn vị.
- Chưa định nghĩa vì sao lỗi sai thời gian qa-071 chỉ trừ 0,5 trong khi lỗi sai nhân vật qa-026 trừ 1. Đây là thang điểm một phần theo câu, khác phép chấm hỗ trợ claim nhị phân.
- Từ vựng và số xuất hiện trong context không đủ bảo đảm quan hệ đúng. Đọc tay giúp phát hiện thêm, nhưng chưa chứng minh tất cả các đơn vị còn lại đều được hỗ trợ. Các review trước còn nêu điểm nghi vấn ở qa-017 và qa-100; chưa thấy báo cáo giải quyết các điểm này trước khi giữ 1 cho chúng.

**Đề nghị:** đổi nhãn thành “ước tính bám nguồn theo câu, rubric có điểm một phần”; đổi “Bám ngữ cảnh 649” thành “Tổng điểm bám ngữ cảnh 649/653”; không sử dụng con số này để chứng minh RAGAS Faithfulness chấm thấp có hệ thống.

## 5. Phân tích mã nguồn: có phần đúng, nhưng chưa chứng minh nguyên nhân điểm thấp

Đã xác nhận `venv/Lib/site-packages/ragas-0.4.3.dist-info/METADATA` là 0.4.3; đọc trực tiếp `_factual_correctness.py` và `_faithfulness.py`.

**Đúng:** NLI few-shot hiện có 4 verdict 0 và 1 verdict 1; upstream đang cài cũng có tỉ lệ ấy. Công thức FC hiện tại đúng như báo cáo mô tả: TP đếm claim response được gold hỗ trợ, FN đếm claim gold không được response hỗ trợ. Hai phía có thể có cách tách khác nhau.

**Chưa chứng minh:** tỉ lệ few-shot là nguyên nhân điểm thấp; lỗi riêng với tiếng Việt; công thức làm điểm giảm có hệ thống. Công thức có thể làm điểm tăng hoặc giảm tùy số claim và verdict, không chỉ giảm. Muốn khẳng định nguyên nhân cần trace và thí nghiệm kiểm soát.

Phần số liệu chấm lại FC tính đúng: chênh lệch tuyệt đối trung bình **0,0928125**, lớn nhất **0,40**; 14/32 lệch ≥0,10; 12 tăng, 11 giảm, 9 không đổi.

Nhưng điểm 0,29/0,71/0,86 **không chứng minh mẫu số thay đổi**. Chúng có thể cùng là 2/7, 5/7, 6/7 với mẫu số không đổi; kết quả còn bị làm tròn. Cả verdict thay đổi và claim thay đổi đều có thể làm điểm đổi. Cần đổi tiêu đề “Bước tách mệnh đề không ổn định” thành “Điểm khác nhau giữa hai lần chấm, chưa xác định nguyên nhân”.

“qa-081 ra 0 hai lần — không phải nhiễu ngẫu nhiên” cũng quá mạnh. Hai kết quả giống nhau chưa loại trừ ngẫu nhiên và chưa xác nhận hai lần chạy độc lập/cùng cấu hình. Nên viết “bất thường lặp lại, ưu tiên điều tra”. Giả thuyết claim rỗng chỉ là một khả năng; verdict tất cả 0 cũng có thể cho điểm 0.

## 6. Khuyến nghị đổi metric cần sửa

Đổi recall sang **precision** thay đổi câu hỏi đánh giá: precision đo claim của response được reference hỗ trợ, không đo phần gold bị bỏ sót. Một câu chỉ trả lời một phần như qa-083 vẫn có thể đạt precision cao. Không nên dùng nó thay thế độ phủ.

Đổi sang **F1** cũng không tự khắc phục việc TP/FN đếm trên hai tập claim trong mã đang cài: nhánh F1 vẫn nhận cùng TP, FP, FN.

**Đề nghị:** nếu cần đo độ phủ gold, dùng một danh sách gold claim cố định và tính `số claim gold được response hỗ trợ / tổng gold claim`; giữ precision hoặc F1 làm metric bổ sung với tên và giới hạn rõ. Nếu thử cân bằng few-shot thì gọi đó là thử nghiệm, chạy cùng tập/cấu hình đối chứng; không coi tỉ lệ 50/50 là giải pháp đã chứng minh.

## 7. Các nhận định về tập chấm lại chưa chính xác

- ids32 **không phải đúng 32 câu thấp nhất** theo FC bản gốc. Theo sắp xếp điểm gốc, tập chọn có thêm qa-011/031/034, trong khi qa-053/083/094 thuộc 32 thấp nhất lại không được chọn.
- ids20 **không phải đúng 20 câu thấp nhất**, như chính hai trung bình khác nhau trong báo cáo đã cho thấy. Trung bình nhóm được chọn trước khi chấm lại **0,60325968**, trung bình 20 thấp nhất **0,58837873**: hai phép tính đúng.
- Hồi quy về trung bình là **nguy cơ/cách giải thích khả dĩ**, chưa phải nguyên nhân đã xác định khi không có manifest cấu hình.
- Chọn bản gốc đủ 100 câu làm baseline là hợp lí. Không cần gọi các bản chấm lại “không dùng” tuyệt đối: chúng vẫn dùng để điều tra ca bất thường, nhưng không đại diện cho một thí nghiệm đồng nhất toàn bộ 100 câu hay chứng minh độ ổn định.
- CSV gốc có đủ 100 ID và 5 metric, nhưng tự nó chưa chứng minh “một lần chạy” và “prompt đồng nhất”. Với giới hạn thiếu manifest mà báo cáo thừa nhận, nên gọi là “bản gốc đủ 100 câu được chọn làm baseline”.

## 8. Các lỗi diễn đạt và phạm vi nhỏ hơn

| Vị trí | Cần sửa |
|---|---|
| Mục 3.2 | Có 98 câu điểm 1, qa-045 trả lời một phần, qa-083 thiếu một vế. “99/100 đúng vào câu hỏi” không được suy ra trực tiếp từ rubric hoàn thành vế; qa-083 vẫn đúng vào chủ đề nhưng thiếu. Nên ghi đúng ba nhóm này. |
| Mục 4.1 | Tiêu đề “7 câu” nhưng bảng có **8 ID**: 026, 069, 083, 041, 092, 066, 071, 012. Nếu tách qa-012 thành lỗi nguồn thì phải nêu rõ “7 câu lỗi đáp án và 1 câu mâu thuẫn nguồn”. |
| Mục 4.3 | “Mọi metric ... đều trừ điểm oan” là quá rộng. Thiếu chi tiết gold vẫn bị trừ đúng nếu đo recall toàn gold; vấn đề là gold rộng hơn yêu cầu và cách dùng metric để kết luận chất lượng trả lời. |
| Mục 4.3, khuyến nghị dataset | Không nên bỏ mọi lời lưu ý: mức phỏng đoán ở qa-041/092 là thuộc tính có nghĩa của nguồn, cần giữ trong claim hoặc tiêu chí riêng. Lưu ý chống hiểu sai ở qa-068 khác về vai trò. |
| Mục 7.2 | qa-053 không phải thiếu “nhiều môn học”: claim danh sách môn học hiện ghi thiếu **môn hát**; claim khác thiếu **dân quyền/tự chủ**. Mỗi nhóm mất 0,5/6 ≈8,33 điểm phần trăm, cả câu mất 1/6≈16,67 điểm phần trăm. |
| Mục 8 | Hai file review là hai lượt rà soát; chưa có căn cứ về người chấm độc lập/đánh giá mù. Không nên dùng chữ “độc lập” như bằng chứng đồng thuận giữa các giám khảo. |

Đúng về số lượng **5 câu chứa định danh chunk**: qa-026, 050, 076, 089, 090. Đây là hiện tượng đã kiểm tra được. Gọi là lỗi prompt duy nhất vẫn cần thận trọng vì cách render/ẩn citation ở đầu ra cũng có thể liên quan.

## 9. Những phần có thể giữ

- Năm trung bình RAGAS baseline: **0,8658 / 0,9672 / 0,8268 / 0,8280 / 0,8071** đều khớp CSV gốc.
- Thống kê FC manual **473 claim; 431/20/22; 441 điểm; macro 0,9421; micro 0,9323; 69 câu tối đa** đúng với nhãn đang lưu. Chưa đồng nghĩa nhãn đã được xác nhận hết; các vấn đề qa-016/045/083 và rubric trong claims.review vẫn còn.
- Phân tích độ nhạy **0,9230 / 0,9421 / 0,9612** tính đúng khi chỉ đổi giá trị 20 nhãn một phần. Đây là ba kịch bản, không phải khoảng tin cậy; chưa có bằng chứng đó là “nguồn sai số lớn nhất” vì chưa định lượng các nguồn sai lệch khác.
- AR **190,5/192; macro 0,9933; micro 0,9922** tính đúng theo bảng. Việc tách biệt nó khỏi RAGAS embedding relevancy là đúng; nên gọi là độ hoàn thành các vế câu hỏi.
- Không dùng proxy context precision như nhãn thủ công chuẩn là hợp lí.

**Cách viết kết luận an toàn hơn:** “Bản RAGAS gốc cho thấy retrieval đạt điểm cao. Rà soát nội dung phát hiện một số lỗi tổng hợp, một số thiếu sót retrieval và một số điểm judge bất thường. Các điểm manual phản ánh rubric riêng; context recall manual và Faithfulness manual cần bảng bằng chứng từng đơn vị trước khi xác nhận. Chưa đủ dữ liệu để kết luận RAGAS chấm thấp có hệ thống trên tiếng Việt hoặc xác định nguyên nhân của từng điểm bất thường.”
