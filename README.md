# Chức Năng Dự Án Agentic RAG Lịch Sử Việt Nam

Tài liệu này dùng để ghi lại các nhóm chức năng của dự án. Nội dung chỉ mô tả chức năng, không chứa code triển khai.

## 1. Tổng Quan Sản Phẩm

Dự án là một hệ thống hỏi đáp lịch sử dành cho giáo viên. Người dùng có thể đặt câu hỏi lịch sử bằng tiếng Việt, hệ thống trả lời dựa trên dữ liệu đã được quản lý trong kho tri thức. Với các câu trả lời có liên quan đến thời gian và địa điểm, hệ thống có thể hiển thị sự kiện lên bản đồ và timeline.

Mục tiêu chính:

- Hỏi đáp lịch sử có căn cứ từ tài liệu.
- Hỗ trợ giáo viên khai thác kiến thức theo hướng trực quan.
- Kết hợp RAG truyền thống, GraphRAG và hybrid retrieval.
- Hiển thị sự kiện lịch sử trên bản đồ Việt Nam.
- Liên kết bản đồ, timeline và dữ liệu sự kiện.
- Cho phép admin quản lý dữ liệu phục vụ RAG.

Frontend chốt dùng:

- React + TypeScript + Vite.

## 2. Nhóm Người Dùng

### Admin

Admin là người quản trị hệ thống và dữ liệu.

Chức năng dự kiến:

- Đăng nhập hệ thống.
- Quản lý tài liệu lịch sử.
- Thêm tài liệu vào kho tri thức.
- Xóa tài liệu khỏi kho tri thức.
- Xem danh sách tài liệu.
- Xem trạng thái xử lý tài liệu.
- Kích hoạt xử lý lại tài liệu nếu cần.
- Quản lý người dùng giáo viên trong tương lai.
- Xem chất lượng dữ liệu trong tương lai.

### Giáo Viên

Giáo viên là người dùng chính của hệ thống hỏi đáp.

Chức năng dự kiến:

- Đăng nhập hệ thống.
- Đặt câu hỏi lịch sử bằng tiếng Việt.
- Nhận câu trả lời có nguồn tham khảo.
- Xem citation hoặc nguồn tài liệu liên quan.
- Bấm hiển thị kết quả lên bản đồ nếu câu trả lời có dữ liệu địa điểm.
- Xem timeline các mốc sự kiện.
- Xem chi tiết sự kiện trên marker bản đồ.
- Xem chi tiết sự kiện trên timeline.
- Lưu phiên hỏi đáp trong tương lai.
- Tạo dàn ý bài giảng từ câu trả lời trong tương lai.

## 3. Chức Năng Xác Thực Và Phân Quyền

Chức năng chính:

- Đăng nhập.
- Đăng xuất.
- Xác định role người dùng.
- Phân quyền theo role admin và giáo viên.
- Chặn giáo viên truy cập chức năng quản trị.
- Cho phép admin sử dụng cả chức năng quản trị và hỏi đáp.

Phạm vi ban đầu:

- Chỉ cần hai role: admin và user.
- Chưa cần đăng ký tài khoản công khai.
- Chưa cần quên mật khẩu.

## 4. Chức Năng Quản Lý Tài Liệu

Đây là phần dành cho admin.

Chức năng chính:

- Xem danh sách tài liệu.
- Thêm tài liệu.
- Xóa tài liệu.
- Xem loại tài liệu.
- Xem trạng thái tài liệu.
- Xem thời gian tạo tài liệu.
- Xem số lượng chunk đã tạo trong tương lai.
- Xử lý lại tài liệu trong tương lai.

Loại dữ liệu dự kiến:

- PDF.
- DOCX.
- TXT.

Giai đoạn mock:

- Có thể dùng dữ liệu giả.
- Chưa cần upload file thật.
- Chưa cần xử lý embedding thật.

Giai đoạn thật:

- Tài liệu được đọc nội dung.
- Tài liệu được chia nhỏ thành các đoạn.
- Các đoạn được lưu vào database.
- Vector được lưu vào Qdrant.

## 5. Chức Năng Hỏi Đáp Lịch Sử

Đây là chức năng trung tâm của hệ thống.

Chức năng chính:

- Giáo viên nhập câu hỏi.
- Hệ thống phân tích câu hỏi.
- Hệ thống tìm dữ liệu liên quan.
- Hệ thống trả lời bằng tiếng Việt.
- Câu trả lời có nguồn tham khảo.
- Nếu câu hỏi mập mờ, hệ thống có thể hỏi lại.
- Nếu không đủ dữ liệu, hệ thống cần nói rõ là chưa đủ dữ liệu.

