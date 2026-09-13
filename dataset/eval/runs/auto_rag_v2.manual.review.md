# Rà soát auto_rag_v2.manual.csv

Đối chiếu ngày 2026-09-08. Không thay đổi điểm hoặc dữ liệu chạy.

## Phạm vi và cách hiểu điểm

- Đã đọc question, gold_answer và response của toàn bộ 100 ID, đối chiếu ghi chú/điểm manual; kiểm tra các đoạn retrieved_contexts liên quan tới những điểm nghi vấn bên dưới. Đây không phải bản chấm Faithfulness từng mệnh đề cho toàn bộ 100 câu.
- Gold lấy từ `../retrieval_qa_v2.json`; response/context lấy từ `auto_rag_v2.json`. Cả 100 câu hỏi và ID khớp giữa hai file.
- Script `apps/agent-service/scripts/run_ragas_eval.py` cấu hình FC ở mode recall. Cần phân biệt: độ phủ gold, tính được context hỗ trợ (Faithfulness), và độ liên quan tới câu hỏi (AR).
- Prompt tách claim của dự án yêu cầu giữ thời điểm, địa điểm, quan hệ, phủ định và mức độ chắc chắn. Nếu manual áp dụng tiêu chí này thì không được bỏ qua các thuộc tính đó tùy từng câu.
- Chưa có danh sách claim và quy tắc tính điểm manual đi kèm CSV. Vì vậy có thể xác định thiếu/sai nội dung, nhưng chưa đủ cơ sở chứng nhận chính xác từng điểm như 0,83 hay 0,93.

## Các đánh giá/ghi chú cần sửa hoặc bổ sung rõ ràng

| ID | Hiện tại | Đối chiếu và đề nghị |
|---|---|---|
| qa-041 | FC 1,00; có cờ mất sắc thái | Context 1 viết **“Có lẽ”** nơi cư trú hiếm quặng đồng. Gold còn nói rõ đây là phỏng đoán. Response khẳng định nguyên nhân như kết luận. Ghi cờ là đúng nhưng để FC 1,00 không nhất quán với yêu cầu giữ mức độ chắc chắn. Cần đánh dấu claim về nguyên nhân chưa bảo toàn sắc thái và ghi lỗi Faithfulness. |
| qa-016 | FC 1,00; không ghi chú | Gold và context 1 có **tháng 1-1285**, response chỉ nói **đầu năm 1285**. Trả lời đúng câu hỏi, nhưng chưa phủ chính xác mốc tháng trong gold. Nếu đã trừ các chi tiết phụ ở qa-030/033/075 thì phải áp dụng cùng nguyên tắc ở đây. |
| qa-017 | FC 1,00; không ghi chú | Gold và context 1 nêu lợi thế Đại La **tránh cảnh ngập lụt**; response có “cao và thoáng” nhưng không nêu kết quả tránh ngập. Đây là thiếu thuộc tính khi chấm recall gold chặt. Ngoài ra, câu kết nói Đại La có **“ưu thế lớn hơn”** dễ tạo so sánh hơn Cổ Loa mà hai đoạn nguồn mô tả riêng chưa chứng minh. |
| qa-035 | FC 1,00; không ghi chú | Gold và context 2 ghi **thuyền lớn đi biển có lầu**; response chỉ ghi **thuyền chiến có lầu**, thiếu thuộc tính lớn/đi biển. Tên “Tải lương cổ lâu” được nêu đúng, nhưng không tự thay thế các thuộc tính bị bỏ. “Súng lớn, nhỏ” được context 1 hỗ trợ, không nên coi là bịa. |
| qa-045 | FC 0,83; ghi thiếu quân thứ trung tâm do Phan Đình Phùng chỉ huy | Ghi chú đúng nhưng chưa đủ: response còn không nêu rõ **liên lạc giữa đại bản doanh và các quân thứ để bảo đảm chỉ huy thống nhất**. Cách kết luận Hương Khê phân tán, Ba Đình thống nhất làm mờ chính phần chỉ huy chung mà câu hỏi yêu cầu. Cần bổ sung thiếu sót này và xét lại điểm bằng claim cụ thể. Đoạn nguồn gold `tap2_clean-000078` chứa đầy đủ cơ chế này không xuất hiện nguyên đoạn trong retrieved_contexts của câu. |
| qa-053 | FC 0,88; ghi thiếu dân quyền và hát | Còn thiếu mục tiêu **tự chủ**, không thể mặc nhiên coi “lòng yêu nước/tự hào dân tộc” đồng nghĩa với mục tiêu này. Response tập trung mô hình Đông Kinh nghĩa thục. Nguồn gold `tap2_clean-000155` nêu trực tiếp “dân quyền, tự chủ” và môn hát; các đoạn retrieved liên quan đang đọc không cung cấp những ý này. Bổ sung ghi chú và kiểm tra độ phủ retrieval. |
| qa-009 | FC 0,56; liệt kê một số ý thiếu | Ghi chú chưa liệt kê hết: ngoài phá căn cứ, cam kết không can thiệp và hai chính quyền/hai quân đội/ba lực lượng, còn có **rút quân các nước thân Mĩ** và **hai vùng kiểm soát**. Response có ý giải phóng Sài Gòn, nhưng không gọi đích danh sự toàn thắng của **Chiến dịch Hồ Chí Minh** như gold. Không thể xác nhận 0,56 nếu chưa chốt cách tách/gộp các ý này. |
| qa-091 | FC 0,60; ghi thiếu trầm tích đỏ và xương động vật Cánh tân | Hai thiếu sót đã ghi là có thật. Nếu dùng tiêu chí bao phủ mọi địa điểm như prompt hiện tại thì response còn không nêu **Lạng Sơn** trong gold/context 1. Cần áp dụng quy tắc chi tiết địa điểm nhất quán. |

