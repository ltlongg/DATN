/* Prototype chỉ đọc. Nguồn biên soạn và đối chiếu video ở tệp notes cùng tên. */
(() => {
'use strict';
const $ = id => document.getElementById(id);
const beat = (label, time, text, action) => ({label,time,text,action});
const chapters = [
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
const sites=[
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
const river='M420 10C470 60 403 90 438 140S411 210 458 249S438 298 478 330S445 365 490 405S439 443 472 478S427 523 451 566S404 624 432 704';
const scenicRiver='M462 181Q497 221 469 250T482 296Q533 327 489 353T520 401Q557 427 492 451T532 497Q572 523 509 550T490 624';
const trenchPath='M759 310L731 331L741 349L708 366L721 386L741 405L724 425L744 443L723 463L692 480L701 502L676 520M283 360L307 377L296 396L322 413L311 432L340 450L329 470L356 486';
let ci=0,bi=0,running=false,elapsed=0,last=0,raf=0,chapterOnly=false;
const reduced=()=> $('motion').checked;
const chapter=()=>chapters[ci];
const activeSites=()=>sites.filter(s=>chapter().targets.includes(s.id));
function controlled(id){return chapters.some((c,i)=>c.gain.includes(id)&&(i<ci||i===ci&&bi===2));}
const definitions=`<defs>
<linearGradient id="dbp-sky" x2="0" y2="1"><stop stop-color="#8ecbda"/><stop offset="1" stop-color="#dfebcd"/></linearGradient>
<linearGradient id="dbp-soil" x2="0" y2="1"><stop stop-color="#d7c689"/><stop offset="1" stop-color="#eee0a7"/></linearGradient>
<linearGradient id="dbp-hill" x2=".2" y2="1"><stop stop-color="#87a76d"/><stop offset="1" stop-color="#c5ca87"/></linearGradient>
<pattern id="dbp-fields" width="44" height="30" patternUnits="userSpaceOnUse" patternTransform="rotate(-15)"><path d="M0 12H35M0 17H35M0 22H35" stroke="#b4a96d" stroke-width=".7" opacity=".5"/></pattern>
<g id="dbp-bunker"><ellipse cy="11" rx="23" ry="7" fill="#56614622"/><path d="M-20 8L-13 -7L9 -11L22 3L17 10Z" fill="#67704e"/><path d="M-20 8L-13 -7L9 -11L1 3Z" fill="#a2a37c"/><path d="M2 3H13V10H2Z" fill="#303c2c"/><path d="M-22 12L-14 13M17 13L25 10" stroke="#b49e63" stroke-width="4"/></g>
<g id="dbp-tent"><path d="M-15 8L0 -14L18 7Z" fill="#9a9a65"/><path d="M0 -14L2 8H18Z" fill="#657347"/><path d="M-2 0L-7 8H4Z" fill="#39452f"/></g>
<g id="dbp-tree"><path d="M0 -1V16M0 6L-7 0" stroke="#867147" stroke-width="2"/><path d="M0 -26C-19 -25 -17 -5 -8 -3C-12 7 9 10 11 -2C25 -12 13 -29 0 -26Z" fill="#7f9c57"/><path d="M-2 -24C-14 -24 -15 -10 -7 -7L3 -8L9 -17Z" fill="#99af66"/></g>
<g id="dbp-gun"><path d="M-5 4L-29 18M-5 4L-26 -2" stroke="#566246" stroke-width="4"/><path d="M-17 -4L34 -15" stroke="#4f6041" stroke-width="7"/><path d="M-2 -6L7 -19L13 -1Z" fill="#788162"/><circle cx="0" cy="7" r="10" fill="#3d4d36"/><circle cx="0" cy="7" r="5" fill="#a6a583"/><path d="M-7 7H7M0 0V14" stroke="#647052"/></g>
<g id="dbp-soldier"><ellipse cy="17" rx="7" ry="3" fill="#243c3220"/><path d="M-3 9L-5 17M2 9L6 17" stroke="#465c37" stroke-width="3"/><path d="M-4 1H4L6 10H-5Z" fill="#708449"/><circle cy="-5" r="4" fill="#caa97a"/><path d="M-6 -6Q0 -15 6 -6Z" fill="#4f6c3b"/><path d="M-4 4L4 2L11 -5" fill="none" stroke="#705e3f" stroke-width="2"/></g>
<g id="dbp-plane"><path d="M-49 1L-6 -4L1 -35L10 -35L9 -4L45 0L48 7L8 7L12 26L4 26L-7 8L-49 8Z" fill="#647a70" stroke="#42594f" stroke-width="1.5"/><path d="M-28 0V11M28 0V11" stroke="#4c5d55" stroke-width="4"/></g>
<g id="dbp-parachute"><path d="M-20 0Q0 -30 20 0Q11 -5 5 0Q0 -4 -5 0Q-11 -5 -20 0Z" fill="#eee4be" stroke="#aba680"/><path d="M-20 0L-5 28M20 0L5 28M-5 0L-3 28M5 0L3 28" stroke="#aaa589"/><rect x="-6" y="28" width="12" height="11" fill="#a88c54"/><path d="M0 28V39" stroke="#d5bf8c"/></g>
<marker id="dbp-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#285d45"/></marker>
</defs>`;
function flag(x,y,taken){return `<path d="M${x} ${y+8}V${y-30}" stroke="#786645" stroke-width="1.8"/><g class="flag-cloth"><path d="M${x+1} ${y-30}h25v16h-25Z" fill="${taken?'#ad4030':'#f6f3dc'}"/>${taken?`<text x="${x+13}" y="${y-18}" text-anchor="middle" fill="#ffe28e" font-size="13">★</text>`:`<path d="M${x+1} ${y-30}h8v16h-8Z" fill="#4b6384"/><path d="M${x+18} ${y-30}h8v16h-8Z" fill="#a44439"/>`}</g>`;}
function terrain(){let out=`<rect width="960" height="640" fill="url(#dbp-sky)"/><path d="M0 161Q49 80 92 137T165 168Q227 77 274 146T356 173Q416 111 467 161T550 176Q612 113 660 94T742 129Q798 51 844 103T960 135V640H0Z" fill="#719573"/><path d="M0 200Q39 143 91 177T194 175Q252 149 319 193T453 188Q510 144 566 182Q614 144 660 106L640 160L687 146L665 180Q728 164 764 140Q802 99 828 95L810 140L850 128L823 169Q899 147 960 185V640H0Z" fill="#95ae7e"/><path d="M0 266Q116 210 241 244T463 244Q648 204 786 257T960 257V640H0Z" fill="url(#dbp-soil)"/><path d="M0 286Q123 253 246 280T507 270Q714 236 960 323V640H0Z" fill="url(#dbp-fields)"/><path d="M0 278Q60 241 104 285T133 369Q155 411 104 445T48 549L0 558ZM960 245Q868 213 831 289T866 423Q820 473 883 528L960 569Z" fill="url(#dbp-hill)"/>
<path d="M91 484Q232 461 367 501T683 530M56 535Q212 506 300 554T740 586M209 293Q324 263 396 296M692 277Q760 272 818 291" fill="none" stroke="#c0ae71" stroke-width="1.2"/>
<path d="${scenicRiver}" fill="none" stroke="#73a9ae" stroke-width="16"/><path d="${scenicRiver}" fill="none" stroke="#b5d5c6" stroke-width="5"/>
<path d="M310 277Q324 335 391 389T431 479L458 611M192 344L611 355M343 462L651 488M481 543L739 575" fill="none" stroke="#bca772" stroke-width="8"/><path d="M310 277Q324 335 391 389T431 479L458 611M192 344L611 355M343 462L651 488M481 543L739 575" fill="none" stroke="#f3e5b6" stroke-width="4"/>
<path d="M351 341L369 334L420 432L400 440Z" fill="#ada787" stroke="#8e8b6c"/><path d="M363 347L406 425" stroke="#f8f1d3" stroke-width="2" stroke-dasharray="10 7"/>
<path d="M476 454L523 446" stroke="#716343" stroke-width="9"/><path d="M476 448L523 440M476 460L523 452" stroke="#9e8b5c" stroke-width="2"/><path d="M486 445V463M502 442V460M518 440V457" stroke="#655e44" stroke-width="2"/>`;
for(let i=0;i<32;i++){const x=48+(i*157)%844,y=320+(i*73)%280;if(x<165||x>768)out+=`<use href="#dbp-tree" x="${x}" y="${y}"/>`;}
for(let i=0;i<23;i++){const x=225+(i*71)%326,y=363+(i*37)%173;if(Math.abs(x-494)>38&&Math.abs(y-480)>24)out+=`<use href="${i%3?'#dbp-tent':'#dbp-bunker'}" transform="translate(${x} ${y}) scale(.55)"/>`;}
out+=`<text x="306" y="418" class="svg-note" transform="rotate(-9 306 418)">Sân bay Mường Thanh</text><text x="531" y="555" class="svg-note" fill="#4e8995">Nậm Rốm</text>`;return out;}
function landmark(s,map=false){const x=map?s.x:s.sx,y=map?s.y:s.sy,selected=chapter().targets.includes(s.id),taken=controlled(s.id);let shape='';
if(map){shape=s.id==='airfield'?`<rect x="${x-7}" y="${y-16}" width="14" height="32" fill="#fff9e4" stroke="#8f9272"/>`:`<rect x="${x-6}" y="${y-6}" width="12" height="12" rx="2" fill="${taken?'#285d45':'#a74737'}"/>`;}
else if(s.id==='airfield'){shape='';}
else{if(s.hill)shape+=`<path d="M${x-43} ${y+15}Q${x-24} ${y-32} ${x} ${y-24}Q${x+29} ${y-28} ${x+46} ${y+14}Z" fill="url(#dbp-hill)"/><path d="M${x-31} ${y+11}Q${x} ${y-13} ${x+35} ${y+9}" stroke="#94a36a" fill="none"/>`;
shape+=`<use href="#dbp-bunker" x="${x}" y="${y}"/>`;if(!s.hill)shape+=`<use href="#dbp-tent" x="${x-29}" y="${y+10}"/><use href="#dbp-bunker" transform="translate(${x+33} ${y+9}) scale(.65)"/>`;
shape+=`<path d="M${x-38} ${y+20}q12 9 24 4t24 0t24-4" fill="none" stroke="#8f8157" stroke-width="1.5" stroke-dasharray="2 2"/>`;
if(!s.hill||taken)shape+=flag(x+(s.hill?-22:18),y-11,taken);}
const lx=map?(s.id==='command'?x-21:x+21):s.hill?x+44:x,ly=map?y+4:s.hill?y-6:y-43;
return `<g class="landmark ${selected?'active':''} ${taken?'captured':''}" data-site="${s.id}" data-chapter="${s.c}" role="button" tabindex="0" aria-label="${s.name}" aria-pressed="${selected}"><ellipse class="marker-ring" cx="${x}" cy="${y}" rx="${map?19:43}" ry="${map?19:24}"/>${shape}${s.id==='airfield'&&!map?'':`<text class="label" x="${lx}" y="${ly}" text-anchor="${map?s.id==='command'?'end':'start':s.hill?'start':'middle'}" style="font-size:${map?12:13}px">${s.name}</text>`}<ellipse class="hit" cx="${x}" cy="${y}" rx="${map?14:25}" ry="${map?14:17}"/></g>`;
}
function squads(route,count=3){return Array.from({length:count},(_,i)=>`<g class="squad" style="offset-path:path('${route}');animation-delay:${i*.22}s"><use href="#dbp-soldier" x="${-i*12}" y="${i%2*8}"/></g>`).join('');}
function route(d,label,x,y){return `<path class="route" pathLength="1" d="${d}" marker-end="url(#dbp-arrow)"/><text x="${x}" y="${y}" class="svg-note" style="fill:#285d45">${label}</text>`;}
function impact(x,y){return `<g class="impact"><path d="M${x} ${y-30}l9 18 22-9-12 21 18 12-25 1-6 23-12-19-23 8 12-20-15-16 22 1Z" fill="#f3c261" stroke="#9d7447" stroke-width="2"/><circle cx="${x}" cy="${y}" r="11" fill="#ffe3a0"/></g>`;}
function scenicEffects(){const c=chapter(),t=activeSites()[0];let out='';
if(ci===0&&bi>=1){out+=`<use href="#dbp-gun" transform="translate(789 315) rotate(-154)"/><use href="#dbp-gun" transform="translate(821 344) rotate(-154)"/><text x="716" y="293" class="svg-note">Trận địa pháo (minh họa)</text>`;}
if(ci>=4)out+=`<path class="trench-line ${ci===5&&bi===0?'':'steady'}" pathLength="1" d="${trenchPath}"/>`;
if(ci===5){out+=`<path class="trench-line ${bi===2?'':'steady'}" pathLength="1" d="M317 373L353 376L349 392L380 397L383 414L425 423"/><text x="245" y="340" class="svg-note">Chiến hào áp sát sân bay</text>`;
if(bi===1){out+=`<g class="plane-flight"><use href="#dbp-plane" x="120" y="225"/></g><g class="parachute"><use href="#dbp-parachute" x="393" y="300"/></g><g class="parachute" style="animation-delay:.5s"><use href="#dbp-parachute" x="461" y="277"/></g>`;}return out;}
if(!t||ci===3||ci===8)return out;
if((ci===1&&bi===0)||(ci===2&&bi===1)||(ci===4&&bi===1)){const x=t.sx,y=t.sy;out+=`<use href="#dbp-gun" transform="translate(792 332) rotate(-155)"/><use href="#dbp-gun" transform="translate(835 373) rotate(-155)"/><path class="shell" d="M775 320Q${x+75} ${y-150} ${x} ${y}"/><path class="shell" style="animation-delay:.45s" d="M821 360Q${x+60} ${y-110} ${x} ${y}"/>${impact(x,y)}<text x="753" y="303" class="svg-note">Pháo chuẩn bị</text>`;}
if(bi===1&&[1,2,4,7].includes(ci)){const d=`M${t.sx+142} ${t.sy+62}Q${t.sx+83} ${t.sy+42} ${t.sx+27} ${t.sy+10}`;out+=route(d,ci===1?'Đại đoàn 312 · Tiến công':'Bộ đội · Tiến công',t.sx+65,t.sy+23)+squads(d);if(ci===7){const d2=`M${t.sx-127} ${t.sy+47}Q${t.sx-65} ${t.sy+31} ${t.sx-26} ${t.sy+10}`;out+=route(d2,'Tiến vào khu chỉ huy',t.sx-164,t.sy+20)+squads(d2,2);}}
if(bi===2&&c.gain.length)out+=`<use href="#dbp-soldier" x="${t.sx-18}" y="${t.sy+5}"/><use href="#dbp-soldier" x="${t.sx-34}" y="${t.sy+12}"/>`;
return out;}
function a1Cutaway(){const blast=bi===1;return `<g id="a1-cutaway"><rect width="960" height="640" fill="#dbe7c5"/><path d="M0 180Q96 93 188 158T367 149Q470 61 601 141T802 142Q874 78 960 112V640H0Z" fill="#a9bf8d"/><path d="M0 360Q137 321 272 314Q400 297 518 188Q572 126 637 180Q685 227 717 284Q817 297 960 329V640H0Z" fill="#d6c889"/><path d="M0 398Q162 379 291 388Q496 358 656 375T960 398V640H0Z" fill="#91704d"/><path d="M0 409Q183 391 291 398Q485 372 650 387T960 411" stroke="#c4a16c" stroke-width="16" fill="none"/><path d="M0 534Q189 501 371 552T737 530T960 552" fill="none" stroke="#795d43" stroke-width="3"/>
<path d="M73 411H235Q280 411 310 454H560Q607 454 607 342" fill="none" stroke="#493e30" stroke-width="36" stroke-linejoin="round"/><path class="tunnel-dig" pathLength="1" d="M73 411H235Q280 411 310 454H560Q607 454 607 342" fill="none" stroke="#b39562" stroke-width="4" stroke-linejoin="round"/>
<path d="M542 190L554 156H614L628 185Z" fill="#6a7250"/><path d="M561 178H593V190H561Z" fill="#303d2b"/>${flag(628,151,false)}<path d="M670 264h-94l-8 12h120" fill="#6f7655"/><path d="M591 262L530 248" stroke="#535e41" stroke-width="9"/>
<path d="M725 327V362M749 331V366M773 335V370M797 339V374M821 343V378" stroke="#69674c" stroke-width="3"/><path d="M714 346q12-25 24 0t24 0t24 0t24 0t24 0" fill="none" stroke="#67664d" stroke-width="1.8"/>
<use href="#dbp-soldier" transform="translate(153 416) scale(1.2)"/><use href="#dbp-soldier" transform="translate(344 459) scale(1.2)"/><path d="M357 445L373 435" stroke="#b4a781" stroke-width="4"/>
<rect x="588" y="327" width="36" height="25" rx="3" fill="#aa5f3a"/><path d="M596 328V350M605 328V350M614 328V350" stroke="#edb766" stroke-width="3"/>
<text x="104" y="354" class="svg-note" style="font-size:17px">Cửa đường hầm</text><text x="294" y="511" class="svg-note" style="font-size:17px">Công binh đào tiếp cận</text><path d="M356 486V466" stroke="#c6b185"/>
<text x="676" y="437" class="svg-note" style="font-size:17px">Bộc phá dưới mục tiêu</text><path d="M670 421L622 357" stroke="#d7bf8f" fill="none"/><text x="454" y="122" class="svg-note" style="font-size:20px">ĐỒI A1 · MẶT CẮT MINH HỌA</text>
${blast?`${impact(604,302)}<path class="route" pathLength="1" d="M826 303Q762 243 661 204" marker-end="url(#dbp-arrow)"/><text x="713" y="225" class="svg-note">Bộ binh tiến công</text>${squads('M826 303Q762 243 661 204',3)}`:''}<text x="500" y="588" text-anchor="middle" fill="#e9dab7" font-size="12">Mặt cắt giải thích cách đánh, không mô tả kích thước công trình.</text></g>`;}
function camera(){if(ci===0)return {x:480,y:340,z:1};if(ci===5)return {x:478,y:419,z:1.3};const targets=activeSites(),x=targets.reduce((a,t)=>a+t.sx,0)/targets.length,y=targets.reduce((a,t)=>a+t.sy,0)/targets.length;return {x:Math.max(330,Math.min(640,x)),y:Math.max(310,Math.min(480,y)),z:bi===0?1.18:ci===4?1.32:1.48};}
function drawScene(){const cut=ci===6&&bi<2;$('scene-tag').textContent=cut?'A1 / TIẾP CẬN DƯỚI LÒNG ĐẤT':'PHỐI CẢNH TRẬN ĐỊA';const svg=$('scene');if(!svg.querySelector('#world'))svg.innerHTML=definitions+'<g id="world" class="world"></g><g id="detail"></g>';
const world=svg.querySelector('#world'),cam=camera();world.innerHTML=terrain()+scenicEffects()+sites.map(s=>landmark(s)).join('');world.style.transform=`translate(480px, 340px) scale(${cam.z}) translate(${-cam.x}px, ${-cam.y}px)`;world.style.visibility=cut?'hidden':'visible';svg.querySelector('#detail').innerHTML=cut?a1Cutaway():'';
if((ci===1&&bi===1)||(ci===2&&bi<2))world.insertAdjacentHTML('beforeend','<rect class="night" x="-200" y="-200" width="1400" height="1100" opacity=".12"/>');
}
function mapDrawing(){let out=`<defs><marker id="dbp-map-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#285d45"/></marker></defs><path d="M176 0Q114 181 179 354T235 760H130V0ZM692 0Q767 196 704 359T689 760H775V0Z" fill="#b4c6a3"/><path d="M286 65Q390 44 460 110L652 143L675 225L365 275L235 264Z" fill="${ci>=3?'#dce4c6':'#e9ddba'}"/><path d="M352 281Q446 232 607 293L627 463L501 515L371 486Z" fill="#e7dfad"/><path d="M378 580L495 579L513 675L383 685Z" fill="#e8e0bc"/><path d="${river}" fill="none" stroke="#6faab3" stroke-width="4"/><path d="M376 25L396 206L348 284L385 422L403 510L414 703" fill="none" stroke="#8d7c67" stroke-width="2"/><path d="M371 278L384 274L411 393L398 397Z" fill="#fffbed" stroke="#aaa38c"/><text x="215" y="90" fill="#7f8267" font-size="11">PHÂN KHU BẮC</text><text x="214" y="402" fill="#7f8267" font-size="11">MƯỜNG THANH</text><text x="216" y="611" fill="#7f8267" font-size="11">PHÂN KHU NAM</text><text x="476" y="557" font-size="11" fill="#638d92" transform="rotate(77 476 557)">Nậm Rốm</text>`;
if(ci>=4){const d=ci===5&&bi===2?'M358 337Q477 271 595 335L590 462L449 501L357 437Z':'M331 289Q505 220 648 290L644 482L471 536L318 432Z';out+=`<path d="${d}" fill="none" stroke="#8d7452" stroke-width="2" stroke-dasharray="5 4"/>`;}
if(ci>0){const ts=activeSites(),xs=ts.map(t=>t.x),ys=ts.map(t=>t.y),x=Math.min(...xs)-39,y=Math.min(...ys)-34,w=Math.max(...xs)-x+39,h=Math.max(...ys)-y+34;out+=`<rect class="map-focus" x="${x}" y="${y}" width="${w}" height="${h}" rx="11"/>`;}
if(bi===1&&[1,2,4,7].includes(ci)){const targets=ci===4?activeSites().slice(0,3):activeSites();for(const t of targets){out+=`<path class="route" pathLength="1" d="M${t.x+100} ${t.y-50}Q${t.x+67} ${t.y-37} ${t.x+18} ${t.y-5}" marker-end="url(#dbp-map-arrow)"/>`;}const t=targets[0];out+=`<text x="${t.x+26}" y="${t.y-59}" font-size="11" fill="#285d45">Tiến công</text>`;}
out+=sites.map(s=>landmark(s,true)).join('');out+=`<g transform="translate(699 651)" fill="#4b6b4c"><path d="M0 20V-18L-5 -4L0 -8L5 -4L0 -18M-14 3H14" fill="none" stroke="#4b6b4c"/><text x="0" y="-27" text-anchor="middle" font-size="11">B</text><text x="0" y="34" text-anchor="middle" font-size="10">N</text><text x="-24" y="7" font-size="10">T</text><text x="18" y="7" font-size="10">Đ</text></g><text x="451" y="715" text-anchor="middle" font-size="11" fill="#7b816b">Lược đồ tương đối</text>`;return out;}
function draw(){const c=chapter(),b=c.beats[bi];drawScene();$('map').innerHTML=mapDrawing();$('scene-date').textContent=c.date+' · 1954';$('scene-clock').textContent=b.time;$('phase').textContent=c.phase;$('title').textContent=c.title;$('description').textContent=b.text;$('result').textContent=c.result;$('action-kind').textContent=`${bi+1}/3 · ${b.label}`;$('action-text').textContent=b.action;
$('chapters').innerHTML=chapters.map((c,i)=>`<button class="chapter ${i===ci?'active':i<ci?'done':''}" data-c="${i}" aria-current="${i===ci?'step':'false'}"><small>${c.date}</small><strong>${c.name}</strong></button>`).join('');
$('beats').innerHTML='<span>TRONG CẢNH NÀY</span>'+c.beats.map((b,i)=>`<button class="beat ${i===bi?'active':''}" data-b="${i}" aria-pressed="${i===bi}"><b>0${i+1}</b>${b.label}</button>`).join('');
document.querySelectorAll('[data-c]').forEach(el=>el.onclick=()=>select(+el.dataset.c,0));document.querySelectorAll('[data-b]').forEach(el=>el.onclick=()=>select(ci,+el.dataset.b));document.querySelectorAll('[data-site]').forEach(el=>{el.onclick=()=>select(+el.dataset.chapter,0);el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(+el.dataset.chapter,0)}}});
$('prev').disabled=ci===0;$('next').disabled=ci===chapters.length-1;$('position').textContent=`Cảnh ${ci+1}/${chapters.length} · Bước ${bi+1}/3 · Địa hình và hướng hoạt động được khái quát.`;sync();progress();}
function sync(){$('play').textContent=running?'Ⅱ Tạm dừng':'▶ Trình chiếu';$('play').setAttribute('aria-pressed',String(running));$('theater').classList.toggle('paused',!running&&elapsed>0);$('theater').classList.toggle('reduced',reduced());}
function progress(){$('progress').style.width=(elapsed / +$('speed').value *100)+'%';}
function pause(){running=false;cancelAnimationFrame(raf);raf=0;last=0;sync();}
function select(c,b){pause();ci=Math.max(0,Math.min(chapters.length-1,c));bi=b;elapsed=0;chapterOnly=false;draw();}
function tick(now){if(!running)return;if(last)elapsed+=now-last;last=now;const duration=+$('speed').value;if(elapsed>=duration){elapsed=0;if(bi<2)bi++;else if(ci===chapters.length-1||chapterOnly){elapsed=duration;pause();progress();return;}else{ci++;bi=0;}draw();}progress();raf=requestAnimationFrame(tick);}
function start(replay=false){if(replay){bi=0;elapsed=0;chapterOnly=true;draw();}else{chapterOnly=false;if(ci===chapters.length-1&&bi===2&&elapsed>=+$('speed').value){ci=0;bi=0;elapsed=0;draw();}}running=true;last=0;sync();cancelAnimationFrame(raf);raf=requestAnimationFrame(tick);}
$('play').onclick=()=>running?pause():start();$('replay').onclick=()=>{pause();start(true);};$('prev').onclick=()=>select(ci-1,0);$('next').onclick=()=>select(ci+1,0);$('speed').onchange=()=>{elapsed=0;last=0;progress();};$('motion').checked=matchMedia('(prefers-reduced-motion: reduce)').matches;$('motion').onchange=sync;
document.addEventListener('visibilitychange',()=>{if(document.hidden&&running)pause();});document.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA','BUTTON'].includes(e.target.tagName)||e.target.isContentEditable)return;if(e.key==='ArrowRight'){e.preventDefault();select(ci+1,0);}if(e.key==='ArrowLeft'){e.preventDefault();select(ci-1,0);}});
draw();
})();