Ví dụ câu hỏi:

- Cuộc đời Chủ tịch Hồ Chí Minh có những mốc quan trọng nào?
- Diễn biến chính của chiến dịch Điện Biên Phủ là gì?
- Cách mạng tháng Tám diễn ra như thế nào?
- Những sự kiện nào dẫn đến sự ra đời của Đảng Cộng sản Việt Nam?

## 6. Chức Năng RAG Truyền Thống

RAG truyền thống tập trung vào tìm kiếm tài liệu dạng văn bản.

Chức năng chính:

- Tìm các đoạn tài liệu liên quan đến câu hỏi.
- Xếp hạng các đoạn tài liệu theo mức độ liên quan.
- Dùng các đoạn tài liệu làm căn cứ trả lời.
- Gắn nguồn tham khảo cho câu trả lời.

Phù hợp với câu hỏi:

- Hỏi diễn biến.
- Hỏi tiểu sử.
- Hỏi giải thích một sự kiện.
- Hỏi tóm tắt một giai đoạn lịch sử.

## 7. Chức Năng GraphRAG

GraphRAG tập trung vào quan hệ giữa các thực thể lịch sử.

Thực thể có thể gồm:

- Nhân vật.
- Sự kiện.
- Địa điểm.
- Tổ chức.
- Giai đoạn.
- Nguyên nhân.
- Hệ quả.

Chức năng chính:

- Tìm các nút liên quan đến câu hỏi.
- Mở rộng quan hệ giữa các nút.
- Tìm sự kiện trước và sau một sự kiện.
- Tìm nhân vật liên quan đến một sự kiện.
- Tìm nguyên nhân và hệ quả của một sự kiện.
- Hỗ trợ trả lời các câu hỏi có tính liên kết.

Phù hợp với câu hỏi:

- Sự kiện nào dẫn đến Cách mạng tháng Tám?
- Những nhân vật nào liên quan đến Hội nghị thành lập Đảng?
- Quan hệ giữa Nguyễn Ái Quốc và phong trào yêu nước đầu thế kỷ XX là gì?
- Một sự kiện ảnh hưởng đến các sự kiện nào sau đó?

## 8. Chức Năng Hybrid Retrieval

Hybrid retrieval kết hợp RAG truyền thống và GraphRAG.

Chức năng chính:

- Tìm bằng chứng từ tài liệu văn bản.
- Tìm quan hệ từ graph tri thức.
- Kết hợp hai loại bằng chứng.
- Trả lời vừa có nội dung văn bản, vừa có quan hệ sự kiện.
- Giảm rủi ro trả lời thiếu ngữ cảnh.

Phù hợp với câu hỏi:

- Câu hỏi vừa cần nguồn tài liệu, vừa cần quan hệ lịch sử.
- Câu hỏi cần giải thích nguyên nhân, diễn biến và hệ quả.
- Câu hỏi cần so sánh nhiều sự kiện hoặc nhiều nhân vật.

## 9. Chức Năng Agent

Agent là phần điều phối thông minh của hệ thống.

Chức năng chính:

- Nhận câu hỏi từ backend.
- Phân tích ý định câu hỏi.
- Quyết định dùng RAG truyền thống, GraphRAG hay hybrid.
- Hỏi lại nếu câu hỏi mập mờ.
- Gọi công cụ tìm kiếm dữ liệu.
- Tổng hợp bằng chứng.
- Tạo câu trả lời.
- Trích xuất sự kiện để phục vụ bản đồ và timeline.
- Trả kết quả chuẩn về backend.

Các loại quyết định của agent:

- Câu hỏi đủ rõ hay chưa.
- Nên dùng retrieval kiểu nào.
- Có cần sinh dữ liệu visualization không.
- Có đủ nguồn để trả lời không.

## 10. Chức Năng Bản Đồ

Bản đồ dùng để hiển thị các địa điểm liên quan đến sự kiện lịch sử.

Chức năng chính:

- Hiển thị bản đồ Việt Nam.
- Hiển thị marker tại tỉnh/thành liên quan.
- Marker chứa thông tin sự kiện.
- Click marker để xem chi tiết.
- Marker liên kết với timeline qua event_id.
- Marker được làm nổi bật khi người dùng chọn mốc timeline tương ứng.

Ví dụ:

- Nghệ An: nơi Chủ tịch Hồ Chí Minh sinh ra.
- Huế: nơi gắn với thời niên thiếu.
- TP.HCM: nơi có các mốc học tập, hoạt động hoặc tưởng niệm tùy dữ liệu.