Các thiếu sót nhỏ hơn cũng đáng rà lại nếu chọn recall chặt: **qa-025** thay chủ thể “tầng lớp quý tộc bản địa” bằng “người Việt”, làm mất tính cụ thể của nhận định về năng lực quản lí; **qa-050** không nói rõ quân Pháp buộc phải rút khỏi Việt Bắc năm 1947 dù có trong gold và context 6; **qa-085** không nêu chức danh “Tổng Bí thư” của Trường Chinh. Đây không phải các câu trả lời sai toàn bộ; chúng cho thấy cách cho điểm chi tiết chưa nhất quán.

## Lỗi nội dung chưa được bảng manual thể hiện đầy đủ

Các lỗi thêm thông tin không nên tự động trừ FC-recall nếu response vẫn bao phủ gold. Chúng cần ghi nhận ở Faithfulness/chất lượng câu trả lời; AR cần rubric riêng.

| ID | Bằng chứng | Nhận xét |
|---|---|---|
| qa-026 | Trong phần Ngô Quyền, response đưa **Ghềnh Cốc** vào ví dụ khai thác địa hình. Context 1 nói rõ người chú ý và khai thác Ghềnh Cốc là **Trần Quốc Tuấn**; context 3 mới là trận Ngô Quyền năm 938. | Ghép bằng chứng khác nhân vật/trận đánh vào phần Ngô Quyền. FC-recall có thể vẫn cao vì các ý gold đều có, nhưng không thể coi chất lượng nội dung hoàn toàn không có lỗi. |
| qa-069 | Response viết từ **hơn 2,5 triệu** lên **10 triệu** là **“tăng thêm hơn 7,5 triệu”**. | Suy luận số học không đúng: nếu coi 10 triệu là mốc chính xác thì phần tăng nhỏ hơn 7,5 triệu; nếu số liệu làm tròn thì chỉ nên nói tăng khoảng 7,5 triệu. Đây là lỗi mới ngoài thiếu lớp dự bị đã ghi. |
| qa-092 | Đầu response giữ **“có lẽ”**, nhưng đoạn kết đổi thành **“công dụng chủ yếu là chặt, cắt”**. Context 2 và gold trình bày công dụng dưới dạng phỏng đoán. | Cần ghi mất sắc thái ở phần kết; không nói toàn bộ response đã bỏ phỏng đoán vì phần đầu vẫn giữ đúng. Nhận xét công cụ Ngườm “phong phú và chuyên biệt hơn” cũng cần thận trọng vì nguồn chủ yếu mô tả khác biệt hình dạng/công dụng. |
| qa-071 | Câu hỏi giới hạn trước khởi nghĩa Mai Thúc Loan; response đưa cả **phép lưỡng thuế** vào nguyên nhân. Context 5 chỉ nói chính sách nhà Đường nói chung, không xác lập nó thuộc giai đoạn trước cuộc khởi nghĩa. | Context có tên chính sách không đủ chứng minh mốc thời gian mà response gán cho nó. Cần ghi lỗi/điểm nghi vấn về phạm vi thời gian; bản review này không dùng nguồn ngoài để xác định niên đại của phép lưỡng thuế. |
| qa-012 | Response vừa nói kháng chiến kết thúc khoảng **208 TCN**, sau đó Âu Lạc ra đời, vừa nói **đầu thế kỉ III TCN**. Context 1 tự có cả “đầu thế kỉ III” và khoảng tồn tại **208–179 TCN**. | Nguồn đầu vào có mâu thuẫn niên đại; response lặp lại mâu thuẫn. Không nên quy đây đơn thuần là bịa ngoài context. Cần đánh dấu chất lượng nguồn và khả năng xử lí mâu thuẫn của hệ. |
| qa-066 | Context nói khuyến khích thương nhân, **đề nghị** nhà Thanh cho buôn bán. Response khái quát thành **“đã được triển khai”**, **“chính sách thực hành”**, trực tiếp tổ chức hoạt động tại các khu vực đó. | Nên giảm mức khẳng định về việc đề nghị đã được thực thi. Ý khác biệt giữa chủ trương của chính quyền và các kiến nghị cải cách vẫn được trả lời đúng. |
| qa-100 | Gold nói hai tác động: ngăn nguồn tăng viện từ miền Trung và mở cửa ngõ phía đông. Response gọi thành **“hai hướng chủ yếu”** Bắc/ven biển và Đông. | Phần thân vẫn phủ gold, nhưng kết luận chuyển từ hai tác động chiến lược sang hai hướng địa lí; nên ghi chú diễn giải mạnh hơn nguồn thay vì tự động hạ FC-recall. |

