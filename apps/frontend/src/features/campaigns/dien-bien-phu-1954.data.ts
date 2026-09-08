/**
 * Dữ liệu cảnh của chiến dịch Điện Biên Phủ.
 *
 * Chép nguyên chữ, toạ độ và đường path từ bản thử
 * `docs/design/mockups/chien-dich-dien-bien-phu-1954.js` — cố ý giữ y hệt để còn đối chiếu
 * được với mockup; khác biệt duy nhất là thêm kiểu và `export`. Nội dung biên soạn cùng
 * phần đối chiếu nguồn nằm ở tệp `.notes.md` cạnh mockup đó.
 *
 * Mỗi địa điểm mang HAI cặp toạ độ vì được vẽ ở hai khung khác nhau: `x`/`y` cho lược đồ
 * (viewBox `140 0 620 760`), `sx`/`sy` cho phối cảnh (viewBox `0 0 960 640`).
 */

/** Một bước trong cảnh. Mỗi cảnh đúng ba bước — bản dựng và thanh tiến độ dựa vào con số này. */
export interface Beat {
  label: string;
  /** Mốc thời gian hiện ở góc phối cảnh, ví dụ "17:05 · 13/3". */
  time: string;
  text: string;
  /** Câu ngắn trong nhãn hành động, mô tả thứ đang diễn ra trên hình. */
  action: string;
}

export interface Chapter {
  id: string;
  name: string;
  date: string;
  phase: string;
  title: string;
  /** Địa điểm cảnh này đang nói tới: camera bám theo, lược đồ khoanh vùng. */
  targets: string[];
  /** Địa điểm đổi sang trạng thái đã kiểm soát khi cảnh chạy hết bước thứ ba. */
  gain: string[];
  result: string;
  beats: Beat[];
}

export interface Site {
  id: string;
  name: string;
  x: number;
  y: number;
  sx: number;
  sy: number;
  /** Chỉ số cảnh liên quan — bấm vào địa điểm là nhảy tới cảnh đó. */
  c: number;
  /** Vẽ thêm sườn đồi ở phối cảnh (dãy đồi phía đông). */
  hill?: boolean;
}