## 11. Chức Năng Timeline

Timeline dùng để hiển thị các mốc sự kiện theo thời gian.

Chức năng chính:

- Hiển thị danh sách mốc thời gian.
- Mỗi mốc gắn với một sự kiện.
- Click timeline item để xem chi tiết.
- Timeline item liên kết với marker bản đồ qua event_id.
- Timeline item sáng lên khi marker tương ứng được chọn.
- Hỗ trợ sự kiện không rõ ngày chính xác trong tương lai.

## 12. Chức Năng Visualization Tổng Hợp

Visualization là lớp chuyển dữ liệu trả lời thành dữ liệu trực quan.

Chức năng chính:

- Trích xuất sự kiện từ câu trả lời hoặc bằng chứng.
- Tạo danh sách sự kiện.
- Tạo dữ liệu marker bản đồ.
- Tạo dữ liệu timeline.
- Đảm bảo map và timeline dùng chung event_id.

Nguyên tắc:

- Nếu user không bấm hiển thị bản đồ thì không cần render map/timeline.
- Nếu sự kiện thiếu địa điểm thì chỉ hiển thị trên timeline.
- Nếu sự kiện thiếu thời gian thì có thể chỉ hiển thị trên map.
- Nếu không đủ dữ liệu visualization thì không ép sinh marker.

## 13. Chức Năng Frontend

Các trang chính:

- Trang đăng nhập.
- Trang hỏi đáp.
- Trang admin quản lý tài liệu.

Trang hỏi đáp:

- Ô nhập câu hỏi.
- Khu vực hiển thị câu trả lời.
- Khu vực hiển thị nguồn tham khảo.
- Nút hiển thị trên bản đồ.
- Khu vực bản đồ.
- Khu vực timeline.

Trang admin:

- Danh sách tài liệu.
- Thêm tài liệu mock hoặc upload thật trong tương lai.
- Xóa tài liệu.
- Xem trạng thái tài liệu.

## 14. Chức Năng Backend

Backend là API chính cho frontend.

Chức năng chính:

- Xử lý đăng nhập.
- Quản lý người dùng.
- Quản lý tài liệu.
- Nhận câu hỏi từ frontend.
- Gọi agent-service.
- Trả câu trả lời về frontend.
- Trả dữ liệu visualization về frontend.
- Kiểm tra quyền truy cập.

Backend không trực tiếp là agent. Backend chỉ gọi agent-service qua agent client.

## 15. Chức Năng Agent-Service

Agent-service là service riêng xử lý logic agent.

Chức năng chính:

- Nhận yêu cầu hỏi đáp từ backend.
- Điều phối traditional RAG, GraphRAG và hybrid.
- Quản lý prompt.
- Gọi các tool cần thiết.
- Tạo câu trả lời cuối.
- Tạo dữ liệu sự kiện cho map/timeline.
- Trả kết quả có cấu trúc về backend.

## 16. Chức Năng Mock Giai Đoạn Đầu

Giai đoạn đầu có thể mock để dựng nhanh luồng chính.

Mock cần có:

- User admin mẫu.
- User thường (role `user`) mẫu.
- Danh sách tài liệu mẫu.
- Câu trả lời mẫu.
- Citation mẫu.
- Event mẫu.
- Marker bản đồ mẫu.
- Timeline item mẫu.

Mục tiêu mock:

- Frontend chạy được.
- Backend API có contract rõ.
- Agent-service trả dữ liệu đúng format.
- Map và timeline test được trước khi có RAG thật.

## 17. Chức Năng Quản Trị Nâng Cao

Đây là các chức năng admin nên có sau khi luồng hỏi đáp, tài liệu, map và timeline đã chạy ổn.

### Conversation Logs

Admin có thể quản lý lịch sử hội thoại giữa người dùng và hệ thống.

Chức năng dự kiến:

- Xem user đã hỏi gì.
- Xem hệ thống đã trả lời gì.
- Xem thời gian hỏi và thời gian trả lời.
- Xem người dùng nào đã đặt câu hỏi.
- Xem câu trả lời dùng nguồn tham khảo nào.
- Lọc log theo user, thời gian, chủ đề hoặc trạng thái lỗi.
- Tìm kiếm trong lịch sử hội thoại.
- Ẩn hoặc xóa log nhạy cảm nếu cần.
- Export log để phân tích hoặc phục vụ báo cáo.

### Cost Dashboard

Admin có thể theo dõi chi phí sử dụng hệ thống AI.

Chức năng dự kiến:

- Xem tổng chi phí theo ngày, tuần, tháng.
- Xem chi phí theo user.
- Xem chi phí theo loại tác vụ.
- Theo dõi token input và token output.
- Theo dõi chi phí embedding.
- Theo dõi chi phí gọi LLM để trả lời.
- Theo dõi chi phí gọi LLM để trích xuất sự kiện.
- Theo dõi chi phí GraphRAG hoặc hybrid nếu có.
- Cảnh báo khi chi phí vượt ngưỡng.
- Hiển thị các câu hỏi hoặc phiên hội thoại tốn nhiều chi phí nhất.

### User Và Quota Management

Admin có thể quản lý người dùng và giới hạn sử dụng.

Chức năng dự kiến:

- Tạo tài khoản giáo viên.
- Sửa thông tin tài khoản.
- Khóa hoặc mở khóa tài khoản.
- Đổi role người dùng.
- Đặt quota câu hỏi theo ngày hoặc theo tháng.
- Đặt quota chi phí theo user.
- Xem mức sử dụng của từng user.
- Cảnh báo user sắp vượt quota.
- Tạm dừng quyền hỏi đáp khi user vượt quota.

### Answer Quality Monitoring

Admin có thể theo dõi chất lượng câu trả lời của hệ thống.

Chức năng dự kiến:

- Xem danh sách câu hỏi không trả lời được.
- Xem danh sách câu trả lời thiếu nguồn.
- Xem câu trả lời có ít citation.
- Xem câu trả lời có độ tin cậy thấp.
- Xem các câu hỏi agent phải hỏi lại.
- Xem những câu hỏi retrieval không tìm được dữ liệu tốt.
- Xem các tài liệu thường được dùng làm nguồn.
- Xem các chủ đề hệ thống trả lời kém.
- Đánh dấu câu trả lời cần kiểm tra lại.

### Model Và Agent Configuration

Admin có thể quản lý model và cấu hình hành vi của agent.

Chức năng dự kiến:

- Chọn model trả lời chính.
- Chọn model embedding.
- Cấu hình temperature.
- Cấu hình số lượng tài liệu retrieve.
- Bật hoặc tắt traditional RAG.
- Bật hoặc tắt GraphRAG.
- Bật hoặc tắt hybrid mode.
- Cấu hình chiến lược chọn RAG, GraphRAG hoặc hybrid.
- Quản lý phiên bản prompt.
- Rollback prompt về phiên bản cũ nếu prompt mới hoạt động kém.
- Cấu hình ngưỡng hỏi lại khi câu hỏi mập mờ.
- Cấu hình ngưỡng từ chối trả lời khi thiếu nguồn.

## 18. Chức Năng Để Sau

Các chức năng chưa cần làm ở MVP:

- Trace log chi tiết.
- Feedback nâng cao.
- Guardrails nâng cao.
- Graph visualization đầy đủ.
- Lesson mode.
- Compare mode.
- Dataset versioning.
- Rollback dữ liệu.
- Admin analytics.
- CI/CD tự động.
- Autoscaling cloud.
- Multi-tenant theo trường học.

## 19. Luồng Chính Cần Hoàn Thành Trước

Luồng user (người dùng thường):

- Đăng nhập.
- Nhập câu hỏi.
- Nhận câu trả lời.
- Xem nguồn.
- Bấm hiển thị bản đồ.
- Xem marker.
- Xem timeline.
- Click marker và timeline để thấy chúng liên kết với nhau.

Luồng admin:

- Đăng nhập.
- Xem danh sách tài liệu.
- Thêm tài liệu mock.
- Xóa tài liệu mock.
- Xem trạng thái tài liệu.
- Xem conversation logs ở mức cơ bản trong tương lai.
- Xem cost dashboard ở mức cơ bản trong tương lai.
- Quản lý quota user trong tương lai.
- Theo dõi chất lượng câu trả lời trong tương lai.
- Cấu hình model và agent trong tương lai.

Luồng agent:

- Nhận câu hỏi.
- Phân loại câu hỏi.
- Chọn traditional RAG, GraphRAG hoặc hybrid.
- Tạo câu trả lời.
- Tạo dữ liệu sự kiện.
- Trả kết quả về backend.

## 20. Ghi Chú Bổ Sung Dần

Khi có ý tưởng mới, có thể bổ sung vào các nhóm:

- Chức năng cho admin.
- Chức năng cho giáo viên.
- Chức năng hỏi đáp.
- Chức năng bản đồ.
- Chức năng timeline.
- Chức năng GraphRAG.
- Chức năng deploy.
- Chức năng mở rộng sau MVP.
