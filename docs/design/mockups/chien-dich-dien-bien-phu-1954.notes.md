# Điện Biên Phủ — bản thử kể chuyện theo cảnh

## Mục tiêu

Cải tiến prototype riêng theo cách trình bày trong video người dùng gửi, không sửa ứng dụng, catalog hay JSON chiến dịch hiện có. Tệp mở đầu vẫn là `dien-bien-phu-animation-prototype.html`; CSS và JavaScript nằm cạnh nó, không có phụ thuộc mạng hoặc thư viện ngoài.

## Đối chiếu hình ảnh video

Tư liệu người dùng: `C:/Users/Admin/Videos/Screen Recordings/Screen Recording 2026-09-07 195914.mp4`, 246,57 giây, 1178 × 652, 30 fps. Đã trích và xem các khung hình xuyên suốt mỗi 10 giây, cùng các chuỗi dày hơn ở đầu, A1 và kết thúc. Ảnh đối chiếu nằm trong `output/playwright/dbp-video-study/`. Phân tích này tập trung vào hình ảnh, nhịp chuyển cảnh và chữ hiện trong video, không phải bản chép lời âm thanh.

| Thời điểm trong bản ghi | Cách video trình bày | Áp dụng trong bản thử |
| --- | --- | --- |
| 00:00–00:20 | Him Lam: pháo chuẩn bị, bộ binh, thay đổi giờ và cờ; bản đồ giữ góc toàn cảnh | Ba bước riêng; chỉ phát hỏa lực ở bước tương ứng, đổi trạng thái ở kết quả |
| 00:20–00:47 | Dịch cảnh sang Độc Lập; giữ dấu các mục tiêu đã chiếm trên bản đồ | Camera chỉ dịch ở bên trái, trạng thái các cứ điểm trước được giữ |
| 01:00–01:45 | Phóng gần dãy đồi phía đông; giao tranh qua nhiều vị trí | Cảnh dãy đồi riêng, không tự đổi tất cả mục tiêu sang đã chiếm ngay 30/3 |
| 01:45–02:35 | Đường hầm, tiếp tế, vây lấn; thay loại hình minh họa để giải thích cách đánh | Thêm cảnh chiến hào áp sát và thả dù tiếp tế; không bê số liệu tổn thất từ video |
| 03:04–03:34 | Chuyển sang mặt cắt A1 rồi quay về cảnh chiến đấu | Hai bước mặt cắt: đào hầm / bộc phá; bước ba trở về phối cảnh, A1 đổi trạng thái |
| 03:42–04:06 | Sở chỉ huy, Hồng Cúm, cảnh kết thúc | Hai cảnh cuối riêng; kết quả của trung tâm và phân khu nam được phân biệt |

Không sao chép hình, logo hoặc âm thanh từ video vào giao diện. SVG được dựng trong mã của prototype. Đây là bản thử thiết kế; hình công sự, người, địa hình, mặt cắt và hướng hoạt động được khái quát.

## Nội dung

- Nguồn chính cho các cảnh: `apps/frontend/src/features/battles/content/dien-bien-phu-1954.json`, các mục overview, himlam, doclap, bankeo, east, a1, command, hongcum.
- Bổ sung vây lấn và tiếp tế từ `lichsu.clean.md`: đoạn 2082 về khống chế sân bay và thả dù, 2090 về đợt hai, 2286–2296 về hào áp sát và phạm vi phòng ngự thu hẹp.
- Mặt cắt A1 dựa vào đoạn 2169–2173: đề xuất đào hầm, công binh đào tiếp cận và đặt bộc phá. Không đưa kích thước đo đạc hoặc vị trí hầm chính xác vào hình minh họa.
- Bản Kéo không có pháo kích hay cảnh nổ; nội dung giữ chi tiết tiếp quản không cần nổ súng.
- Không tự gán thời điểm chiếm E/D1/C1/C2 trong đợt hai. Chúng chỉ đổi trạng thái toàn bộ khi cảnh trung tâm kết thúc với việc đầu hàng ngày 7/5.
- Hồng Cúm không có mũi rút quân tự suy ra. Cảnh nhấn mạnh địa bàn và tóm tắt truy tìm, bắt giữ.
- Tọa độ bản đồ kế thừa lược đồ JSON hiện có. Phối cảnh trái bố trí lại để đọc hình, không phải mô hình địa hình 3D hay tuyến hành quân đã xác minh.

## Điều khiển và thời lượng

9 cảnh × 3 bước. Nhịp mặc định 4 giây/bước = khoảng 108 giây; có 6 và 9 giây/bước. Có thể bấm từng bước, chọn cảnh, chọn địa điểm, dùng phím mũi tên hoặc Enter trên địa điểm.

Phát/dừng giữ thời gian đã chạy. Diễn lại cảnh bắt đầu lại ba bước của riêng cảnh đó và dừng ở kết quả. Tua ngược tính lại trạng thái kiểm soát từ mốc đang xem. Khi chuyển sang tab khác, trình chiếu tạm dừng. Có chế độ giảm chuyển động.

Giữ cấu trúc HTML đầy đủ `head`/`body`, sửa lỗi Live Server từng chèn mã reload và trả thiếu đoạn script ở bản đầu. Script hiện tách thành file riêng.

## Kiểm tra

- `node --check` xác nhận JavaScript hợp lệ.
- Playwright: 9 cảnh, 27 bước, 18 lần bấm địa điểm trên hai khung, đồng bộ lựa chọn, tua ngược/kết quả, chuyển mặt cắt A1, Bản Kéo không có hỏa lực, bàn phím, giảm chuyển động và không tràn ngang ở 390 px đều đạt; không có lỗi JavaScript.
- Playwright clock: tự phát, tạm dừng/tiếp tục đúng phần thời gian còn lại, diễn lại riêng cảnh, dừng cuối chiến dịch và phát lại từ đầu đều đạt.
- Đã xem ảnh desktop toàn cảnh, Him Lam, A1, tiếp tế. Ảnh kiểm tra: `output/playwright/dbp-v2-*.png`; kịch bản: `dbp-v2-review.js`, `dbp-v2-playback.js` trong cùng thư mục output.
- Lần kiểm tra này dùng máy chủ nội bộ cổng 8767 vì Live Server cổng 5500 không hoạt động. Có thể mở lại bằng Live Server hoặc mở HTML trực tiếp cùng các file CSS/JS bên cạnh.
