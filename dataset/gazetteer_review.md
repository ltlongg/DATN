# Gazetteer review

Tổng 31 địa danh. Sắp theo confidence tăng dần + tần suất giảm dần (soát mấy dòng đầu trước). Sửa toạ độ sai trực tiếp trong `gazetteer.json` rồi chạy lại `build_gazetteer.py` (không cần --overwrite).

| location_norm | display | lat | lon | conf | nguồn | #event | modern_name | note | provider |
|---|---|---|---|---|---|---|---|---|---|
| bình cách | Bình Cách | 10.4500 | 106.3500 | thấp | llm | 5 | khu vực Bình Cách, Tiền Giang | Địa danh lịch sử nhỏ, thường gắn với căn cứ Bình Cách ở vùng Tiền Giang; vị trí chỉ áng chừng theo khu vực, không xác định chắc đến điểm cụ thể. | khu vực Bình Cách, Tiền Giang |
| thuộc nhiêu | Thuộc Nhiêu | 10.3880 | 106.1470 | thấp | llm | 2 | khu vực Thuộc Nhiêu, xã Mỹ Thành Nam, huyện Cai Lậy, Tiền Giang | Địa danh Thuộc Nhiêu nhiều khả năng là khu vực/chợ/cầu Thuộc Nhiêu ở Cai Lậy, Tiền Giang; toạ độ chỉ áng chừng theo khu vực, chưa xác định được điểm lịch sử chính xác. | khu vực Thuộc Nhiêu, xã Mỹ Thành Nam, huyện Cai Lậy, Tiền Giang |
| cầu cái lọc | Cầu Cái Lọc |  |  | thấp | none | 1 |  | Chưa xác định chắc chắn được địa danh 'Cầu Cái Lọc'; tên này có thể là cầu/địa điểm nhỏ hoặc tên cũ trùng lặp ở nhiều nơi. |  |
| đường sài gòn tây ninh | Đường Sài Gòn - Tây Ninh | 11.0665 | 106.3640 | thấp | llm | 1 | Tuyến TP. Hồ Chí Minh - Tây Ninh | Đây là tuyến đường chứ không phải một điểm; tọa độ lấy gần đúng theo trung điểm tuyến Sài Gòn - Tây Ninh (xấp xỉ theo hành lang QL22 hiện nay). | Tuyến TP. Hồ Chí Minh - Tây Ninh |
| làng tịch hà | Làng Tịch Hà | 16.4860 | 107.5850 | thấp | llm | 1 | khu vực Hương Vinh, TP. Huế | Nhiều khả năng là làng Tịch Hà/Tích Hà ở vùng Hương Vinh, gần Huế; tên cổ và cách chép không thật chắc nên toạ độ chỉ áng chừng theo khu vực. | khu vực Hương Vinh, TP. Huế |
| rêuyniông | Rêuyniông | -20.8789 | 55.4481 | thấp | llm | 1 | La Réunion, Pháp | Địa danh này không thuộc Việt Nam; lấy theo trung tâm hành chính Saint-Denis của đảo Réunion. | La Réunion, Pháp |
| an giang | An Giang | 10.3904 | 105.4344 | vừa | mapbox | 3 |  |  | An Giang, Việt Nam |
| chợ lớn | Chợ Lớn | 10.7553 | 106.6621 | vừa | llm | 3 | Quận 5, TP. Hồ Chí Minh | Chợ Lớn là khu đô thị lịch sử của Sài Gòn, nay chủ yếu tương ứng khu vực Quận 5 và lân cận ở TP. Hồ Chí Minh; toạ độ lấy gần trung tâm khu Chợ Lớn. | Quận 5, TP. Hồ Chí Minh |
| thành gia định | Thành Gia Định | 10.7870 | 106.6990 | vừa | llm | 2 | TP. Hồ Chí Minh | Thành Gia Định (thành Phiên An/Gia Định) là thành cũ ở khu trung tâm Sài Gòn; tọa độ lấy gần khu vực vị trí thành xưa, nay thuộc quận 1, TP. Hồ Chí Minh. | TP. Hồ Chí Minh |
| đồn rạch tra | Đồn Rạch Tra | 10.9220 | 106.5860 | vừa | llm | 1 | khu vực Rạch Tra, xã Bình Mỹ, huyện Củ Chi, TP. Hồ Chí Minh | Đồn Rạch Tra là đồn/cứ điểm lịch sử ở vùng Rạch Tra; toạ độ lấy gần khu vực Rạch Tra hiện nay tại Bình Mỹ, Củ Chi, không phải vị trí công trình còn xác định chính xác. | khu vực Rạch Tra, xã Bình Mỹ, huyện Củ Chi, TP. Hồ Chí Minh |
| sông vàm cỏ đông | Sông Vàm Cỏ Đông | 11.0210 | 106.3840 | vừa | llm | 1 | Sông Vàm Cỏ Đông | Sông dài qua Tây Ninh và Long An; toạ độ là điểm đại diện trên đoạn sông gần Trảng Bàng, Tây Ninh, không phải toàn tuyến. | Sông Vàm Cỏ Đông |
| đường sài gòn biên hòa | Đường Sài Gòn - Biên Hòa | 10.8970 | 106.8070 | vừa | llm | 1 | trục TP. Hồ Chí Minh - Biên Hòa (Xa lộ Hà Nội / Quốc lộ 1) | Đây là tuyến đường nối Sài Gòn với Biên Hòa, không phải một điểm hành chính. Tọa độ lấy gần đúng tại điểm giữa tuyến, khu vực Dĩ An - giáp TP. Thủ Đức. | trục TP. Hồ Chí Minh - Biên Hòa (Xa lộ Hà Nội / Quốc lộ 1) |
| gò công | Gò Công | 10.3593 | 106.6749 | cao | mapbox | 6 |  |  | Gò Công, Đồng Tháp, Việt Nam |
| gia định | Gia Định | 10.7980 | 106.6963 | cao | mapbox | 4 |  |  | Gia Dinh, Thành phố Hồ Chí Minh, Việt Nam |
| mĩ tho | Mĩ Tho | 10.3583 | 106.3618 | cao | mapbox | 4 |  |  | Mỹ Tho, Đồng Tháp, Việt Nam |
| tân an | Tân An | 10.5236 | 106.4144 | cao | mapbox | 3 |  |  | Tân An, Tây Ninh, Việt Nam |
| tân hòa | Tân Hòa | 10.9713 | 106.9087 | cao | mapbox | 2 |  |  | Tân Hòa, Hố Nai, Đồng Nai, Việt Nam |
| chợ gạo | Chợ Gạo | 10.3540 | 106.4608 | cao | mapbox | 2 |  |  | Chợ Gạo, Đồng Tháp, Việt Nam |
| định tường | Định Tường | 19.9646 | 105.6486 | cao | mapbox | 2 |  |  | Định Tường, Yên Định, Thanh Hóa, Việt Nam |
| sài gòn | Sài Gòn | 10.7763 | 106.7013 | cao | mapbox | 1 |  |  | Sai Gon, Thành phố Hồ Chí Minh, Việt Nam |
| bà rịa | Bà Rịa | 10.5875 | 107.1459 | cao | mapbox | 1 |  |  | Bà Rịa - Sông Pha - Sông Xoài, 78700, Châu Pha, Thành phố Hồ Chí Minh, Việt Nam |
| châu đốc | Châu Đốc | 10.7090 | 105.1179 | cao | mapbox | 1 |  |  | Châu Đốc, An Giang, Việt Nam |
| tam bình | Tam Bình | 10.8677 | 106.7371 | cao | mapbox | 1 |  |  | Tam Bình, Thành phố Hồ Chí Minh, Việt Nam |
| đà nẵng | Đà Nẵng | 16.0680 | 108.2120 | cao | mapbox | 1 |  |  | Đà Nẵng, Việt Nam |
| cai lậy | Cai Lậy | 10.4047 | 106.1236 | cao | llm | 1 | Cai Lậy, Tiền Giang | Địa danh hiện còn dùng; lấy theo khu vực trung tâm Cai Lậy (Tiền Giang). | Cai Lậy, Tiền Giang |
| hà tiên | Hà Tiên | 10.3823 | 104.4875 | cao | mapbox | 1 |  |  | Hà Tiên, An Giang, Việt Nam |
| cần giờ | Cần Giờ | 10.4151 | 106.9727 | cao | mapbox | 1 |  |  | Can Gio, Thành phố Hồ Chí Minh, Việt Nam |
| phúc lộc | Phúc Lộc | 22.4293 | 105.8505 | cao | mapbox | 1 |  |  | Phúc Lộc, Thái Nguyên, Việt Nam |
| mĩ quý | Mĩ Quý | 10.3621 | 105.4525 | cao | mapbox | 1 |  |  | Mỹ Quý, Long Xuyên, An Giang, Việt Nam |
| biên hòa | Biên Hòa | 10.9393 | 106.8041 | cao | mapbox | 1 |  |  | Biên Hòa, Đồng Nai, Việt Nam |
| bán đảo sơn trà | Bán đảo Sơn Trà | 16.1173 | 108.2772 | cao | llm | 1 | Bán đảo Sơn Trà, quận Sơn Trà, Đà Nẵng | Tọa độ gần đúng khu vực trung tâm bán đảo Sơn Trà. | Bán đảo Sơn Trà, quận Sơn Trà, Đà Nẵng |