const beat = (label: string, time: string, text: string, action: string): Beat => ({ label, time, text, action });
export const chapters: Chapter[] = [
 {id:'overview',name:'Toàn cảnh',date:'13/3–7/5',phase:'Chuẩn bị · Toàn cảnh',title:'Đánh chắc, tiến chắc',targets:[],gain:[],result:'Tiêu diệt từng cứ điểm, đồng thời siết dần vòng vây quanh Mường Thanh.',beats:[
 beat('Thế trận','Trước 13/3','Tập đoàn cứ điểm nằm trong lòng chảo Mường Thanh. Phân khu bắc bảo vệ ngoại vi; sân bay, sở chỉ huy và dãy đồi phía đông tạo thành khu trung tâm.','Xác định ngoại vi, sân bay và khu chỉ huy'),
 beat('Chuẩn bị','26/1/1954','Bộ chỉ huy chuyển sang phương châm đánh chắc, tiến chắc. Pháo được kéo ra để chuẩn bị lại, xây dựng trận địa kiên cố và thế bao vây.','Chuẩn bị trận địa pháo và bao vây'),
 beat('Cách đánh','Ba đợt tiến công','Chiến dịch đi từ các cứ điểm ngoại vi phía bắc, tới dãy đồi phía đông và khu trung tâm. Bấm vào địa điểm trên một trong hai khung để theo dõi.','Ngoại vi → vây lấn → khu trung tâm')]},
 {id:'himlam',name:'Him Lam',date:'13/3',phase:'Đợt 1 · Trận mở màn',title:'Mở cửa từ Him Lam',targets:['himlam'],gain:['himlam'],result:'Him Lam bị tiêu diệt, mở đầu việc phá vỡ lớp phòng ngự ngoại vi.',beats:[
 beat('Pháo chuẩn bị','17:05 · 13/3','Pháo và súng cối đồng loạt khai hỏa vào Him Lam. Hỏa lực đánh trúng sở chỉ huy, làm gián đoạn liên lạc với Mường Thanh.','Pháo chuẩn bị vào cụm cứ điểm'),
 beat('Bộ binh tiến công','Tối 13/3','Sau hỏa lực chuẩn bị, Đại đoàn 312 tiến công các vị trí trong trung tâm đề kháng Him Lam. Bộ binh tiếp cận và đánh vào hệ thống công sự.','Đại đoàn 312 · Tiến công'),
 beat('Làm chủ mục tiêu','23:30 · 13/3','Đơn vị báo cáo hoàn thành nhiệm vụ tiêu diệt trung tâm đề kháng Him Lam. Một vị trí quan trọng ở ngoại vi đông bắc đã bị loại khỏi hệ thống phòng ngự của Pháp.','Làm chủ Him Lam')]},
 {id:'doclap',name:'Độc Lập',date:'14–15/3',phase:'Đợt 1 · Hướng bắc',title:'Phá tuyến phòng ngự bắc',targets:['doclap'],gain:['doclap'],result:'Độc Lập thất thủ sau Him Lam; lớp phòng ngự phía bắc suy yếu rõ rệt.',beats:[
 beat('Mục tiêu','Đêm 14/3','Độc Lập nằm ở đầu bắc cánh đồng, bảo vệ hướng từ Lai Châu vào. Sau Him Lam, đây là trung tâm đề kháng tiếp theo bị tiến công.','Chuyển mục tiêu lên phía bắc'),
 beat('Tiến công','Đêm 14 → 15/3','Bộ đội tiến công cứ điểm trong đêm, giành quyền kiểm soát ngọn đồi và đẩy lùi phản kích.','Tiến công và chống phản kích'),
 beat('Kết quả','Rạng sáng 15/3','Quân ta làm chủ Độc Lập. Hai cứ điểm quan trọng ở ngoại vi phía bắc và đông bắc đã bị loại khỏi hệ thống phòng ngự.','Làm chủ Độc Lập')]},
 {id:'bankeo',name:'Bản Kéo',date:'17/3',phase:'Đợt 1 · Ngoại vi',title:'Ngoại vi phía bắc tan vỡ',targets:['bankeo'],gain:['bankeo'],result:'Lớp phòng ngự ngoại vi phía bắc coi như không còn.',beats:[
 beat('Sức ép','Sau 15/3','Sau thất bại ở Him Lam và Độc Lập, các vị trí Bản Kéo chịu sức ép trong một thế phòng ngự đã suy yếu.','Sức ép sau hai trận ngoại vi'),
 beat('Bỏ vị trí','17/3','Binh sĩ thuộc hai đại đội tại Anne Marie 1 và 2 bỏ ngũ đồng loạt. Diễn biến ở đây không phải một trận công phá bằng hỏa lực.','Binh sĩ rời vị trí'),
 beat('Tiếp quản','17/3','Bộ đội Việt Nam chiếm các vị trí này mà không cần nổ súng. Bản Kéo đổi trạng thái cùng Him Lam và Độc Lập.','Tiếp quản Bản Kéo, không nổ súng')]},
 {id:'east',name:'Dãy đồi đông',date:'Từ 30/3',phase:'Đợt 2 · Phía đông',title:'Giành các điểm cao',targets:['e','d1','c1','a1'],gain:[],result:'Các trận đánh kéo dài, giằng co; A1 vẫn là mục tiêu quan trọng của đợt cuối.',beats:[
 beat('Dãy điểm cao','Từ 30/3','Đợt hai tập trung vào các điểm cao E, D1, C1, C2 và A1, đồng thời vây lấn phân khu trung tâm Mường Thanh.','Tập trung vào dãy đồi phía đông'),
 beat('Đánh và giữ','Cuối tháng 3','Tiến công các công sự trên đồi đi cùng chống phản kích. Nhiều vị trí phải giành giật; việc chiếm một điểm cao không đồng nghĩa làm chủ cả dãy đồi.','Tiến công từng vị trí, chống phản kích'),
 beat('Tiếp tục vây lấn','Sang tháng 4','Không phải mọi mục tiêu đều bị chiếm ngay ngày 30/3. Bộ đội tiếp tục xây dựng trận địa và siết vòng vây; A1 còn giao tranh tới đợt cuối.','Tiếp tục vây lấn · A1 chưa kết thúc')]},
 {id:'trench',name:'Vây lấn',date:'Tháng 4',phase:'Đợt 2 · Siết vòng vây',title:'Đưa chiến hào tới cứ điểm',targets:['airfield','command'],gain:[],result:'Phạm vi phòng ngự bị thu hẹp; tiếp tế đường không ngày càng khó khăn.',beats:[
 beat('Đào áp sát','Tháng 4','Giao thông hào được đào dần tới gần công sự Pháp. Bộ đội có đường tiếp cận được che chắn hơn, tạo bàn đạp cho các đợt tiến công.','Đào hào áp sát · Mở rộng trận địa'),
 beat('Khống chế tiếp tế','Tháng 4','Sân bay bị khống chế; quân Pháp phải dựa vào thả dù tiếp tế. Vòng vây thu hẹp khiến việc thu nhận hàng và tiếp viện khó khăn hơn.','Thả dù trong một khu vực ngày càng hẹp'),
 beat('Siết khu trung tâm','Cuối tháng 4','Hào tiến sát các lô cốt, cắt qua sân bay. Vây lấn kết hợp tiến công từng mục tiêu làm giảm dần không gian phòng ngự của tập đoàn cứ điểm.','Thu hẹp phạm vi phòng ngự')]},
 {id:'a1',name:'Cao điểm A1',date:'6–7/5',phase:'Đợt 3 · Cao điểm A1',title:'Mở đường qua A1',targets:['a1'],gain:['a1'],result:'A1 mất đi, khu trung tâm mất một vị trí khống chế quan trọng.',beats:[
 beat('Đường hầm','Chuẩn bị trước 6/5','Công binh đào đường hầm tới dưới vị trí phòng ngự trên A1 để đặt bộc phá. Mặt cắt bên trái minh họa cách tiếp cận dưới lòng đất.','Đào hầm → đặt bộc phá dưới mục tiêu'),
 beat('Tạo cửa mở','Đêm 6/5','Khối bộc phá phát nổ, tạo cửa mở. Bộ đội tiếp tục tiến công để đánh dứt điểm cao điểm A1.','Bộc phá tạo cửa mở · Bộ binh tiến công'),
 beat('Làm chủ cao điểm','Sáng 7/5','Bộ đội làm chủ A1. Cao điểm có vai trò khống chế khu chỉ huy và cầu qua sông Nậm Rốm; kết quả này tạo điều kiện tiến vào trung tâm.','Làm chủ A1')]},
 {id:'command',name:'Mường Thanh',date:'Chiều 7/5',phase:'Đợt 3 · Khu trung tâm',title:'Tiến vào sở chỉ huy',targets:['command'],gain:['command','e','d1','c1','airfield'],result:'Tướng de Castries và các sĩ quan bị bắt; quân Pháp ở khu trung tâm đầu hàng.',beats:[
 beat('Thời cơ','Chiều 7/5','Sau khi các điểm cao then chốt thất thủ, khu trung tâm bị uy hiếp. Các đơn vị tiến công Mường Thanh từ nhiều hướng.','Các đơn vị tiến vào khu trung tâm'),
 beat('Đánh sở chỉ huy','Chiều 7/5','Bộ đội tiến vào khu sở chỉ huy, bắt tướng de Castries cùng các sĩ quan trong hầm chỉ huy.','Tiếp cận và chiếm hầm chỉ huy'),
 beat('Đầu hàng','17:30 · 7/5','Đại đoàn 312 báo cáo toàn bộ quân Pháp tại khu trung tâm đã đầu hàng. Diễn biến còn tiếp tục ở phân khu nam Hồng Cúm.','Khu trung tâm đầu hàng')]},
 {id:'hongcum',name:'Hồng Cúm',date:'Đêm 7/5',phase:'Đợt 3 · Phân khu nam',title:'Khép lại chiến dịch',targets:['hongcum'],gain:['hongcum'],result:'Chiến dịch Điện Biên Phủ kết thúc sau các trận đánh từ 13/3 đến 7/5/1954.',beats:[
 beat('Phân khu nam','Sau Mường Thanh','Khi khu trung tâm thất thủ, quân Pháp ở Hồng Cúm tìm cách thoát khỏi vòng vây. Đây là diễn biến cuối cùng của chiến dịch.','Theo dõi phân khu nam Hồng Cúm'),
 beat('Truy tìm, bắt giữ','Đêm 7/5','Bộ đội và lực lượng địa phương tổ chức truy tìm, bắt giữ lực lượng rời Hồng Cúm, khép lại những diễn biến cuối cùng ở phân khu nam.','Truy tìm và bắt giữ'),
 beat('Kết thúc','24:00 · 7/5','Báo cáo ghi nhận toàn bộ quân Pháp ở Hồng Cúm đã bị bắt. Từ ngoại vi đến Mường Thanh và phân khu nam, chiến dịch kết thúc.','Điện Biên Phủ · Chiến dịch kết thúc')]}
];
export const sites: Site[] = [
 {id:'doclap',name:'ĐỘC LẬP',x:333,y:111,sx:295,sy:242,c:2},
 {id:'himlam',name:'HIM LAM',x:622,y:182,sx:650,sy:285,c:1},
 {id:'bankeo',name:'BẢN KÉO',x:253,y:270,sx:192,sy:344,c:3},
 {id:'airfield',name:'SÂN BAY',x:385,y:331,sx:385,sy:396,c:5},
 {id:'e',name:'ĐỒI E',x:566,y:307,sx:595,sy:351,c:4,hill:true},
 {id:'d1',name:'D1',x:574,y:350,sx:642,sy:389,c:4,hill:true},
 {id:'c1',name:'C1 · C2',x:580,y:391,sx:696,sy:430,c:4,hill:true},
 {id:'a1',name:'A1',x:566,y:445,sx:643,sy:488,c:6,hill:true},
 {id:'command',name:'HẦM DE CASTRIES',x:422,y:448,sx:439,sy:481,c:7},
 {id:'hongcum',name:'HỒNG CÚM',x:430,y:629,sx:466,sy:570,c:8}
];
export const river ='M420 10C470 60 403 90 438 140S411 210 458 249S438 298 478 330S445 365 490 405S439 443 472 478S427 523 451 566S404 624 432 704';
export const scenicRiver ='M462 181Q497 221 469 250T482 296Q533 327 489 353T520 401Q557 427 492 451T532 497Q572 523 509 550T490 624';
export const trenchPath ='M759 310L731 331L741 349L708 366L721 386L741 405L724 425L744 443L723 463L692 480L701 502L676 520M283 360L307 377L296 396L322 413L311 432L340 450L329 470L356 486';