## Những điểm đang đánh giá đúng hoặc không nên sửa theo cảm tính

- **qa-083:** Xác định bỏ hẳn vế Đại hội V Quốc tế Cộng sản 1924 là đúng. Retrieved context **6** có đầy đủ ngày 17-6 đến 8-7-1924, báo cáo dân tộc/thuộc địa và đóng góp phát triển luận điểm Lênin. Do đó bằng chứng đã được truy xuất; lỗi thể hiện rõ ở khâu tổng hợp response. Điểm thấp có cơ sở, nhưng con số FC 0,43 và AR 0,40 vẫn cần rubric/claim để tái lập.
- **qa-002, 004, 012, 013, 030, 033, 034, 037, 039, 048, 069, 075, 079, 084, 096:** Các ý thiếu đang được ghi nhận là có cơ sở khi so với toàn bộ gold. Bổ sung ở những câu đã nêu phía trên không phủ nhận ghi chú cũ.
- **qa-030:** 0,80 có thể giải thích minh bạch bằng bốn trong năm mốc sự kiện của gold. Nhưng response đã trả lời đủ bốn mốc mà câu hỏi yêu cầu. Không nên gọi đây là câu trả lời sai lịch sử.
- **qa-013, 033, 037, 075, 079:** Tên gọi phụ, người đề nghị, nơi tuyển quân, quan hệ cha con, nguồn tiền/ban phụ trách có thể nằm ngoài yêu cầu trực tiếp của câu hỏi. Trừ FC-recall gold vẫn có lý; dùng cùng mức trừ cho chất lượng đáp ứng câu hỏi thì không nhất thiết phù hợp.
- **qa-068:** Response không quy toàn bộ đóng góp cho Tuần lễ vàng, nên không cần lặp nguyên câu cảnh báo trong gold để được coi là hiểu đúng phạm vi.
- **qa-086:** Response nói rõ điều hiệp định quy định và dùng “sẽ”; không khẳng định lịch rút quân đã diễn ra đầy đủ. Không nên trừ chỉ vì không lặp nguyên câu cảnh báo của gold.
- **qa-081, 089, 099:** FC tự động thấp không tự chứng minh manual sai. Các nội dung cốt lõi của gold được response trả lời; riêng số liệu phụ trong qa-089 có trong context 3, không nên gọi là bịa khi đang đánh giá theo tài liệu cung cấp.

## AR_manual và khả năng so sánh với RAGAS

99/100 câu có AR_manual = 1,00; riêng qa-083 = 0,40. Điều này có thể chấp nhận nếu AR_manual chỉ đo câu trả lời có hướng vào câu hỏi hay không, nhưng không có rubric để biết 0,40 được tính thế nào.

RAGAS answer_relevancy sinh ngược câu hỏi rồi dùng embedding/cosine. Điểm manual là đánh giá của người/LLM đọc nội dung, không phải phép tính đó. Vì thế `AR_chenh` chỉ là hiệu số của hai thang đo khác cách xây dựng; chưa thể diễn giải thành mức RAGAS “chấm sai”. Nếu manual còn đo đầy đủ và súc tích thì cần xét lại ít nhất qa-045 (thiếu vế chỉ huy chung) và qa-023 (chen thêm giai đoạn sau năm 43, dù response có tự phân biệt nó với trước khởi nghĩa).

## Kiểm tra số liệu CSV

- 100 dòng; FC_manual trung bình **0,9606**, AR_manual trung bình **0,9940**; **80** dòng FC_manual = 1,00.
- Các cột chênh lệch FC và AR đều tính đúng theo số đã ghi trong CSV.
- AR_ragas khớp `auto_rag_v2.ragas.csv` sau làm tròn.
- FC_ragas có **23 dòng khác** file `auto_rag_v2.ragas.csv` gốc, nhưng **khớp toàn bộ** khi ghép bản gốc với `auto_rag_v2.factual_correctness.ids32.csv`, ưu tiên bản ids32. Đây là khác phiên bản kết quả, không phải lỗi sao chép điểm.
- Nên ghi rõ nguồn ghép này khi dùng bảng manual trong báo cáo.

## Đề nghị xử lí

Giữ file manual gốc để đối chiếu. Trước khi sửa điểm, lập danh sách claim gold cho từng câu cần điều chỉnh, đánh dấu claim được phủ/thiếu/mất sắc thái, rồi tính FC_manual bằng một công thức thống nhất. Ghi riêng lỗi thêm thông tin không được context hỗ trợ và lỗi nguồn mâu thuẫn. Công bố rubric AR_manual trước khi dùng chênh lệch với AR_ragas để kết luận về chất lượng bộ chấm.

Không coi đây là bản xác nhận 100 câu đã hoàn toàn đúng Faithfulness; các kết luận phía trên có phạm vi bằng chứng được nêu cụ thể.
